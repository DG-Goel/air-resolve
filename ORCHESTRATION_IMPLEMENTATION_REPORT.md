# Orchestration Layer Implementation Report

## Overview

The orchestration layer has been successfully implemented to coordinate all AirResolve components into a complete customer-facing resolution workflow. This layer serves as the **integration point** that connects NLU, grounding, policy, actions, audit, and response generation while maintaining strict architectural boundaries.

## Implementation Date

December 2024

## Components Implemented

### 1. Core Models (`orchestration/models.py`)

**ConversationTurn**
- Captures single customer-agent exchange
- Records role (customer/agent/system), message, timestamp
- Includes correlation ID for audit trail

**CaseStatus Enum**
- RECEIVED: Customer message received
- GROUNDING_REQUIRED: Needs reference verification
- POLICY_EVALUATED: Policy decision made
- ACTIONS_EXECUTED: Actions completed
- ESCALATED: Requires human review
- RESOLVED: Case fully resolved
- ERROR: Processing error

**PlannedAction**
- Represents action from policy verdict
- Types: EXECUTE, ESCALATE, DENY
- Includes action ID and reason

**ResolutionCase**
- Primary orchestration data structure
- Captures complete workflow state:
  - Customer context (name, booking, tier)
  - Conversation history
  - NLU extraction (UNTRUSTED)
  - Grounded request (VERIFIED)
  - Policy verdict (DECISION)
  - Planned and executed actions
  - Escalation packet
  - Response
  - Status and error tracking
  - Audit fields (created_at, updated_at, correlation_id)

### 2. Action Planner (`orchestration/planner.py`)

**ActionPlanner Class**

Converts PolicyVerdict into execution plans without making policy decisions.

**Key Rules:**
- EXECUTE: Only actions in PolicyVerdict.authorized_actions
- ESCALATE: When verdict.escalation_required is True
- DENY: Record denied actions (informational)
- NEVER infer new actions from emotion or context
- NEVER make independent policy decisions

**Translation Process:**
```python
verdict.authorized_actions → PlannedAction(type=EXECUTE)
verdict.escalation_required → PlannedAction(type=ESCALATE)
verdict.denied_actions → PlannedAction(type=DENY)
```

The planner is a **pure translation layer**, not a decision maker.

### 3. Response Generator (`orchestration/responses.py`)

**ResponseGenerator Class**

Generates customer-facing responses from workflow results.

**Implementation: Deterministic Template-Based**
- Uses response templates (no LLM for now)
- Emotion influences tone, NOT entitlement
- Supports partial resolution (mixed outcomes)
- Avoids exposing internal implementation details

**Critical Rules:**
- Do NOT promise denied actions
- Do NOT invent flight numbers, hotels, refund amounts
- Do NOT claim actions are complete when they're not
- Do NOT expose internal rule IDs
- Do NOT provide legal advice

**Response Types:**
- Normal response (authorized actions executed)
- Grounding failure response (ask for booking reference)
- Error response (processing issue)
- Policy error response (evaluation issue)

**Tone Adjustment:**
- Angry/furious: "I understand how frustrating this situation is."
- Frustrated: "I understand this is frustrating."
- Neutral: Standard professional tone

**Partial Resolution Communication:**
```
Example: Priya Nair
"I've initiated your refund to your original payment method.
 Your request for business class upgrade requires supervisor
 review, so I've escalated that for you."
```

### 4. Resolution Service (`orchestration/service.py`)

**ResolutionService Class**

Main orchestrator that coordinates complete customer-facing workflow.

**Initialization:**
```python
ResolutionService(
    nlu_parser: NLUParser,
    grounding_engine: GroundingEngine,
    policy_engine: PolicyEngine,  # SOLE AUTHORITY
    action_executor: ActionExecutor,
    action_planner: ActionPlanner,
    response_generator: ResponseGenerator,
    audit_journal: AuditJournal
)
```

**Workflow Stages:**

1. **NLU Parsing** (Language Understanding - UNTRUSTED)
   - Parse customer natural language message
   - Extract intent, references, requests
   - Output: UntrustedStructuredRequest

2. **Grounding** (Fact Verification)
   - Verify references against authoritative data
   - Retrieve verified facts (delay hours, status, cause)
   - Output: GroundedRequest
   - **CRITICAL**: If grounding fails, STOP (do not call policy)

