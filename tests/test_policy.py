"""
Comprehensive tests for AirResolve deterministic policy engine.

Tests verify:
1. Cancellation policy (airline-caused)
2. Delay compensation tiers
3. Authority boundaries
4. Loyalty benefits
5. Escalation triggers
6. Emotion vs escalation distinction
7. Input validation
8. Determinism property
9. Traceability
10. Three mandatory scenarios
"""

import pytest
from policy.engine import PolicyEngine
from policy.models import StructuredRequest


@pytest.fixture
def engine():
    """Create policy engine with test data."""
    return PolicyEngine(data_dir="data")


# ============================================================================
# CANCELLATION TESTS
# ============================================================================

def test_airline_caused_cancellation_refund_eligible(engine):
    """Airline-caused cancellation makes customer eligible for refund."""
    request = StructuredRequest(
        booking_reference="SK4821X",
        requested_actions=["refund"],
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    assert verdict.status in ["AUTHORIZED", "ESCALATION_REQUIRED"]
    assert "full_refund_to_original_payment_method" in verdict.eligible_compensations
    assert "RULE-CANCEL-AIRLINE-01" in verdict.applicable_policy_rules


def test_airline_caused_cancellation_rebooking_eligible(engine):
    """Airline-caused cancellation makes customer eligible for rebooking."""
    request = StructuredRequest(
        booking_reference="SK4821X",
        requested_actions=["rebooking"],
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    assert verdict.status in ["AUTHORIZED", "ESCALATION_REQUIRED"]
    assert "free_rebooking_next_available_within_24h" in verdict.eligible_compensations
    assert "RULE-CANCEL-AIRLINE-01" in verdict.applicable_policy_rules


def test_refund_must_be_original_payment_method(engine):
    """Refund must be to original payment method."""
    request = StructuredRequest(
        booking_reference="SK4821X",
        requested_actions=["refund"],
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    if "initiate_refund_to_original_payment_method" in verdict.authorized_actions:
        assert verdict.refund_destination == "original_payment_method"
        assert verdict.refund_processing_days == 7


def test_refund_different_payment_method_escalates(engine):
    """Refund to different payment method requires escalation."""
    request = StructuredRequest(
        booking_reference="SK4821X",
        requested_actions=["refund"],
        refund_to_different_payment_method=True,
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    assert verdict.status == "ESCALATION_REQUIRED"
    assert verdict.escalation_required is True
    assert any("different payment method" in reason.lower() for reason in verdict.escalation_reasons)
    assert "RULE-ESCALATE-PAYMENT-METHOD" in verdict.applicable_policy_rules


# ============================================================================
# DELAY COMPENSATION TESTS
# ============================================================================

def test_delay_under_3_hours_meal_voucher(engine):
    """Delay < 3 hours → ₹500 meal voucher."""
    request = StructuredRequest(
        booking_reference="TR1190B",  # 4h delay - will use modified data
        requested_actions=["meal_voucher"],
        disruption_cause="airline_operational"  # From scenario context
    )
    
    # Get booking and modify delay for test
    bookings = engine.get_all_bookings("TR1190B")
    booking = bookings[0]
    original_delay = booking.delay_hours
    booking.delay_hours = 2.5  # Under 3 hours
    
    verdict = engine.evaluate(request)
    
    # Restore original
    booking.delay_hours = original_delay
    
    assert "issue_meal_voucher_500" in verdict.authorized_actions
    assert verdict.meal_voucher_amount == 500
    assert "RULE-DELAY-COMP-TIER1" in verdict.applicable_policy_rules


def test_delay_more_than_3_hours_meal_and_lounge(engine):
    """Delay > 3 hours → meal voucher + lounge access."""
    request = StructuredRequest(
        booking_reference="TR1190B",  # 4h delay
        requested_actions=["meal_voucher", "lounge_access"],
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    assert verdict.status == "AUTHORIZED"
    assert "issue_meal_voucher_500" in verdict.authorized_actions
    assert "provide_lounge_access" in verdict.authorized_actions
    assert verdict.meal_voucher_amount == 500
    assert "RULE-DELAY-COMP-TIER2" in verdict.applicable_policy_rules


def test_delay_more_than_5_hours_meal_and_hotel(engine):
    """Delay > 5 hours → meal voucher + hotel (delayed hours)."""
    request = StructuredRequest(
        booking_reference="WL7742",  # 6h delay
        requested_actions=["meal_voucher", "hotel"],
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    assert verdict.status in ["AUTHORIZED", "POLICY_UNSPECIFIED"]
    assert "issue_meal_voucher_500" in verdict.authorized_actions
    assert "arrange_hotel_accommodation_delayed_hours" in verdict.authorized_actions
    assert verdict.meal_voucher_amount == 500
    assert verdict.hotel_accommodation_hours == 6.0
    assert "RULE-DELAY-COMP-TIER3" in verdict.applicable_policy_rules


def test_delay_exactly_3_hours_unspecified(engine):
    """Exactly 3.0 hours → POLICY_UNSPECIFIED (AMBIGUITY-01)."""
    request = StructuredRequest(
        booking_reference="TR1190B",
        requested_actions=["meal_voucher"],
        disruption_cause="airline_operational"  # From scenario context
    )
    
    # Modify delay to exactly 3.0
    bookings = engine.get_all_bookings("TR1190B")
    booking = bookings[0]
    original_delay = booking.delay_hours
    booking.delay_hours = 3.0
    
    verdict = engine.evaluate(request)
    
    # Restore
    booking.delay_hours = original_delay
    
    assert verdict.status == "POLICY_UNSPECIFIED"
    assert "AMBIGUITY-01" in verdict.ambiguities_flagged


def test_delay_exactly_5_hours_hotel_unspecified(engine):
    """Exactly 5.0 hours → hotel POLICY_UNSPECIFIED, but Tier 2 authorized."""
    request = StructuredRequest(
        booking_reference="WL7742",
        requested_actions=["meal_voucher", "lounge_access", "hotel"],
        disruption_cause="airline_operational"  # From scenario context
    )
    
    # Modify delay to exactly 5.0
    bookings = engine.get_all_bookings("WL7742")
    booking = bookings[0]
    original_delay = booking.delay_hours
    booking.delay_hours = 5.0
    
    verdict = engine.evaluate(request)
    
    # Restore
    booking.delay_hours = original_delay
    
    # At 5.0h, Tier 2 is authorized but Tier 3 (hotel) is ambiguous
    assert "issue_meal_voucher_500" in verdict.authorized_actions
    assert "provide_lounge_access" in verdict.authorized_actions
    assert "AMBIGUITY-01" in verdict.ambiguities_flagged


def test_delay_tier3_lounge_unspecified(engine):
    """Delay > 5h lounge access is POLICY_UNSPECIFIED (AMBIGUITY-02)."""
    request = StructuredRequest(
        booking_reference="WL7742",  # 6h delay
        requested_actions=["lounge_access"],
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    # Source Tier 3 doesn't mention lounge access
    assert "AMBIGUITY-02" in verdict.ambiguities_flagged


def test_hotel_requires_more_than_5_hours(engine):
    """Hotel requires delay > 5 hours. 4h delay should deny hotel."""
    request = StructuredRequest(
        booking_reference="TR1190B",  # 4h delay
        requested_actions=["hotel_accommodation"],
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    assert "hotel_accommodation" in verdict.denied_actions
    assert "hotel" in verdict.denial_reasons["hotel_accommodation"].lower()
    assert "5 hours" in verdict.denial_reasons["hotel_accommodation"]


# ============================================================================
# AUTHORITY BOUNDARY TESTS
# ============================================================================

def test_cancelled_flight_rebooking_authorized(engine):
    """Agent can rebook airline-caused cancelled flights."""
    request = StructuredRequest(
        booking_reference="SK4821X",  # Cancelled
        requested_actions=["rebooking"],
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    assert verdict.status in ["AUTHORIZED", "ESCALATION_REQUIRED"]
    if verdict.status == "AUTHORIZED":
        assert "rebook_next_available_within_24h" in verdict.authorized_actions
        assert "RULE-AGENT-AUTHORITY-REBOOK" in verdict.applicable_policy_rules


def test_delayed_flight_alternate_rebooking_escalates(engine):
    """Delayed flight alternate rebooking requires escalation (AMBIGUITY-03)."""
    request = StructuredRequest(
        booking_reference="WL7742",  # Delayed
        requested_actions=["rebooking"],
        alternate_flight="SK-999",
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    assert verdict.status == "ESCALATION_REQUIRED"
    assert verdict.escalation_required is True
    assert any("delayed flight" in reason.lower() for reason in verdict.escalation_reasons)
    assert "AMBIGUITY-03" in verdict.applicable_policy_rules


def test_fare_waiver_above_1500_escalates(engine):
    """Fare waiver > ₹1,500 requires escalation."""
    request = StructuredRequest(
        booking_reference="WL7742",
        requested_actions=["fare_waiver"],
        fare_difference=2000,
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    assert verdict.status == "ESCALATION_REQUIRED"
    assert verdict.escalation_required is True
    assert any("1,500" in reason or "1500" in reason for reason in verdict.escalation_reasons)
    assert "RULE-ESCALATE-FARE-WAIVER" in verdict.applicable_policy_rules


def test_fare_waiver_at_1500_not_escalated(engine):
    """Fare waiver exactly ₹1,500 (NOT above) does not escalate for fare limit alone."""
    request = StructuredRequest(
        booking_reference="WL7742",
        requested_actions=["fare_waiver"],
        fare_difference=1500,
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    # ₹1,500 is NOT above ₹1,500, so no escalation for fare alone
    # Note: The evaluation notes this is inferred, not explicitly authorized
    fare_escalation = [r for r in verdict.escalation_reasons if "waiver" in r.lower() and ("1,500" in r or "1500" in r)]
    assert len(fare_escalation) == 0


def test_fare_waiver_1501_escalates(engine):
    """Fare waiver ₹1,501 (above ₹1,500) requires escalation."""
    request = StructuredRequest(
        booking_reference="WL7742",
        requested_actions=["fare_waiver"],
        fare_difference=1501,
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    assert verdict.status == "ESCALATION_REQUIRED"
    assert verdict.escalation_required is True
    assert "RULE-ESCALATE-FARE-WAIVER" in verdict.applicable_policy_rules


# ============================================================================
# LOYALTY TESTS
# ============================================================================

def test_gold_priority_rebooking(engine):
    """Gold tier receives priority rebooking flag."""
    request = StructuredRequest(
        booking_reference="SK4821X",  # Priya - Gold
        requested_actions=["rebooking"],
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    assert verdict.loyalty_tier == "Gold"
    assert verdict.priority_rebooking is True
    assert "RULE-LOYALTY-PRIORITY" in verdict.applicable_policy_rules


def test_platinum_priority_rebooking(engine):
    """Platinum tier receives priority rebooking flag."""
    request = StructuredRequest(
        booking_reference="WL7742",  # Meher - Platinum
        requested_actions=["meal_voucher"],
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    assert verdict.loyalty_tier == "Platinum"
    assert verdict.priority_rebooking is True


def test_silver_no_priority(engine):
    """Silver tier does not receive priority rebooking."""
    request = StructuredRequest(
        booking_reference="TR1190B",  # Arvind - Silver
        requested_actions=["meal_voucher"],
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    assert verdict.loyalty_tier == "Silver"
    assert verdict.priority_rebooking is False


def test_loyalty_no_additional_compensation(engine):
    """Gold/Platinum receive same delay compensation as Silver."""
    # All three customers with same 4h delay should get same compensation
    request_silver = StructuredRequest(
        booking_reference="TR1190B",  # Silver, 4h delay
        requested_actions=["meal_voucher", "lounge_access"],
        disruption_cause="airline_operational"  # From scenario context
    )
    
    # Temporarily test with Gold booking at 4h delay
    bookings_gold = engine.get_all_bookings("SK4821X")
    for b in bookings_gold:
        if b.status == "cancelled":
            original_status = b.status
            original_delay = b.delay_hours
            b.status = "delayed"
            b.delay_hours = 4.0
            
            request_gold = StructuredRequest(
                booking_reference="SK4821X",  # Gold, 4h delay
                requested_actions=["meal_voucher", "lounge_access"],
                disruption_cause="airline_operational"  # From scenario context
            )
            
            verdict_silver = engine.evaluate(request_silver)
            verdict_gold = engine.evaluate(request_gold)
            
            # Restore
            b.status = original_status
            b.delay_hours = original_delay
            
            # Same compensation (excluding priority flag)
            assert set(verdict_silver.eligible_compensations) == set(verdict_gold.eligible_compensations) or \
                   set(verdict_silver.authorized_actions) == set(verdict_gold.authorized_actions)
            break


# ============================================================================
# ESCALATION TRIGGER TESTS
# ============================================================================

def test_business_class_upgrade_escalates(engine):
    """Business class upgrade request requires escalation (not in policy)."""
    request = StructuredRequest(
        booking_reference="SK4821X",
        requested_actions=["business_class_upgrade"],
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    assert verdict.status == "ESCALATION_REQUIRED"
    assert verdict.escalation_required is True
    assert "business_class_upgrade" in verdict.denied_actions
    assert any("beyond" in reason.lower() or "not covered" in reason.lower() 
               for reason in verdict.escalation_reasons)
    assert "RULE-ESCALATE-POLICY-EXCEPTION" in verdict.applicable_policy_rules


def test_legal_threat_escalates(engine):
    """Legal threat triggers mandatory escalation."""
    request = StructuredRequest(
        booking_reference="TR1190B",
        requested_actions=["meal_voucher"],
        escalation_intents=["legal_threat"],
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    assert verdict.status == "ESCALATION_REQUIRED"
    assert verdict.escalation_required is True
    assert any("legal" in reason.lower() for reason in verdict.escalation_reasons)
    assert "RULE-ESCALATE-LEGAL" in verdict.applicable_policy_rules


def test_formal_complaint_escalates(engine):
    """Formal complaint triggers mandatory escalation."""
    request = StructuredRequest(
        booking_reference="TR1190B",
        requested_actions=["meal_voucher"],
        escalation_intents=["formal_complaint"],
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    assert verdict.status == "ESCALATION_REQUIRED"
    assert verdict.escalation_required is True
    assert any("complaint" in reason.lower() for reason in verdict.escalation_reasons)
    assert "RULE-ESCALATE-FORMAL-COMPLAINT" in verdict.applicable_policy_rules


def test_non_airline_cause_escalates(engine):
    """Non-airline-caused disruption requires escalation."""
    request = StructuredRequest(
        booking_reference="TR1190B",
        requested_actions=["meal_voucher"],
        disruption_cause="weather"  # Non-airline cause from scenario context
    )
    verdict = engine.evaluate(request)
    
    assert verdict.status == "ESCALATION_REQUIRED"
    assert verdict.escalation_required is True
    assert "RULE-ESCALATE-NON-AIRLINE" in verdict.applicable_policy_rules


# ============================================================================
# EMOTION VS ESCALATION TESTS
# ============================================================================

def test_furious_emotion_no_automatic_escalation(engine):
    """'Furious' emotion does NOT trigger automatic escalation."""
    request = StructuredRequest(
        booking_reference="TR1190B",
        requested_actions=["meal_voucher", "lounge_access"],
        customer_emotion="furious",
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    # Should authorize meal + lounge for 4h delay, not escalate due to emotion
    assert verdict.status == "AUTHORIZED"
    assert "issue_meal_voucher_500" in verdict.authorized_actions
    assert "provide_lounge_access" in verdict.authorized_actions


def test_frustrated_emotion_no_escalation(engine):
    """'Frustrated' emotion does NOT trigger escalation."""
    request = StructuredRequest(
        booking_reference="TR1190B",
        requested_actions=["meal_voucher"],
        customer_emotion="frustrated",
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    assert verdict.status == "AUTHORIZED"
    assert not verdict.escalation_required


def test_angry_emotion_no_escalation(engine):
    """'Angry' emotion does NOT trigger escalation."""
    request = StructuredRequest(
        booking_reference="TR1190B",
        requested_actions=["meal_voucher"],
        customer_emotion="angry",
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    assert verdict.status == "AUTHORIZED"
    assert not verdict.escalation_required


# ============================================================================
# VALIDATION TESTS
# ============================================================================

def test_missing_booking_reference_error(engine):
    """Missing booking reference returns ERROR verdict."""
    request = StructuredRequest(
        booking_reference="",
        requested_actions=["refund"]
    )
    verdict = engine.evaluate(request)
    
    assert verdict.status == "ERROR"
    assert verdict.error_type == "missing_booking_reference"
    assert verdict.required_field == "booking_reference"


def test_unknown_booking_reference_error(engine):
    """Unknown booking reference returns ERROR verdict."""
    request = StructuredRequest(
        booking_reference="UNKNOWN123",
        requested_actions=["refund"]
    )
    verdict = engine.evaluate(request)
    
    assert verdict.status == "ERROR"
    assert verdict.error_type in ["customer_not_found", "booking_not_found"]


def test_negative_delay_hours_error(engine):
    """Negative delay_hours returns ERROR verdict."""
    bookings = engine.get_all_bookings("TR1190B")
    booking = bookings[0]
    original_delay = booking.delay_hours
    booking.delay_hours = -1.0
    
    request = StructuredRequest(
        booking_reference="TR1190B",
        requested_actions=["meal_voucher"]
    )
    verdict = engine.evaluate(request)
    
    # Restore
    booking.delay_hours = original_delay
    
    assert verdict.status == "ERROR"
    assert verdict.error_type == "invalid_delay_hours"


def test_negative_fare_difference_error(engine):
    """Negative fare_difference returns ERROR verdict."""
    request = StructuredRequest(
        booking_reference="TR1190B",
        requested_actions=["fare_waiver"],
        fare_difference=-100
    )
    verdict = engine.evaluate(request)
    
    assert verdict.status == "ERROR"
    assert verdict.error_type == "invalid_fare_difference"


# ============================================================================
# DETERMINISM TESTS
# ============================================================================

def test_determinism_same_input_same_output(engine):
    """Same inputs produce identical outputs (determinism property)."""
    request = StructuredRequest(
        booking_reference="TR1190B",
        requested_actions=["meal_voucher", "lounge_access"],
        customer_emotion="frustrated",
        disruption_cause="airline_operational"  # From scenario context
    )
    
    # Evaluate 10 times
    verdicts = [engine.evaluate(request) for _ in range(10)]
    
    # All verdicts should be identical
    for i in range(1, len(verdicts)):
        assert verdicts[0] == verdicts[i]
        assert verdicts[0].status == verdicts[i].status
        assert verdicts[0].authorized_actions == verdicts[i].authorized_actions
        assert verdicts[0].denied_actions == verdicts[i].denied_actions
        assert verdicts[0].escalation_required == verdicts[i].escalation_required


# ============================================================================
# TRACEABILITY TESTS
# ============================================================================

def test_verdict_contains_applicable_rules(engine):
    """Every non-error verdict references source policy rules."""
    request = StructuredRequest(
        booking_reference="TR1190B",
        requested_actions=["meal_voucher", "lounge_access"],
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    assert verdict.status != "ERROR"
    assert len(verdict.applicable_policy_rules) > 0
    assert all(rule.startswith("RULE-") or rule.startswith("AMBIGUITY-") 
               for rule in verdict.applicable_policy_rules)


def test_escalation_has_reason(engine):
    """Escalations include escalation_reason."""
    request = StructuredRequest(
        booking_reference="SK4821X",
        requested_actions=["business_class_upgrade"],
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    if verdict.escalation_required:
        assert len(verdict.escalation_reasons) > 0


def test_decision_trace_present(engine):
    """Verdicts include decision trace."""
    request = StructuredRequest(
        booking_reference="TR1190B",
        requested_actions=["meal_voucher"],
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    assert verdict.decision_trace is not None
    assert verdict.decision_trace.booking_reference == "TR1190B"
    assert len(verdict.decision_trace.rules_evaluated) > 0


# ============================================================================
# HARDENING TESTS
# ============================================================================

def test_unknown_cause_not_converted_to_airline_operational(engine):
    """Unknown cause is NOT silently converted to airline_operational."""
    request = StructuredRequest(
        booking_reference="TR1190B",  # 4h delay
        requested_actions=["meal_voucher"],
        # No disruption_cause provided - cause is unknown
    )
    verdict = engine.evaluate(request)
    
    # Should escalate because cause is unknown (not airline-caused)
    assert verdict.status == "ESCALATION_REQUIRED"
    assert verdict.escalation_required is True
    # Should NOT authorize airline-caused compensation without knowing cause
    assert any("cause" in reason.lower() or "unknown" in reason.lower() 
               for reason in verdict.escalation_reasons)


def test_fare_waiver_within_boundary_noted_as_inferred(engine):
    """Fare waiver ≤₹1,500 is noted as inferred, NOT explicitly authorized."""
    request = StructuredRequest(
        booking_reference="WL7742",
        requested_actions=["fare_waiver"],
        fare_difference=1000,
        disruption_cause="airline_operational"
    )
    verdict = engine.evaluate(request)
    
    # The evaluation should note this is inferred from the boundary
    # Check that we don't claim explicit authorization
    # This is captured in the rule evaluation trace
    assert len(verdict.decision_trace.rules_evaluated) > 0
    
    # The key point: ₹1,000 does NOT escalate (it's ≤₹1,500)
    # But we should not claim "The policy explicitly authorizes ₹1,000 waiver"
    fare_escalation = [r for r in verdict.escalation_reasons 
                      if "waiver" in r.lower() and ("1,500" in r or "1500" in r)]
    assert len(fare_escalation) == 0  # Not escalated


def test_every_denied_action_has_reason(engine):
    """Every denied action must have a non-empty denial reason."""
    # Test multiple scenarios that should produce denials
    test_cases = [
        # Hotel with 4h delay
        StructuredRequest(
            booking_reference="TR1190B",
            requested_actions=["hotel_accommodation"],
            disruption_cause="airline_operational"
        ),
        # Business class upgrade
        StructuredRequest(
            booking_reference="SK4821X",
            requested_actions=["business_class_upgrade"],
            disruption_cause="airline_operational"
        ),
        # Full-night hotel when only delayed hours authorized
        StructuredRequest(
            booking_reference="WL7742",
            requested_actions=["full_night_hotel"],
            disruption_cause="airline_operational"
        ),
    ]
    
    for request in test_cases:
        verdict = engine.evaluate(request)
        
        # For every denied action, there must be a non-empty reason
        for action in verdict.denied_actions:
            assert action in verdict.denial_reasons
            assert verdict.denial_reasons[action] is not None
            assert len(verdict.denial_reasons[action].strip()) > 0
            assert verdict.denial_reasons[action] != "No reason provided"


def test_partial_resolution_authorized_with_escalation(engine):
    """Partial resolution: authorized actions present even with escalation."""
    # Meher scenario: some things authorized, some escalate
    request = StructuredRequest(
        booking_reference="WL7742",
        requested_actions=["meal_voucher", "hotel", "rebooking"],
        alternate_flight="SK-999",
        fare_difference=2000,
        disruption_cause="airline_operational"
    )
    verdict = engine.evaluate(request)
    
    # Should have BOTH authorized actions AND escalation
    assert verdict.status == "ESCALATION_REQUIRED"
    assert verdict.escalation_required is True
    
    # Meal voucher should be authorized despite escalation
    assert "issue_meal_voucher_500" in verdict.authorized_actions
    
    # Hotel (delayed hours) should be authorized
    assert "arrange_hotel_accommodation_delayed_hours" in verdict.authorized_actions
    
    # But rebooking + fare waiver should escalate
    assert len(verdict.escalation_reasons) > 0
    
    # Partial resolution preserved
    assert len(verdict.authorized_actions) > 0
    assert len(verdict.escalation_reasons) > 0


def test_every_escalation_has_meaningful_reason(engine):
    """Every escalation must have a meaningful reason with RULE-* or AMBIGUITY-* identifier."""
    test_cases = [
        # Legal threat
        StructuredRequest(
            booking_reference="TR1190B",
            requested_actions=["meal_voucher"],
            escalation_intents=["legal_threat"],
            disruption_cause="airline_operational"
        ),
        # Fare waiver > ₹1,500
        StructuredRequest(
            booking_reference="WL7742",
            requested_actions=["fare_waiver"],
            fare_difference=2000,
            disruption_cause="airline_operational"
        ),
        # Delayed flight alternate rebooking
        StructuredRequest(
            booking_reference="WL7742",
            requested_actions=["rebooking"],
            alternate_flight="SK-999",
            disruption_cause="airline_operational"
        ),
        # Non-airline cause
        StructuredRequest(
            booking_reference="TR1190B",
            requested_actions=["meal_voucher"],
            disruption_cause="weather"
        ),
    ]
    
    for request in test_cases:
        verdict = engine.evaluate(request)
        
        if verdict.escalation_required:
            # Must have at least one escalation reason
            assert len(verdict.escalation_reasons) > 0
            
            # Each reason should be meaningful
            for reason in verdict.escalation_reasons:
                assert reason is not None
                assert len(reason.strip()) > 0
                assert reason != "Escalation required"  # Too generic
            
            # Should reference at least one RULE-* or AMBIGUITY-*
            assert len(verdict.applicable_policy_rules) > 0
            has_rule_or_ambiguity = any(
                rule.startswith("RULE-") or rule.startswith("AMBIGUITY-")
                for rule in verdict.applicable_policy_rules
            )
            assert has_rule_or_ambiguity


# ============================================================================
# SCENARIO TESTS (Three Mandatory Scenarios)
# ============================================================================

def test_scenario_1_priya_nair(engine):
    """
    Scenario 1: Priya Nair - SK4821X cancelled.
    Requests: full refund + business class upgrade on return flight.
    Expected: Authorize refund, deny upgrade, escalate upgrade request.
    """
    request = StructuredRequest(
        booking_reference="SK4821X",
        requested_actions=["refund", "business_class_upgrade"],
        customer_emotion="furious",
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    # Should escalate due to business class upgrade (not in policy)
    assert verdict.status == "ESCALATION_REQUIRED"
    assert verdict.escalation_required is True
    
    # Refund should be authorized or pending escalation resolution
    assert "full_refund_to_original_payment_method" in verdict.eligible_compensations
    
    # Business class upgrade should be denied/escalated
    assert "business_class_upgrade" in verdict.denied_actions
    assert any("business" in reason.lower() for reason in verdict.escalation_reasons)
    
    # Gold tier priority
    assert verdict.loyalty_tier == "Gold"
    
    # Furious emotion should NOT cause escalation by itself
    # Escalation is due to business class request
    assert "RULE-ESCALATE-POLICY-EXCEPTION" in verdict.applicable_policy_rules


def test_scenario_2_arvind_kulkarni(engine):
    """
    Scenario 2: Arvind Kulkarni - TR1190B 4h delay.
    Requests: hotel accommodation.
    Expected: Authorize meal + lounge, deny hotel (requires >5h).
    """
    request = StructuredRequest(
        booking_reference="TR1190B",
        requested_actions=["hotel_accommodation"],
        customer_emotion="frustrated",
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    # Should authorize Tier 2 benefits
    assert verdict.status in ["AUTHORIZED", "DENIED"]
    assert "issue_meal_voucher_500" in verdict.authorized_actions
    assert "provide_lounge_access" in verdict.authorized_actions
    assert verdict.meal_voucher_amount == 500
    
    # Hotel should be denied (4h < 5h threshold)
    assert "hotel_accommodation" in verdict.denied_actions
    assert "5 hours" in verdict.denial_reasons["hotel_accommodation"]
    
    # Silver tier, no priority
    assert verdict.loyalty_tier == "Silver"
    assert verdict.priority_rebooking is False
    
    # No escalation (frustrated emotion doesn't trigger escalation)
    assert not verdict.escalation_required


def test_scenario_3_meher_kaur(engine):
    """
    Scenario 3: Meher Kaur - WL7742 6h delay.
    Requests: full-night hotel + alternate higher-fare flight + ₹2,000 fare waiver.
    Expected: 
    - Authorize meal + hotel (6h delayed hours)
    - Deny full-night hotel
    - Escalate alternate flight (delayed flight rebooking not authorized)
    - Escalate ₹2,000 fare waiver (exceeds ₹1,500 limit)
    - Flag lounge access as POLICY_UNSPECIFIED
    """
    request = StructuredRequest(
        booking_reference="WL7742",
        requested_actions=["full_night_hotel", "rebooking"],
        alternate_flight="SK-999",
        fare_difference=2000,
        disruption_cause="airline_operational"  # From scenario context
    )
    verdict = engine.evaluate(request)
    
    # Should escalate due to multiple reasons
    assert verdict.status in ["ESCALATION_REQUIRED", "POLICY_UNSPECIFIED"]
    assert verdict.escalation_required is True
    
    # Tier 3 benefits authorized
    assert "issue_meal_voucher_500" in verdict.authorized_actions
    assert "arrange_hotel_accommodation_delayed_hours" in verdict.authorized_actions
    assert verdict.meal_voucher_amount == 500
    assert verdict.hotel_accommodation_hours == 6.0
    
    # Full-night hotel denied
    if "full_night_hotel" in verdict.denied_actions:
        assert "delayed hours" in verdict.denial_reasons["full_night_hotel"].lower()
    
    # Alternate flight escalates (delayed flight rebooking not authorized)
    assert any("delayed flight" in reason.lower() or "alternate" in reason.lower() 
               for reason in verdict.escalation_reasons)
    
    # Fare waiver escalates (₹2,000 > ₹1,500)
    assert any("1,500" in reason or "1500" in reason or "2,000" in reason or "2000" in reason
               for reason in verdict.escalation_reasons)
    
    # Platinum tier priority
    assert verdict.loyalty_tier == "Platinum"
    assert verdict.priority_rebooking is True
    
    # Lounge access ambiguity flagged
    assert "AMBIGUITY-02" in verdict.ambiguities_flagged
    
    # Multiple escalation rules
    assert "RULE-ESCALATE-FARE-WAIVER" in verdict.applicable_policy_rules
    assert "AMBIGUITY-03" in verdict.applicable_policy_rules


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
