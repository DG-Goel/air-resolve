"""
Streamlit UI components for AirResolve operations console.

Presentation only — all decisions come from the backend orchestration layer.
"""

from typing import Optional, Dict, List

import streamlit as st

from ui.helpers import (
    format_case_id,
    format_timestamp,
    get_action_display_name,
    get_audit_event_display,
    get_customer_by_booking,
    get_emotion_display,
    get_fare_waiver_context,
    get_flight_by_booking,
    get_resolution_status_label,
    get_status_label,
    determine_resolution_status,
    extract_denied_items,
    extract_escalation_items,
    extract_requested_actions,
    format_disruption_reason,
    mask_phone,
)
from ui.styles import get_status_color


def render_header(case=None) -> None:
    """Render product header and pipeline banner."""
    status = "Ready for Case Intake"
    if case is not None:
        status = get_status_label(
            case.status.value if hasattr(case.status, "value") else str(case.status)
        )

    st.markdown(
        f"""
        <div class="header-container">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.75rem;">
                <div>
                    <div class="header-title">AirResolve</div>
                    <div class="header-subtitle">Policy-Grounded Airline Resolution Agent</div>
                    <div class="header-subtitle" style="margin-top:0.35rem; font-style:italic;">
                        Understand with AI. Decide with policy. Act with authority. Escalate with context.
                    </div>
                </div>
                <div class="header-status">Console Status: {status}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="pipeline-banner">
            <span class="pipeline-step">UNDERSTAND</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">DECIDE</span>
            <span class="pipeline-arrow">→</span>
            <span class="pipeline-step">ACT / ESCALATE</span>
        </div>
        <div class="simulation-label">Simulation / Assignment Data</div>
        """,
        unsafe_allow_html=True,
    )


