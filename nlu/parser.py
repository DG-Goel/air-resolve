"""
NLU Parser implementations.

Provides abstraction for LLM-based NLU with mock implementation for testing.
"""

from typing import Protocol, Optional, Dict, Any
from abc import ABC, abstractmethod
import json
import re

from nlu.models import UntrustedStructuredRequest, CustomerIntent
from nlu.prompts import SYSTEM_PROMPT, create_extraction_prompt, MOCK_RESPONSES


class LLMProvider(Protocol):
    """
    Protocol for LLM provider abstraction.
    
    This allows swapping OpenAI, Groq, or other providers without
    changing the NLU layer.
    """
    
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """
        Get completion from LLM.
        
        Args:
            system_prompt: System/instruction prompt
            user_prompt: User message prompt
            
        Returns:
            LLM completion text
        """
        ...


class NLUParser(ABC):
    """
    Abstract base for NLU parsers.
    
    Implementations must extract structured information from natural language
    customer messages without inventing facts or making policy decisions.
    """
    
    @abstractmethod
    def parse(self, message: str) -> UntrustedStructuredRequest:
        """
        Parse natural language message into structured request.
        
        Args:
            message: Customer natural language message
            
        Returns:
            UntrustedStructuredRequest (must be verified by grounding)
        """
        pass


class MockNLUParser(NLUParser):
    """
    Deterministic mock NLU parser for testing.
    
    Uses pattern matching against known test cases.
    Does NOT require API key or external LLM.
    
    This is the REQUIRED implementation for testing.
    """
    
    def parse(self, message: str) -> UntrustedStructuredRequest:
        """
        Parse message using deterministic pattern matching.
        
        Matches message against known patterns in MOCK_RESPONSES.
        Falls back to basic extraction for unknown messages.
        """
        message_lower = message.lower()
        
        # Try to match against known patterns
        for mock_name, mock_data in MOCK_RESPONSES.items():
            keywords = mock_data["pattern_keywords"]
            # Check if most keywords match
            matched_keywords = sum(1 for kw in keywords if kw.lower() in message_lower)
            if matched_keywords >= len(keywords) * 0.6:  # 60% threshold
                # Found match, use mock response
                response_data = mock_data["response"].copy()
                response_data["raw_message"] = message
                return UntrustedStructuredRequest(**response_data)
        
        # No pattern match - do basic extraction
        return self._basic_extraction(message)
    
    def _basic_extraction(self, message: str) -> UntrustedStructuredRequest:
        """
        Basic extraction for messages without pattern match.
        
        Extracts obvious patterns without LLM.
        """
        message_lower = message.lower()
        
        # Extract booking reference (common patterns: SK4821X, TR1190B, WL7742)
        booking_ref = None
        booking_patterns = [
            r'\b([A-Z]{2}\d{4}[A-Z])\b',  # SK4821X format
            r'\b([A-Z]{2}\d{4})\b',       # SK4821 format
            r'\b([A-Z]{2}-\d{3,4})\b'     # SK-204 format (flight, not booking)
        ]
        for pattern in booking_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                booking_ref = match.group(1).upper()
                break
        
        # Extract flight reference (SK-204, SK-118, SK-305)
        flight_ref = None
        flight_pattern = r'\b([A-Z]{2}-\d{3,4})\b'
        match = re.search(flight_pattern, message, re.IGNORECASE)
        if match:
            flight_ref = match.group(1).upper()
        
        # Detect requested actions
        requested_actions = []
        action_keywords = {
            "refund": ["refund", "money back"],
            "rebooking": ["rebook", "another flight", "different flight", "alternate flight"],
            "hotel": ["hotel", "accommodation"],
            "meal_voucher": ["meal", "voucher", "food"],
            "lounge": ["lounge"],
            "business_class_upgrade": ["business class", "upgrade"]
        }
        
        for action, keywords in action_keywords.items():
            if any(kw in message_lower for kw in keywords):
                requested_actions.append(action)
        
        # Detect intent
        intent = CustomerIntent.UNKNOWN
        if len(requested_actions) > 1:
            intent = CustomerIntent.MULTIPLE_REQUEST
        elif "refund" in requested_actions:
            intent = CustomerIntent.REFUND_REQUEST
        elif "rebooking" in requested_actions:
            intent = CustomerIntent.REBOOKING_REQUEST
        elif "hotel" in requested_actions:
            intent = CustomerIntent.HOTEL_REQUEST
        elif "business_class_upgrade" in requested_actions:
            intent = CustomerIntent.CLASS_UPGRADE_REQUEST
        
        # Detect legal/complaint escalation (EXPLICIT only)
        mentions_legal = any(word in message_lower for word in [
            "legal action", "sue", "lawyer", "court", "attorney"
        ])
        mentions_complaint = any(phrase in message_lower for phrase in [
            "formal complaint", "file a complaint", "escalate to management",
            "speak to supervisor"
        ])
        
        # Detect emotional state
        emotional_state = "neutral"
        if any(word in message_lower for word in ["furious", "outraged", "livid"]):
            emotional_state = "furious"
        elif any(word in message_lower for word in ["angry", "mad", "upset"]):
            emotional_state = "angry"
        elif any(word in message_lower for word in ["frustrated", "annoyed", "disappointed"]):
            emotional_state = "frustrated"
        
        # Extract fare difference (₹2,000 or 2000)
        fare_diff = None
        fare_patterns = [
            r'₹\s*(\d+[,.]?\d*)',
            r'(\d+)\s*rupees',
            r'rs\.?\s*(\d+)'
        ]
        for pattern in fare_patterns:
            match = re.search(pattern, message_lower)
            if match:
                fare_str = match.group(1).replace(',', '')
                try:
                    fare_diff = float(fare_str)
                except ValueError:
                    pass
                break
        
        # Detect hotel scope
        hotel_scope = None
        if "hotel" in message_lower:
            if any(phrase in message_lower for phrase in ["full night", "whole night", "overnight"]):
                hotel_scope = "full_night"
            elif any(phrase in message_lower for phrase in ["delayed hours", "delay hours"]):
                hotel_scope = "delayed_hours"
        
        # Detect class upgrade
        class_upgrade = None
        if "business" in message_lower:
            class_upgrade = "business"
        elif "first class" in message_lower:
            class_upgrade = "first"
        
        return UntrustedStructuredRequest(
            customer_name=None,  # Would need named entity recognition
            booking_reference=booking_ref,
            flight_reference=flight_ref,
            intent=intent,
            requested_actions=requested_actions,
            requested_amount=None,
            requested_fare_difference=fare_diff,
            hotel_scope_requested=hotel_scope,
            class_upgrade_requested=class_upgrade,
            alternate_flight_requested=None,
            mentions_legal_action=mentions_legal,
            mentions_formal_complaint=mentions_complaint,
            emotional_state=emotional_state,
            raw_message=message,
            uncertain_references=[]
        )


