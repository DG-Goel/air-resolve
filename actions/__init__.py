"""
Action execution layer for AirResolve.

CRITICAL ARCHITECTURAL PRINCIPLE:
The action layer MUST NOT make policy decisions.
It may ONLY execute actions explicitly authorized by PolicyVerdict.

Architecture:
    Policy Engine → PolicyVerdict → Action Layer → Execution

NOT:
    LLM → Action
    UI → Action
    Customer Request → Action

The authorization firewall ensures no action executes without
explicit authorization from the deterministic policy engine.
"""

from actions.models import (
    ActionRequest,
    ActionResult,
    ActionStatus,
    HumanHandoffPacket
)
from actions.executor import ActionExecutor

__all__ = [
    "ActionRequest",
    "ActionResult",
    "ActionStatus",
    "HumanHandoffPacket",
    "ActionExecutor"
]
