"""
Data models for orchestration layer.

These models represent the customer-facing resolution workflow state.
"""

from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import uuid

from nlu.models import UntrustedStructuredRequest, GroundedRequest
from policy.models import PolicyVerdict
from actions.models import ActionResult, HumanHandoffPacket


class CaseStatus(str, Enum):
    """Resolution case status."""
    RECEIVED = "RECEIVED"  # Customer message received
    GROUNDING_REQUIRED = "GROUNDING_REQUIRED"  # Needs reference verification
    POLICY_EVALUATED = "POLICY_EVALUATED"  # Policy decision made
    ACTIONS_EXECUTED = "ACTIONS_EXECUTED"  # Actions completed
    ESCALATED = "ESCALATED"  # Requires human review
    RESOLVED = "RESOLVED"  # Case fully resolved
    ERROR = "ERROR"  # Processing error


class ConversationTurn(BaseModel):
    """
    Single turn in customer-agent conversation.
    
    Captures one exchange in the conversation history.
    """
    turn_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique turn identifier"
    )
    role: Literal["customer", "agent", "system"] = Field(
        description="Who is speaking"
    )
    message: str = Field(
        description="Message content"
    )
    timestamp: Optional[datetime] = Field(
        default_factory=datetime.now,
        description="When this turn occurred"
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID for audit trail"
    )


class PlannedAction(BaseModel):
    """
    Planned action from policy verdict.
    
    Represents an action that should be executed or escalated.
    """
    action_id: str
    action_type: Literal["EXECUTE", "ESCALATE", "DENY"]
    reason: Optional[str] = None


class ResolutionCase(BaseModel):
    """
    Complete resolution case with full workflow state.
    
    This is the primary orchestration data structure.
    It captures the entire customer interaction and resolution flow.
    """
    # Case identification
    case_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique case identifier"
    )
    
    # Customer context (verified after grounding)
    customer_name: Optional[str] = None
    booking_reference: Optional[str] = None
    loyalty_tier: Optional[str] = None
    
    # Conversation
    conversation_history: List[ConversationTurn] = Field(
        default_factory=list,
        description="Full conversation history"
    )
    current_customer_message: Optional[str] = None
    
    # NLU Layer (UNTRUSTED)
    structured_request: Optional[UntrustedStructuredRequest] = None
    
    # Grounding Layer (VERIFICATION)
    grounded_request: Optional[GroundedRequest] = None
    grounding_warnings: List[str] = Field(
        default_factory=list,
        description="Issues found during grounding"
    )
    
    # Policy Layer (DECISION - SOLE AUTHORITY)
    policy_verdict: Optional[PolicyVerdict] = None
    
    # Action Layer (EXECUTION)
    planned_actions: List[PlannedAction] = Field(
        default_factory=list,
        description="Actions planned from policy verdict"
    )
    executed_actions: List[ActionResult] = Field(
        default_factory=list,
        description="Actions successfully executed"
    )
    rejected_actions: List[ActionResult] = Field(
        default_factory=list,
        description="Actions rejected by authorization firewall"
    )
    
    # Escalation
    escalation: Optional[HumanHandoffPacket] = None
    
    # Response
    response: Optional[str] = None
    
    # Status tracking
    status: CaseStatus = Field(
        default=CaseStatus.RECEIVED,
        description="Current case status"
    )
    
    # Error handling
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    correlation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Correlation ID for audit trail"
    )
    
    def add_customer_message(self, message: str) -> None:
        """Add customer message to conversation."""
        turn = ConversationTurn(
            role="customer",
            message=message,
            correlation_id=self.correlation_id
        )
        self.conversation_history.append(turn)
        self.current_customer_message = message
        self.updated_at = datetime.now()
    
    def add_agent_response(self, response: str) -> None:
        """Add agent response to conversation."""
        turn = ConversationTurn(
            role="agent",
            message=response,
            correlation_id=self.correlation_id
        )
        self.conversation_history.append(turn)
        self.response = response
        self.updated_at = datetime.now()
    
    def add_system_message(self, message: str) -> None:
        """Add system message to conversation."""
        turn = ConversationTurn(
            role="system",
            message=message,
            correlation_id=self.correlation_id
        )
        self.conversation_history.append(turn)
        self.updated_at = datetime.now()
