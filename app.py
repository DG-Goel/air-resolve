"""
AirResolve Operations Console — Streamlit UI.

Thin presentation layer over the existing orchestration pipeline.
The UI never makes policy decisions; it delegates to ResolutionService.
"""

import streamlit as st

from actions.executor import ActionExecutor
from audit.journal import AuditJournal
from nlu.grounding import GroundingEngine
from nlu.parser import MockNLUParser
from orchestration.planner import ActionPlanner
from orchestration.responses import ResponseGenerator
from orchestration.service import ResolutionService
from policy.engine import PolicyEngine
from ui.components import (
    render_audit_journal,
    render_conversation,
    render_customer_profile,
    render_decision_trace,
    render_demo_buttons,
    render_header,
    render_human_handoff,
    render_policy_authority_panel,
    render_resolution_console,
)
from ui.helpers import DATA_DIR, load_scenario_data
from ui.styles import get_custom_css


def _build_service() -> ResolutionService:
    """Initialize the backend orchestration service (single pipeline entry point)."""
    return ResolutionService(
        nlu_parser=MockNLUParser(),
        grounding_engine=GroundingEngine(data_dir=DATA_DIR),
        policy_engine=PolicyEngine(data_dir=DATA_DIR),
        action_executor=ActionExecutor(),
        action_planner=ActionPlanner(),
        response_generator=ResponseGenerator(),
        audit_journal=AuditJournal(),
    )


def _init_session_state() -> None:
    if "service" not in st.session_state:
        st.session_state.service = _build_service()
    if "case" not in st.session_state:
        st.session_state.case = None
    if "active_booking_ref" not in st.session_state:
        st.session_state.active_booking_ref = None
    if "scenario_disruption_cause" not in st.session_state:
        st.session_state.scenario_disruption_cause = None
    if "active_scenario" not in st.session_state:
        st.session_state.active_scenario = None
    if "customer_message" not in st.session_state:
        st.session_state.customer_message = ""
    
    # Handle pending scenario message before widgets are created
    if "scenario_message_pending" in st.session_state:
        st.session_state.customer_message = st.session_state.scenario_message_pending
        del st.session_state.scenario_message_pending



def _load_scenario(scenario_key: str) -> None:
    """Load demo scenario metadata and prefill message (does not execute pipeline)."""
    scenarios = load_scenario_data()
    scenario = scenarios.get(scenario_key)
    if not scenario:
        return

    st.session_state.active_scenario = scenario_key
    st.session_state.active_booking_ref = scenario["booking_reference"]
    st.session_state.scenario_disruption_cause = scenario["scenario_disruption_cause"]
    # Store the message to be loaded on next rerun (before widget is created)
    st.session_state.scenario_message_pending = scenario["initial_message"]
    st.session_state.case = None


def _process_message(message: str) -> None:
    """
    Run the existing orchestration pipeline once.

    NLU → Grounding → Policy → Planner → Executor → Audit → Response
    """
    message = (message or "").strip()
    if not message:
        st.warning("Enter a customer message before analyzing.")
        return

    service: ResolutionService = st.session_state.service
    existing_case = st.session_state.case
    scenario_cause = st.session_state.scenario_disruption_cause

    # If we have active scenario metadata, prepend booking/flight info to message
    # This helps NLU extract references correctly
    if st.session_state.active_booking_ref and st.session_state.active_scenario:
        scenarios = load_scenario_data()
        scenario = scenarios.get(st.session_state.active_scenario)
        if scenario:
            # Prepend booking and flight reference for better NLU extraction
            message = f"My booking is {scenario['booking_reference']} on flight {scenario['flight']}. {message}"

    case = service.process_message(
        message,
        case=existing_case,
        scenario_disruption_cause=scenario_cause,
    )

    st.session_state.case = case
    if case.booking_reference:
        st.session_state.active_booking_ref = case.booking_reference


def main() -> None:
    st.set_page_config(
        page_title="AirResolve — Operations Console",
        page_icon="✈",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    st.markdown(get_custom_css(), unsafe_allow_html=True)
    _init_session_state()

    case = st.session_state.case
    render_header(case)

    left_col, center_col, right_col = st.columns([1, 1.4, 1.2], gap="medium")

    with left_col:
        render_customer_profile(st.session_state.active_booking_ref)

    with center_col:
        message = render_conversation(case, message_key="customer_message")

        st.markdown('<div class="review-resolve-btn">', unsafe_allow_html=True)
        analyze = st.button("REVIEW & RESOLVE", type="primary", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
        st.caption("Runs NLU → Grounding → Policy → Planner → Executor → Audit → Response")

        scenario_key = render_demo_buttons()

        if scenario_key:
            _load_scenario(scenario_key)
            st.rerun()

        if analyze:
            _process_message(message)
            st.rerun()

    with right_col:
        render_resolution_console(st.session_state.case)

    st.markdown("---")
    render_policy_authority_panel()
    render_decision_trace(st.session_state.case)
    render_audit_journal(st.session_state.service, st.session_state.case)
    render_human_handoff(st.session_state.case)


if __name__ == "__main__":
    main()
