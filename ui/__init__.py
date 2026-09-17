"""
UI helper modules for AirResolve operations console.

This package contains UI components, styles, and helpers
that keep presentation logic separate from business logic.
"""

from ui.components import *
from ui.styles import *
from ui.helpers import *

__all__ = [
    "render_header",
    "render_customer_profile",
    "render_conversation",
    "render_resolution_console",
    "render_decision_trace",
    "render_audit_journal",
    "get_custom_css",
    "get_status_color",
    "format_case_id",
    "load_scenario_data",
]
