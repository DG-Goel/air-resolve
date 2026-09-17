# NLU Layer Implementation Report

## Summary

Successfully implemented the Natural Language Understanding (NLU) layer for AirResolve with strict architectural separation between language understanding and policy decisions.

## Files Created

### Core NLU Package (`nlu/`)

1. **`nlu/__init__.py`**
   - Package initialization
   - Exports: CustomerIntent, GroundingStatus, UntrustedStructuredRequest, GroundedRequest, NLUParser, MockNLUParser, LLMNLUParser, GroundingEngine

2. **`nlu/models.py`**
   - `CustomerIntent` enum: Controlled vocabulary for intents (refund_request, rebooking_request, hotel_request, etc.)
   - `GroundingStatus` enum: VERIFIED, UNRESOLVED, MISMATCH, INCOMPLETE, ERROR
   - `UntrustedStructuredRequest`: UNTRUSTED LLM extraction output
     - Contains: customer claims, references, requests, emotions
     - Does NOT contain: verified facts, policy decisions, entitlements
   - `GroundedRequest`: VERIFIED facts after grounding
     - Contains: original untrusted request + verified customer/booking/flight data
     - `to_policy_engine_input()`: Converts to StructuredRequest with verified facts only

3. **`nlu/parser.py`**
   - `LLMProvider` protocol: Abstraction for LLM providers (OpenAI, Groq, etc.)
   - `NLUParser` abstract base class
   - `MockNLUParser`: **Deterministic** mock for testing (no API key required)
     - Pattern matching against known test cases
     - Falls back to basic regex extraction
   - `LLMNLUParser`: Optional real LLM implementation (requires provider)

4. **`nlu/grounding.py`**
   - `GroundingEngine`: Verifies references against authoritative data
     - Loads customers.json and bookings.json
     - Resolves customer by booking reference or name
     - Verifies flight references match bookings
     - Detects mismatches (customer claims wrong booking)
     - Rejects unknown references
     - Returns GroundedRequest with verification status

5. **`nlu/prompts.py`**
   - `SYSTEM_PROMPT`: LLM constraints (what LLM can/cannot extract)
   - `create_extraction_prompt()`: Formats extraction prompts
   - `MOCK_RESPONSES`: Deterministic responses for testing
     - Priya, Arvind, Meher scenarios
     - Legal escalation, emotion-only, prompt injection patterns

### Tests (`tests/test_nlu.py`)

Created **24 comprehensive NLU tests**:

**Mock Parser Tests (8 tests):**
- Priya scenario (refund + upgrade)
- Arvind scenario (hotel request)
- Meher scenario (full night hotel + alternate flight + fare waiver)
- Legal escalation (explicit threat detection)
- Formal complaint detection
- Emotion only (no automatic escalation)
- Prompt injection attempt (adversarial input)
- Uncertain language handling

**Grounding Engine Tests (8 tests):**
- Verified Priya references (all fields correct)
- Verified Arvind references
- Verified Meher references
- Unknown booking reference → UNRESOLVED
- Booking/customer mismatch detection
- Incomplete references → INCOMPLETE
- Grounding does NOT trust LLM-supplied disruption cause
- Grounding does NOT trust LLM-supplied delay hours
- Grounding does NOT trust LLM-supplied loyalty tier

**Integration Tests (6 tests):**
- Priya full flow (NLU → Grounding → Policy)
- Arvind full flow
- Meher full flow
- Ungrounded request cannot be processed
- Emotion does not affect policy decisions
- Mock parser determinism
- Grounding determinism

**Total Test Count: 85 tests**
- 43 policy tests (existing, all passing)
- 18 action tests (existing, all passing)
- 24 NLU tests (new, all passing)

### Documentation Updates

1. **README.md**
   - Updated core architecture diagram with NLU flow
   - Added "NLU/Grounding Architecture" section
   - Documented three-layer NLU stack
   - Explained critical design principles
   - Added adversarial input handling examples
   - Updated usage examples with full NLU flow
   - Updated test count and file structure

2. **example_usage.py**
   - Added `nlu_demonstration()` function
   - 5 NLU examples:
     - Priya full end-to-end flow
     - Arvind delayed flight
     - Prompt injection attempt
     - Grounding does not trust customer claims
     - Emotion vs escalation distinction
   - Demonstrates complete flow: Natural Language → NLU → Grounding → Policy

## Architecture Principles Enforced

### 1. LLM Output is UNTRUSTED

✓ LLM produces `UntrustedStructuredRequest`
✓ Clearly documented as untrusted
✓ Must go through grounding before policy evaluation
✓ Cannot bypass authorization firewall

### 2. Three-Layer Separation

```
1. NLU Parser → UntrustedStructuredRequest (customer claims)
2. Grounding Engine → GroundedRequest (verified facts)
3. Policy Engine → PolicyVerdict (decisions)
```

### 3. LLM Cannot Invent Facts

**LLM CANNOT extract/invent:**
- Customer data (loyalty tier, travel history)
- Booking data (status, delays, causes)
- Flight data (cancellations, disruptions)
- Disruption causes
- Delay hours
- Entitlements
- Policy decisions

