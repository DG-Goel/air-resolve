"""
Deterministic policy rule evaluation functions.

Each function evaluates a specific Assignment 3 Data Pack policy rule.
Rules are pure functions: same inputs → same outputs (determinism).

CRITICAL: Do NOT invent policy. Implement ONLY what Assignment 3 Data Pack
explicitly states. Flag ambiguities as POLICY_UNSPECIFIED.
"""

from typing import List, Tuple, Optional
from policy.models import (
    BookingData,
    CustomerData,
    StructuredRequest,
    RuleEvaluation
)


def evaluate_cancellation_entitlement(
    booking: BookingData,
    request: StructuredRequest
) -> Tuple[bool, RuleEvaluation]:
    """
    RULE-CANCEL-AIRLINE-01: Airline-Caused Cancellation Entitlement.
    
    Source: "If a flight is cancelled by the airline: Customer may choose free
    rebooking on the next available flight within 24 hours OR customer may choose
    a full refund. This is the customer's choice."
    
    Returns:
        (triggered, RuleEvaluation)
    """
    rule_id = "RULE-CANCEL-AIRLINE-01"
    
    # Determine cause: booking.cause takes precedence, then request.disruption_cause
    cause = booking.cause or request.disruption_cause
    
    if booking.status == "cancelled" and cause == "airline_operational":
        return (True, RuleEvaluation(
            rule_id=rule_id,
            rule_description="Airline-caused cancellation entitlement",
            triggered=True,
            result="authorized",
            reason="Flight cancelled by airline. Customer eligible for free rebooking OR full refund (customer choice)."
        ))
    
    return (False, RuleEvaluation(
        rule_id=rule_id,
        rule_description="Airline-caused cancellation entitlement",
        triggered=False,
        result="not_applicable",
        reason=f"Booking status: {booking.status}, cause: {cause or 'unknown'}"
    ))