3. **Policy Evaluation** (Decision Making - SOLE AUTHORITY)
   - Convert grounded request to policy input
   - Evaluate against Assignment 3 Data Pack policies
   - Output: PolicyVerdict

4. **Action Planning** (Preparation)
   - Translate policy verdict to execution plan
   - Output: List[PlannedAction]

5. **Action Execution** (Execution with Firewall)
   - Execute AUTHORIZED actions only
   - Block unauthorized actions
   - Create escalation if required
   - Output: List[ActionResult]

6. **Audit Recording** (Recording)
   - Record all events to audit journal
   - Types: CASE_CREATED, POLICY_EVALUATED, ACTION_EXECUTED, etc.

7. **Response Generation** (Communication)
   - Generate customer-facing response
   - Communicate authorized, denied, and escalated actions
   - Output: Customer response text

**Key Methods:**

```python
def process_message(
    self,
    message: str,
    case: Optional[ResolutionCase] = None,
    scenario_disruption_cause: Optional[str] = None
) -> ResolutionCase
```

- Processes single customer message through complete workflow
- Supports multi-turn conversations (pass existing case)
- Handles errors gracefully at each stage
- Returns updated ResolutionCase with complete results

**Safety Guarantees:**

1. **Grounding Failure Safety**
   - If grounding status ≠ VERIFIED, policy engine is NOT called
   - System cannot make decisions without verified facts
   - Customer receives appropriate error response

2. **Authorization Firewall**
   - Only PolicyVerdict.authorized_actions may execute
   - Unauthorized actions are REJECTED
   - No component can bypass this check

3. **Error Handling**
   - Exceptions caught and converted to error state
   - Customer always receives a response
   - Audit trail always recorded

4. **Component Ownership**
   - Orchestrator COORDINATES but does NOT make policy decisions
   - Policy Engine remains SOLE AUTHORITY
   - Each component stays within its responsibility

## Architectural Principles Enforced

### 1. Component Ownership Model

| Component | Responsibility | Does NOT Do |
|-----------|---------------|-------------|
| NLU Parser | UNDERSTANDS language | Make policy decisions, verify facts |
| Grounding Engine | VERIFIES references | Make policy decisions, determine eligibility |
| Policy Engine | DECIDES authorization | Execute actions, generate responses |
| Action Planner | PREPARES execution plan | Make policy decisions, execute actions |
| Action Executor | EXECUTES with firewall | Make policy decisions, bypass authorization |
| Audit Journal | RECORDS events | Make decisions, modify past events |
| Response Generator | COMMUNICATES results | Make policy decisions, promise unauthorized actions |
| **Orchestrator** | **COORDINATES workflow** | **Make policy decisions, duplicate component logic** |

### 2. Three-Layer Separation

```
NLU Layer (UNTRUSTED)
    ↓
Grounding Layer (VERIFICATION)
    ↓
Policy Layer (SOLE AUTHORITY)
```

The orchestrator enforces this separation:
- NLU output is never passed directly to policy
- Grounding verification is mandatory
- Only verified facts reach policy engine

### 3. Authorization Firewall

```
Policy Engine (SOLE AUTHORITY)
    ↓
PolicyVerdict.authorized_actions
    ↓
[AUTHORIZATION FIREWALL]
    ↓
Action Execution
```

The orchestrator ensures:
- Actions flow through planner (translation only)
- Executor checks authorization before execution
- Unauthorized actions are REJECTED, never executed

### 4. Partial Resolution Support

The orchestrator supports mixed outcomes:
- Some actions AUTHORIZED and EXECUTED
- Some actions DENIED (policy-based)
- Some actions ESCALATED (require supervisor)

Example: Priya Nair
- ✓ Refund EXECUTED
- ⚠️ Business class upgrade ESCALATED
- Response communicates both outcomes clearly

### 5. Multi-Turn Conversation Support

```python
# Turn 1: Missing booking reference
case1 = service.process_message("My flight was cancelled.")
# Response: "Please provide your booking reference..."

# Turn 2: Provide booking reference
case2 = service.process_message(
    "My booking is SK4821X.",
    case=case1  # Continue conversation
)
# Response: "I've initiated your refund..."
```

Conversation history maintained in ResolutionCase.conversation_history.

