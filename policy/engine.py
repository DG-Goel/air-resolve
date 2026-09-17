"""
Deterministic Policy Engine for AirResolve.

This engine is the SOLE AUTHORITY for policy decisions.
The LLM is NOT involved in decision-making - only in NLU and response generation.

ARCHITECTURE:
    Customer → LLM/NLU → StructuredRequest → [POLICY ENGINE] → PolicyVerdict
    → LLM Response Generation → Customer

The policy engine:
1. Loads customer and booking data
2. Evaluates Assignment 3 Data Pack policy rules
3. Returns deterministic PolicyVerdict
4. Never guesses or invents missing information
5. Flags ambiguities as POLICY_UNSPECIFIED
"""

import json
from pathlib import Path
from typing import List, Optional, Tuple

from policy.models import (
    BookingData,
    CustomerData,
    StructuredRequest,
    PolicyVerdict,
    RuleEvaluation,
    DecisionTrace
)
from policy.rules import (
    evaluate_cancellation_entitlement,
    evaluate_delay_compensation,
    evaluate_refund_authorization,
    evaluate_rebooking_authorization,
    evaluate_fare_difference_waiver,
    evaluate_loyalty_benefits,
    evaluate_escalation_triggers,
    check_requested_action_in_policy
)


class PolicyEngine:
    """
    Deterministic policy engine for AirResolve.
    
    The engine evaluates customer requests against Assignment 3 Data Pack
    policies and returns machine-readable policy verdicts.
    
    Properties:
    - Deterministic: Same inputs always produce same outputs
    - Traceable: Every decision references source policy rules
    - Conservative: Flags ambiguities rather than inventing policy
    - Error-safe: Returns structured errors for invalid inputs
    """
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize policy engine with data directory.
        
        Args:
            data_dir: Path to directory containing customers.json, bookings.json
        """
        self.data_dir = Path(data_dir)
        self.customers: List[CustomerData] = []
        self.bookings: List[BookingData] = []
        self._load_data()
    
    def _load_data(self):
        """Load customer and booking data from JSON files."""
        # Load customers
        customers_file = self.data_dir / "customers.json"
        if customers_file.exists():
            with open(customers_file, 'r', encoding='utf-8') as f:
                customers_data = json.load(f)
                self.customers = [CustomerData(**c) for c in customers_data]
        
        # Load bookings
        bookings_file = self.data_dir / "bookings.json"
        if bookings_file.exists():
            with open(bookings_file, 'r', encoding='utf-8') as f:
                bookings_data = json.load(f)
                self.bookings = [BookingData(**b) for b in bookings_data]
    
    def get_customer(self, booking_reference: str) -> Optional[CustomerData]:
        """Get customer by booking reference."""
        for customer in self.customers:
            if customer.booking_reference == booking_reference:
                return customer
        return None
    
    def get_booking(self, booking_reference: str) -> Optional[BookingData]:
        """Get booking by reference. Returns first matching booking."""
        for booking in self.bookings:
            if booking.booking_reference == booking_reference:
                return booking
        return None
    
    def get_all_bookings(self, booking_reference: str) -> List[BookingData]:
        """Get all bookings for a booking reference (may include return flights)."""
        return [b for b in self.bookings if b.booking_reference == booking_reference]
    
    def evaluate(self, request: StructuredRequest) -> PolicyVerdict:
        """
        Evaluate customer request against Assignment 3 Data Pack policies.
        
        This is the main entry point for policy evaluation.
        
        Args:
            request: Structured customer request from NLU module
            
        Returns:
            PolicyVerdict with deterministic policy decision
            
        Properties:
        - Deterministic: evaluate(r) == evaluate(r) for all r
        - Traceable: verdict.applicable_policy_rules references source rules
        - Complete: verdict contains all information needed for action/escalation
        """
        # Validate required fields
        if not request.booking_reference:
            return self._error_verdict(
                error_type="missing_booking_reference",
                error_message="Booking reference is required",
                required_field="booking_reference"
            )
        
        # Get customer and booking data
        customer = self.get_customer(request.booking_reference)
        if not customer:
            return self._error_verdict(
                error_type="customer_not_found",
                error_message=f"Customer not found for booking reference: {request.booking_reference}",
                required_field="booking_reference"
            )
        
        bookings = self.get_all_bookings(request.booking_reference)
        if not bookings:
            return self._error_verdict(
                error_type="booking_not_found",
                error_message=f"Booking not found: {request.booking_reference}",
                required_field="booking_reference"
            )
        
        # Use first booking with disruption (cancelled or delayed)
        booking = None
        for b in bookings:
            if b.status in ["cancelled", "delayed"]:
                booking = b
                break
        
        if not booking:
            # No disrupted booking found
            booking = bookings[0]
        
        # Validate booking data
        if booking.status == "delayed" and booking.delay_hours is None:
            return self._error_verdict(
                error_type="missing_delay_hours",
                error_message=f"Booking status is 'delayed' but delay_hours is missing",
                required_field="delay_hours"
            )
        
        if booking.status == "delayed" and booking.delay_hours is not None and booking.delay_hours < 0:
            return self._error_verdict(
                error_type="invalid_delay_hours",
                error_message=f"delay_hours cannot be negative: {booking.delay_hours}",
                required_field="delay_hours"
            )
        
        if request.fare_difference is not None and request.fare_difference < 0:
            return self._error_verdict(
                error_type="invalid_fare_difference",
                error_message=f"fare_difference cannot be negative: {request.fare_difference}",
                required_field="fare_difference"
            )
        
        # Evaluate policy rules
        return self._evaluate_policy(request, booking, customer)
    
    def _evaluate_policy(
        self,
        request: StructuredRequest,
        booking: BookingData,
        customer: CustomerData
    ) -> PolicyVerdict:
        """
        Evaluate all applicable policy rules and construct verdict.
        
        This is the core policy evaluation logic.
        """
        # Initialize verdict components
        eligible_compensations = []
        authorized_actions = []
        denied_actions = []
        denial_reasons = {}
        escalation_reasons = []
        applicable_rules = []
        ambiguities_flagged = []
        rule_evaluations = []
        
        # Track intermediate calculations for decision trace
        cause = booking.cause or request.disruption_cause
        intermediate = {
            "booking_status": booking.status,
            "booking_cause": booking.cause,
            "request_disruption_cause": request.disruption_cause,
            "resolved_cause": cause,
            "delay_hours": booking.delay_hours,
            "loyalty_tier": customer.loyalty_tier,
            "fare_difference": request.fare_difference
        }
        
        # Evaluate escalation triggers first (highest priority)
        escalation_trigger_reasons, escalation_evals = evaluate_escalation_triggers(request, booking)
        escalation_reasons.extend(escalation_trigger_reasons)
        rule_evaluations.extend(escalation_evals)
        applicable_rules.extend([e.rule_id for e in escalation_evals if e.triggered])
        
        # Evaluate cancellation entitlement
        cancellation_triggered, cancel_eval = evaluate_cancellation_entitlement(booking, request)
        rule_evaluations.append(cancel_eval)
        if cancellation_triggered:
            applicable_rules.append(cancel_eval.rule_id)
            eligible_compensations.extend([
                "free_rebooking_next_available_within_24h",
                "full_refund_to_original_payment_method"
            ])
            
            # Check which option customer chose
            refund_requested = any(
                action in ["refund", "full_refund", "cash_refund"]
                for action in request.requested_actions
            )
            rebooking_requested = any(
                action in ["rebooking", "rebook", "free_rebooking"]
                for action in request.requested_actions
            )
            
            # Evaluate refund authorization if requested
            if refund_requested:
                refund_auth, refund_esc, refund_eval = evaluate_refund_authorization(
                    booking, customer, request
                )
                rule_evaluations.append(refund_eval)
                if refund_auth:
                    applicable_rules.append(refund_eval.rule_id)
                    authorized_actions.append("initiate_refund_to_original_payment_method")
                elif refund_esc:
                    escalation_reasons.extend(refund_esc)
                    applicable_rules.append(refund_eval.rule_id)
            
            # Evaluate rebooking authorization if requested
            if rebooking_requested:
                rebook_auth, rebook_esc, rebook_eval = evaluate_rebooking_authorization(
                    booking, customer, request
                )
                rule_evaluations.append(rebook_eval)
                if rebook_auth:
                    applicable_rules.append(rebook_eval.rule_id)
                    authorized_actions.append("rebook_next_available_within_24h")
                elif rebook_esc:
                    escalation_reasons.extend(rebook_esc)
                    applicable_rules.append(rebook_eval.rule_id)
        
        # Check rebooking for delayed flights (even if not cancelled)
        rebooking_requested = any(
            action in ["rebooking", "rebook", "free_rebooking"]
            for action in request.requested_actions
        )
        if rebooking_requested and booking.status == "delayed":
            rebook_auth, rebook_esc, rebook_eval = evaluate_rebooking_authorization(
                booking, customer, request
            )
            rule_evaluations.append(rebook_eval)
            if rebook_auth:
                applicable_rules.append(rebook_eval.rule_id)
                authorized_actions.append("rebook_next_available_within_24h")
            elif rebook_esc:
                escalation_reasons.extend(rebook_esc)
                applicable_rules.append(rebook_eval.rule_id)
        
        # Evaluate delay compensation
        delay_actions, delay_ambiguities, delay_evals = evaluate_delay_compensation(booking, request)
        rule_evaluations.extend(delay_evals)
        authorized_actions.extend(delay_actions)
        ambiguities_flagged.extend(delay_ambiguities)
        applicable_rules.extend([e.rule_id for e in delay_evals if e.triggered])
        
        # Evaluate fare difference waiver if requested
        if request.fare_difference is not None:
            fare_esc, fare_esc_reasons, fare_eval = evaluate_fare_difference_waiver(request)
            rule_evaluations.append(fare_eval)
            if fare_esc:
                escalation_reasons.extend(fare_esc_reasons)
                applicable_rules.append(fare_eval.rule_id)
            elif fare_eval.result == "authorized":
                applicable_rules.append(fare_eval.rule_id)
                # Note: Fare waiver is authorized but not added to actions
                # because it's a constraint on alternate flight rebooking
        
        # Evaluate loyalty benefits
        priority_rebooking, loyalty_eval = evaluate_loyalty_benefits(customer, booking)
        rule_evaluations.append(loyalty_eval)
        if loyalty_eval.triggered:
            applicable_rules.append(loyalty_eval.rule_id)
        
        # Check for requested actions not in policy
        for action in request.requested_actions:
            if not check_requested_action_in_policy(action):
                denied_actions.append(action)
                denial_reasons[action] = (
                    f"'{action}' is not covered by Assignment 3 Data Pack policies. "
                    "Requires escalation for policy exception (RULE-ESCALATE-POLICY-EXCEPTION)."
                )
                escalation_reasons.append(
                    f"Requested action '{action}' is compensation beyond stated policy (RULE-ESCALATE-POLICY-EXCEPTION)"
                )
                applicable_rules.append("RULE-ESCALATE-POLICY-EXCEPTION")
                rule_evaluations.append(RuleEvaluation(
                    rule_id="RULE-ESCALATE-POLICY-EXCEPTION",
                    rule_description="Compensation beyond policy escalation",
                    triggered=True,
                    result="escalated",
                    reason=f"Requested action '{action}' not in Assignment 3 Data Pack."
                ))
        
        # Check for denied actions that ARE in policy but not applicable
        for action in request.requested_actions:
            if check_requested_action_in_policy(action):
                action_authorized = any(
                    action.lower().replace("_", "").replace(" ", "") in auth.lower().replace("_", "").replace(" ", "")
                    or auth.lower().replace("_", "").replace(" ", "") in action.lower().replace("_", "").replace(" ", "")
                    for auth in authorized_actions
                )
                if not action_authorized and action not in denied_actions:
                    # Action is in policy but not authorized for this case
                    denied_actions.append(action)
                    
                    # Determine denial reason based on context
                    if "hotel" in action.lower() and booking.status == "delayed":
                        if booking.delay_hours and booking.delay_hours <= 5.0:
                            denial_reasons[action] = (
                                f"Hotel accommodation requires delay more than 5 hours per Assignment 3 Data Pack policy. "
                                f"Current delay is {booking.delay_hours} hours, qualifying for meal voucher and lounge access only."
                            )
                        elif "full" in action.lower() or "night" in action.lower():
                            denial_reasons[action] = (
                                "Assignment 3 Data Pack policy covers hotel for delayed hours only, not full night stay."
                            )
                        else:
                            denial_reasons[action] = (
                                f"Hotel accommodation not authorized for current disruption circumstances."
                            )
                    elif ("rebooking" in action.lower() or "rebook" in action.lower()) and booking.status == "delayed":
                        # This should have been caught by rebooking evaluation
                        # But if it wasn't, provide a meaningful reason
                        if request.alternate_flight:
                            denial_reasons[action] = (
                                "Alternate rebooking for a delayed flight is not explicitly authorized by the supplied agent authority. "
                                "Source limits rebooking authority to airline-caused cancelled flights. Requires human review."
                            )
                        else:
                            denial_reasons[action] = (
                                "Rebooking request for delayed flight not explicitly authorized by Assignment 3 Data Pack. "
                                "Agent authority limited to cancelled flights."
                            )
                    else:
                        denial_reasons[action] = (
                            f"'{action}' not authorized under current circumstances based on Assignment 3 Data Pack policies."
                        )
        
        # Build decision trace
        decision_trace = DecisionTrace(
            booking_reference=request.booking_reference,
            input_values={
                "booking_reference": request.booking_reference,
                "requested_actions": request.requested_actions,
                "customer_emotion": request.customer_emotion,
                "escalation_intents": request.escalation_intents,
                "fare_difference": request.fare_difference,
                "alternate_flight": request.alternate_flight,
                "refund_to_different_payment_method": request.refund_to_different_payment_method,
                "disruption_cause": request.disruption_cause
            },
            rules_evaluated=rule_evaluations,
            intermediate_calculations=intermediate
        )
        
        # Determine overall status
        # Priority: ESCALATION > UNSPECIFIED > AUTHORIZED/DENIED
        if escalation_reasons:
            status = "ESCALATION_REQUIRED"
        elif ambiguities_flagged:
            status = "POLICY_UNSPECIFIED"
        elif denied_actions and not authorized_actions:
            status = "DENIED"
        elif authorized_actions:
            status = "AUTHORIZED"
        else:
            status = "DENIED"
        
        # Build compensation details
        meal_voucher = 500 if "issue_meal_voucher_500" in authorized_actions else None
        hotel_hours = booking.delay_hours if "arrange_hotel_accommodation_delayed_hours" in authorized_actions else None
        refund_days = 7 if "initiate_refund_to_original_payment_method" in authorized_actions else None
        refund_dest = "original_payment_method" if refund_days else None
        
        # Construct final verdict
        return PolicyVerdict(
            status=status,
            eligible_compensations=eligible_compensations,
            authorized_actions=authorized_actions,
            denied_actions=denied_actions,
            denial_reasons=denial_reasons,
            escalation_required=bool(escalation_reasons),
            escalation_reasons=escalation_reasons,
            authority_limit_exceeded=any("authority limit" in r.lower() for r in escalation_reasons),
            applicable_policy_rules=list(set(applicable_rules)),  # Remove duplicates
            ambiguities_flagged=list(set(ambiguities_flagged)),
            decision_trace=decision_trace,
            loyalty_tier=customer.loyalty_tier,
            priority_rebooking=priority_rebooking,
            meal_voucher_amount=meal_voucher,
            hotel_accommodation_hours=hotel_hours,
            refund_processing_days=refund_days,
            refund_destination=refund_dest
        )
    
    def _error_verdict(
        self,
        error_type: str,
        error_message: str,
        required_field: Optional[str] = None
    ) -> PolicyVerdict:
        """Create error verdict for invalid inputs."""
        return PolicyVerdict(
            status="ERROR",
            error_type=error_type,
            error_message=error_message,
            required_field=required_field
        )
