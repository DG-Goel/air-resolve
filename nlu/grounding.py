"""
Grounding Engine for verifying customer claims against authoritative data.

The grounding engine's job is NOT to make policy decisions.
Its job is to resolve references and verify facts against source data.
"""

import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from nlu.models import (
    UntrustedStructuredRequest,
    GroundedRequest,
    GroundingStatus
)
from policy.models import CustomerData, BookingData


class GroundingEngine:
    """
    Verifies customer references against authoritative data.
    
    CRITICAL: This engine does NOT make policy decisions.
    It only verifies:
    - Customer references exist
    - Booking references exist
    - Flight references match bookings
    - Retrieves authoritative facts from source data
    
    Policy decisions remain with PolicyEngine.
    """
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize grounding engine with data directory.
        
        Args:
            data_dir: Path to directory containing customers.json, bookings.json
        """
        self.data_dir = Path(data_dir)
        self.customers: List[CustomerData] = []
        self.bookings: List[BookingData] = []
        self._load_data()
    
    def _load_data(self):
        """Load authoritative data from JSON files."""
        # Load customers
        customers_file = self.data_dir / "customers.json"
        if customers_file.exists():
            with open(customers_file, 'r', encoding='utf-8') as f:
                customers_data = json.load(f)
                self.customers = [CustomerData(**c) for c in customers_data]
        
        # Load bookings
        bookings_file = self.data_dir / "bookings.json"
        if bookings_file.exists():
            with open(bookings_file, 'r', encoding='utf-8') as f:
                bookings_data = json.load(f)
                self.bookings = [BookingData(**b) for b in bookings_data]
    
    def get_customer(self, booking_reference: str) -> Optional[CustomerData]:
        """Get customer by booking reference."""
        for customer in self.customers:
            if customer.booking_reference == booking_reference:
                return customer
        return None
    
    def get_customer_by_name(self, name: str) -> Optional[CustomerData]:
        """Get customer by name (case-insensitive)."""
        name_lower = name.lower()
        for customer in self.customers:
            if customer.name.lower() == name_lower:
                return customer
        return None
    
    def get_booking(self, booking_reference: str, flight_reference: Optional[str] = None) -> Optional[BookingData]:
        """
        Get booking by reference and optional flight reference.
        
        Args:
            booking_reference: Booking reference to search
            flight_reference: Optional flight reference to match
            
        Returns:
            Matching booking or None
        """
        for booking in self.bookings:
            if booking.booking_reference == booking_reference:
                if flight_reference:
                    # Check if flight matches
                    if booking.flight == flight_reference or booking.flight.lower() == flight_reference.lower():
                        return booking
                else:
                    # Return first matching booking with disruption status
                    if booking.status in ["cancelled", "delayed"]:
                        return booking
        
        # No disrupted booking found, return first match
        for booking in self.bookings:
            if booking.booking_reference == booking_reference:
                return booking
        
        return None
    
    def ground(self, untrusted: UntrustedStructuredRequest) -> GroundedRequest:
        """
        Verify untrusted request against authoritative data.
        
        This is the main entry point for grounding.
        
        Args:
            untrusted: Untrusted extraction from NLU
            
        Returns:
            GroundedRequest with verification results
        """
        warnings: List[str] = []
        
        # Initialize verification flags
        customer_found = False
        booking_found = False
        flight_matches = False
        
        # Initialize verified data
        verified_customer_name: Optional[str] = None
        verified_loyalty_tier: Optional[str] = None
        verified_booking_ref: Optional[str] = None
        verified_flight_ref: Optional[str] = None
        verified_status: Optional[str] = None
        verified_cause: Optional[str] = None
        verified_delay: Optional[float] = None
        
        # Check if we have minimum required references
        if not untrusted.booking_reference and not untrusted.customer_name:
            return GroundedRequest(
                untrusted_request=untrusted,
                grounding_status=GroundingStatus.INCOMPLETE,
                grounding_warnings=["Missing booking reference and customer name - cannot verify"],
                customer_reference_found=False,
                booking_reference_found=False,
                flight_reference_matches_booking=False
            )
        
        # Try to resolve customer
        customer: Optional[CustomerData] = None
        
        if untrusted.booking_reference:
            # Try booking reference first (most reliable)
            customer = self.get_customer(untrusted.booking_reference)
            if customer:
                customer_found = True
                verified_customer_name = customer.name
                verified_loyalty_tier = customer.loyalty_tier
                verified_booking_ref = customer.booking_reference
            else:
                warnings.append(f"Booking reference '{untrusted.booking_reference}' not found in customer database")
        
        if not customer and untrusted.customer_name:
            # Try customer name as fallback
            customer = self.get_customer_by_name(untrusted.customer_name)
            if customer:
                customer_found = True
                verified_customer_name = customer.name
                verified_loyalty_tier = customer.loyalty_tier
                verified_booking_ref = customer.booking_reference
                
                # Check if claimed booking reference matches
                if untrusted.booking_reference and untrusted.booking_reference != customer.booking_reference:
                    return GroundedRequest(
                        untrusted_request=untrusted,
                        grounding_status=GroundingStatus.MISMATCH,
                        grounding_warnings=[
                            f"Customer '{untrusted.customer_name}' found but booking reference mismatch: "
                            f"claimed '{untrusted.booking_reference}', actual '{customer.booking_reference}'"
                        ],
                        verified_customer_name=verified_customer_name,
                        verified_loyalty_tier=verified_loyalty_tier,
                        verified_booking_reference=customer.booking_reference,
                        customer_reference_found=True,
                        booking_reference_found=False,
                        flight_reference_matches_booking=False
                    )
            else:
                warnings.append(f"Customer '{untrusted.customer_name}' not found")
        
        if not customer:
            # Customer not resolved
            return GroundedRequest(
                untrusted_request=untrusted,
                grounding_status=GroundingStatus.UNRESOLVED,
                grounding_warnings=warnings + ["Cannot verify customer identity"],
                customer_reference_found=False,
                booking_reference_found=False,
                flight_reference_matches_booking=False
            )
        
        # Customer verified - now verify booking and flight
        booking = self.get_booking(verified_booking_ref, untrusted.flight_reference)
        
        if booking:
            booking_found = True
            verified_flight_ref = booking.flight
            verified_status = booking.status
            verified_cause = booking.cause  # May be None if not in source data
            verified_delay = booking.delay_hours
            
            # Check if flight reference matches (if provided)
            if untrusted.flight_reference:
                if booking.flight.lower() == untrusted.flight_reference.lower():
                    flight_matches = True
                else:
                    # Flight reference doesn't match this booking
                    # Check if it matches another booking for this customer
                    found_match = False
                    for other_booking in self.bookings:
                        if (other_booking.booking_reference == verified_booking_ref and
                            other_booking.flight.lower() == untrusted.flight_reference.lower()):
                            # Found matching flight in another booking
                            booking = other_booking
                            verified_flight_ref = booking.flight
                            verified_status = booking.status
                            verified_cause = booking.cause
                            verified_delay = booking.delay_hours
                            flight_matches = True
                            found_match = True
                            break
                    
                    if not found_match:
                        warnings.append(
                            f"Flight reference '{untrusted.flight_reference}' does not match "
                            f"booking '{verified_booking_ref}'"
                        )
            else:
                # No flight reference provided, using first disrupted booking
                flight_matches = True  # Implicit match
        else:
            warnings.append(f"No booking data found for '{verified_booking_ref}'")
            return GroundedRequest(
                untrusted_request=untrusted,
                grounding_status=GroundingStatus.UNRESOLVED,
                grounding_warnings=warnings,
                verified_customer_name=verified_customer_name,
                verified_loyalty_tier=verified_loyalty_tier,
                verified_booking_reference=verified_booking_ref,
                customer_reference_found=True,
                booking_reference_found=False,
                flight_reference_matches_booking=False
            )
        
        # All verifications successful
        status = GroundingStatus.VERIFIED
        if warnings:
            # Has warnings but verification succeeded
            status = GroundingStatus.VERIFIED
        
        return GroundedRequest(
            untrusted_request=untrusted,
            grounding_status=status,
            grounding_warnings=warnings,
            verified_customer_name=verified_customer_name,
            verified_loyalty_tier=verified_loyalty_tier,
            verified_booking_reference=verified_booking_ref,
            verified_flight_reference=verified_flight_ref,
            verified_flight_status=verified_status,
            verified_disruption_cause=verified_cause,
            verified_delay_hours=verified_delay,
            customer_reference_found=customer_found,
            booking_reference_found=booking_found,
            flight_reference_matches_booking=flight_matches
        )