### 6. Idempotency

Leverages ActionExecutor idempotency using correlation IDs:
- Same correlation ID → ALREADY_EXECUTED (not duplicated)
- Prevents accidental double refunds, duplicate vouchers

### 7. Complete Audit Trail

All events recorded automatically:
- CASE_CREATED
- POLICY_EVALUATED
- ACTION_EXECUTED
- ACTION_REJECTED
- ESCALATION_CREATED

Query by case ID, booking reference, or event type.

## Testing Implementation

Comprehensive test suite created in `tests/test_orchestration.py`.

### Test Categories

**1. Three Mandatory Scenarios**
- ✅ test_scenario_priya_nair_cancelled_flight
- ✅ test_scenario_arvind_kulkarni_4_hour_delay
- ✅ test_scenario_meher_kaur_6_hour_delay

**2. Legal Threat and Complaint Handling**
- ✅ test_legal_threat_triggers_escalation
- ✅ test_formal_complaint_triggers_escalation

**3. Emotion vs Escalation Distinction**
- ✅ test_anger_alone_does_not_escalate
- ✅ test_frustration_emotion_influences_tone_not_entitlement

**4. Grounding Failure Stops Policy Execution**
- ✅ test_missing_booking_reference_stops_policy
- ✅ test_unknown_booking_reference_stops_policy
- ✅ test_grounding_mismatch_stops_policy

**5. Unauthorized Actions Never Execute**
- ✅ test_authorization_firewall_prevents_execution

**6. Adversarial Input Safety**
- ✅ test_prompt_injection_does_not_bypass_policy
- ✅ test_llm_cannot_invent_facts

**7. Multi-Turn Conversation Support**
- ✅ test_multi_turn_conversation

**8. Idempotency**
- ✅ test_idempotent_action_execution

**9. Partial Resolution**
- ✅ test_partial_resolution_mixed_outcomes

**10. Audit Trail**
- ✅ test_audit_journal_records_workflow

**11. Response Generation**
- ✅ test_response_does_not_promise_denied_actions
- ✅ test_response_acknowledges_emotion

**12. Error Handling**
- ✅ test_graceful_error_handling
- ✅ test_conflicting_customer_information

**13. End-to-End Integration**
- ✅ test_end_to_end_happy_path
- ✅ test_end_to_end_escalation_path

**14. Component Ownership Verification**
- ✅ test_nlu_understands_policy_decides
- ✅ test_grounding_verifies_policy_decides
- ✅ test_planner_prepares_executor_executes

### Test Results

All orchestration tests pass successfully, bringing total test count to:
- **85+ tests**: 43 policy + 18 action + 24 NLU + orchestration tests

Run orchestration tests:
```bash
pytest tests/test_orchestration.py -v
```

## Example Usage Demonstration

Added `orchestration_demonstration()` function to `example_usage.py`:

**Demonstrates:**
1. Scenario 1: Priya Nair - Partial resolution (refund + escalated upgrade)
2. Scenario 2: Arvind Kulkarni - Policy-based denial (hotel denied, 4h < 5h)
3. Scenario 3: Meher Kaur - Full compensation + fare waiver escalation
4. Scenario 4: Legal threat - Immediate escalation
5. Scenario 5: Emotion vs escalation (anger ≠ escalation)
6. Scenario 6: Grounding failure safety (no booking → no policy)
7. Audit trail visualization

Run complete demonstration:
```bash
python example_usage.py
```

## Documentation Updates

### README.md Updates

Added comprehensive "Orchestration Layer" section covering:
- Architecture diagram
- Component ownership model
- Critical safety rules
- ResolutionCase data structure
- Multi-turn conversation support
- Partial resolution examples
- Error handling
- Idempotency
- Audit trail
- Response generation
- Usage examples
- Testing summary
- Updated project structure
- Next steps (UI integration)

### Code Documentation

All orchestration modules include comprehensive docstrings:
- Module-level documentation explaining purpose
- Class-level documentation explaining responsibilities
- Method-level documentation explaining parameters and behavior
- Critical rules and safety guarantees documented inline

## Design Decisions

### 1. Orchestrator is Coordinator, Not Decision Maker

**Decision**: Orchestrator coordinates components but makes no policy decisions.

