"""
Meal voucher action implementation (SIMULATED).

This module executes authorized meal voucher issuance.
It does NOT make policy decisions about voucher eligibility.

CRITICAL: Voucher amount is FIXED at ₹500 per Assignment 3 Data Pack.
Do NOT allow arbitrary voucher amounts.
"""

from actions.models import ActionResult, ActionStatus
from datetime import datetime


def issue_meal_voucher_500(
    booking_reference: str,
    correlation_id: str,
    **kwargs
) -> ActionResult:
    """
    Issue ₹500 meal voucher (SIMULATED).
    
    This action MUST be authorized by PolicyVerdict before execution.
    The authorization firewall enforces this constraint.
    
    Assignment 3 Data Pack policy states:
    - Meal voucher amount: ₹500 (FIXED)
    - Applies to all delay compensation tiers
    
    IMPORTANT: The amount is FIXED at ₹500. This function does NOT accept
    an arbitrary amount parameter because that would create authority risk.
    
    Args:
        booking_reference: Booking for voucher issuance
        correlation_id: Unique identifier for idempotency
        **kwargs: Additional parameters (ignored)
        
    Returns:
        ActionResult with EXECUTED status and ₹500 amount
    """
    # SIMULATION: In production, this would:
    # 1. Generate voucher code
    # 2. Register with merchant/vendor system
    # 3. Send voucher to customer (email/SMS)
    
    # For prototype, we just record that voucher was issued
    return ActionResult(
        action_id="issue_meal_voucher_500",
        status=ActionStatus.EXECUTED,
        booking_reference=booking_reference,
        message="Meal voucher issued: ₹500",
        executed_at=datetime.now(),
        metadata={
            "voucher_amount": 500,
            "currency": "INR",
            "type": "meal_voucher",
            "simulation": True
        },
        correlation_id=correlation_id
    )
