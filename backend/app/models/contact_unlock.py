# app/models/contact_unlock.py
"""
KES 50 pay-to-unlock-landlord-contact flow. Mirrors Bash's manual M-Pesa
matching design (see services/manual_payment_service.py + refund_service's
parse_mpesa_message) rather than inventing a new verification approach:
the buyer pastes their M-Pesa code/SMS, an admin separately pastes the
real paybill statement, and a match on BOTH code AND amount is what
actually unlocks the contact. Per the spec's acceptance checklist, STK
Push is intentionally NOT wired up yet — this is pure manual-match.
"""
import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base

CONTACT_UNLOCK_FEE_KES = 50.0


class ContactUnlock(Base):
    __tablename__ = "contact_unlocks"
    __table_args__ = (
        UniqueConstraint("user_id", "property_id", name="uq_contact_unlock_user_property"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False, index=True)

    amount = Column(Float, default=CONTACT_UNLOCK_FEE_KES, nullable=False)

    # pending -> awaiting_admin_match -> unlocked  (or stays pending until
    # the buyer submits a claim)
    status = Column(String, default="pending", nullable=False)

    buyer_claimed_code = Column(String, nullable=True)
    buyer_claimed_raw_message = Column(String, nullable=True)
    buyer_claimed_at = Column(DateTime(timezone=True), nullable=True)

    matched_code = Column(String, nullable=True)
    unlocked_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)

    property = relationship("Property")


class ContactUnlockPoolEntry(Base):
    """An admin-pasted paybill statement line not yet matched to a buyer
    claim, parked here the same way ManualPaymentPoolEntry parks unmatched
    booking payments — so whichever side (buyer claim or admin paste)
    arrives second is what triggers the unlock."""

    __tablename__ = "contact_unlock_pool_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String, nullable=False, index=True)
    amount = Column(Float, nullable=True)
    raw_message = Column(String, nullable=True)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    matched = Column(String, default="false", nullable=False)  # "true"/"false" — kept string for ensure_schema_upgrades simplicity
    matched_unlock_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
