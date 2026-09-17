"""
Comprehensive tests for AirResolve action execution layer.

Tests verify:
1. Authorization firewall blocks unauthorized actions
2. Action specificity (fixed voucher amounts, etc.)
3. Hotel accommodation respects delayed hours policy
4. Rebooking executes without invented data
5. Escalation packet creation
6. Audit journal records all events
7. Idempotency prevents duplicate execution
8. Policy remains sole authority
"""

import pytest
from policy.engine import PolicyEngine
from policy.models import StructuredRequest, PolicyVerdict
from actions.executor import ActionExecutor
from actions.models import ActionRequest, ActionStatus
from audit.journal import AuditJournal, AuditEvent, EventType


@pytest.fixture
def engine():
    """Create policy engine with test data."""
    return PolicyEngine(data_dir="data")


@pytest.fixture
def executor():
    """Create action executor."""
    return ActionExecutor()


@pytest.fixture
def journal():
    """Create audit journal."""
    return AuditJournal()


# ============================================================================
# AUTHORIZATION FIREWALL TESTS
# ============================================================================

def test_authorized_refund_executes(engine, executor):
    """Authorized refund action executes successfully."""
    # Get policy decision
    request = StructuredRequest(
        booking_reference="SK4821X",
        requested_actions=["refund"],
        disruption_cause="airline_operational"
    )
    verdict = engine.evaluate(request)
    
    # Verify policy authorized the refund
    assert "initiate_refund_to_original_payment_method" in verdict.authorized_actions
    
    # Execute action
    action_req = ActionRequest(
        action_id="initiate_refund_to_original_payment_method",
        booking_reference="SK4821X"
    )
    result = executor.execute(action_req, verdict)
    
    # Verify execution succeeded
    assert result.status == ActionStatus.EXECUTED
    assert result.metadata["destination"] == "original_payment_method"
    assert result.metadata["processing_days"] == 7


def test_unauthorized_business_class_upgrade_rejected(engine, executor):
    """Unauthorized business class upgrade is rejected by firewall."""
    # Get policy decision
    request = StructuredRequest(
        booking_reference="SK4821X",
        requested_actions=["refund", "business_class_upgrade"],
        disruption_cause="airline_operational"
    )
    verdict = engine.evaluate(request)
    
    # Verify policy did NOT authorize business class upgrade
    assert "business_class_upgrade" not in verdict.authorized_actions
    assert "business_class_upgrade" in verdict.denied_actions
    
    # Attempt to execute unauthorized action
    action_req = ActionRequest(
        action_id="business_class_upgrade",
        booking_reference="SK4821X"
    )
    result = executor.execute(action_req, verdict)
    
    # Verify authorization firewall rejected it
    assert result.status == ActionStatus.REJECTED
    assert "authorization firewall" in result.message.lower()
    assert "not authorized" in result.message.lower()


def test_unauthorized_full_night_hotel_rejected(engine, executor):
    """Unauthorized full-night hotel is rejected by firewall."""
    # Get policy decision for 6h delay (only delayed hours authorized)
    request = StructuredRequest(
        booking_reference="WL7742",
        requested_actions=["full_night_hotel"],
        disruption_cause="airline_operational"
    )
    verdict = engine.evaluate(request)
    
    # Verify policy did NOT authorize full night hotel
    assert "full_night_hotel" not in verdict.authorized_actions
    assert "full_night_hotel" in verdict.denied_actions
    
    # Attempt to execute unauthorized action
    action_req = ActionRequest(
        action_id="full_night_hotel",
        booking_reference="WL7742"
    )
    result = executor.execute(action_req, verdict)
    
    # Verify authorization firewall rejected it
    assert result.status == ActionStatus.REJECTED
    assert "authorization firewall" in result.message.lower()


