"""
Escalation action implementation (SIMULATED).

This module creates human supervisor escalation cases.
It does NOT make policy decisions about when escalation is required.
"""

from actions.models import ActionResult, ActionStatus, HumanHandoffPacket
from datetime import datetime
from typing import Optional, List


def create_human_escalation(
    booking_reference: str,
    correlation_id: str,
    customer_name: str,
    loyalty_tier: str,
    disruption_status: str,
    disruption_cause: Optional[str],
    delay_hours: Optional[float],
    requested_actions: List[str],
    authorized_actions: List[str],
    denied_actions: List[str],
    escalation_reasons: List[str],
    applicable_policy_rules: List[str],
    ambiguities_flagged: List[str],
    **kwargs
) -> tuple[ActionResult, HumanHandoffPacket]:
    """
    Create human supervisor escalation case (SIMULATED).
    
    This action executes when PolicyVerdict indicates escalation_required=True.
    It packages all relevant information for supervisor review.
    
    Assignment 3 Data Pack escalation triggers:
    - Compensation beyond stated policy
    - Fare waivers > ₹1,500
    - Non-airline-caused disruption exceptions
    - Legal threats
    - Formal complaints
    - Refund to different payment method
    
    This function does NOT decide when to escalate.
    It only creates the escalation packet after policy decision.
    
    Args:
        booking_reference: Customer booking
        correlation_id: Unique identifier
        customer_name: Customer name
        loyalty_tier: Customer loyalty tier
        disruption_status: cancelled, delayed, etc.
        disruption_cause: Known cause if available
        delay_hours: Delay hours if applicable
        requested_actions: What customer requested
        authorized_actions: What policy authorized
        denied_actions: What was denied
        escalation_reasons: Why escalation required
        applicable_policy_rules: Policy rules applied
        ambiguities_flagged: Policy ambiguities encountered
        **kwargs: Additional parameters
        
    Returns:
        Tuple of (ActionResult, HumanHandoffPacket)
    """
    # Generate deterministic conversation summary
    summary = _generate_deterministic_summary(
        customer_name=customer_name,
        loyalty_tier=loyalty_tier,
        disruption_status=disruption_status,
        disruption_cause=disruption_cause,
        delay_hours=delay_hours,
        requested_actions=requested_actions,
        authorized_actions=authorized_actions,
        denied_actions=denied_actions,
        escalation_reasons=escalation_reasons
    )
    
    # Determine priority based on escalation reasons
    priority = _determine_priority(escalation_reasons)
    
    # Create handoff packet
    packet = HumanHandoffPacket(
        booking_reference=booking_reference,
        customer_name=customer_name,
        loyalty_tier=loyalty_tier,
        disruption_status=disruption_status,
        disruption_cause=disruption_cause,
        delay_hours=delay_hours,
        requested_actions=requested_actions,
        authorized_actions=authorized_actions,
        denied_actions=denied_actions,
        escalation_reasons=escalation_reasons,
        applicable_policy_rules=applicable_policy_rules,
        ambiguities_flagged=ambiguities_flagged,
        conversation_summary=summary,
        priority=priority
    )
    
    # SIMULATION: In production, this would:
    # 1. Create case in supervisor queue system
    # 2. Notify supervisor via appropriate channel
    # 3. Set SLA based on priority
    # 4. Track case status
    
    result = ActionResult(
        action_id="create_human_escalation",
        status=ActionStatus.EXECUTED,
        booking_reference=booking_reference,
        message=f"Escalation case created: {packet.case_id} (Priority: {priority})",
        executed_at=datetime.now(),
        metadata={
            "case_id": packet.case_id,
            "priority": priority,
            "escalation_count": len(escalation_reasons),
            "simulation": True
        },
        correlation_id=correlation_id
    )
    
    return result, packet


def _generate_deterministic_summary(
    customer_name: str,
    loyalty_tier: str,
    disruption_status: str,
    disruption_cause: Optional[str],
    delay_hours: Optional[float],
    requested_actions: List[str],
    authorized_actions: List[str],
    denied_actions: List[str],
    escalation_reasons: List[str]
) -> str:
    """
    Generate deterministic conversation summary (no LLM).
    
    For prototype, this creates a structured summary from available data.
    In production, this could use LLM for natural conversation summary.
    """
    lines = [
        f"CUSTOMER: {customer_name} ({loyalty_tier} tier)",
        f"DISRUPTION: {disruption_status}"
    ]
    
    if disruption_cause:
        lines.append(f"CAUSE: {disruption_cause}")
    
    if delay_hours:
        lines.append(f"DELAY: {delay_hours} hours")
    
    lines.append(f"\nREQUESTED: {', '.join(requested_actions)}")
    
    if authorized_actions:
        lines.append(f"AUTHORIZED: {', '.join(authorized_actions)}")
    
    if denied_actions:
        lines.append(f"DENIED: {', '.join(denied_actions)}")
    
    lines.append(f"\nESCALATION REQUIRED:")
    for reason in escalation_reasons:
        lines.append(f"  - {reason}")
    
    return "\n".join(lines)


def _determine_priority(escalation_reasons: List[str]) -> str:
    """
    Determine escalation priority based on reasons.
    
    Priority levels:
    - urgent: Legal threats
    - high: Formal complaints, authority limit exceeded
    - medium: Policy exceptions, ambiguities
    - low: General review
    """
    reasons_lower = [r.lower() for r in escalation_reasons]
    
    if any("legal" in r for r in reasons_lower):
        return "urgent"
    
    if any("complaint" in r or "authority limit" in r for r in reasons_lower):
        return "high"
    
    if any("policy exception" in r or "ambiguity" in r for r in reasons_lower):
        return "medium"
    
    return "medium"  # Default
