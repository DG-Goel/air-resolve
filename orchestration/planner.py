"""
Action planner.

Converts PolicyVerdict into planned actions for execution.

CRITICAL: The planner does NOT make policy decisions.
It only translates the policy verdict into execution plans.
"""

from typing import List
from orchestration.models import PlannedAction
from policy.models import PolicyVerdict


class ActionPlanner:
    """
    Plans actions based on policy verdict.
    
    The planner follows these rules:
    1. EXECUTE only actions in PolicyVerdict.authorized_actions
    2. ESCALATE actions requiring human review
    3. DENY actions explicitly denied
    4. NEVER infer new actions from emotion or context
    5. NEVER make independent policy decisions
    
    The planner is a translation layer, NOT a decision maker.
    """
    
    def plan(self, verdict: PolicyVerdict) -> List[PlannedAction]:
        """
        Convert policy verdict into execution plan.
        
        Args:
            verdict: Policy decision from deterministic policy engine
            
        Returns:
            List of planned actions (EXECUTE, ESCALATE, or DENY)
        """
        planned = []
        
        # EXECUTE: Actions explicitly authorized by policy engine
        for action_id in verdict.authorized_actions:
            planned.append(PlannedAction(
                action_id=action_id,
                action_type="EXECUTE",
                reason="Authorized by policy engine"
            ))
        
        # ESCALATE: Actions requiring human review
        if verdict.escalation_required:
            # Create escalation action
            planned.append(PlannedAction(
                action_id="create_human_escalation",
                action_type="ESCALATE",
                reason="; ".join(verdict.escalation_reasons) if verdict.escalation_reasons else "Escalation required"
            ))
        
        # DENY: Record denied actions (informational, not executed)
        for action_id in verdict.denied_actions:
            reason = verdict.denial_reasons.get(action_id, "Not authorized by policy")
            planned.append(PlannedAction(
                action_id=action_id,
                action_type="DENY",
                reason=reason
            ))
        
        return planned
