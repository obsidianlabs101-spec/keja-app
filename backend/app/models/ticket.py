import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    booking_id = Column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id"),
        nullable=False,
        index=True,
    )

    qr_payload = Column(String, nullable=False, index=True)

    # Short, human-typeable code (staff can type this at the gate instead of
    # scanning) — the Live Gate lookup (_find_ticket_for_code) matches on
    # this column. It was already being queried before this fix, but had
    # never actually been declared on the model.
    ticket_code = Column(String, nullable=True, index=True, unique=True)

    status = Column(String, nullable=False, default="issued")
    checked_in_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    booking = relationship("Booking", back_populates="tickets")


Index("ix_tickets_booking_status", Ticket.booking_id, Ticket.status)

