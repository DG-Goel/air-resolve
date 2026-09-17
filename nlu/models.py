"""
Data models for NLU layer.

These models enforce the architectural boundary between:
- UNTRUSTED customer language extraction (LLM output)
- VERIFIED facts (grounding output)
- POLICY DECISIONS (policy engine output)
"""

from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

from policy.models import StructuredRequest


class CustomerIntent(str, Enum):
    """
    Controlled vocabulary for customer intents.
    
    DO NOT add arbitrary intents. Each intent must map to Assignment 3 Data Pack
    policies or established escalation triggers.
    """
    REFUND_REQUEST = "refund_request"
    REBOOKING_REQUEST = "rebooking_request"
    MEAL_VOUCHER_REQUEST = "meal_voucher_request"
    LOUNGE_REQUEST = "lounge_request"
    HOTEL_REQUEST = "hotel_request"
    FARE_CHANGE_REQUEST = "fare_change_request"
    CLASS_UPGRADE_REQUEST = "class_upgrade_request"
    STATUS_QUESTION = "status_question"
    COMPLAINT_OR_LEGAL_ESCALATION = "complaint_or_legal_escalation"
    MULTIPLE_REQUEST = "multiple_request"
    UNKNOWN = "unknown"


class GroundingStatus(str, Enum):
    """Status of grounding verification."""
    VERIFIED = "VERIFIED"  # All references verified against authoritative data
    UNRESOLVED = "UNRESOLVED"  # Unknown customer/booking reference
    MISMATCH = "MISMATCH"  # Reference exists but doesn't match (e.g., booking belongs to different customer)
    INCOMPLETE = "INCOMPLETE"  # Missing required references
    ERROR = "ERROR"  # Grounding process error


class UntrustedStructuredRequest(BaseModel):
    """
    UNTRUSTED extraction from customer natural language.
    
    This represents ONLY what the customer appears to be asking for.
    It is UNTRUSTED until grounding verifies references.
    
    CRITICAL: The LLM must NEVER invent:
    - Customer data (name, tier, contact)
    - Booking data (status, flights, dates)
    - Flight data (delays, cancellations, causes)
    - Disruption causes
    - Delay hours
    - Loyalty tiers
    - Entitlements
    - Compensation amounts (except customer-requested amounts)
    - Policy decisions
    
    The LLM may extract:
    - Customer name (if mentioned)
    - Booking reference (if mentioned)
    - Flight reference (if mentioned)
    - What the customer is requesting
    - Customer emotions
    - Legal threats or complaint language
    - Amounts customer mentions (e.g., "₹2,000 more")
    """
    
    # References (may be missing, misspelled, or wrong)
    customer_name: Optional[str] = Field(
        None,
        description="Customer name if mentioned in message"
    )
    booking_reference: Optional[str] = Field(
        None,
        description="Booking reference if mentioned in message"
    )
    flight_reference: Optional[str] = Field(
        None,
        description="Flight number/reference if mentioned in message"
    )
    
    # Customer intent and requests
    intent: CustomerIntent = Field(
        CustomerIntent.UNKNOWN,
        description="Primary customer intent from controlled vocabulary"
    )
    requested_actions: List[str] = Field(
        default_factory=list,
        description="List of actions customer appears to be requesting"
    )
    
    # Customer-mentioned amounts (NOT verified facts)
    requested_amount: Optional[float] = Field(
        None,
        description="Amount customer mentions wanting (e.g., refund amount)"
    )
    requested_fare_difference: Optional[float] = Field(
        None,
        description="Fare difference customer mentions for alternate flight"
    )
    
    # Scope qualifiers
    hotel_scope_requested: Optional[str] = Field(
        None,
        description="Hotel scope if specified: 'delayed_hours', 'full_night', etc."
    )
    class_upgrade_requested: Optional[str] = Field(
        None,
        description="Class upgrade if specified: 'business', 'first', etc."
    )
    alternate_flight_requested: Optional[str] = Field(
        None,
        description="Specific alternate flight if mentioned"
    )
    
    # Escalation indicators (explicit mentions, NOT inferred from emotion)
    mentions_legal_action: bool = Field(
        False,
        description="Customer explicitly mentions legal action, lawyer, court, sue"
    )
    mentions_formal_complaint: bool = Field(
        False,
        description="Customer explicitly requests formal complaint, escalation to management"
    )
    
    # Emotional state (separate from escalation)
    emotional_state: Optional[Literal["neutral", "frustrated", "angry", "furious"]] = Field(
        None,
        description="Customer emotional state from language tone"
    )
    
    # Raw input for audit
    raw_message: str = Field(
        description="Original customer message"
    )
    
    # Confidence/uncertainty markers
    uncertain_references: List[str] = Field(
        default_factory=list,
        description="References customer expressed uncertainty about (e.g., 'probably SK4821X')"
    )


