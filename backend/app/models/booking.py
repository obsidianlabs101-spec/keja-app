import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Integer, Float, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.event import Event
from app.models.user import User


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("events.id"),
        nullable=False,
    )

    status = Column(
        String,
        nullable=False,
        default="pending",  # pending | booked | cancelled | refunded
    )

    quantity = Column(
        Integer,
        nullable=False,
        default=1,
    )

    # These two were already being read/written by booking_service.py,
    # bookings.py, and payments.py, but were never actually declared on the
    # model — every ticket purchase was silently crashing (AttributeError)
    # before this fix.
    ticket_tier = Column(
        String,
        nullable=True,
    )

    unit_price = Column(
        Float,
        nullable=True,
    )

    # Host's raw, pre-markup value: quantity * unit_price. This is what
    # withdrawal_service.py sums for host payouts and what
    # attendance_service.py tallies as the event's gross — it must NEVER
    # have the buyer markup baked in, or every payout calc downstream
    # breaks.
    total_amount = Column(
        Float,
        nullable=True,
    )

    # What the buyer is actually charged via M-Pesa: total_amount plus the
    # 12% checkout markup (10% platform + 2% mpesa — see bookings.py).
    # This is the only amount /payments/mpesa/stk-push is allowed to charge.
    # Kept separate from total_amount on purpose (see comment above) —
    # collapsing the two back into one field is what caused buyers to be
    # charged the bare host price with the 12% silently never collected.
    buyer_total_amount = Column(
        Float,
        nullable=True,
    )

    booking_reference = Column(
        String,
        nullable=False,
        unique=True,
        index=True,
    )

    note = Column(Text, nullable=True)

    # --- T-2hr "are you going?" confirmation + auto-refund pipeline -------
    # not_due          -> more than 2h before the event, nothing sent yet
    # awaiting_response -> reminder sent, waiting on the buyer
    # confirmed        -> buyer said yes; funds are locked in for payout
    # refunded         -> buyer said no (or never answered by the deadline);
    #                     refunded minus the 12% fee, ticket back in circulation
    confirmation_status = Column(
        String,
        nullable=False,
        default="not_due",
    )
    reminder_sent_at = Column(DateTime, nullable=True)
    # T-1hr cutoff: if the buyer hasn't responded by this time, they're
    # treated as a "no" and auto-refunded.
    confirmation_deadline = Column(DateTime, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    refunded_at = Column(DateTime, nullable=True)
    refund_fee_amount = Column(Float, nullable=True)
    refund_amount = Column(Float, nullable=True)

    # --- Admin Refunds subpage: manual M-Pesa payout tracking --------------
    # A booking landing on "refunded" above just means the buyer is OWED
    # money back — it says nothing about whether the admin has actually
    # sent it yet. This is that second, admin-facing step: every refunded
    # booking starts "requested" and stays there (and counts toward the
    # Refunds sidebar badge) until an admin pastes in the M-Pesa code they
    # sent it with, which flips it to "paid" with a timestamp.
    refund_payout_status = Column(String, nullable=True)  # "requested" | "paid"
    refund_mpesa_code = Column(String, nullable=True)
    refund_paid_at = Column(DateTime, nullable=True)
    refund_paid_by_admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    # Tickets page "history" box (drag a paid ticket onto the archive icon).
    # Archiving only ever sets/clears this timestamp — it NEVER changes
    # `status` or deletes the row, so a paid booking can never actually
    # disappear, only move between the "Booked" and "History" tabs. Synced
    # server-side (not just localStorage) so the same booking shows up
    # archived on every device the buyer logs into.
    archived_at = Column(DateTime, nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    event = relationship("Event")
    tickets = relationship("Ticket", back_populates="booking")
    payments = relationship("Payment", back_populates="booking")
Index("ix_bookings_user_status_created", Booking.user_id, Booking.status, Booking.created_at)
Index("ix_bookings_event_status_created", Booking.event_id, Booking.status, Booking.created_at)
Index("ix_bookings_confirmation_sweep", Booking.confirmation_status, Booking.confirmation_deadline)