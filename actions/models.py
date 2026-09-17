"""
Data models for action execution layer.

These models define the structure for action requests, results,
and human escalation handoff packets.
"""

from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class ActionStatus:
    """Action execution status constants."""
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    ALREADY_EXECUTED = "ALREADY_EXECUTED"


class ActionRequest(BaseModel):
    """
    Request to execute a specific action.
    
    The action_id must match an authorized action from PolicyVerdict.
    """
    action_id: str = Field(
        description="Action identifier (must be in PolicyVerdict.authorized_actions)"
    )
    booking_reference: str = Field(
        description="Booking reference for this action"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Action-specific parameters"
    )
    requested_by: str = Field(
        default="agent",
        description="Who/what requested this action (agent, system, supervisor)"
    )
    correlation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique ID for idempotency and audit correlation"
    )


class ActionResult(BaseModel):
    """
    Result of action execution attempt.
    
    Status indicates whether the action was executed, rejected, or failed.
    """
    action_id: str
    status: Literal["EXECUTED", "REJECTED", "FAILED", "ALREADY_EXECUTED"]
    booking_reference: str
    message: str
    executed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    correlation_id: Optional[str] = None


class HumanHandoffPacket(BaseModel):
    """
    Structured packet for human supervisor escalation.
    
    Contains all information needed for a supervisor to understand
    the case without rereading the entire conversation.
    """
    case_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique escalation case identifier"
    )
    booking_reference: str
    customer_name: str
    loyalty_tier: str
    
    # Disruption context
    disruption_status: str  # cancelled, delayed, etc.
    disruption_cause: Optional[str]
    delay_hours: Optional[float]
    
    # Request and policy outcome
    requested_actions: List[str]
    authorized_actions: List[str]
    denied_actions: List[str]
    escalation_reasons: List[str]
    
    # Policy trace
    applicable_policy_rules: List[str]
    ambiguities_flagged: List[str]
    
    # Conversation summary (deterministic generation for now, no LLM)
    conversation_summary: str = Field(
        description="Summary of customer interaction (deterministic for prototype)"
    )
    
    created_at: datetime = Field(default_factory=datetime.now)
    priority: Literal["low", "medium", "high", "urgent"] = "medium"