def test_unauthorized_delayed_flight_rebooking_rejected(engine, executor):
    """Unauthorized delayed flight alternate rebooking is rejected."""
    # Get policy decision for delayed flight alternate rebooking
    request = StructuredRequest(
        booking_reference="WL7742",
        requested_actions=["rebooking"],
        alternate_flight="SK-999",
        disruption_cause="airline_operational"
    )
    verdict = engine.evaluate(request)
    
    # Verify policy did NOT authorize rebooking (requires escalation)
    assert "rebook_next_available_within_24h" not in verdict.authorized_actions
    assert verdict.escalation_required is True
    
    # Attempt to execute unauthorized action
    action_req = ActionRequest(
        action_id="rebook_next_available_within_24h",
        booking_reference="WL7742"
    )
    result = executor.execute(action_req, verdict)
    
    # Verify authorization firewall rejected it
    assert result.status == ActionStatus.REJECTED
    assert "authorization firewall" in result.message.lower()


def test_unauthorized_fare_waiver_rejected(engine, executor):
    """Unauthorized ₹2,000 fare waiver is rejected."""
    # Get policy decision for fare waiver > ₹1,500
    request = StructuredRequest(
        booking_reference="WL7742",
        requested_actions=["fare_waiver"],
        fare_difference=2000,
        disruption_cause="airline_operational"
    )
    verdict = engine.evaluate(request)
    
    # Verify policy requires escalation (no authorized fare waiver action)
    assert verdict.escalation_required is True
    assert any("1,500" in r or "2,000" in r or "2000" in r for r in verdict.escalation_reasons)
    
    # Attempt to execute non-existent fare waiver action
    action_req = ActionRequest(
        action_id="waive_fare_difference",
        booking_reference="WL7742",
        parameters={"amount": 2000}
    )
    result = executor.execute(action_req, verdict)
    
    # Verify authorization firewall rejected it
    assert result.status == ActionStatus.REJECTED


# ============================================================================
# ACTION SPECIFICITY TESTS
# ============================================================================

def test_meal_voucher_always_500(engine, executor):
    """Meal voucher action always represents ₹500, not arbitrary amount."""
    # Get policy decision
    request = StructuredRequest(
        booking_reference="TR1190B",
        requested_actions=["meal_voucher"],
        disruption_cause="airline_operational"
    )
    verdict = engine.evaluate(request)
    
    # Verify meal voucher authorized
    assert "issue_meal_voucher_500" in verdict.authorized_actions
    
    # Execute action
    action_req = ActionRequest(
        action_id="issue_meal_voucher_500",
        booking_reference="TR1190B"
    )
    result = executor.execute(action_req, verdict)
    
    # Verify amount is FIXED at ₹500
    assert result.status == ActionStatus.EXECUTED
    assert result.metadata["voucher_amount"] == 500
    assert result.metadata["currency"] == "INR"
    
    # Note: No generic "issue_voucher(amount)" function exists
    # This prevents arbitrary voucher amounts


# ============================================================================
# HOTEL ACCOMMODATION TESTS
# ============================================================================

def test_hotel_delayed_hours_only(engine, executor):
    """Hotel accommodation for 6 hours (delayed hours), no full night conversion."""
    # Get policy decision for 6h delay
    request = StructuredRequest(
        booking_reference="WL7742",
        requested_actions=["hotel"],
        disruption_cause="airline_operational"
    )
    verdict = engine.evaluate(request)
    
    # Verify policy authorized delayed hours hotel
    assert "arrange_hotel_accommodation_delayed_hours" in verdict.authorized_actions
    assert verdict.hotel_accommodation_hours == 6.0
    
    # Execute action
    action_req = ActionRequest(
        action_id="arrange_hotel_accommodation_delayed_hours",
        booking_reference="WL7742"
    )
    result = executor.execute(action_req, verdict)
    
    # Verify execution with correct hours (no full night conversion)
    assert result.status == ActionStatus.EXECUTED
    assert result.metadata["accommodation_hours"] == 6.0
    assert result.metadata["coverage_type"] == "delayed_hours_only"
    assert "NOT a full night stay" in result.metadata["note"]


# ============================================================================
# REBOOKING TESTS
# ============================================================================

