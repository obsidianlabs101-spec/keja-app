from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class BookingCreate(BaseModel):
    event_id: UUID
    ticket_tier: Optional[str] = None
    quantity: Optional[int] = 1
    note: Optional[str] = None


class BookingQuoteResponse(BaseModel):
    event_id: UUID
    ticket_tier: Optional[str] = None
    quantity: int
    unit_price: float
    subtotal: float
    platform_fee: float
    mpesa_fee_estimate: float
    total: float


class BookingResponse(BaseModel):
    booking_id: UUID
    booking_reference: str
    event_id: UUID
    user_id: UUID
    ticket_tier: Optional[str] = None
    quantity: int
    unit_price: Optional[float] = None
    total_amount: Optional[float] = None
    buyer_total_amount: Optional[float] = None
    status: str

    # Added so the frontend tickets page (saved-events.js) can rebuild a
    # user's ticket list purely from this endpoint (source of truth), with
    # localStorage only ever used as a fast local cache — not the only copy.
    event_title: Optional[str] = None
    event_venue: Optional[str] = None
    event_date: Optional[datetime] = None
    event_description: Optional[str] = None
    host_username: Optional[str] = None
    mpesa_receipt_number: Optional[str] = None
    qr_payload: Optional[str] = None
    archived_at: Optional[datetime] = None

    # "Door Notes" — the host's special instructions for people who've
    # actually paid (parking, dress code, gate password, etc). Only ever
    # populated by _to_booking_response() when this booking's own status
    # is "paid" — see that function's docstring in app/api/v1/bookings.py.
    # A "booked"/unpaid reservation always gets None here, even if the
    # event itself has door_notes set.
    door_notes: Optional[str] = None

    class Config:
        from_attributes = True


class BookingStatusUpdate(BaseModel):
    booking_id: UUID
    status: str
    payment_id: Optional[UUID] = None


class BookingQRResponse(BaseModel):
    booking_id: UUID
    ticket_id: UUID
    qr_payload: str
    ticket_code: Optional[str] = None
    status: str


class AttendanceResponseRequest(BaseModel):
    going: bool