def evaluate_delay_compensation(
    booking: BookingData,
    request: StructuredRequest
) -> Tuple[List[str], List[str], List[RuleEvaluation]]:
    """
    Evaluate delay compensation tiers.
    
    Source tiers:
    - Tier 1: "Delay under 3 hours → ₹500 meal voucher"
    - Tier 2: "Delay more than 3 hours → meal voucher + lounge access"
    - Tier 3: "Delay more than 5 hours → meal voucher + hotel accommodation
               covering only the delayed hours, not a full night's stay"
    
    CRITICAL AMBIGUITIES:
    - Exactly 3.0 hours: source does not specify (AMBIGUITY-01)
    - Exactly 5.0 hours: source does not specify (AMBIGUITY-01)
    - Tier 3 lounge access: source does not mention (AMBIGUITY-02)
    
    IMPORTANT: Delay compensation applies to airline-caused delays.
    Without known cause, compensation cannot be authorized.
    
    Returns:
        (authorized_actions, ambiguities_flagged, rule_evaluations)
    """
    if booking.status != "delayed" or booking.delay_hours is None:
        return ([], [], [])
    
    # Determine cause: booking.cause takes precedence, then request.disruption_cause
    cause = booking.cause or request.disruption_cause
    
    # Without a known airline-operational cause, we cannot authorize compensation
    # This is NOT evaluated here - escalation triggers handle unknown/non-airline causes
    # We only evaluate delay tiers IF the cause is airline-operational
    if cause != "airline_operational":
        return ([], [], [])
    
    delay_hours = booking.delay_hours
    authorized_actions = []
    ambiguities = []
    evaluations = []
    
    # Check for exact boundary ambiguities first
    if delay_hours == 3.0:
        ambiguities.append("AMBIGUITY-01")
        evaluations.append(RuleEvaluation(
            rule_id="AMBIGUITY-01",
            rule_description="Delay threshold boundary at exactly 3.0 hours",
            triggered=True,
            result="unspecified",
            reason="Source uses 'under 3 hours' and 'more than 3 hours'. Behavior at exactly 3.0 hours is POLICY_UNSPECIFIED."
        ))
        return ([], ambiguities, evaluations)
    
    if delay_hours == 5.0:
        # At exactly 5.0, we know it qualifies for Tier 2, but Tier 3 is ambiguous
        ambiguities.append("AMBIGUITY-01")
        # Authorize Tier 2 benefits (delay > 3.0 is satisfied)
        authorized_actions = ["issue_meal_voucher_500", "provide_lounge_access"]
        evaluations.append(RuleEvaluation(
            rule_id="RULE-DELAY-COMP-TIER2",
            rule_description="Delay more than 3 hours compensation",
            triggered=True,
            result="authorized",
            reason=f"Delay {delay_hours}h > 3.0h. Tier 2: meal voucher ₹500 + lounge access."
        ))
        evaluations.append(RuleEvaluation(
            rule_id="AMBIGUITY-01",
            rule_description="Delay threshold boundary at exactly 5.0 hours",
            triggered=True,
            result="unspecified",
            reason="Source uses 'more than 5 hours' for hotel. Behavior at exactly 5.0 hours is POLICY_UNSPECIFIED for Tier 3."
        ))
        return (authorized_actions, ambiguities, evaluations)
    
    # Tier 1: delay < 3.0 hours
    if delay_hours < 3.0:
        authorized_actions.append("issue_meal_voucher_500")
        evaluations.append(RuleEvaluation(
            rule_id="RULE-DELAY-COMP-TIER1",
            rule_description="Delay under 3 hours compensation",
            triggered=True,
            result="authorized",
            reason=f"Delay {delay_hours}h < 3.0h. Tier 1: meal voucher ₹500."
        ))
        return (authorized_actions, ambiguities, evaluations)
    
    # Tier 2: 3.0 < delay <= 5.0 (we've already handled exactly 5.0 above)
    if 3.0 < delay_hours < 5.0:
        authorized_actions.extend(["issue_meal_voucher_500", "provide_lounge_access"])
        evaluations.append(RuleEvaluation(
            rule_id="RULE-DELAY-COMP-TIER2",
            rule_description="Delay more than 3 hours compensation",
            triggered=True,
            result="authorized",
            reason=f"Delay {delay_hours}h > 3.0h. Tier 2: meal voucher ₹500 + lounge access."
        ))
        return (authorized_actions, ambiguities, evaluations)
    
    # Tier 3: delay > 5.0 hours
    if delay_hours > 5.0:
        # Explicitly stated in Tier 3: meal voucher + hotel
        authorized_actions.extend([
            "issue_meal_voucher_500",
            "arrange_hotel_accommodation_delayed_hours"
        ])
        evaluations.append(RuleEvaluation(
            rule_id="RULE-DELAY-COMP-TIER3",
            rule_description="Delay more than 5 hours compensation",
            triggered=True,
            result="authorized",
            reason=f"Delay {delay_hours}h > 5.0h. Tier 3: meal voucher ₹500 + hotel for delayed hours ({delay_hours}h)."
        ))
        
        # AMBIGUITY-02: Lounge access not mentioned in Tier 3 source text
        ambiguities.append("AMBIGUITY-02")
        evaluations.append(RuleEvaluation(
            rule_id="AMBIGUITY-02",
            rule_description="Tier 3 lounge access unspecified",
            triggered=True,
            result="unspecified",
            reason="Source Tier 3 states 'meal voucher + hotel' but does NOT mention lounge access. Whether Tier 3 includes lounge access is POLICY_UNSPECIFIED."
        ))
        
        return (authorized_actions, ambiguities, evaluations)
    
    # Should not reach here given conditions above
    return ([], ambiguities, evaluations)