def test_rebooking_no_invented_flight_number(engine, executor):
    """Rebooking executes without inventing flight numbers."""
    # Get policy decision for cancelled flight rebooking
    request = StructuredRequest(
        booking_reference="SK4821X",
        requested_actions=["rebooking"],
        disruption_cause="airline_operational"
    )
    verdict = engine.evaluate(request)
    
    # Verify policy authorized rebooking
    assert "rebook_next_available_within_24h" in verdict.authorized_actions
    
    # Execute action without specific flight
    action_req = ActionRequest(
        action_id="rebook_next_available_within_24h",
        booking_reference="SK4821X"
    )
    result = executor.execute(action_req, verdict)
    
    # Verify execution succeeded
    assert result.status == ActionStatus.EXECUTED
    assert result.metadata["flight_selection"] == "next_available_within_24h"
    assert result.metadata["charge"] == "no_charge"
    # No specific flight number invented


# ============================================================================
# ESCALATION TESTS
# ============================================================================

def test_escalation_packet_creation(engine, executor):
    """Escalation creates complete human handoff packet."""
    # Get policy decision requiring escalation
    request = StructuredRequest(
        booking_reference="SK4821X",
        requested_actions=["refund", "business_class_upgrade"],
        disruption_cause="airline_operational"
    )
    verdict = engine.evaluate(request)
    
    # Verify escalation required
    assert verdict.escalation_required is True
    
    # Create escalation
    result, packet = executor.create_escalation(
        policy_verdict=verdict,
        customer_name="Priya Nair"
    )
    
    # Verify result
    assert result.status == ActionStatus.EXECUTED
    assert result.action_id == "create_human_escalation"
    assert "case_id" in result.metadata
    
    # Verify packet structure
    assert packet.case_id is not None
    assert packet.booking_reference == "SK4821X"
    assert packet.customer_name == "Priya Nair"
    assert packet.loyalty_tier == "Gold"
    assert len(packet.authorized_actions) > 0
    assert len(packet.denied_actions) > 0
    assert len(packet.escalation_reasons) > 0
    assert len(packet.conversation_summary) > 0


# ============================================================================
# AUDIT JOURNAL TESTS
# ============================================================================

def test_audit_action_executed(journal):
    """Every executed action creates ACTION_EXECUTED event."""
    event = AuditEvent(
        event_type=EventType.ACTION_EXECUTED,
        case_id="case-123",
        booking_reference="SK4821X",
        action_id="initiate_refund_to_original_payment_method",
        status="EXECUTED",
        details={"amount": 5000}
    )
    
    journal.record(event)
    
    # Verify event recorded
    events = journal.list_events(event_type=EventType.ACTION_EXECUTED)
    assert len(events) == 1
    assert events[0].action_id == "initiate_refund_to_original_payment_method"


def test_audit_action_rejected(journal):
    """Every rejected unauthorized action creates ACTION_REJECTED event."""
    event = AuditEvent(
        event_type=EventType.ACTION_REJECTED,
        case_id="case-123",
        booking_reference="SK4821X",
        action_id="business_class_upgrade",
        status="REJECTED",
        details={"reason": "not_authorized"}
    )
    
    journal.record(event)
    
    # Verify event recorded
    events = journal.list_events(event_type=EventType.ACTION_REJECTED)
    assert len(events) == 1
    assert events[0].action_id == "business_class_upgrade"
    assert events[0].status == "REJECTED"


def test_audit_escalation_created(journal):
    """Escalation creates ESCALATION_CREATED event."""
    event = AuditEvent(
        event_type=EventType.ESCALATION_CREATED,
        case_id="case-123",
        booking_reference="SK4821X",
        details={
            "escalation_reasons": ["business_class_upgrade not in policy"],
            "priority": "medium"
        }
    )
    
    journal.record(event)
    
    # Verify event recorded
    events = journal.list_events(event_type=EventType.ESCALATION_CREATED)
    assert len(events) == 1


def test_audit_query_by_booking(journal):
    """Audit journal can query events by booking reference."""
    # Record multiple events
    journal.record(AuditEvent(
        event_type=EventType.POLICY_EVALUATED,
        booking_reference="SK4821X"
    ))
    journal.record(AuditEvent(
        event_type=EventType.ACTION_EXECUTED,
        booking_reference="SK4821X",
        action_id="initiate_refund_to_original_payment_method"
    ))
    journal.record(AuditEvent(
        event_type=EventType.ACTION_EXECUTED,
        booking_reference="TR1190B",  # Different booking
        action_id="issue_meal_voucher_500"
    ))
    
    # Query by booking
    events = journal.get_booking_events("SK4821X")
    
    # Verify only SK4821X events returned
    assert len(events) == 2
    assert all(e.booking_reference == "SK4821X" for e in events)