class GroundedRequest(BaseModel):
    """
    GROUNDED request after verification against authoritative data.
    
    This contains:
    1. Original untrusted extraction
    2. VERIFIED facts from authoritative data sources
    3. Grounding status and warnings
    
    Only verified facts may be passed to the policy engine.
    """
    
    # Original untrusted extraction
    untrusted_request: UntrustedStructuredRequest
    
    # Grounding status
    grounding_status: GroundingStatus
    grounding_warnings: List[str] = Field(
        default_factory=list,
        description="Issues found during grounding (mismatches, unknowns)"
    )
    
    # VERIFIED customer information (from customers.json)
    verified_customer_name: Optional[str] = None
    verified_loyalty_tier: Optional[str] = None
    verified_booking_reference: Optional[str] = None
    
    # VERIFIED booking information (from bookings.json)
    verified_flight_reference: Optional[str] = None
    verified_flight_status: Optional[str] = None  # cancelled, delayed, unaffected
    verified_disruption_cause: Optional[str] = None  # Only if present in source data
    verified_delay_hours: Optional[float] = None
    
    # Reference verification results
    customer_reference_found: bool = False
    booking_reference_found: bool = False
    flight_reference_matches_booking: bool = False
    
    def to_policy_engine_input(self, scenario_disruption_cause: Optional[str] = None) -> Optional[StructuredRequest]:
        """
        Convert grounded request to policy engine input.
        
        Args:
            scenario_disruption_cause: Optional disruption cause from scenario context.
                                      Use this when the scenario explicitly establishes the cause
                                      (e.g., "airline operational delay" in assignment prompt).
                                      
        Returns None if grounding failed (UNRESOLVED, MISMATCH, INCOMPLETE, ERROR).
        Only VERIFIED requests can be converted to policy engine input.
        
        IMPORTANT: Only verified facts are passed to policy engine.
        Customer claims/requests are NOT trusted as facts.
        """
        if self.grounding_status != GroundingStatus.VERIFIED:
            return None
        
        if not self.verified_booking_reference:
            return None
        
        # Map untrusted requested_actions to policy engine format
        requested_actions = self.untrusted_request.requested_actions
        
        # Determine escalation intents (explicit only)
        escalation_intents = []
        if self.untrusted_request.mentions_legal_action:
            escalation_intents.append("legal_threat")
        if self.untrusted_request.mentions_formal_complaint:
            escalation_intents.append("formal_complaint")
        
        # Map emotional state (if present)
        customer_emotion = self.untrusted_request.emotional_state or "neutral"
        
        # Determine disruption cause:
        # 1. Use verified_disruption_cause if present in source data (highest priority)
        # 2. Use scenario_disruption_cause if provided (scenario context)
        # 3. Otherwise None (unknown cause)
        disruption_cause = self.verified_disruption_cause or scenario_disruption_cause
        
        # Build policy engine input using VERIFIED facts only
        return StructuredRequest(
            booking_reference=self.verified_booking_reference,
            requested_actions=requested_actions,
            customer_emotion=customer_emotion,
            escalation_intents=escalation_intents,
            fare_difference=self.untrusted_request.requested_fare_difference,
            alternate_flight=self.untrusted_request.alternate_flight_requested,
            refund_to_different_payment_method=False,  # Would need explicit detection
            disruption_cause=disruption_cause
        )