def evaluate_refund_authorization(
    booking: BookingData,
    customer: CustomerData,
    request: StructuredRequest
) -> Tuple[bool, List[str], RuleEvaluation]:
    """
    RULE-AGENT-AUTHORITY-REFUND: Agent Refund Initiation Authority.
    
    Source: "Initiate a refund for an airline-caused cancellation."
    Constraint (RULE-REFUND-PROCESS-01): "Refund must be issued to the original
    payment method."
    
    Returns:
        (authorized, escalation_reasons, RuleEvaluation)
    """
    rule_id = "RULE-AGENT-AUTHORITY-REFUND"
    escalation_reasons = []
    
    # Check if refund to different payment method requested
    if request.refund_to_different_payment_method:
        escalation_reasons.append(
            "Refund to different payment method requires supervisor approval (RULE-ESCALATE-PAYMENT-METHOD)"
        )
        return (False, escalation_reasons, RuleEvaluation(
            rule_id="RULE-ESCALATE-PAYMENT-METHOD",
            rule_description="Refund to different payment method escalation",
            triggered=True,
            result="escalated",
            reason="Customer requested refund to different payment method. Source explicitly prohibits this without supervisor approval."
        ))
    
    # Determine cause: booking.cause takes precedence, then request.disruption_cause
    cause = booking.cause or request.disruption_cause
    
    # Check airline-caused cancellation
    if booking.status == "cancelled" and cause == "airline_operational":
        return (True, [], RuleEvaluation(
            rule_id=rule_id,
            rule_description="Agent refund initiation authority",
            triggered=True,
            result="authorized",
            reason="Airline-caused cancellation. Agent authorized to initiate refund to original payment method within 7 business days."
        ))
    
    return (False, [], RuleEvaluation(
        rule_id=rule_id,
        rule_description="Agent refund initiation authority",
        triggered=False,
        result="not_applicable",
        reason=f"Booking status: {booking.status}, cause: {cause or 'unknown'}"
    ))


def evaluate_rebooking_authorization(
    booking: BookingData,
    customer: CustomerData,
    request: StructuredRequest
) -> Tuple[bool, List[str], RuleEvaluation]:
    """
    RULE-AGENT-AUTHORITY-REBOOK: Agent Rebooking Authority.
    
    Source: "Rebook an airline-caused cancelled flight on the next available
    flight within 24 hours at no charge."
    
    CRITICAL: Source explicitly limits this to CANCELLED flights.
    Delayed flight rebooking is NOT explicitly authorized (AMBIGUITY-03).
    
    Returns:
        (authorized, escalation_reasons, RuleEvaluation)
    """
    rule_id = "RULE-AGENT-AUTHORITY-REBOOK"
    
    # If delayed flight and customer requests alternate flight
    if booking.status == "delayed" and request.alternate_flight:
        return (False, [
            "Delayed flight alternate rebooking not explicitly authorized by Assignment 3 Data Pack. Agent authority limited to cancelled flights (AMBIGUITY-03)."
        ], RuleEvaluation(
            rule_id="AMBIGUITY-03",
            rule_description="Delayed flight rebooking authority unspecified",
            triggered=True,
            result="escalated",
            reason="Source explicitly authorizes rebooking for cancelled flights only. Delayed flight alternate rebooking requires human review."
        ))
    
    # Determine cause: booking.cause takes precedence, then request.disruption_cause
    cause = booking.cause or request.disruption_cause
    
    # Cancelled flight rebooking
    if booking.status == "cancelled" and cause == "airline_operational":
        return (True, [], RuleEvaluation(
            rule_id=rule_id,
            rule_description="Agent rebooking authority for cancelled flights",
            triggered=True,
            result="authorized",
            reason="Airline-caused cancellation. Agent authorized to rebook on next available flight within 24 hours at no charge."
        ))
    
    return (False, [], RuleEvaluation(
        rule_id=rule_id,
        rule_description="Agent rebooking authority",
        triggered=False,
        result="not_applicable",
        reason=f"Booking status: {booking.status}, cause: {cause or 'unknown'}"
    ))