**LLM CAN ONLY extract:**
- Customer name (if mentioned)
- Booking reference (if mentioned)
- Flight reference (if mentioned)
- Requested actions
- Emotional tone
- Explicit legal/complaint language

### 4. Grounding Verifies ALL Facts

✓ Customer identity verified against customers.json
✓ Booking verified against bookings.json
✓ Flight references verified
✓ Mismatches detected and rejected
✓ Unknown references rejected
✓ Only verified facts passed to policy engine

### 5. Policy Engine Remains Sole Authority

✓ No LLM involvement in policy decisions
✓ Deterministic evaluation
✓ Same inputs → same outputs
✓ All 43 existing policy tests still passing

### 6. Adversarial Safety

✓ Prompt injection attempts handled safely
✓ LLM cannot bypass policy
✓ LLM cannot authorize actions
✓ LLM cannot override rules
✓ All requests evaluated by policy engine

### 7. Emotion vs Escalation

✓ Emotion alone does NOT trigger escalation
✓ "furious", "angry", "frustrated" → no escalation
✓ Explicit threats/complaints → escalation
✓ "legal action", "sue", "formal complaint" → escalation

## Key Features

### MockNLUParser (Testing)

- **Deterministic**: Same input → same output
- **No API key required**: Pattern matching only
- **Complete coverage**: All test scenarios supported
- **Fallback extraction**: Basic regex for unknown patterns

### Grounding Status Types

- `VERIFIED`: All references verified
- `UNRESOLVED`: Reference not found
- `MISMATCH`: Reference exists but doesn't match
- `INCOMPLETE`: Missing required references
- `ERROR`: Grounding process error

### GroundedRequest.to_policy_engine_input()

- Converts grounded request to policy engine input
- Returns `None` if grounding failed
- Passes ONLY verified facts
- Supports scenario_disruption_cause parameter

## Testing Results

```bash
$ python -m pytest tests/ -v
======================== 85 passed, 1 warning in 0.28s ========================

Breakdown:
- 43 policy tests ✓ (all existing tests still passing)
- 18 action tests ✓ (all existing tests still passing)
- 24 NLU tests ✓ (all new tests passing)
```

### Example Usage Output

```bash
$ python example_usage.py
```

Successfully demonstrates:
- Policy engine evaluation (5 examples)
- Action layer authorization firewall
- Audit journal
- Idempotency
- Full NLU flow (5 examples)
- Adversarial input handling
- Grounding verification
- Complete end-to-end flow

## Remaining Limitations

### Not Implemented (By Design)

1. **Real LLM integration** - Using MockNLUParser for testing
   - Next step: Integrate OpenAI/Groq with LLMNLUParser
   - Provider abstraction ready

2. **Web UI** - No Streamlit/React interface yet
   - Next step: Build UI on top of existing NLU layer

3. **Conversational response generation** - PolicyVerdict → natural language
   - Next step: LLM response generation from verdict

4. **Multi-turn dialog** - Single-turn request/response only
   - Next step: Conversation state management

5. **Real external APIs** - All actions simulated
   - By design for prototype

## Verification Checklist

✅ **Architecture**
- [x] LLM is NOT the policy decision-maker
- [x] Three-layer separation (NLU → Grounding → Policy)
- [x] LLM output treated as UNTRUSTED
- [x] Grounding verifies all facts
- [x] Policy engine remains sole authority

✅ **Implementation**
- [x] UntrustedStructuredRequest model
- [x] GroundedRequest model
- [x] NLUParser abstraction
- [x] MockNLUParser (deterministic, no API key)
- [x] LLMNLUParser (optional, provider abstraction)
- [x] GroundingEngine
- [x] Reference verification logic
- [x] Mismatch detection
- [x] Unknown reference handling

✅ **Testing**
- [x] 24 NLU tests created
- [x] All 43 policy tests still passing
- [x] All 18 action tests still passing
- [x] Mock parser determinism verified
- [x] Grounding determinism verified
- [x] Integration tests (NLU → Policy)
- [x] Adversarial input tests
- [x] Emotion vs escalation tests

✅ **Documentation**
- [x] README updated with NLU architecture
- [x] example_usage.py extended with NLU demo
- [x] Code comments and docstrings
- [x] Architecture principles documented
- [x] What LLM can/cannot do documented

✅ **Safety**
- [x] LLM cannot invent facts
- [x] LLM cannot authorize actions
- [x] LLM cannot bypass policy
- [x] Prompt injection handled safely
- [x] Customer claims verified before use
- [x] Unknown references rejected

## Conclusion

The NLU layer is complete and ready for the next phase (UI integration). All architectural principles are enforced, all tests passing, and the system maintains strict separation between language understanding and policy decisions.

**Key Achievement:** Successfully demonstrated that an LLM-based system can be built with the LLM serving ONLY as a language understanding component, NOT as a decision-maker. All policy authority remains with the deterministic Python policy engine.
