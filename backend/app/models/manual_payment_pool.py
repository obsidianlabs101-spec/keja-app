import uuid

from sqlalchemy import Column, String, Float, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class ManualPaymentPoolEntry(Base):
    """One row per M-Pesa code an admin pasted in from the real paybill
    statement while batch-matching manual payments (see
    POST /admin/manual-payments/batch-match).

    Matching is order-independent: a buyer's claimed code (Payment.
    buyer_claimed_code) can arrive before OR after the admin pastes the
    real statement. Whichever side shows up second is the one that
    triggers the match — see app.services.manual_payment_service. Any
    code from a batch paste that doesn't immediately match a pending
    buyer claim is parked here so a buyer claim arriving later still
    matches instantly instead of needing the admin to re-paste.
    """

    __tablename__ = "manual_payment_pool"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    code = Column(String, nullable=False, index=True)
    amount = Column(Float, nullable=True)
    raw_message = Column(Text, nullable=False)

    matched = Column(Boolean, nullable=False, default=False, server_default="false")
    matched_payment_id = Column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=True)
    matched_at = Column(DateTime, nullable=True)

    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)