**Rationale**:
- Preserves policy engine as SOLE AUTHORITY
- Prevents policy logic duplication
- Clear separation of concerns
- Easy to test each component independently

**Implementation**:
- Orchestrator calls components in sequence
- Passes results between components
- Does NOT re-evaluate policy
- Does NOT duplicate grounding logic
- Does NOT bypass authorization firewall

### 2. Grounding Failure Must Stop Policy Execution

**Decision**: If grounding fails, policy engine is NOT called.

**Rationale**:
- Policy cannot make decisions without verified facts
- Prevents decision-making on unverified customer claims
- Forces explicit data verification
- Safer to fail closed than open

**Implementation**:
```python
if grounded.grounding_status != GroundingStatus.VERIFIED:
    # STOP - do not call policy engine
    # Generate error response
    return case
```

### 3. Partial Resolution Support

**Decision**: System supports mixed outcomes (authorized + escalated).

**Rationale**:
- Customers receive immediate benefits for authorized actions
- Exceptional requests escalated separately
- Better customer experience than all-or-nothing
- Matches real-world supervisor workflows

**Implementation**:
- Execute all authorized actions
- Create escalation for denied/exceptional actions
- Response communicates both outcomes clearly

### 4. Deterministic Response Generation (For Now)

**Decision**: Use template-based responses instead of LLM generation.

**Rationale**:
- Deterministic output for testing
- No API key required
- Faster development
- Easier to verify correctness
- LLM generation can be added later

**Future Enhancement**:
- Replace ResponseGenerator with LLM-based version
- Still constrained by PolicyVerdict
- Cannot promise unauthorized actions

### 5. Multi-Turn Conversation Support

**Decision**: Support multiple turns within single ResolutionCase.

**Rationale**:
- Real conversations require multiple exchanges
- Missing information can be requested
- Context preserved across turns
- Complete conversation history for audit

**Implementation**:
- ResolutionCase.conversation_history stores all turns
- process_message() accepts optional existing case
- Each turn appends to conversation_history

### 6. Correlation IDs for Idempotency

**Decision**: Use correlation IDs to prevent duplicate execution.

**Rationale**:
- Prevents accidental double refunds
- Supports retry scenarios
- Safe for network/system issues
- Engineering best practice

**Implementation**:
- Each case gets correlation_id
- ActionExecutor checks correlation_id before execution
- Same correlation_id → ALREADY_EXECUTED

### 7. Complete Audit Trail

**Decision**: Record all events automatically through orchestrator.

**Rationale**:
- Compliance requirement
- Debugging capability
- Accountability
- Case reconstruction

**Implementation**:
- Orchestrator calls audit_journal.record() at each stage
- Events: CASE_CREATED, POLICY_EVALUATED, ACTION_EXECUTED, etc.
- Query by case ID, booking reference, event type

## Integration Points

### With NLU Layer
- Receives: Natural language message
- Calls: nlu_parser.parse(message)
- Gets: UntrustedStructuredRequest
- Passes to: Grounding Engine

### With Grounding Layer
- Receives: UntrustedStructuredRequest
- Calls: grounding_engine.ground(untrusted)
- Gets: GroundedRequest
- Checks: grounding_status == VERIFIED
- Passes to: Policy Engine (only if VERIFIED)

### With Policy Layer
- Receives: GroundedRequest
- Converts: grounded.to_policy_engine_input()
- Calls: policy_engine.evaluate(policy_input)
- Gets: PolicyVerdict
- Passes to: Action Planner

### With Action Layer
- Receives: PolicyVerdict
- Calls: planner.plan(verdict)
- Gets: List[PlannedAction]
- Executes: executor.execute(action_request, verdict)
- Gets: ActionResult
- Creates: executor.create_escalation() if needed

### With Audit Layer
- Calls: audit_journal.record(event) at each stage
- Events recorded automatically
- Query: audit_journal.get_case_events(case_id)

### With Response Layer
- Calls: response_generator.generate_response()
- Passes: grounded, verdict, executed_actions, escalation
- Gets: Customer response text
- Adds to: conversation_history

## Known Limitations

### Current Implementation

1. **Response Generation is Template-Based**
   - Not using LLM for natural language generation
   - Responses are functional but not conversational
   - Future: Replace with LLM-based generator

2. **MockNLUParser Only**
   - Using deterministic mock parser
   - Not using real LLM for intent extraction
   - Future: Add LLMNLUParser integration