def evaluate_fare_difference_waiver(
    request: StructuredRequest
) -> Tuple[bool, List[str], RuleEvaluation]:
    """
    RULE-FARE-DIFF-AUTHORITY: Fare Difference Waiver Authority Limit.
    
    Source: "Agent cannot waive a fare difference above ₹1,500 without
    supervisor approval."
    
    CRITICAL: Source states what agent CANNOT do (waive > ₹1,500).
    It does NOT explicitly state agent CAN or MUST waive ≤₹1,500.
    Amounts ≤₹1,500 are inferred to be within authority based on the boundary,
    but this is NOT an explicit source authorization.
    
    Returns:
        (requires_escalation, escalation_reasons, RuleEvaluation)
    """
    rule_id = "RULE-FARE-DIFF-AUTHORITY"
    
    if request.fare_difference is None:
        return (False, [], RuleEvaluation(
            rule_id=rule_id,
            rule_description="Fare difference waiver authority",
            triggered=False,
            result="not_applicable",
            reason="No fare difference waiver requested"
        ))
    
    if request.fare_difference > 1500:
        return (True, [
            f"Fare difference waiver of ₹{request.fare_difference} exceeds ₹1,500 agent authority limit (RULE-ESCALATE-FARE-WAIVER)"
        ], RuleEvaluation(
            rule_id="RULE-ESCALATE-FARE-WAIVER",
            rule_description="Fare difference waiver above ₹1,500 escalation",
            triggered=True,
            result="escalated",
            reason=f"Fare difference ₹{request.fare_difference} > ₹1,500. Source requires supervisor approval."
        ))
    
    # fare_difference <= 1500
    # Source does NOT explicitly authorize waiver, only prohibits > 1500
    # This is inferred from the boundary, not an explicit source statement
    return (False, [], RuleEvaluation(
        rule_id=rule_id,
        rule_description="Fare difference waiver authority",
        triggered=True,
        result="authorized",
        reason=f"Fare difference ₹{request.fare_difference} ≤ ₹1,500. Not above agent authority limit (inferred from source prohibition of amounts > ₹1,500; not explicit authorization)."
    ))


def evaluate_loyalty_benefits(
    customer: CustomerData,
    booking: BookingData
) -> Tuple[bool, RuleEvaluation]:
    """
    RULE-LOYALTY-PRIORITY: Loyalty Tier Priority Rebooking.
    
    Source: "Gold customers receive priority rebooking. Platinum customers
    receive priority rebooking. Gold and Platinum do not receive additional
    compensation beyond the standard policy."
    
    Returns:
        (priority_rebooking, RuleEvaluation)
    """
    rule_id = "RULE-LOYALTY-PRIORITY"
    
    if customer.loyalty_tier in ["Gold", "Platinum"]:
        return (True, RuleEvaluation(
            rule_id=rule_id,
            rule_description="Loyalty tier priority rebooking",
            triggered=True,
            result="authorized",
            reason=f"{customer.loyalty_tier} tier: priority rebooking flag set. NO additional compensation."
        ))
    
    return (False, RuleEvaluation(
        rule_id=rule_id,
        rule_description="Loyalty tier priority rebooking",
        triggered=False,
        result="not_applicable",
        reason=f"{customer.loyalty_tier} tier: no priority benefit explicitly stated in source."
    ))


