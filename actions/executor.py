"""
Action executor with authorization firewall.

CRITICAL ARCHITECTURAL COMPONENT:
The authorization firewall ensures NO action executes without
explicit authorization from the deterministic policy engine.

This is one of the most important security boundaries in AirResolve.
"""

from typing import Optional, Dict, Any, Tuple
from actions.models import ActionRequest, ActionResult, ActionStatus, HumanHandoffPacket
from policy.models import PolicyVerdict

# Import action implementations
from actions import refund, voucher, lounge, hotel, rebooking, escalation


class ActionExecutor:
    """
    Executes authorized actions with authorization firewall protection.
    
    The executor:
    1. Verifies action is in PolicyVerdict.authorized_actions
    2. Checks for duplicate execution (idempotency)
    3. Executes the appropriate action implementation
    4. Records execution in audit journal
    
    The executor NEVER executes unauthorized actions.
    The executor NEVER re-evaluates policy.
    """
    
    def __init__(self):
        """Initialize action executor."""
        # Track executed actions for idempotency
        self._executed_actions: Dict[str, ActionResult] = {}
        
        # Map action IDs to implementation functions
        self._action_registry = {
            "initiate_refund_to_original_payment_method": refund.initiate_refund_to_original_payment_method,
            "issue_meal_voucher_500": voucher.issue_meal_voucher_500,
            "provide_lounge_access": lounge.provide_lounge_access,
            "arrange_hotel_accommodation_delayed_hours": hotel.arrange_hotel_accommodation_delayed_hours,
            "rebook_next_available_within_24h": rebooking.rebook_next_available_within_24h,
        }
    
    def execute(
        self,
        action_request: ActionRequest,
        policy_verdict: PolicyVerdict
    ) -> ActionResult:
        """
        Execute action with authorization firewall protection.
        
        AUTHORIZATION FIREWALL:
        This method first verifies the requested action is explicitly
        authorized in PolicyVerdict.authorized_actions. If not authorized,
        the action is REJECTED without execution.
        
        Args:
            action_request: Action to execute
            policy_verdict: Policy decision containing authorized_actions
            
        Returns:
            ActionResult indicating execution outcome
        """
        # AUTHORIZATION FIREWALL: Verify action is authorized
        if action_request.action_id not in policy_verdict.authorized_actions:
            return ActionResult(
                action_id=action_request.action_id,
                status=ActionStatus.REJECTED,
                booking_reference=action_request.booking_reference,
                message=(
                    f"Action rejected by authorization firewall: '{action_request.action_id}' "
                    f"was not authorized by the deterministic policy engine. "
                    f"Authorized actions: {policy_verdict.authorized_actions}"
                ),
                metadata={
                    "reason": "not_authorized",
                    "policy_status": policy_verdict.status,
                    "authorized_actions": policy_verdict.authorized_actions
                },
                correlation_id=action_request.correlation_id
            )
        
        # IDEMPOTENCY: Check for duplicate execution
        idempotency_key = f"{action_request.booking_reference}:{action_request.action_id}:{action_request.correlation_id}"
        if idempotency_key in self._executed_actions:
            previous_result = self._executed_actions[idempotency_key]
            return ActionResult(
                action_id=action_request.action_id,
                status=ActionStatus.ALREADY_EXECUTED,
                booking_reference=action_request.booking_reference,
                message=f"Action already executed with correlation_id {action_request.correlation_id}",
                executed_at=previous_result.executed_at,
                metadata={
                    "reason": "duplicate_execution_prevented",
                    "original_execution_time": previous_result.executed_at.isoformat() if previous_result.executed_at else None
                },
                correlation_id=action_request.correlation_id
            )
        
        # Get action implementation
        if action_request.action_id not in self._action_registry:
            return ActionResult(
                action_id=action_request.action_id,
                status=ActionStatus.FAILED,
                booking_reference=action_request.booking_reference,
                message=f"No implementation found for action '{action_request.action_id}'",
                metadata={"reason": "not_implemented"},
                correlation_id=action_request.correlation_id
            )
        
        # Execute action
        try:
            action_func = self._action_registry[action_request.action_id]
            
            # Prepare parameters
            params = {
                "booking_reference": action_request.booking_reference,
                "correlation_id": action_request.correlation_id,
                **action_request.parameters
            }
            
            # Add policy verdict metadata if action needs it
            if action_request.action_id == "arrange_hotel_accommodation_delayed_hours":
                params["accommodation_hours"] = policy_verdict.hotel_accommodation_hours
            
            # Execute
            result = action_func(**params)
            
            # Record for idempotency
            self._executed_actions[idempotency_key] = result
            
            return result
            
        except Exception as e:
            return ActionResult(
                action_id=action_request.action_id,
                status=ActionStatus.FAILED,
                booking_reference=action_request.booking_reference,
                message=f"Action execution failed: {str(e)}",
                metadata={"error": str(e), "error_type": type(e).__name__},
                correlation_id=action_request.correlation_id
            )
    
    def create_escalation(
        self,
        policy_verdict: PolicyVerdict,
        customer_name: str,
        correlation_id: Optional[str] = None
    ) -> Tuple[ActionResult, HumanHandoffPacket]:
        """
        Create human escalation case.
        
        This should be called when PolicyVerdict.escalation_required is True.
        
        Args:
            policy_verdict: Policy verdict requiring escalation
            customer_name: Customer name for escalation packet
            correlation_id: Optional correlation ID
            
        Returns:
            Tuple of (ActionResult, HumanHandoffPacket)
        """
        import uuid
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())
        
        # Extract disruption details from decision trace
        trace = policy_verdict.decision_trace
        disruption_status = trace.intermediate_calculations.get("booking_status", "unknown") if trace else "unknown"
        disruption_cause = trace.intermediate_calculations.get("resolved_cause") if trace else None
        delay_hours = trace.intermediate_calculations.get("delay_hours") if trace else None
        
        # Get requested actions from trace
        requested_actions = trace.input_values.get("requested_actions", []) if trace else []
        
        return escalation.create_human_escalation(
            booking_reference=trace.booking_reference if trace else policy_verdict.decision_trace.booking_reference,
            correlation_id=correlation_id,
            customer_name=customer_name,
            loyalty_tier=policy_verdict.loyalty_tier or "unknown",
            disruption_status=disruption_status,
            disruption_cause=disruption_cause,
            delay_hours=delay_hours,
            requested_actions=requested_actions,
            authorized_actions=policy_verdict.authorized_actions,
            denied_actions=policy_verdict.denied_actions,
            escalation_reasons=policy_verdict.escalation_reasons,
            applicable_policy_rules=policy_verdict.applicable_policy_rules,
            ambiguities_flagged=policy_verdict.ambiguities_flagged
        )