# ============================================================================
# IDEMPOTENCY TESTS
# ============================================================================

def test_idempotency_duplicate_execution_prevented(engine, executor):
    """Executing same action twice with same correlation ID prevents duplicate."""
    # Get policy decision
    request = StructuredRequest(
        booking_reference="SK4821X",
        requested_actions=["refund"],
        disruption_cause="airline_operational"
    )
    verdict = engine.evaluate(request)
    
    # Execute action first time
    correlation_id = "test-correlation-123"
    action_req = ActionRequest(
        action_id="initiate_refund_to_original_payment_method",
        booking_reference="SK4821X",
        correlation_id=correlation_id
    )
    result1 = executor.execute(action_req, verdict)
    
    # Verify first execution succeeded
    assert result1.status == ActionStatus.EXECUTED
    
    # Attempt to execute same action again with same correlation ID
    action_req2 = ActionRequest(
        action_id="initiate_refund_to_original_payment_method",
        booking_reference="SK4821X",
        correlation_id=correlation_id  # Same correlation ID
    )
    result2 = executor.execute(action_req2, verdict)
    
    # Verify second execution was prevented
    assert result2.status == ActionStatus.ALREADY_EXECUTED
    assert "already executed" in result2.message.lower()


# ============================================================================
# POLICY IS SOLE AUTHORITY TEST
# ============================================================================

def test_policy_is_sole_authority(engine, executor):
    """Action layer cannot execute actions not authorized by PolicyVerdict."""
    # Create a policy verdict that authorizes ONLY refund
    request = StructuredRequest(
        booking_reference="SK4821X",
        requested_actions=["refund"],  # Only requesting refund
        disruption_cause="airline_operational"
    )
    verdict = engine.evaluate(request)
    
    # Verify only refund authorized
    assert "initiate_refund_to_original_payment_method" in verdict.authorized_actions
    assert "issue_meal_voucher_500" not in verdict.authorized_actions
    
    # Attempt to execute meal voucher (not authorized)
    action_req = ActionRequest(
        action_id="issue_meal_voucher_500",
        booking_reference="SK4821X"
    )
    result = executor.execute(action_req, verdict)
    
    # Verify authorization firewall rejected it
    # Even though meal voucher is a valid action, it's not authorized for this verdict
    assert result.status == ActionStatus.REJECTED
    assert "authorization firewall" in result.message.lower()


# ============================================================================
# INTEGRATION TESTS WITH SCENARIOS
# ============================================================================

def test_scenario_priya_integration(engine, executor):
    """Integration test: Priya scenario with refund and rejected upgrade."""
    # Policy evaluation
    request = StructuredRequest(
        booking_reference="SK4821X",
        requested_actions=["refund", "business_class_upgrade"],
        customer_emotion="furious",
        disruption_cause="airline_operational"
    )
    verdict = engine.evaluate(request)
    
    # Verify policy decisions
    assert verdict.status == "ESCALATION_REQUIRED"
    assert "initiate_refund_to_original_payment_method" in verdict.authorized_actions
    assert "business_class_upgrade" in verdict.denied_actions
    
    # Execute authorized refund
    refund_req = ActionRequest(
        action_id="initiate_refund_to_original_payment_method",
        booking_reference="SK4821X"
    )
    refund_result = executor.execute(refund_req, verdict)
    assert refund_result.status == ActionStatus.EXECUTED
    
    # Attempt unauthorized business class upgrade
    upgrade_req = ActionRequest(
        action_id="business_class_upgrade",
        booking_reference="SK4821X"
    )
    upgrade_result = executor.execute(upgrade_req, verdict)
    assert upgrade_result.status == ActionStatus.REJECTED
    
    # Create escalation
    esc_result, esc_packet = executor.create_escalation(verdict, "Priya Nair")
    assert esc_result.status == ActionStatus.EXECUTED
    assert "business_class_upgrade" in str(esc_packet.escalation_reasons)