def evaluate_escalation_triggers(
    request: StructuredRequest,
    booking: BookingData
) -> Tuple[List[str], List[RuleEvaluation]]:
    """
    Evaluate mandatory escalation triggers.
    
    Source escalation requirements:
    - Legal action threats (RULE-ESCALATE-LEGAL)
    - Formal complaints (RULE-ESCALATE-FORMAL-COMPLAINT)
    - Non-airline-caused disruptions (RULE-ESCALATE-NON-AIRLINE)
    - Compensation beyond stated policy (RULE-ESCALATE-POLICY-EXCEPTION)
    
    CRITICAL: Emotions like "furious" or "angry" are NOT escalation triggers.
    Only explicit legal threats or formal complaint requests trigger escalation.
    
    UNKNOWN CAUSE HANDLING:
    - If disruption exists (cancelled/delayed) but cause is unknown (None),
      escalate because we cannot authorize airline-caused compensation without
      knowing the cause.
    
    Returns:
        (escalation_reasons, rule_evaluations)
    """
    escalation_reasons = []
    evaluations = []
    
    # Legal threat
    if "legal_threat" in request.escalation_intents:
        escalation_reasons.append("Legal action threat requires immediate human supervisor (RULE-ESCALATE-LEGAL)")
        evaluations.append(RuleEvaluation(
            rule_id="RULE-ESCALATE-LEGAL",
            rule_description="Legal action threat escalation",
            triggered=True,
            result="escalated",
            reason="Customer threatened legal action. Source requires immediate escalation."
        ))
    
    # Formal complaint
    if "formal_complaint" in request.escalation_intents:
        escalation_reasons.append("Formal complaint requires human supervisor (RULE-ESCALATE-FORMAL-COMPLAINT)")
        evaluations.append(RuleEvaluation(
            rule_id="RULE-ESCALATE-FORMAL-COMPLAINT",
            rule_description="Formal complaint escalation",
            triggered=True,
            result="escalated",
            reason="Customer requested formal complaint filing. Source requires escalation."
        ))
    
    # Determine cause
    cause = booking.cause or request.disruption_cause
    
    # Unknown cause for disrupted flights
    if booking.status in ["cancelled", "delayed"] and cause is None:
        escalation_reasons.append(
            "Disruption cause unknown - cannot authorize airline-caused compensation without known cause (RULE-ESCALATE-UNKNOWN-CAUSE)"
        )
        evaluations.append(RuleEvaluation(
            rule_id="RULE-ESCALATE-UNKNOWN-CAUSE",
            rule_description="Unknown disruption cause escalation",
            triggered=True,
            result="escalated",
            reason="Disruption cause is unknown. Cannot authorize airline-caused compensation without knowing cause."
        ))
    
    # Non-airline-caused disruption (only if cause is KNOWN and NOT airline_operational)
    elif booking.status in ["cancelled", "delayed"] and cause is not None and cause != "airline_operational":
        escalation_reasons.append(
            f"Non-airline-caused disruption (cause: {cause}) requires supervisor approval for exceptions (RULE-ESCALATE-NON-AIRLINE)"
        )
        evaluations.append(RuleEvaluation(
            rule_id="RULE-ESCALATE-NON-AIRLINE",
            rule_description="Non-airline-caused disruption escalation",
            triggered=True,
            result="escalated",
            reason=f"Disruption cause '{cause}' is not airline operational. Source requires escalation for exceptions."
        ))
    
    return (escalation_reasons, evaluations)


def check_requested_action_in_policy(action: str) -> bool:
    """
    Check if requested action is explicitly in Assignment 3 Data Pack.
    
    Explicitly supported actions:
    - free_rebooking (for airline-caused cancellations)
    - full_refund (for airline-caused cancellations)
    - meal_voucher (for delays)
    - lounge_access (for delays > 3h)
    - hotel_accommodation (for delays > 5h, delayed hours only)
    - fare_waiver (with authority limits)
    
    NOT in policy:
    - business_class_upgrade
    - full_night_hotel
    - additional loyalty compensation
    - etc.
    """
    known_actions = {
        "free_rebooking",
        "free_rebooking_next_available_within_24h",
        "rebook",
        "rebooking",
        "full_refund",
        "refund",
        "meal_voucher",
        "issue_meal_voucher_500",
        "lounge_access",
        "provide_lounge_access",
        "hotel_accommodation",
        "hotel",
        "arrange_hotel_accommodation_delayed_hours",
        "fare_waiver",
        "waive_fare_difference"
    }
    
    # Normalize action for comparison
    action_normalized = action.lower().replace("_", "").replace(" ", "")
    
    for known in known_actions:
        known_normalized = known.lower().replace("_", "").replace(" ", "")
        if action_normalized in known_normalized or known_normalized in action_normalized:
            return True
    
    return False