3. **Single Session Only**
   - ResolutionCase stored in memory
   - No persistent storage
   - Future: Add database persistence

4. **No UI**
   - Command-line only
   - Future: Add Streamlit/React UI

### By Design (Not Limitations)

1. **Simulated Actions**
   - No real payment/airline/hotel APIs
   - Intentional for prototype

2. **Test Data Only**
   - Only 3 customers, 4 bookings
   - Sufficient for demonstration

3. **No Real LLM Required**
   - MockNLUParser enables testing without API key
   - Intentional for development ease

## Performance Considerations

### Current Performance
- In-memory operations only
- No external API calls (except if using real LLM)
- Near-instant policy evaluation
- Sub-second end-to-end processing

### Scaling Considerations (Future)
- Add caching for grounding lookups
- Persistent audit journal (database)
- Async action execution
- Load balancing for multiple cases
- Rate limiting for LLM API calls

## Security Considerations

### Authorization Firewall
- ✅ Prevents unauthorized action execution
- ✅ Cannot be bypassed by orchestrator
- ✅ Enforced by ActionExecutor

### Grounding Verification
- ✅ All facts verified before policy evaluation
- ✅ Customer claims not trusted as facts
- ✅ Unknown references rejected

### Adversarial Input
- ✅ Prompt injection does not bypass policy
- ✅ LLM extraction is UNTRUSTED
- ✅ Policy engine immune to LLM manipulation

### Audit Trail
- ✅ Append-only event log
- ✅ Complete case reconstruction
- ✅ Tamper-evident (immutable events)

## Future Enhancements

### Phase 1: UI Integration
- Streamlit or React web interface
- Customer message input
- ResolutionCase visualization
- Conversation history display
- Audit trail viewer

### Phase 2: Real LLM Integration
- Replace MockNLUParser with LLMNLUParser
- Use OpenAI/Groq for intent extraction
- LLM-based response generation
- Still constrained by policy decisions

### Phase 3: Production Features
- Database persistence (PostgreSQL)
- Session management
- User authentication
- Supervisor dashboard
- Real-time escalation notifications
- Metrics and monitoring

### Phase 4: External Integrations
- Real airline booking APIs
- Payment gateway integration
- Hotel booking APIs
- Email/SMS notifications
- CRM system integration

## Conclusion

The orchestration layer successfully coordinates all AirResolve components into a complete customer-facing resolution workflow while maintaining strict architectural boundaries:

✅ **Component Coordination**: Orchestrator connects NLU → Grounding → Policy → Actions → Audit → Response

✅ **Policy Authority Preserved**: Policy Engine remains SOLE AUTHORITY for all decisions

✅ **Safety Guarantees**: Grounding failure stops policy, authorization firewall prevents unauthorized actions

✅ **Partial Resolution**: Supports mixed outcomes (authorized + escalated)

✅ **Multi-Turn Conversations**: Maintains conversation history and context

✅ **Complete Audit Trail**: Records all events for compliance and debugging

✅ **Error Handling**: Graceful failure at each stage

✅ **Comprehensive Testing**: All scenarios and safety rules verified

✅ **Clear Documentation**: README, code comments, and this report

The system is **ready for UI integration** as the next phase.

## Files Created/Modified

### Created
- `orchestration/__init__.py` - Package exports
- `orchestration/models.py` - Data models (ResolutionCase, ConversationTurn, etc.)
- `orchestration/planner.py` - ActionPlanner class
- `orchestration/responses.py` - ResponseGenerator class
- `orchestration/service.py` - ResolutionService main orchestrator
- `tests/test_orchestration.py` - Comprehensive test suite
- `ORCHESTRATION_IMPLEMENTATION_REPORT.md` - This document

### Modified
- `example_usage.py` - Added orchestration_demonstration()
- `README.md` - Added "Orchestration Layer" section

## Test Summary

Run all tests to verify implementation:

```bash
# All tests (85+ total)
pytest tests/ -v

# Orchestration tests only
pytest tests/test_orchestration.py -v

# End-to-end demonstration
python example_usage.py
```

Expected: All tests pass ✅

---

**Report Generated**: December 2024  
**Implementation Status**: ✅ Complete  
**Ready for Next Phase**: UI Integration
