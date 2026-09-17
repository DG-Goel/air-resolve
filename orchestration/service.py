"""
Resolution service - orchestrates complete customer-facing workflow.

This is the main orchestration component that coordinates all layers.
"""

from typing import Optional
from orchestration.models import ResolutionCase, CaseStatus
from orchestration.planner import ActionPlanner
from orchestration.responses import ResponseGenerator
from nlu.parser import NLUParser
from nlu.grounding import GroundingEngine
from nlu.models import GroundingStatus
from policy.engine import PolicyEngine
from policy.models import StructuredRequest
from actions.executor import ActionExecutor
from actions.models import ActionRequest, HumanHandoffPacket
from audit.journal import AuditJournal, AuditEvent, EventType


class ResolutionService:
    """
    Customer-facing resolution workflow orchestrator.
    
    Coordinates the complete flow:
        Customer Message
            ↓
        NLU Parser (understand)
            ↓
        Grounding Engine (verify)
            ↓
        Policy Engine (decide - SOLE AUTHORITY)
            ↓
        Action Planner (prepare)
            ↓
        Action Executor (execute with authorization firewall)
            ↓
        Audit Journal (record)
            ↓
        Response Generator (communicate)
            ↓
        Customer Response
    
    CRITICAL: This service COORDINATES components.
    It does NOT make policy decisions or duplicate component logic.
    """
    
    def __init__(
        self,
        nlu_parser: NLUParser,
        grounding_engine: GroundingEngine,
        policy_engine: PolicyEngine,
        action_executor: Optional[ActionExecutor] = None,
        action_planner: Optional[ActionPlanner] = None,
        response_generator: Optional[ResponseGenerator] = None,
        audit_journal: Optional[AuditJournal] = None
    ):
        """
        Initialize resolution service with components.
        
        Args:
            nlu_parser: Parser for natural language understanding
            grounding_engine: Engine for reference verification
            policy_engine: Deterministic policy engine (SOLE AUTHORITY)
            action_executor: Executor with authorization firewall
            action_planner: Planner for converting verdicts to actions
            response_generator: Generator for customer responses
            audit_journal: Audit journal for recording events
        """
        self.nlu_parser = nlu_parser
        self.grounding_engine = grounding_engine
        self.policy_engine = policy_engine
        self.action_executor = action_executor or ActionExecutor()
        self.action_planner = action_planner or ActionPlanner()
        self.response_generator = response_generator or ResponseGenerator()
        self.audit_journal = audit_journal or AuditJournal()
    
    def process_message(
        self,
        message: str,
        case: Optional[ResolutionCase] = None,
        scenario_disruption_cause: Optional[str] = None
    ) -> ResolutionCase:
        """
        Process customer message through complete resolution workflow.
        
        Args:
            message: Customer natural language message
            case: Existing case for multi-turn conversations (None for new case)
            scenario_disruption_cause: Optional scenario context for disruption cause
                                       (e.g., from assignment scenario description)
        
        Returns:
            Updated ResolutionCase with complete workflow results
        """
        # Create or update case
        if case is None:
            case = ResolutionCase()
            case.status = CaseStatus.RECEIVED
            
            # Record case creation
            self.audit_journal.record(AuditEvent(
                event_type=EventType.CASE_CREATED,
                case_id=case.case_id,
                details={"correlation_id": case.correlation_id}
            ))
        
        # Add customer message to conversation
        case.add_customer_message(message)
        case.current_customer_message = message
        
        try:
            # STEP 1: NLU PARSING (Language Understanding - UNTRUSTED)
            case.structured_request = self.nlu_parser.parse(message)
            
            # STEP 2: GROUNDING (Fact Verification)
            case.status = CaseStatus.GROUNDING_REQUIRED
            case.grounded_request = self.grounding_engine.ground(case.structured_request)
            case.grounding_warnings = case.grounded_request.grounding_warnings
            
            # CRITICAL: If grounding fails, STOP - do NOT call policy engine
            if case.grounded_request.grounding_status != GroundingStatus.VERIFIED:
                case.status = CaseStatus.ERROR
                case.error_type = f"grounding_failed_{case.grounded_request.grounding_status.value}"
                case.error_message = "; ".join(case.grounding_warnings) if case.grounding_warnings else "Grounding verification failed"
                
                # Generate response for grounding failure
                case.response = self.response_generator.generate_response(
                    grounded=case.grounded_request,
                    verdict=None,
                    executed_actions=[],
                    escalation=None
                )
                case.add_agent_response(case.response)
                
                # Record audit event
                self.audit_journal.record(AuditEvent(
                    event_type=EventType.CASE_CREATED,
                    case_id=case.case_id,
                    booking_reference=None,
                    details={
                        "grounding_status": case.grounded_request.grounding_status.value,
                        "warnings": case.grounding_warnings
                    }
                ))
                
                return case
            
            # Update case with verified customer information
            case.customer_name = case.grounded_request.verified_customer_name
            case.booking_reference = case.grounded_request.verified_booking_reference
            case.loyalty_tier = case.grounded_request.verified_loyalty_tier
            
            # Record customer identification
            self.audit_journal.record(AuditEvent(
                event_type=EventType.CASE_CREATED,
                case_id=case.case_id,
                booking_reference=case.booking_reference,
                details={
                    "customer_name": case.customer_name,
                    "loyalty_tier": case.loyalty_tier,
                    "correlation_id": case.correlation_id
                }
            ))
            
            # STEP 3: POLICY EVALUATION (Decision Making - SOLE AUTHORITY)
            policy_input = case.grounded_request.to_policy_engine_input(
                scenario_disruption_cause=scenario_disruption_cause
            )
            
            if not policy_input:
                case.status = CaseStatus.ERROR
                case.error_type = "policy_input_conversion_failed"
                case.error_message = "Could not convert grounded request to policy input"
                
                case.response = self.response_generator.generate_response(
                    grounded=case.grounded_request,
                    verdict=None,
                    executed_actions=[],
                    escalation=None,
                    error_type=case.error_type,
                    error_message=case.error_message
                )
                case.add_agent_response(case.response)
                return case
            
            case.policy_verdict = self.policy_engine.evaluate(policy_input)
            case.status = CaseStatus.POLICY_EVALUATED
            
            # Record policy evaluation
            self.audit_journal.record(AuditEvent(
                event_type=EventType.POLICY_EVALUATED,
                case_id=case.case_id,
                booking_reference=case.booking_reference,
                details={
                    "policy_status": case.policy_verdict.status,
                    "authorized_actions": case.policy_verdict.authorized_actions,
                    "denied_actions": case.policy_verdict.denied_actions,
                    "escalation_required": case.policy_verdict.escalation_required
                }
            ))
            
            # STEP 4: ACTION PLANNING (Preparation)
            case.planned_actions = self.action_planner.plan(case.policy_verdict)
            
            # STEP 5: ACTION EXECUTION (Execute with authorization firewall)
            for planned in case.planned_actions:
                if planned.action_type == "EXECUTE":
                    # Execute authorized action
                    action_request = ActionRequest(
                        action_id=planned.action_id,
                        booking_reference=case.booking_reference,
                        correlation_id=case.correlation_id
                    )
                    
                    result = self.action_executor.execute(action_request, case.policy_verdict)
                    
                    if result.status == "EXECUTED":
                        case.executed_actions.append(result)
                        
                        # Record execution
                        self.audit_journal.record(AuditEvent(
                            event_type=EventType.ACTION_EXECUTED,
                            case_id=case.case_id,
                            booking_reference=case.booking_reference,
                            action_id=planned.action_id,
                            status="EXECUTED"
                        ))
                    elif result.status == "REJECTED":
                        case.rejected_actions.append(result)
                        
                        # Record rejection
                        self.audit_journal.record(AuditEvent(
                            event_type=EventType.ACTION_REJECTED,
                            case_id=case.case_id,
                            booking_reference=case.booking_reference,
                            action_id=planned.action_id,
                            status="REJECTED",
                            details={"reason": result.message}
                        ))
                    else:
                        # ALREADY_EXECUTED or FAILED
                        case.executed_actions.append(result)
                
                elif planned.action_type == "ESCALATE":
                    # Create escalation
                    esc_result, esc_packet = self.action_executor.create_escalation(
                        case.policy_verdict,
                        case.customer_name or "Customer"
                    )
                    case.escalation = esc_packet
                    case.status = CaseStatus.ESCALATED
                    
                    # Record escalation
                    self.audit_journal.record(AuditEvent(
                        event_type=EventType.ESCALATION_CREATED,
                        case_id=case.case_id,
                        booking_reference=case.booking_reference,
                        details={
                            "escalation_case_id": esc_packet.case_id,
                            "escalation_reasons": esc_packet.escalation_reasons,
                            "priority": esc_packet.priority
                        }
                    ))
            
            # Update status based on results
            if case.status != CaseStatus.ESCALATED:
                if case.executed_actions:
                    case.status = CaseStatus.ACTIONS_EXECUTED
                elif not case.planned_actions:
                    case.status = CaseStatus.RESOLVED
                else:
                    case.status = CaseStatus.RESOLVED
            
            # STEP 6: RESPONSE GENERATION (Communication)
            case.response = self.response_generator.generate_response(
                grounded=case.grounded_request,
                verdict=case.policy_verdict,
                executed_actions=case.executed_actions,
                escalation=case.escalation
            )
            case.add_agent_response(case.response)
            
        except Exception as e:
            # Handle unexpected errors gracefully
            case.status = CaseStatus.ERROR
            case.error_type = "processing_error"
            case.error_message = str(e)
            
            case.response = self.response_generator.generate_response(
                grounded=case.grounded_request if hasattr(case, 'grounded_request') else None,
                verdict=None,
                executed_actions=[],
                escalation=None,
                error_type=case.error_type,
                error_message=case.error_message
            )
            case.add_agent_response(case.response)
            
            # Record error
            self.audit_journal.record(AuditEvent(
                event_type=EventType.CASE_CREATED,
                case_id=case.case_id,
                booking_reference=case.booking_reference if hasattr(case, 'booking_reference') else None,
                details={
                    "error_type": case.error_type,
                    "error_message": case.error_message
                }
            ))
        
        return case
