"""
AirResolve Policy Engine Package.

This package contains the deterministic policy engine that serves as the
sole authority for policy decisions in the AirResolve system.

Main components:
- models: Pydantic data models for inputs and outputs
- rules: Individual policy rule evaluation functions
- engine: PolicyEngine class that orchestrates rule evaluation
"""

from policy.engine import PolicyEngine
from policy.models import (
    CustomerData,
    BookingData,
    StructuredRequest,
    PolicyVerdict,
    RuleEvaluation,
    DecisionTrace
)

__all__ = [
    "PolicyEngine",
    "CustomerData",
    "BookingData",
    "StructuredRequest",
    "PolicyVerdict",
    "RuleEvaluation",
    "DecisionTrace"
]
