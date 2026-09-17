"""
LLM prompts for NLU extraction.

These prompts enforce strict constraints on what the LLM can extract vs invent.
"""

# System prompt for LLM-based NLU extraction
SYSTEM_PROMPT = """You are an NLU extraction assistant for an airline customer service system.

Your ONLY job is to extract structured information from customer messages.

CRITICAL CONSTRAINTS - YOU MUST NEVER:
1. Infer airline policy or entitlements
2. Infer eligibility or compensation amounts
3. Infer disruption causes (weather, airline operational, etc.)
4. Invent booking, flight, or customer information
5. Invent delay hours, cancellation status, or flight data
6. Invent loyalty tiers or customer data
7. Invent alternative flights or fare amounts
8. Convert emotions into entitlements or policy decisions
9. Make policy decisions of any kind

YOU MAY ONLY EXTRACT:
1. Customer name if explicitly mentioned
2. Booking reference if explicitly mentioned
3. Flight reference if explicitly mentioned
4. What the customer is requesting (refund, rebooking, hotel, etc.)
5. Amounts the customer explicitly mentions (e.g., "₹2,000 more")
6. Emotional tone from language (neutral, frustrated, angry, furious)
7. Explicit legal threats ("I will sue", "I'll take legal action")
8. Explicit complaint requests ("I want to file a formal complaint")

CRITICAL DISTINCTION:
- CUSTOMER CLAIM ≠ VERIFIED FACT ≠ POLICY DECISION
- You extract claims, NOT facts
- Another system verifies facts against authoritative data
- A deterministic policy engine makes decisions

LEGAL/ESCALATION DETECTION:
- Only flag legal threats if EXPLICITLY mentioned (sue, lawyer, court, legal action)
- Only flag complaints if EXPLICITLY requested (formal complaint, escalate to management)
- Emotions alone (even "furious") do NOT trigger escalation

UNKNOWN INFORMATION:
- If customer doesn't mention something, leave it null/empty
- Do not guess booking references, flight numbers, delays, causes
- Do not infer information from context

OUTPUT FORMAT:
Return a JSON object matching the UntrustedStructuredRequest schema.
"""


def create_extraction_prompt(customer_message: str) -> str:
    """
    Create extraction prompt for a customer message.
    
    Args:
        customer_message: Raw customer message text
        
    Returns:
        Formatted prompt for LLM
    """
    return f"""Extract structured information from this customer message:

Customer Message:
\"\"\"{customer_message}\"\"\"

Return a JSON object with these fields:
{{
    "customer_name": "name if mentioned, else null",
    "booking_reference": "reference if mentioned, else null",
    "flight_reference": "flight number if mentioned, else null",
    "intent": "primary intent from: refund_request, rebooking_request, meal_voucher_request, lounge_request, hotel_request, fare_change_request, class_upgrade_request, status_question, complaint_or_legal_escalation, multiple_request, unknown",
    "requested_actions": ["list of requested actions"],
    "requested_amount": null or number,
    "requested_fare_difference": null or number,
    "hotel_scope_requested": "delayed_hours, full_night, or null",
    "class_upgrade_requested": "business, first, or null",
    "alternate_flight_requested": "flight number or null",
    "mentions_legal_action": true/false,
    "mentions_formal_complaint": true/false,
    "emotional_state": "neutral, frustrated, angry, or furious",
    "raw_message": "original message",
    "uncertain_references": ["list of uncertain references"]
}}

Remember: Extract ONLY what is explicitly stated. Do not infer policy, eligibility, causes, delays, or make decisions.
"""


# Mock responses for deterministic testing (no API key required)
MOCK_RESPONSES = {
    # Priya scenario
    "priya_refund_upgrade": {
        "pattern_keywords": ["SK-204", "cancelled", "refund", "business class", "upgrade"],
        "response": {
            "customer_name": "Priya Nair",
            "booking_reference": "SK4821X",
            "flight_reference": "SK-204",
            "intent": "multiple_request",
            "requested_actions": ["refund", "business_class_upgrade"],
            "requested_amount": None,
            "requested_fare_difference": None,
            "hotel_scope_requested": None,
            "class_upgrade_requested": "business",
            "alternate_flight_requested": None,
            "mentions_legal_action": False,
            "mentions_formal_complaint": False,
            "emotional_state": "furious",
            "uncertain_references": []
        }
    },
    
    # Arvind scenario
    "arvind_hotel": {
        "pattern_keywords": ["SK-118", "delayed", "four hours", "hotel"],
        "response": {
            "customer_name": "Arvind Kulkarni",
            "booking_reference": "TR1190B",
            "flight_reference": "SK-118",
            "intent": "hotel_request",
            "requested_actions": ["hotel"],
            "requested_amount": None,
            "requested_fare_difference": None,
            "hotel_scope_requested": None,
            "class_upgrade_requested": None,
            "alternate_flight_requested": None,
            "mentions_legal_action": False,
            "mentions_formal_complaint": False,
            "emotional_state": "frustrated",
            "uncertain_references": []
        }
    },
    
    # Meher scenario
    "meher_full_request": {
        "pattern_keywords": ["SK-305", "delayed", "six hours", "hotel", "whole night", "another flight", "2000", "2,000"],
        "response": {
            "customer_name": "Meher Kaur",
            "booking_reference": "WL7742",
            "flight_reference": "SK-305",
            "intent": "multiple_request",
            "requested_actions": ["hotel", "rebooking", "fare_waiver"],
            "requested_amount": None,
            "requested_fare_difference": 2000,
            "hotel_scope_requested": "full_night",
            "class_upgrade_requested": None,
            "alternate_flight_requested": None,
            "mentions_legal_action": False,
            "mentions_formal_complaint": False,
            "emotional_state": "frustrated",
            "uncertain_references": []
        }
    },
    
    # Legal escalation
    "legal_threat": {
        "pattern_keywords": ["legal action", "sue", "lawyer", "court"],
        "response": {
            "customer_name": None,
            "booking_reference": None,
            "flight_reference": None,
            "intent": "complaint_or_legal_escalation",
            "requested_actions": [],
            "requested_amount": None,
            "requested_fare_difference": None,
            "hotel_scope_requested": None,
            "class_upgrade_requested": None,
            "alternate_flight_requested": None,
            "mentions_legal_action": True,
            "mentions_formal_complaint": False,
            "emotional_state": "angry",
            "uncertain_references": []
        }
    },
    
    # Emotion only (no escalation)
    "emotion_only": {
        "pattern_keywords": ["furious", "angry", "frustrated"],
        "response": {
            "customer_name": None,
            "booking_reference": None,
            "flight_reference": None,
            "intent": "unknown",
            "requested_actions": [],
            "requested_amount": None,
            "requested_fare_difference": None,
            "hotel_scope_requested": None,
            "class_upgrade_requested": None,
            "alternate_flight_requested": None,
            "mentions_legal_action": False,
            "mentions_formal_complaint": False,
            "emotional_state": "furious",
            "uncertain_references": []
        }
    },
    
    # Prompt injection attempt
    "prompt_injection": {
        "pattern_keywords": ["ignore", "policy", "give me", "business class"],
        "response": {
            "customer_name": None,
            "booking_reference": None,
            "flight_reference": None,
            "intent": "class_upgrade_request",
            "requested_actions": ["business_class_upgrade"],
            "requested_amount": None,
            "requested_fare_difference": None,
            "hotel_scope_requested": None,
            "class_upgrade_requested": "business",
            "alternate_flight_requested": None,
            "mentions_legal_action": False,
            "mentions_formal_complaint": False,
            "emotional_state": "neutral",
            "uncertain_references": []
        }
    }
}
