import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    host_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("events.id"),
        nullable=True,
    )

    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False, default="KES")

    # Revenue breakdown, captured at request time so the numbers in the
    # admin alert and the host's payout record stay stable even if more
    # tickets sell for the event afterwards.
    gross_revenue = Column(Float, nullable=True)
    platform_cut = Column(Float, nullable=True)   # our 12% cut, in KES
    host_payout_amount = Column(Float, nullable=True)  # == amount, kept explicit for clarity in financial records

    status = Column(String, nullable=False, default="requested")
    # requested -> awaiting_host_confirmation -> confirmed_by_host -> paid
    #           -> denied_by_host -> (host edits bank/mpesa details) -> requested again

    # Bank/M-Pesa details snapshotted at request time — this is what the
    # host is shown to confirm/deny, so editing their profile later never
    # silently changes an in-flight or already-settled payout record.
    bank_name = Column(String, nullable=True)
    account_number = Column(String, nullable=True)
    account_name = Column(String, nullable=True)
    bank_business_number = Column(String, nullable=True)
    mpesa_paybill = Column(String, nullable=True)

    # M-Pesa proof once we've manually sent the money and logged the code.
    mpesa_code = Column(String, nullable=True)

    # NOTE: admins in this app are Users with is_admin=True (see
    # get_current_admin in core/dependencies.py) — there's a separate,
    # unused `admins` table left over from an earlier auth design. This
    # FK used to point at admins.id, so every "Message" / "Mark Paid"
    # admin action wrote a users.id into a column FK'd to a table it was
    # never actually in, which Postgres rejects outright (IntegrityError
    # -> unhandled 500). Pointing this at users.id matches the real
    # authentication path.
    admin_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    payout_reference = Column(String, nullable=True)
    note = Column(String, nullable=True)

    requested_at = Column(DateTime, nullable=False)
    messaged_at = Column(DateTime, nullable=True)
    host_responded_at = Column(DateTime, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)

    host = relationship("User", foreign_keys=[host_id])
    event = relationship("Event")
    admin = relationship("User", foreign_keys=[admin_id])