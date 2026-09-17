"""
Response generator.

Generates customer-facing responses from resolution workflow results.

IMPORTANT: For now, this is DETERMINISTIC (no LLM).
Future phase will add LLM-based natural language generation.
"""

from typing import List, Optional
from policy.models import PolicyVerdict
from nlu.models import GroundedRequest, GroundingStatus
from actions.models import ActionResult, HumanHandoffPacket
from orchestration.models import PlannedAction


class ResponseGenerator:
    """
    Generates customer-facing responses.
    
    DETERMINISTIC IMPLEMENTATION (no LLM):
    - Uses template-based response generation
    - Emotion influences tone, NOT entitlement
    - Supports partial resolution (mixed outcomes)
    - Avoids exposing internal implementation details
    - Professional and empathetic tone
    
    CRITICAL RULES:
    - Do NOT promise denied actions
    - Do NOT invent flight numbers, hotels, refund amounts
    - Do NOT claim actions are complete when they're not
    - Do NOT expose internal rule IDs
    - Do NOT say "according to our database" unless appropriate
    - Do NOT provide legal advice
    - Do NOT argue with customer
    """
    
    def generate_response(
        self,
        grounded: Optional[GroundedRequest],
        verdict: Optional[PolicyVerdict],
        executed_actions: List[ActionResult],
        escalation: Optional[HumanHandoffPacket],
        error_type: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> str:
        """
        Generate customer-facing response.
        
        Args:
            grounded: Grounded request (may be None if grounding failed)
            verdict: Policy verdict (may be None if policy not evaluated)
            executed_actions: Actions successfully executed
            escalation: Escalation handoff packet if created
            error_type: Error type if processing failed
            error_message: Error message if processing failed
            
        Returns:
            Customer-facing response text
        """
        # Handle errors first
        if error_type or error_message:
            return self._generate_error_response(error_type, error_message)
        
        # Handle grounding failures
        if not grounded or grounded.grounding_status != GroundingStatus.VERIFIED:
            return self._generate_grounding_failure_response(grounded)
        
        # Handle policy errors
        if verdict and verdict.status == "ERROR":
            return self._generate_policy_error_response(verdict)
        
        # Generate normal response
        return self._generate_normal_response(grounded, verdict, executed_actions, escalation)
    
    def _generate_grounding_failure_response(self, grounded: Optional[GroundedRequest]) -> str:
        """Generate response when grounding fails."""
        if not grounded:
            return (
                "I'm unable to process your request at the moment. "
                "Please provide your booking reference so I can assist you."
            )
        
        if grounded.grounding_status == GroundingStatus.INCOMPLETE:
            return (
                "I need your booking reference to help you with your request. "
                "Could you please provide your booking reference number?"
            )
        
        if grounded.grounding_status == GroundingStatus.UNRESOLVED:
            messages = grounded.grounding_warnings or []
            return (
                "I wasn't able to find your booking in our system. "
                "Please check your booking reference and try again. "
                "If you continue to have issues, I can connect you with a supervisor for assistance."
            )
        
        if grounded.grounding_status == GroundingStatus.MISMATCH:
            return (
                "There appears to be a discrepancy in the booking information. "
                "For your security, I'll need to escalate this to a supervisor who can verify your details."
            )
        
        return (
            "I encountered an issue verifying your booking information. "
            "A supervisor will review your request and contact you shortly."
        )
    
    def _generate_error_response(self, error_type: Optional[str], error_message: Optional[str]) -> str:
        """Generate response for processing errors."""
        return (
            "I apologize, but I encountered an issue processing your request. "
            "A supervisor will review your case and contact you shortly."
        )
    
    def _generate_policy_error_response(self, verdict: PolicyVerdict) -> str:
        """Generate response for policy evaluation errors."""
        return (
            "I apologize, but I need additional information to process your request. "
            "A supervisor will review your case and contact you shortly."
        )
    
    def _generate_normal_response(
        self,
        grounded: GroundedRequest,
        verdict: Optional[PolicyVerdict],
        executed_actions: List[ActionResult],
        escalation: Optional[HumanHandoffPacket]
    ) -> str:
        """Generate normal response for successfully processed request."""
        if not verdict:
            return "I'm processing your request and will have an update for you shortly."
        
        # Start with greeting/acknowledgment
        emotional_state = grounded.untrusted_request.emotional_state
        response_parts = []
        
        # Adjust tone based on emotion (NOT entitlement)
        if emotional_state in ["angry", "furious"]:
            response_parts.append("I understand how frustrating this situation is.")
        elif emotional_state == "frustrated":
            response_parts.append("I understand this is frustrating.")
        
        # Acknowledge the disruption
        if grounded.verified_flight_status == "cancelled":
            response_parts.append(f"I see that flight {grounded.verified_flight_reference} was cancelled.")
        elif grounded.verified_flight_status == "delayed" and grounded.verified_delay_hours:
            response_parts.append(
                f"I see that flight {grounded.verified_flight_reference} is delayed by "
                f"{grounded.verified_delay_hours} hours."
            )
        
        # Report executed actions
        completed_actions = []
        for result in executed_actions:
            if result.status == "EXECUTED":
                action_description = self._describe_action(result.action_id, verdict)
                if action_description:
                    completed_actions.append(action_description)
        
        if completed_actions:
            if len(completed_actions) == 1:
                response_parts.append(f"I've {completed_actions[0]}.")
            else:
                response_parts.append("I've completed the following:")
                for action in completed_actions:
                    response_parts.append(f"• {action.capitalize()}")
        
        # Report escalated items (partial resolution)
        if escalation:
            denied_count = len(verdict.denied_actions) if verdict else 0
            
            if denied_count > 0 and completed_actions:
                # Partial resolution - some completed, some need review
                denied_descriptions = []
                for action in verdict.denied_actions:
                    desc = self._describe_action_request(action)
                    if desc:
                        denied_descriptions.append(desc)
                
                if denied_descriptions:
                    if len(denied_descriptions) == 1:
                        response_parts.append(
                            f"Your request for {denied_descriptions[0]} requires supervisor review, "
                            "so I've escalated that for you."
                        )
                    else:
                        response_parts.append("The following requests require supervisor review:")
                        for desc in denied_descriptions:
                            response_parts.append(f"• {desc.capitalize()}")
            else:
                # Full escalation - nothing completed
                response_parts.append(
                    "I've forwarded your request to a supervisor for review. "
                    "They'll be in touch with you shortly."
                )
        
        # Handle legal threats appropriately
        if grounded.untrusted_request.mentions_legal_action:
            response_parts.append(
                "I've noted your concerns and escalated your case to a supervisor "
                "who will review the matter and contact you."
            )
        
        # Join response parts
        return " ".join(response_parts)
    
    def _describe_action(self, action_id: str, verdict: Optional[PolicyVerdict]) -> Optional[str]:
        """Describe an executed action in customer-friendly language."""
        descriptions = {
            "initiate_refund_to_original_payment_method": (
                "initiated your refund to your original payment method. "
                "You'll receive the full refund within 7 business days"
            ),
            "issue_meal_voucher_500": "issued a ₹500 meal voucher",
            "provide_lounge_access": "arranged lounge access for you",
            "arrange_hotel_accommodation_delayed_hours": None,  # Handled specially below
            "rebook_next_available_within_24h": "arranged rebooking on the next available flight",
        }
        
        # Handle hotel specially (needs hours from verdict)
        if action_id == "arrange_hotel_accommodation_delayed_hours" and verdict:
            if verdict.hotel_accommodation_hours:
                return f"arranged hotel accommodation for {verdict.hotel_accommodation_hours} hours"
        
        return descriptions.get(action_id)
    
    def _describe_action_request(self, action: str) -> Optional[str]:
        """Describe a requested action in customer-friendly language."""
        descriptions = {
            "business_class_upgrade": "a business class upgrade",
            "full_night_hotel": "a full-night hotel stay",
            "hotel": "hotel accommodation",
            "rebooking": "an alternate flight",
            "fare_waiver": "a fare difference waiver",
        }
        return descriptions.get(action)