class LLMNLUParser(NLUParser):
    """
    LLM-based NLU parser.
    
    Uses real LLM for natural language understanding.
    Optional - requires API key.
    """
    
    def __init__(self, provider: LLMProvider):
        """
        Initialize with LLM provider.
        
        Args:
            provider: LLM provider implementing LLMProvider protocol
        """
        self.provider = provider
    
    def parse(self, message: str) -> UntrustedStructuredRequest:
        """
        Parse message using LLM.
        
        The LLM is constrained by SYSTEM_PROMPT to extract only
        what is explicitly stated, without inventing facts or
        making policy decisions.
        """
        # Create extraction prompt
        user_prompt = create_extraction_prompt(message)
        
        # Get LLM completion
        completion = self.provider.complete(SYSTEM_PROMPT, user_prompt)
        
        # Parse JSON response
        try:
            # Extract JSON from completion (may have markdown formatting)
            json_match = re.search(r'\{.*\}', completion, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
            else:
                raise ValueError("No JSON found in LLM response")
            
            # Add raw_message if not present
            if "raw_message" not in data:
                data["raw_message"] = message
            
            # Create UntrustedStructuredRequest
            return UntrustedStructuredRequest(**data)
            
        except (json.JSONDecodeError, ValueError) as e:
            # LLM failed to produce valid JSON - return basic extraction
            # This is a safety fallback, not ideal
            return UntrustedStructuredRequest(
                customer_name=None,
                booking_reference=None,
                flight_reference=None,
                intent=CustomerIntent.UNKNOWN,
                requested_actions=[],
                raw_message=message,
                uncertain_references=[f"LLM parsing failed: {str(e)}"]
            )