def test_scenario_arvind_integration(engine, executor):
    """Integration test: Arvind scenario with meal/lounge, rejected hotel."""
    # Policy evaluation
    request = StructuredRequest(
        booking_reference="TR1190B",
        requested_actions=["meal_voucher", "lounge_access", "hotel"],
        customer_emotion="frustrated",
        disruption_cause="airline_operational"
    )
    verdict = engine.evaluate(request)
    
    # Verify policy decisions
    assert verdict.status == "AUTHORIZED"
    assert "issue_meal_voucher_500" in verdict.authorized_actions
    assert "provide_lounge_access" in verdict.authorized_actions
    assert "hotel" in verdict.denied_actions
    
    # Execute authorized meal voucher
    meal_req = ActionRequest(
        action_id="issue_meal_voucher_500",
        booking_reference="TR1190B"
    )
    meal_result = executor.execute(meal_req, verdict)
    assert meal_result.status == ActionStatus.EXECUTED
    assert meal_result.metadata["voucher_amount"] == 500
    
    # Execute authorized lounge access
    lounge_req = ActionRequest(
        action_id="provide_lounge_access",
        booking_reference="TR1190B"
    )
    lounge_result = executor.execute(lounge_req, verdict)
    assert lounge_result.status == ActionStatus.EXECUTED
    
    # Attempt unauthorized hotel
    hotel_req = ActionRequest(
        action_id="arrange_hotel_accommodation_delayed_hours",
        booking_reference="TR1190B"
    )
    hotel_result = executor.execute(hotel_req, verdict)
    assert hotel_result.status == ActionStatus.REJECTED


def test_scenario_meher_integration(engine, executor):
    """Integration test: Meher scenario with partial resolution."""
    # Policy evaluation
    request = StructuredRequest(
        booking_reference="WL7742",
        requested_actions=["meal_voucher", "hotel", "full_night_hotel", "rebooking"],
        alternate_flight="SK-999",
        fare_difference=2000,
        disruption_cause="airline_operational"
    )
    verdict = engine.evaluate(request)
    
    # Verify policy decisions (partial resolution)
    assert verdict.status == "ESCALATION_REQUIRED"
    assert "issue_meal_voucher_500" in verdict.authorized_actions
    assert "arrange_hotel_accommodation_delayed_hours" in verdict.authorized_actions
    assert "full_night_hotel" in verdict.denied_actions
    assert "rebooking" in verdict.denied_actions
    
    # Execute authorized meal voucher
    meal_req = ActionRequest(
        action_id="issue_meal_voucher_500",
        booking_reference="WL7742"
    )
    meal_result = executor.execute(meal_req, verdict)
    assert meal_result.status == ActionStatus.EXECUTED
    
    # Execute authorized hotel (6 hours)
    hotel_req = ActionRequest(
        action_id="arrange_hotel_accommodation_delayed_hours",
        booking_reference="WL7742"
    )
    hotel_result = executor.execute(hotel_req, verdict)
    assert hotel_result.status == ActionStatus.EXECUTED
    assert hotel_result.metadata["accommodation_hours"] == 6.0
    
    # Attempt unauthorized full-night hotel
    full_night_req = ActionRequest(
        action_id="full_night_hotel",
        booking_reference="WL7742"
    )
    full_night_result = executor.execute(full_night_req, verdict)
    assert full_night_result.status == ActionStatus.REJECTED
    
    # Attempt unauthorized rebooking
    rebook_req = ActionRequest(
        action_id="rebook_next_available_within_24h",
        booking_reference="WL7742"
    )
    rebook_result = executor.execute(rebook_req, verdict)
    assert rebook_result.status == ActionStatus.REJECTED
    
    # Create escalation for denied/escalated items
    esc_result, esc_packet = executor.create_escalation(verdict, "Meher Kaur")
    assert esc_result.status == ActionStatus.EXECUTED
    assert len(esc_packet.escalation_reasons) >= 2  # Rebooking + fare waiver


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
