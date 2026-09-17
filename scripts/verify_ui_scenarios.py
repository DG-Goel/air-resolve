"""Verify the three mandatory demo scenarios via the orchestration pipeline."""

from actions.executor import ActionExecutor
from audit.journal import AuditJournal
from nlu.grounding import GroundingEngine
from nlu.parser import MockNLUParser
from orchestration.planner import ActionPlanner
from orchestration.responses import ResponseGenerator
from orchestration.service import ResolutionService
from policy.engine import PolicyEngine
from ui.helpers import DATA_DIR, load_scenario_data


def build_service() -> ResolutionService:
    return ResolutionService(
        nlu_parser=MockNLUParser(),
        grounding_engine=GroundingEngine(data_dir=DATA_DIR),
        policy_engine=PolicyEngine(data_dir=DATA_DIR),
        action_executor=ActionExecutor(),
        action_planner=ActionPlanner(),
        response_generator=ResponseGenerator(),
        audit_journal=AuditJournal(),
    )


def main() -> None:
    service = build_service()
    scenarios = load_scenario_data()
    checks = []

    # Priya
    priya = scenarios["priya"]
    # Include booking and flight reference in message for proper parsing
    priya_message = f"My booking is {priya['booking_reference']} on flight {priya['flight']}. {priya['initial_message']}"
    case = service.process_message(
        priya_message,
        scenario_disruption_cause=priya["scenario_disruption_cause"],
    )
    
    if not case.policy_verdict:
        print(f"ERROR: Priya - No policy verdict. Status: {case.status}, Error: {case.error_message}")
        print(f"Grounding status: {case.grounded_request.grounding_status if case.grounded_request else 'None'}")
        checks.append(("Priya refund authorized", False))
        checks.append(("Priya upgrade escalated", False))
        checks.append(("Priya refund executed", False))
    else:
        v = case.policy_verdict
        checks.append(("Priya refund authorized", "initiate_refund_to_original_payment_method" in v.authorized_actions))
        checks.append(("Priya upgrade escalated", v.escalation_required and "business_class_upgrade" in v.denied_actions))
        checks.append(("Priya refund executed", any(a.action_id == "initiate_refund_to_original_payment_method" and a.status == "EXECUTED" for a in case.executed_actions)))

    # Arvind
    arvind = scenarios["arvind"]
    arvind_message = f"My booking is {arvind['booking_reference']} on flight {arvind['flight']}. {arvind['initial_message']}"
    case = service.process_message(
        arvind_message,
        scenario_disruption_cause=arvind["scenario_disruption_cause"],
    )
    
    if not case.policy_verdict:
        print(f"ERROR: Arvind - No policy verdict. Status: {case.status}, Error: {case.error_message}")
        print(f"Grounding status: {case.grounded_request.grounding_status if case.grounded_request else 'None'}")
        checks.append(("Arvind meal voucher", False))
        checks.append(("Arvind lounge", False))
        checks.append(("Arvind hotel denied", False))
        checks.append(("Arvind no escalation", False))
    else:
        v = case.policy_verdict
        checks.append(("Arvind meal voucher", "issue_meal_voucher_500" in v.authorized_actions))
        checks.append(("Arvind lounge", "provide_lounge_access" in v.authorized_actions))
        checks.append(("Arvind hotel denied", not any("hotel" in a for a in v.authorized_actions)))
        checks.append(("Arvind no escalation", not v.escalation_required))

    # Meher
    meher = scenarios["meher"]
    meher_message = f"My booking is {meher['booking_reference']} on flight {meher['flight']}. {meher['initial_message']}"
    case = service.process_message(
        meher_message,
        scenario_disruption_cause=meher["scenario_disruption_cause"],
    )
    
    if not case.policy_verdict:
        print(f"ERROR: Meher - No policy verdict. Status: {case.status}, Error: {case.error_message}")
        print(f"Grounding status: {case.grounded_request.grounding_status if case.grounded_request else 'None'}")
        checks.append(("Meher meal voucher", False))
        checks.append(("Meher delayed-hours hotel", False))
        checks.append(("Meher escalation", False))
        checks.append(("Meher fare waiver escalated", False))
    else:
        v = case.policy_verdict
        checks.append(("Meher meal voucher", "issue_meal_voucher_500" in v.authorized_actions))
        checks.append(("Meher delayed-hours hotel", "arrange_hotel_accommodation_delayed_hours" in v.authorized_actions))
        checks.append(("Meher escalation", v.escalation_required))
        checks.append(("Meher fare waiver escalated", any("fare" in r.lower() or "1500" in r or "2000" in r for r in v.escalation_reasons)))

    print("Scenario Verification")
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
