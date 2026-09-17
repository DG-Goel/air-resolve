"""
Audit journal for AirResolve.

The audit journal provides an append-only log of all significant events:
- Case creation
- Policy evaluation
- Action authorization
- Action rejection
- Action execution
- Escalation creation

The journal enables complete reconstruction of:
- What the customer requested
- What policy decided
- What was allowed to execute
- What actually executed
- What was escalated
"""

from audit.journal import AuditJournal, AuditEvent, EventType

__all__ = ["AuditJournal", "AuditEvent", "EventType"]
