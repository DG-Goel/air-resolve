"""
Orchestration layer for AirResolve.

The orchestration layer coordinates components into a complete customer-facing workflow:
    Natural Language Message
        ↓
    NLU Parser (language understanding)
        ↓
    Grounding Engine (fact verification)
        ↓
    Policy Engine (decision making - SOLE AUTHORITY)
        ↓
    Action Planner (preparation)
        ↓
    Action Executor (execution with authorization firewall)
        ↓
    Audit Journal (recording)
        ↓
    Response Generator (communication)
        ↓
    Customer Response

CRITICAL: The orchestration layer COORDINATES components.
It does NOT make policy decisions or duplicate component logic.
"""

from orchestration.models import (
    ConversationTurn,
    ResolutionCase,
    CaseStatus,
    PlannedAction
)
from orchestration.service import ResolutionService
from orchestration.planner import ActionPlanner
from orchestration.responses import ResponseGenerator

__all__ = [
    "ConversationTurn",
    "ResolutionCase",
    "CaseStatus",
    "PlannedAction",
    "ResolutionService",
    "ActionPlanner",
    "ResponseGenerator"
]
