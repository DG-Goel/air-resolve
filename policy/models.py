"""
Data models for AirResolve policy engine.

These models define the structure of inputs and outputs for the deterministic
policy engine. The engine does NOT use LLMs for decision-making.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class CustomerData(BaseModel):
    """Customer information from customers.json."""
    name: str
    loyalty_tier: Literal["Silver", "Gold", "Platinum"]
    booking_reference: str
    contact: Dict[str, str]
    travel_history: Dict[str, int]


class BookingData(BaseModel):
    """Booking information from bookings.json."""
    customer: str
    booking_reference: str
    flight: str
    route: str
    date: str
    scheduled_departure: str
    status: Literal["cancelled", "delayed", "unaffected"]
    cause: Optional[str] = None
    delay_hours: Optional[float] = None
    new_departure: Optional[str] = None


class StructuredRequest(BaseModel):
    """
    Parsed customer request.
    
    This will eventually come from an NLU module, but for now is constructed
    directly for testing the policy engine.
    """
    booking_reference: str
    requested_actions: List[str] = Field(
        description="List of action identifiers requested by customer"
    )
    customer_emotion: Literal["neutral", "frustrated", "angry", "furious"] = "neutral"
    escalation_intents: List[Literal["legal_threat", "formal_complaint"]] = Field(
        default_factory=list,
        description="Separate from emotion - explicit escalation triggers"
    )
    fare_difference: Optional[int] = Field(
        None,
        description="Fare difference in ₹ if requesting alternate higher-fare flight"
    )
    alternate_flight: Optional[str] = Field(
        None,
        description="Flight identifier if requesting specific alternate"
    )
    refund_to_different_payment_method: bool = Field(
        False,
        description="True if customer requests refund to non-original payment method"
    )
    disruption_cause: Optional[Literal["airline_operational", "weather", "passenger", "other"]] = Field(
        None,
        description="Known cause of disruption from scenario/context. If None, cause is unknown."
    )


class RuleEvaluation(BaseModel):
    """Record of a single rule evaluation."""
    rule_id: str
    rule_description: str
    triggered: bool
    result: Literal["authorized", "denied", "escalated", "not_applicable", "unspecified"]
    reason: str


class DecisionTrace(BaseModel):
    """
    Audit trail for policy evaluation.
    
    Enables complete reproduction of verdict from inputs.
    Does not include timestamp in equality comparison to maintain determinism.
    """
    booking_reference: str
    input_values: Dict[str, Any]
    rules_evaluated: List[RuleEvaluation]
    intermediate_calculations: Dict[str, Any] = Field(default_factory=dict)


class PolicyVerdict(BaseModel):
    """
    Deterministic policy engine output.
    
    Status indicates overall verdict type:
    - AUTHORIZED: All requested actions authorized
    - DENIED: Some actions denied but no escalation needed
    - ESCALATION_REQUIRED: Human supervisor required
    - POLICY_UNSPECIFIED: Decision depends on unresolved ambiguity
    - ERROR: Invalid input or missing required data
    """
    status: Literal["AUTHORIZED", "DENIED", "ESCALATION_REQUIRED", "POLICY_UNSPECIFIED", "ERROR"]
    
    # Eligibility (what customer qualifies for per Assignment 3 Data Pack)
    eligible_compensations: List[str] = Field(default_factory=list)
    customer_choice: Optional[str] = Field(
        None,
        description="If customer must choose between options (e.g., rebooking vs refund)"
    )
    
    # Actions
    authorized_actions: List[str] = Field(default_factory=list)
    denied_actions: List[str] = Field(default_factory=list)
    denial_reasons: Dict[str, str] = Field(default_factory=dict)
    
    # Escalation
    escalation_required: bool = False
    escalation_reasons: List[str] = Field(default_factory=list)
    authority_limit_exceeded: bool = False
    
    # Traceability
    applicable_policy_rules: List[str] = Field(default_factory=list)
    ambiguities_flagged: List[str] = Field(default_factory=list)
    project_decisions_applied: List[str] = Field(default_factory=list)
    decision_trace: Optional[DecisionTrace] = None
    
    # Loyalty
    loyalty_tier: Optional[str] = None
    priority_rebooking: bool = False
    
    # Compensation Details
    meal_voucher_amount: Optional[int] = None
    hotel_accommodation_hours: Optional[float] = None
    refund_processing_days: Optional[int] = None
    refund_destination: Optional[str] = None
    
    # Error handling
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    required_field: Optional[str] = None

    def __eq__(self, other):
        """
        Equality comparison for determinism testing.
        
        Two verdicts are equal if all fields except decision_trace match.
        Decision trace is compared separately to allow trace comparison.
        """
        if not isinstance(other, PolicyVerdict):
            return False
        
        # Compare all fields except decision_trace
        return (
            self.status == other.status
            and self.eligible_compensations == other.eligible_compensations
            and self.customer_choice == other.customer_choice
            and self.authorized_actions == other.authorized_actions
            and self.denied_actions == other.denied_actions
            and self.denial_reasons == other.denial_reasons
            and self.escalation_required == other.escalation_required
            and self.escalation_reasons == other.escalation_reasons
            and self.authority_limit_exceeded == other.authority_limit_exceeded
            and self.applicable_policy_rules == other.applicable_policy_rules
            and self.ambiguities_flagged == other.ambiguities_flagged
            and self.project_decisions_applied == other.project_decisions_applied
            and self.loyalty_tier == other.loyalty_tier
            and self.priority_rebooking == other.priority_rebooking
            and self.meal_voucher_amount == other.meal_voucher_amount
            and self.hotel_accommodation_hours == other.hotel_accommodation_hours
            and self.refund_processing_days == other.refund_processing_days
            and self.refund_destination == other.refund_destination
            and self.error_type == other.error_type
            and self.error_message == other.error_message
            and self.required_field == other.required_field
        )
