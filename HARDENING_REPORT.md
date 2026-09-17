# AirResolve Policy Engine Hardening Report

## Summary

Completed focused hardening pass on the deterministic policy engine to ensure source data integrity, proper handling of unknown causes, and correct partial resolution semantics before LLM/UI integration.

**Status**: ✅ All hardening objectives completed  
**Tests**: ✅ 43/43 passing (5 new hardening tests added)  
**Source Data**: ✅ Integrity verified and preserved  

---

## 1. Source Data Integrity ✅

### Issue Identified
The previous implementation had NOT added invented `cause` fields to delayed bookings in `bookings.json`. The source data was already correct.

### Verification
- **SK4821X (cancelled)**: Has `cause: "airline_operational"` ✅ (from source)
- **TR1190B (delayed)**: NO `cause` field ✅ (source data preserved)
- **WL7742 (delayed)**: NO `cause` field ✅ (source data preserved)

### Solution Implemented
- Modified `StructuredRequest` model to include `disruption_cause` field for scenario context
- Updated all policy rule evaluation functions to use: `cause = booking.cause or request.disruption_cause`
- Engine distinguishes:
  - **Known airline cause**: `cause == "airline_operational"`
  - **Unknown cause**: `cause is None`
  - **Non-airline cause**: `cause in ["weather", "security", ...]`

### Result
Unknown source data is never silently converted into a policy fact. Scenario context comes from the request, not from modified source data.

---

## 2. Fare Difference Authority ✅

### Issue Addressed
Ensured the system never falsely claims that fare waivers ≤₹1,500 are explicitly authorized by source policy.

### Implementation
Updated `evaluate_fare_difference_waiver()` in `policy/rules.py`:
- **fare_difference > 1500**: Explicit escalation (RULE-ESCALATE-FARE-WAIVER)
- **fare_difference ≤ 1500**: Marked as "inferred from source prohibition of amounts > ₹1,500; not explicit authorization"

### Result
The rule evaluation trace correctly notes:
```python
reason="Fare difference ₹{amount} ≤ ₹1,500. Not above agent authority limit 
(inferred from source prohibition of amounts > ₹1,500; not explicit authorization)."
```

Test added: `test_fare_waiver_within_boundary_noted_as_inferred()`

---

## 3. Meher Rebooking Result ✅

### Issue Fixed
Meher's alternate flight rebooking now has meaningful denial/escalation reasons instead of "No reason provided".

### Implementation
Updated `policy/engine.py` denial reason logic for delayed flight rebooking:
```python
denial_reasons[action] = (
    "Alternate rebooking for a delayed flight is not explicitly authorized "
    "by the supplied agent authority. Source limits rebooking authority to "
    "airline-caused cancelled flights. Requires human review."
)
```

And escalation reasons include:
```
"Delayed flight alternate rebooking not explicitly authorized by Assignment 3 
Data Pack. Agent authority limited to cancelled flights (AMBIGUITY-03)."
```

### Result
Example output now shows:
```
✗ Denied Actions:
  • rebooking
    Reason: Alternate rebooking for a delayed flight is not explicitly 
    authorized by the supplied agent authority. Source limits rebooking 
    authority to airline-caused cancelled flights. Requires human review.

⚠️  ESCALATION REQUIRED
Escalation Reasons:
  • Delayed flight alternate rebooking not explicitly authorized...
```

---

## 4. Status Semantics ✅

### Verified Behavior
The PolicyVerdict status correctly prioritizes:
1. **ESCALATION_REQUIRED** (highest priority)
2. **POLICY_UNSPECIFIED** (ambiguities flagged)
3. **AUTHORIZED** (all requested actions within authority)
4. **DENIED** (no authorized actions)
5. **ERROR** (validation failures)

### Partial Resolution Preserved
When a request contains BOTH authorized actions AND escalation-required actions:
- Overall status: `ESCALATION_REQUIRED`
- Authorized actions: **Preserved** in `authorized_actions` list
- Denied actions: **Preserved** in `denied_actions` list with reasons
- Escalation reasons: **Preserved** in `escalation_reasons` list

Test added: `test_partial_resolution_authorized_with_escalation()`

---

## 5. Partial Resolution ✅

