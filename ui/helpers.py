"""
Helper functions for AirResolve UI.

These functions assist with data loading, formatting, and UI logic
without duplicating business logic from the backend.
"""

import json
import os
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from orchestration.models import CaseStatus

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")


def format_case_id(case_id: str) -> str:
    """Format case ID for display."""
    if not case_id:
        return "N/A"
    # Take first 8 characters for compact display
    short_id = case_id[:8].upper()
    return f"AR-{short_id}"


def load_customers() -> List[Dict]:
    """Load customer data from assignment data file."""
    try:
        with open(os.path.join(DATA_DIR, "customers.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading customers: {e}")
        return []


def load_bookings() -> List[Dict]:
    """Load booking data from assignment data file."""
    try:
        with open(os.path.join(DATA_DIR, "bookings.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading bookings: {e}")
        return []


def get_customer_by_booking(booking_ref: str) -> Optional[Dict]:
    """Get customer data by booking reference."""
    customers = load_customers()
    for customer in customers:
        if customer.get("booking_reference") == booking_ref:
            return customer
    return None


def get_flight_by_booking(booking_ref: str, flight_type: str = "outbound") -> Optional[Dict]:
    """
    Get flight data by booking reference.
    
    Args:
        booking_ref: Booking reference
        flight_type: "outbound" or "return"
    """
    bookings = load_bookings()
    for booking in bookings:
        if booking.get("booking_reference") == booking_ref:
            if flight_type == "return" and booking.get("flight") == "return":
                return booking
            elif flight_type == "outbound" and booking.get("flight") != "return":
                return booking
    return None


def load_scenario_data() -> Dict[str, Dict]:
    """
    Load the three mandatory assignment scenarios.
    
    Returns dict with scenario metadata and initial messages.
    """
    scenarios = {
        "priya": {
            "name": "Priya Nair",
            "booking_reference": "SK4821X",
            "flight": "SK-204",
            "route": "Delhi → Goa",
            "date": "23 September 2026",
            "status": "Cancelled",
            "cause": "Airline operational",
            "initial_message": "I'm furious about this cancellation. I want a full cash refund and a free business-class upgrade on my return because of all this trouble.",
            "scenario_disruption_cause": "airline_operational"
        },
        "arvind": {
            "name": "Arvind Kulkarni",
            "booking_reference": "TR1190B",
            "flight": "SK-118",
            "route": "Mumbai → Bengaluru",
            "date": "23 September 2026",
            "status": "Delayed 4 hours",
            "cause": "Airline operational",
            "initial_message": "This four-hour delay is going to make me miss my connecting meeting. I need a hotel.",
            "scenario_disruption_cause": "airline_operational"
        },
        "meher": {
            "name": "Meher Kaur",
            "booking_reference": "WL7742",
            "flight": "SK-305",
            "route": "Delhi → Hyderabad",
            "date": "23 September 2026",
            "status": "Delayed 6 hours",
            "cause": "Airline operational",
            "initial_message": "I want a full-night hotel, not just a few hours. Also put me on a different higher-fare flight and waive the ₹2,000 difference.",
            "scenario_disruption_cause": "airline_operational"
        }
    }
    return scenarios


def get_scenario_summary(scenario_key: str) -> str:
    """Get short summary for scenario selector."""
    scenarios = load_scenario_data()
    scenario = scenarios.get(scenario_key, {})
    
    name = scenario.get("name", "")
    status = scenario.get("status", "")
    
    return f"{name} — {status}"


def format_timestamp(dt: Optional[datetime]) -> str:
    """Format datetime for display."""
    if not dt:
        return ""
    return dt.strftime("%H:%M:%S")


def get_status_label(case_status: str) -> str:
    """Get human-readable status label."""
    status_labels = {
        "RECEIVED": "Received",
        "GROUNDING_REQUIRED": "Verifying",
        "POLICY_EVALUATED": "Policy Evaluated",
        "ACTIONS_EXECUTED": "Actions Executed",
        "ESCALATED": "Escalation Required",
        "RESOLVED": "Resolved",
        "ERROR": "Error"
    }
    return status_labels.get(case_status, case_status)


def determine_resolution_status(case) -> str:
    """
    Determine overall resolution status from case.

    Returns UI status codes aligned with the operations console.
    """
    status = case.status.value if isinstance(case.status, CaseStatus) else str(case.status)

    if status == CaseStatus.ERROR.value:
        if case.error_type and "grounding" in case.error_type.lower():
            return "GROUNDING_FAILED"
        return "ERROR"

    if not case.policy_verdict:
        if case.grounded_request and case.grounded_request.grounding_status.value != "VERIFIED":
            return "GROUNDING_FAILED"
        return "PROCESSING"

    if case.policy_verdict.status == "POLICY_UNSPECIFIED":
        return "POLICY_UNSPECIFIED"

    has_escalation = case.escalation is not None or case.policy_verdict.escalation_required
    has_executed = any(a.status == "EXECUTED" for a in case.executed_actions)

    if has_escalation and has_executed:
        return "PARTIALLY_RESOLVED"
    if has_escalation:
        return "ESCALATION_REQUIRED"
    if has_executed or status in {CaseStatus.RESOLVED.value, CaseStatus.ACTIONS_EXECUTED.value}:
        return "COMPLETED" if not has_escalation else "AUTHORIZED"
    if case.policy_verdict.authorized_actions and not has_executed:
        return "AUTHORIZED"
    return "PROCESSING"


def get_resolution_status_label(status_code: str) -> str:
    """Human-readable resolution status label."""
    labels = {
        "AUTHORIZED": "Authorized",
        "PARTIALLY_RESOLVED": "Partially Resolved",
        "ESCALATION_REQUIRED": "Escalation Required",
        "POLICY_UNSPECIFIED": "Policy Unspecified",
        "GROUNDING_FAILED": "Grounding Failed",
        "COMPLETED": "Completed",
        "PROCESSING": "Processing",
        "ERROR": "Error",
    }
    return labels.get(status_code, status_code.replace("_", " ").title())


def get_audit_event_display(event) -> Tuple[str, str]:
    """
    Derive a semantic label for audit events while preserving raw event type.

    Backend reuses CASE_CREATED for multiple lifecycle steps; surface that clearly.
    """
    details = event.details or {}
    if event.event_type == "CASE_CREATED":
        if details.get("grounding_status"):
            return "Grounding Failed", event.event_type
        if details.get("customer_name"):
            return "Customer Identified", event.event_type
        if details.get("error_type"):
            return "Processing Error", event.event_type
        return "Case Created", event.event_type
    if event.event_type == "POLICY_EVALUATED":
        return "Policy Evaluated", event.event_type
    if event.event_type == "ACTION_EXECUTED":
        return "Action Executed", event.event_type
    if event.event_type == "ACTION_REJECTED":
        return "Action Rejected", event.event_type
    if event.event_type == "ESCALATION_CREATED":
        return "Escalation Created", event.event_type
    return event.event_type.replace("_", " ").title(), event.event_type


def extract_escalation_items(case) -> List[str]:
    """Escalation reasons from policy verdict (no UI invention)."""
    if not case.policy_verdict:
        return []
    return list(case.policy_verdict.escalation_reasons or [])


def extract_denied_items(case) -> List[Tuple[str, str]]:
    """Denied actions with policy reasons."""
    if not case.policy_verdict:
        return []
    return [
        (action, case.policy_verdict.denial_reasons.get(action, ""))
        for action in case.policy_verdict.denied_actions
    ]


def get_fare_waiver_context(case) -> Dict[str, Any]:
    """Extract fare waiver context from structured request when present."""
    if not case.structured_request:
        return {}
    amount = case.structured_request.requested_fare_difference
    if amount is None:
        return {}
    return {"requested_amount": amount, "policy_limit": 1500}


def format_disruption_reason(booking: Optional[Dict]) -> str:
    """Format disruption reason from assignment booking data only."""
    if not booking:
        return "N/A"
    if booking.get("cause"):
        return booking["cause"].replace("_", " ").title()
    if booking.get("status") == "delayed":
        return "Delay (cause not specified in assignment data)"
    return "N/A"


def extract_requested_actions(case) -> List[str]:
    """Extract requested actions from case."""
    if not case.structured_request:
        return []
    
    actions = case.structured_request.requested_actions or []
    
    # Add class upgrade if specified
    if case.structured_request.class_upgrade_requested:
        if "business_class_upgrade" not in actions:
            actions.append("business_class_upgrade")
    
    # Add hotel with scope if specified
    if case.structured_request.hotel_scope_requested:
        if "hotel" in actions or "full_night_hotel" in actions:
            pass  # Already there
        else:
            actions.append("hotel")
    
    return actions


def get_action_display_name(action_id: str) -> str:
    """Get human-readable action name."""
    action_names = {
        "initiate_refund_to_original_payment_method": "Full Refund",
        "issue_meal_voucher_500": "Meal Voucher ₹500",
        "provide_lounge_access": "Lounge Access",
        "arrange_hotel_accommodation_delayed_hours": "Hotel Accommodation (Delayed Hours)",
        "rebook_next_available_within_24h": "Rebooking",
        "business_class_upgrade": "Business Class Upgrade",
        "full_night_hotel": "Full-Night Hotel",
        "hotel": "Hotel Accommodation",
        "refund": "Refund",
        "rebooking": "Rebooking",
        "meal_voucher": "Meal Voucher",
        "lounge_access": "Lounge Access",
        "lounge": "Lounge Access",
        "fare_waiver": "Fare Difference Waiver"
    }
    return action_names.get(action_id, action_id.replace("_", " ").title())


def get_emotion_display(emotion: Optional[str]) -> Tuple[str, str]:
    """
    Get emotion display label and color.
    
    Returns: (label, color)
    """
    if not emotion:
        return ("Neutral", "#718096")
    
    emotion_map = {
        "furious": ("Highly Frustrated", "#e53e3e"),
        "angry": ("Frustrated", "#ed8936"),
        "frustrated": ("Frustrated", "#ed8936"),
        "neutral": ("Neutral", "#718096")
    }
    
    return emotion_map.get(emotion.lower(), ("Neutral", "#718096"))


def mask_phone(phone: str) -> str:
    """Ensure phone is properly masked."""
    if not phone:
        return "N/A"
    
    # Phone should already be masked in data, but double-check
    if "xxx" in phone:
        return phone
    
    # If not masked, mask it
    if len(phone) > 6:
        return phone[:6] + "xxx" + phone[-1:]
    
    return phone
