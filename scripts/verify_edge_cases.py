"""Verify policy edge cases and boundary conditions."""

from policy.engine import PolicyEngine
from policy.models import StructuredRequest

def main() -> None:
    engine = PolicyEngine(data_dir="data")
    checks = []

    # Edge Case 1: Exactly 3 hours delay
    req = StructuredRequest(
        booking_reference="TR1190B",
        requested_actions=["meal_voucher", "lounge_access"],
        customer_emotion="neutral",
        disruption_cause="airline_operational"
    )
    # Manually override delay to exactly 3.0 hours for edge case testing
    booking = engine.get_booking("TR1190B")
    original_delay = booking.delay_hours if booking else None
    if booking:
        booking.delay_hours = 3.0
    
    verdict = engine.evaluate(req)
    checks.append(("3h delay → POLICY_UNSPECIFIED", verdict.status == "POLICY_UNSPECIFIED"))
    
    # Restore original delay
    if booking and original_delay is not None:
        booking.delay_hours = original_delay

    # Edge Case 2: Exactly 5 hours delay
    if booking:
        booking.delay_hours = 5.0
    
    req2 = StructuredRequest(
        booking_reference="TR1190B",
        requested_actions=["meal_voucher", "hotel"],
        customer_emotion="neutral",
        disruption_cause="airline_operational"
    )
    verdict2 = engine.evaluate(req2)
    checks.append(("5h delay → POLICY_UNSPECIFIED for hotel", "AMBIGUITY-02" in verdict2.ambiguities_flagged or verdict2.status == "POLICY_UNSPECIFIED"))
    
    # Restore
    if booking and original_delay is not None:
        booking.delay_hours = original_delay

    # Edge Case 3: Fare waiver at exactly ₹1,500
    req3 = StructuredRequest(
        booking_reference="SK4821X",
        requested_actions=["fare_waiver"],
        fare_difference=1500,
        customer_emotion="neutral",
        disruption_cause="airline_operational"
    )
    verdict3 = engine.evaluate(req3)
    checks.append(("₹1,500 fare → no escalation", not verdict3.escalation_required))

    # Edge Case 4: Fare waiver at ₹1,501
    req4 = StructuredRequest(
        booking_reference="SK4821X",
        requested_actions=["fare_waiver"],
        fare_difference=1501,
        customer_emotion="neutral",
        disruption_cause="airline_operational"
    )
    verdict4 = engine.evaluate(req4)
    checks.append(("₹1,501 fare → escalation", verdict4.escalation_required))

    # Edge Case 5: Unknown disruption cause
    # NOTE: SK4821X booking already has cause="airline_operational" in bookings.json
    # So we cannot test unknown cause with existing data (booking.cause takes precedence)
    # The test_policy.py::test_unknown_cause_not_converted_to_airline_operational
    # properly tests this with TR1190B where booking.cause is None
    # checks.append(("Unknown cause → escalation", True))  # Covered by test suite

    # Edge Case 6: Emotion alone (furious) does NOT escalate
    req6 = StructuredRequest(
        booking_reference="TR1190B",
        requested_actions=["meal_voucher"],
        customer_emotion="furious",
        disruption_cause="airline_operational"
    )
    verdict6 = engine.evaluate(req6)
    checks.append(("Furious emotion alone → no escalation", not verdict6.escalation_required))

    # Edge Case 7: Legal threat DOES escalate
    req7 = StructuredRequest(
        booking_reference="TR1190B",
        requested_actions=[],
        customer_emotion="neutral",
        escalation_intents=["legal_threat"],
        disruption_cause="airline_operational"
    )
    verdict7 = engine.evaluate(req7)
    checks.append(("Legal threat → escalation", verdict7.escalation_required))

    print("Edge Case Verification")
    print("=" * 50)
    failed = 0
    for name, ok in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"[{status}] {name}")
    print("=" * 50)
    print(f"Total: {len(checks) - failed}/{len(checks)} passed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
