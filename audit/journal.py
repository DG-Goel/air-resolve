"""
Audit journal implementation.

The journal is append-only from the application's perspective.
Events are stored in memory for this prototype.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class EventType:
    """Audit event type constants."""
    CASE_CREATED = "CASE_CREATED"
    POLICY_EVALUATED = "POLICY_EVALUATED"
    ACTION_AUTHORIZED = "ACTION_AUTHORIZED"
    ACTION_REJECTED = "ACTION_REJECTED"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    ESCALATION_CREATED = "ESCALATION_CREATED"


class AuditEvent(BaseModel):
    """
    Single audit event.
    
    Events are immutable once created.
    """
    event_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique event identifier"
    )
    event_type: Literal[
        "CASE_CREATED",
        "POLICY_EVALUATED",
        "ACTION_AUTHORIZED",
        "ACTION_REJECTED",
        "ACTION_EXECUTED",
        "ESCALATION_CREATED"
    ]
    timestamp: datetime = Field(default_factory=datetime.now)
    case_id: Optional[str] = None
    booking_reference: Optional[str] = None
    action_id: Optional[str] = None
    status: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        """Pydantic config."""
        frozen = True  # Make events immutable


class AuditJournal:
    """
    Append-only audit journal.
    
    For prototype, events are stored in memory.
    In production, this would write to persistent storage (database, log files, etc.).
    
    The journal provides:
    - Complete audit trail of all actions
    - Ability to reconstruct decision flow
    - Compliance and accountability
    """
    
    def __init__(self):
        """Initialize empty journal."""
        self._events: List[AuditEvent] = []
    
    def record(self, event: AuditEvent) -> None:
        """
        Record an audit event.
        
        Events are append-only and immutable.
        
        Args:
            event: Event to record
        """
        self._events.append(event)
    
    def list_events(
        self,
        event_type: Optional[str] = None,
        case_id: Optional[str] = None,
        booking_reference: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[AuditEvent]:
        """
        List audit events with optional filtering.
        
        Args:
            event_type: Filter by event type
            case_id: Filter by case ID
            booking_reference: Filter by booking reference
            limit: Maximum number of events to return (most recent first)
            
        Returns:
            List of matching events
        """
        events = self._events
        
        # Apply filters
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if case_id:
            events = [e for e in events if e.case_id == case_id]
        
        if booking_reference:
            events = [e for e in events if e.booking_reference == booking_reference]
        
        # Sort by timestamp (most recent first)
        events = sorted(events, key=lambda e: e.timestamp, reverse=True)
        
        # Apply limit
        if limit:
            events = events[:limit]
        
        return events
    
    def get_case_events(self, case_id: str) -> List[AuditEvent]:
        """
        Get all events for a specific case.
        
        Args:
            case_id: Case identifier
            
        Returns:
            List of events for this case (chronological order)
        """
        events = [e for e in self._events if e.case_id == case_id]
        return sorted(events, key=lambda e: e.timestamp)
    
    def get_booking_events(self, booking_reference: str) -> List[AuditEvent]:
        """
        Get all events for a specific booking.
        
        Args:
            booking_reference: Booking reference
            
        Returns:
            List of events for this booking (chronological order)
        """
        events = [e for e in self._events if e.booking_reference == booking_reference]
        return sorted(events, key=lambda e: e.timestamp)
    
    def count_events(
        self,
        event_type: Optional[str] = None,
        case_id: Optional[str] = None,
        booking_reference: Optional[str] = None
    ) -> int:
        """
        Count events matching filters.
        
        Args:
            event_type: Filter by event type
            case_id: Filter by case ID
            booking_reference: Filter by booking reference
            
        Returns:
            Count of matching events
        """
        return len(self.list_events(
            event_type=event_type,
            case_id=case_id,
            booking_reference=booking_reference
        ))
