"""
Natural Language Understanding layer for AirResolve.

ARCHITECTURE PRINCIPLE:
    The LLM is NOT the policy decision-maker.
    
    LLM Role: Natural language → structured untrusted extraction
    Grounding Role: Verify references against authoritative data
    Policy Engine Role: SOLE AUTHORITY for decisions

Flow:
    Natural language message
        ↓
    NLU Parser (LLM or mock)
        ↓
    UntrustedStructuredRequest (customer claims, NOT verified facts)
        ↓
    Grounding Engine
        ↓
    GroundedRequest (verified facts + customer intent)
        ↓
    Policy Engine Input (StructuredRequest)
        ↓
    PolicyVerdict (deterministic policy decision)

CRITICAL DISTINCTION:
    CUSTOMER CLAIM ≠ VERIFIED FACT ≠ POLICY DECISION
"""

from nlu.models import (
    CustomerIntent,
    GroundingStatus,
    UntrustedStructuredRequest,
    GroundedRequest
)
from nlu.parser import NLUParser, MockNLUParser, LLMNLUParser
from nlu.grounding import GroundingEngine

__all__ = [
    "CustomerIntent",
    "GroundingStatus",
    "UntrustedStructuredRequest",
    "GroundedRequest",
    "NLUParser",
    "MockNLUParser",
    "LLMNLUParser",
    "GroundingEngine"
]