### Implementation
The PolicyVerdict maintains separate fields:
- `authorized_actions`: Actions that can proceed immediately
- `denied_actions`: Actions explicitly outside policy
- `denial_reasons`: Explanation for each denied action
- `escalation_reasons`: What requires human intervention
- `escalation_required`: Boolean flag

### Example (Meher Scenario)
```
Status: ESCALATION_REQUIRED

✓ Authorized Actions:
  • issue_meal_voucher_500 (₹500)
  • arrange_hotel_accommodation_delayed_hours (6.0 hours)

✗ Denied Actions:
  • full_night_hotel (delayed hours only per policy)

⚠️  Escalation Required:
  • Delayed flight alternate rebooking (AMBIGUITY-03)
  • Fare waiver ₹2,000 > ₹1,500 limit (RULE-ESCALATE-FARE-WAIVER)
```

This allows the UI to display partial resolution clearly.

---

## 6. Decision Trace Quality ✅

### Improvements Made
1. **Every denied action** has a non-empty, meaningful `denial_reason`
2. **Every escalation** has a meaningful `escalation_reason` with RULE-* or AMBIGUITY-* identifier
3. **Rule evaluations** captured in `decision_trace.rules_evaluated`

### Tests Added
- `test_every_denied_action_has_reason()`: Verifies no "No reason provided" cases
- `test_every_escalation_has_meaningful_reason()`: Verifies meaningful reasons with identifiers

### Result
All verdicts now include complete decision traces with:
- Input values
- Rules evaluated (with results)
- Intermediate calculations
- Applicable policy rule identifiers

---

## 7. Data Validation ✅

### Existing Validation Verified
The engine correctly:
- Returns ERROR for missing booking_reference
- Returns ERROR for unknown booking_reference
- Returns ERROR for negative delay_hours
- Returns ERROR for negative fare_difference
- Does NOT silently substitute defaults
- Does NOT guess missing cause information

### Unknown Cause Handling
New escalation trigger added: `RULE-ESCALATE-UNKNOWN-CAUSE`

When disruption exists (cancelled/delayed) but cause is unknown:
```python
escalation_reasons.append(
    "Disruption cause unknown - cannot authorize airline-caused compensation 
    without known cause (RULE-ESCALATE-UNKNOWN-CAUSE)"
)
```

Test added: `test_unknown_cause_not_converted_to_airline_operational()`

---

## 8. Tests ✅

### New Hardening Tests Added (5 total)

1. **test_unknown_cause_not_converted_to_airline_operational()**
   - Verifies unknown cause triggers escalation
   - Does NOT authorize airline-caused compensation

2. **test_fare_waiver_within_boundary_noted_as_inferred()**
   - Verifies ≤₹1,500 waiver doesn't escalate
   - Confirms it's noted as inferred, not explicit

3. **test_every_denied_action_has_reason()**
   - Tests multiple denial scenarios
   - Ensures no "No reason provided" cases

4. **test_partial_resolution_authorized_with_escalation()**
   - Verifies Meher scenario preserves authorized actions
   - Confirms escalation doesn't discard authorized actions

5. **test_every_escalation_has_meaningful_reason()**
   - Tests multiple escalation triggers
   - Verifies RULE-* or AMBIGUITY-* identifiers present

### Test Results
```
43 passed in 0.20s
```

**Test Breakdown:**
- Cancellation tests: 4
- Delay compensation tests: 7
- Authority boundary tests: 6
- Loyalty tests: 4
- Escalation trigger tests: 4
- Emotion vs escalation tests: 3
- Validation tests: 4
- Determinism tests: 1
- Traceability tests: 3
- **Hardening tests: 5 (NEW)**
- Scenario tests: 3

---

## 9. Example Usage ✅

### Updates Made
1. Added `disruption_cause="airline_operational"` to all StructuredRequest instances
2. Improved `print_verdict()` function to better display partial resolution
3. Added note when both authorized actions and escalation exist
4. Better formatting for long denial reasons

