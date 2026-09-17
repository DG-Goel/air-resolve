"""
Refund action implementation (SIMULATED).

This module executes authorized refund actions.
It does NOT make policy decisions about refund eligibility.

CRITICAL: This is a simulation for the prototype.
Do NOT connect to real payment processing systems.
"""

from actions.models import ActionResult, ActionStatus
from datetime import datetime


def initiate_refund_to_original_payment_method(
    booking_reference: str,
    correlation_id: str,
    **kwargs
) -> ActionResult:
    """
    Initiate refund to original payment method (SIMULATED).
    
    This action MUST be authorized by PolicyVerdict before execution.
    The authorization firewall enforces this constraint.
    
    Assignment 3 Data Pack policy states:
    - Refund must be to original payment method
    - Processing time: 7 business days
    
    Args:
        booking_reference: Booking to refund
        correlation_id: Unique identifier for idempotency
        **kwargs: Additional parameters (ignored for this simulation)
        
    Returns:
        ActionResult with EXECUTED status
    """
    # SIMULATION: In production, this would:
    # 1. Look up original payment method
    # 2. Calculate refund amount from booking
    # 3. Submit refund to payment processor
    # 4. Record transaction ID
    
    # For prototype, we just record that refund was initiated
    return ActionResult(
        action_id="initiate_refund_to_original_payment_method",
        status=ActionStatus.EXECUTED,
        booking_reference=booking_reference,
        message="Refund initiated to original payment method",
        executed_at=datetime.now(),
        metadata={
            "destination": "original_payment_method",
            "processing_days": 7,
            "currency": "INR",
            "simulation": True
        },
        correlation_id=correlation_id
    )
