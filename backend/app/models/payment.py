import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Float, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Payment(Base):
    __tablename__ = "payments"

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

    provider = Column(String, nullable=False, default="mpesa")
    status = Column(String, nullable=False, default="initiated")

    amount = Column(Float, nullable=True)
    currency = Column(String, nullable=True, default="KES")

    mpesa_receipt_number = Column(String, nullable=True, index=True, unique=True)
    mpesa_checkout_request_id = Column(String, nullable=True, index=True, unique=True)
    mpesa_result_code = Column(String, nullable=True)

    # Refund ledger — populated when the T-2hr attendance sweep auto-refunds
    # (or the buyer declines) a "paid" booking. Kept on the original Payment
    # record so there's one authoritative row of the full money trail.
    refunded_amount = Column(Float, nullable=True)
    refund_fee_amount = Column(Float, nullable=True)
    refunded_at = Column(DateTime, nullable=True)

    # Manual payment flow (provider="mpesa_manual") — populated once the
    # buyer pastes in their code/confirmation SMS after paying the paybill
    # by hand. See app.services.manual_payment_service. buyer_claimed_code
    # is the code we parsed out of what they pasted; buyer_claimed_raw_message
    # is what they actually typed, kept verbatim so an admin reviewing a
    # stuck/mismatched claim can see the original text.
    buyer_claimed_code = Column(String, nullable=True, index=True)
    buyer_claimed_raw_message = Column(String, nullable=True)
    buyer_claimed_at = Column(DateTime, nullable=True)

    raw_payload = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    booking = relationship("Booking", back_populates="payments")