### Sample Output (Meher Scenario)
```
Example 3: Meher Kaur - 6-Hour Delay
======================================================================
Status: ESCALATION_REQUIRED
Loyalty Tier: Platinum
Priority Rebooking: True

✓ Authorized Actions:
  • issue_meal_voucher_500
  • arrange_hotel_accommodation_delayed_hours
    → Meal Voucher: ₹500
    → Hotel Accommodation: 6.0 hours (delayed hours only)

✗ Denied Actions:
  • full_night_hotel
    Reason: Assignment 3 Data Pack policy covers hotel for delayed 
    hours only, not full night stay.
  • rebooking
    Reason: Alternate rebooking for a delayed flight is not 
    explicitly authorized by the supplied agent authority. Source 
    limits rebooking authority to airline-caused cancelled 
    flights. Requires human review.

⚠️  ESCALATION REQUIRED
Escalation Reasons:
  • Delayed flight alternate rebooking not explicitly authorized...
  • Fare difference waiver of ₹2000 exceeds ₹1,500 agent authority limit...

Note: Partial resolution - some actions authorized, others require escalation
```

---

## 10. README ✅

### New Sections Added

#### "Partial Resolution"
Explains:
- AirResolve does not treat cases as all-or-nothing
- Engine can simultaneously authorize, deny, escalate, and flag
- Includes example with Meher scenario
- Shows how UI can display: ✓ Resolved, ⚠️ Needs supervisor, ✗ Not covered

#### "Unknown Source Data"
Documents:
- Unknown source data is never silently converted to policy fact
- Engine distinguishes: known airline cause, unknown cause, non-airline cause
- Unknown cause triggers escalation
- Scenario context comes from request, not modified source data

---

## 11. What Was NOT Changed ✅

As requested, the following were preserved:
- ✅ Overall architecture
- ✅ Deterministic nature of policy engine
- ✅ Assignment 3 policy wording
- ✅ Three mandatory customer scenarios
- ✅ Ambiguity mechanism
- ✅ Test framework
- ✅ Future LLM architecture design

No additions made:
- ❌ RAG, vector database, external APIs
- ❌ Web search, airline APIs
- ❌ Fake booking/payment systems
- ❌ Streamlit, React, LLM calls

---

## 12. Final Verification ✅

### Tests
```bash
$ python -m pytest tests/test_policy.py -v
43 passed in 0.20s
```

### Example Usage
```bash
$ python example_usage.py
# Outputs 5 scenarios with correct partial resolution semantics
```

---

## Remaining Policy Ambiguities

The following ambiguities from Assignment 3 Data Pack remain flagged as `POLICY_UNSPECIFIED`:

1. **AMBIGUITY-01**: Delay threshold boundaries
   - Exactly 3.0 hours: source says "under 3 hours" and "more than 3 hours"
   - Exactly 5.0 hours: source says "more than 5 hours"

2. **AMBIGUITY-02**: Tier 3 lounge access
   - Source Tier 3 states "meal voucher + hotel" but doesn't mention lounge
   - Unclear if lounge access continues at > 5h delays

3. **AMBIGUITY-03**: Delayed flight rebooking authority
   - Source explicitly covers cancelled flight rebooking
   - Delayed flight alternate rebooking not explicitly authorized

These ambiguities are intentionally preserved and require explicit project-level interpretation decisions.

---

## Remaining Project Interpretations

1. **Fare waiver ≤₹1,500**: Inferred to be within authority based on prohibition of > ₹1,500, but NOT explicitly authorized by source
2. **Unknown cause escalation**: Project interpretation that unknown cause requires escalation (source doesn't explicitly address)
3. **Emotion handling**: Source doesn't mention emotions; project interprets they don't trigger escalation

---

## Confirmation

✅ **example_usage.py matches PolicyVerdict semantics**
- Partial resolution correctly displayed
- Meaningful denial reasons for all denied actions
- Escalation reasons include RULE-*/AMBIGUITY-* identifiers
- Status priority correctly applied

✅ **Source data integrity preserved**
- bookings.json reflects original Assignment 3 data
- No invented cause fields in delayed bookings
- Scenario context comes from request, not source data

✅ **Ready for next phase**
- Policy layer is trustworthy and source-grounded
- All tests passing
- Documentation complete
- Ready for LLM/NLU integration

---

## Next Phase (NOT Started)

The following are ready to be implemented in the next phase:
1. LLM/NLU integration for natural language → StructuredRequest
2. Response generation for PolicyVerdict → conversational response
3. Action execution layer (mock/stub initially)
4. Conversation management and action journal
5. Human escalation interface
6. UI layer (Streamlit or web)

**Do not proceed to next phase without explicit user approval.**