def render_customer_profile(booking_ref: Optional[str]) -> None:
    """Render left column customer and PNR panel."""
    st.markdown('<div class="card-header">Customer / PNR</div>', unsafe_allow_html=True)

    if not booking_ref:
        st.info("Load a demo scenario or process a message to view customer context.")
        return

    customer = get_customer_by_booking(booking_ref)
    outbound = get_flight_by_booking(booking_ref, "outbound")
    return_flight = get_flight_by_booking(booking_ref, "return")

    if not customer:
        st.warning("Customer record not found in assignment data.")
        return

    st.markdown(
        f"""
        <div class="info-card">
            <div><strong>Customer:</strong> {customer.get("name", "N/A")}</div>
            <div><strong>Loyalty Tier:</strong> {customer.get("loyalty_tier", "N/A")}</div>
            <div><strong>Booking Reference:</strong> {customer.get("booking_reference", "N/A")}</div>
            <div><strong>Email:</strong> {customer.get("contact", {}).get("email", "N/A")}</div>
            <div><strong>Phone:</strong> {mask_phone(customer.get("contact", {}).get("phone", ""))}</div>
            <div><strong>Flights (12 mo):</strong> {customer.get("travel_history", {}).get("flights_last_12_months", "N/A")}</div>
            <div><strong>Prior Complaints:</strong> {customer.get("travel_history", {}).get("prior_complaints", "N/A")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if outbound:
        status = outbound.get("status", "N/A").replace("_", " ").title()
        departure = outbound.get("scheduled_departure", "N/A")
        if outbound.get("new_departure"):
            departure = f"{departure} → {outbound['new_departure']}"

        st.markdown(
            f"""
            <div class="info-card">
                <div class="card-header" style="margin-top:0;">Affected Flight</div>
                <div><strong>Flight:</strong> {outbound.get("flight", "N/A")}</div>
                <div><strong>Route:</strong> {outbound.get("route", "N/A")}</div>
                <div><strong>Departure:</strong> {departure}</div>
                <div><strong>Status:</strong> <span class="status-badge status-warning">{status}</span></div>
                <div><strong>Disruption Reason:</strong> {format_disruption_reason(outbound)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if return_flight:
        st.markdown(
            f"""
            <div class="info-card return-flight-card">
                <div class="card-header" style="margin-top:0;">Return Flight (Unaffected)</div>
                <div><strong>Flight:</strong> {return_flight.get("flight", "N/A")}</div>
                <div><strong>Route:</strong> {return_flight.get("route", "N/A")}</div>
                <div><strong>Departure:</strong> {return_flight.get("scheduled_departure", "N/A")}</div>
                <div><strong>Status:</strong> <span class="status-badge status-ready">Unaffected</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_conversation(case, message_key: str = "customer_message") -> str:
    """Render center column conversation panel. Returns current message text."""
    st.markdown('<div class="card-header">Conversation</div>', unsafe_allow_html=True)

    if case and case.conversation_history:
        for turn in case.conversation_history:
            if turn.role == "customer":
                st.markdown(
                    f"""
                    <div class="message-customer">
                        <div class="message-label">Customer</div>
                        {turn.message}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            elif turn.role == "agent":
                st.markdown(
                    f"""
                    <div class="message-agent">
                        <div class="message-label">AirResolve</div>
                        {turn.message}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.markdown(
            '<div class="text-muted text-small">No conversation yet. Select a demo scenario or enter a customer message.</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    
    message = st.text_area(
        "Customer Message",
        key=message_key,
        height=120,
        placeholder="Enter customer message or use a demo scenario button below…",
        label_visibility="collapsed",
    )

    return message


def render_demo_buttons() -> Optional[str]:
    """Render quick demo scenario buttons. Returns selected scenario key if clicked."""
    st.markdown('<div class="card-header">Demo Scenarios</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)

    scenario_key = None
    with c1:
        if st.button("Priya — Cancellation + Refund + Upgrade", use_container_width=True):
            scenario_key = "priya"
    with c2:
        if st.button("Arvind — 4h Delay + Hotel", use_container_width=True):
            scenario_key = "arvind"
    with c3:
        if st.button("Meher — 6h Delay + Hotel + Higher-Fare Flight", use_container_width=True):
            scenario_key = "meher"

    return scenario_key


def render_resolution_console(case) -> None:
    """Render right column resolution console."""
    st.markdown('<div class="card-header">Resolution Console</div>', unsafe_allow_html=True)

    if case is None:
        st.info("Resolution details appear after Analyze & Resolve.")
        return

    resolution_status = determine_resolution_status(case)
    status_label = get_resolution_status_label(resolution_status)
    status_color = get_status_color(resolution_status)

    st.markdown(
        f"""
        <div class="info-card">
            <div><strong>Resolution Status</strong></div>
            <div style="margin-top:0.5rem;">
                <span class="status-badge" style="background:{status_color}22;color:{status_color};border:1px solid {status_color};">
                    {status_label}
                </span>
            </div>
            <div class="text-small text-muted" style="margin-top:0.5rem;">
                Case ID: {format_case_id(case.case_id)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    requested = extract_requested_actions(case)
    authorized = list(case.policy_verdict.authorized_actions) if case.policy_verdict else []
    escalations = extract_escalation_items(case)
    denied = extract_denied_items(case)

    st.markdown(
        """
        <div class="requested-vs-authorized">
            <strong>REQUESTED ≠ AUTHORIZED</strong>
            <div class="text-small text-muted">Policy engine is the sole decision authority.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-label requested-label">Requested Actions</div>', unsafe_allow_html=True)
    st.markdown('<div class="text-small text-muted">What the customer asked for.</div>', unsafe_allow_html=True)
    if requested:
        for action in requested:
            st.markdown(
                f'<div class="action-card requested-card"><div class="action-header">{get_action_display_name(action)}</div></div>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("No structured requests extracted yet.")

    st.markdown('<div class="section-label authorized-label">Authorized Actions</div>', unsafe_allow_html=True)
    st.markdown('<div class="text-small text-muted">What the policy engine approved.</div>', unsafe_allow_html=True)
    if authorized:
        for action in authorized:
            executed = any(a.action_id == action and a.status == "EXECUTED" for a in case.executed_actions)
            badge = "Executed" if executed else "Authorized"
            badge_class = "status-authorized" if executed else "status-processing"
            st.markdown(
                f"""
                <div class="action-card authorized-card">
                    <div class="action-header">{get_action_display_name(action)}</div>
                    <span class="status-badge {badge_class}">{badge}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.caption("No actions authorized by policy.")

    st.markdown('<div class="section-label escalated-label">Escalations</div>', unsafe_allow_html=True)
    st.markdown('<div class="text-small text-muted">Requires human / supervisor review.</div>', unsafe_allow_html=True)
    if escalations:
        for reason in escalations:
            st.markdown(
                f'<div class="action-card escalated-card"><div class="action-detail">{reason}</div></div>',
                unsafe_allow_html=True,
            )
    elif denied:
        for action, reason in denied:
            st.markdown(
                f"""
                <div class="action-card denied-card">
                    <div class="action-header">{get_action_display_name(action)} — Denied</div>
                    <div class="action-detail">{reason}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.caption("No escalations required.")

    if case.structured_request and case.structured_request.emotional_state:
        emotion_label, emotion_color = get_emotion_display(case.structured_request.emotional_state)
        st.markdown(
            f'<div class="text-small" style="margin-top:0.75rem;color:{emotion_color};">Detected emotion: {emotion_label} (does not override policy)</div>',
            unsafe_allow_html=True,
        )


def render_policy_authority_panel() -> None:
    """Prominent policy authority callout."""
    st.markdown(
        """
        <div class="policy-panel">
            <div class="policy-title">Decision Source: Deterministic Policy Engine</div>
            <div class="text-small"><strong>LLM Role:</strong> Understand + Communicate</div>
            <div class="text-small"><strong>Authority:</strong> Policy Engine</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_decision_trace(case) -> None:
    """Collapsible decision trace from backend policy evidence."""
    if case is None or case.policy_verdict is None:
        return

    with st.expander("Decision Trace / Policy Evidence", expanded=False):
        render_policy_authority_panel()

        verdict = case.policy_verdict
        grounding_status = (
            case.grounded_request.grounding_status.value
            if case.grounded_request
            else "N/A"
        )

        intents = []
        if case.structured_request and case.structured_request.requested_actions:
            intents = case.structured_request.requested_actions

        st.markdown(f"**Intent:** {', '.join(intents) if intents else 'N/A'}")
        st.markdown(f"**Grounding Status:** {grounding_status}")
        st.markdown(f"**Policy Status:** {verdict.status}")

        if verdict.applicable_policy_rules:
            st.markdown(f"**Applicable Rules:** {', '.join(verdict.applicable_policy_rules[:8])}")

        if verdict.decision_trace and verdict.decision_trace.rules_evaluated:
            st.markdown("**Rule Evaluations**")
            for rule in verdict.decision_trace.rules_evaluated:
                if rule.triggered:
                    st.markdown(
                        f"- **{rule.rule_id}** — {rule.result}: {rule.reason}"
                    )

        if verdict.authorized_actions:
            st.markdown("**Authorized Actions**")
            for action in verdict.authorized_actions:
                st.markdown(f"- {get_action_display_name(action)}")

        if verdict.escalation_reasons:
            st.markdown("**Escalation Reasons**")
            for reason in verdict.escalation_reasons:
                st.markdown(f"- {reason}")

        if verdict.ambiguities_flagged:
            st.markdown("**Policy Ambiguities Flagged**")
            for amb in verdict.ambiguities_flagged:
                st.markdown(f"- {amb}")


def render_audit_journal(service, case) -> None:
    """Action journal / audit trail from backend events."""
    if case is None or service is None:
        return

    with st.expander("Action Journal / Audit Trail", expanded=False):
        events = service.audit_journal.get_case_events(case.case_id)
        if not events:
            st.caption("No audit events recorded for this case.")
            return

        case_created_count = sum(1 for e in events if e.event_type == "CASE_CREATED")
        if case_created_count > 1:
            st.warning(
                f"Backend recorded {case_created_count} CASE_CREATED events for this case. "
                "The orchestration service reuses CASE_CREATED for multiple lifecycle steps."
            )

        for event in events:
            display_label, raw_type = get_audit_event_display(event)
            detail_bits = []
            if event.booking_reference:
                detail_bits.append(f"Booking: {event.booking_reference}")
            if event.action_id:
                detail_bits.append(f"Action: {event.action_id}")
            if event.status:
                detail_bits.append(f"Status: {event.status}")
            details = event.details or {}
            if details.get("customer_name"):
                detail_bits.append(f"Customer: {details['customer_name']}")
            if details.get("grounding_status"):
                detail_bits.append(f"Grounding: {details['grounding_status']}")

            detail_html = " · ".join(detail_bits)
            st.markdown(
                f"""
                <div class="audit-entry">
                    <div class="audit-time">{format_timestamp(event.timestamp)}</div>
                    <div class="audit-event">{display_label}</div>
                    <div class="text-small text-muted">Raw: {raw_type}{(" · " + detail_html) if detail_html else ""}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_human_handoff(case) -> None:
    """Human handoff panel when escalation exists."""
    if case is None or case.escalation is None:
        return

    packet = case.escalation
    fare_ctx = get_fare_waiver_context(case)

    with st.expander("Human Handoff", expanded=True):
        st.markdown(
            f"""
            <div class="info-card escalated-card">
                <div><strong>Case ID:</strong> {format_case_id(packet.case_id)}</div>
                <div><strong>Customer:</strong> {packet.customer_name} ({packet.loyalty_tier})</div>
                <div><strong>Booking:</strong> {packet.booking_reference}</div>
                <div><strong>Priority:</strong> {packet.priority.upper()}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("**Escalation Reasons**")
        for reason in packet.escalation_reasons:
            st.markdown(f"- {reason}")

        if fare_ctx:
            st.markdown(f"**Requested Amount:** ₹{fare_ctx['requested_amount']:,}")
            st.markdown(f"**Policy Limit:** ₹{fare_ctx['policy_limit']:,} (agent authority without supervisor)")

        st.markdown("**Conversation Summary**")
        st.text(packet.conversation_summary)
