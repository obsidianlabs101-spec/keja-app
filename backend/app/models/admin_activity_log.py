import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Float
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class AdminActivityLog(Base):
    """Powers the "Cuto" card on the admin Financials page — every admin's
    logged-in activity throughout the admin panel: page access, payout
    actions (with amounts), event revokes, broadcasts, verifications.
    Deliberately its own table (not Notification) so it's an append-only
    audit trail that never gets marked read/cleared by anything."""

    __tablename__ = "admin_activity_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    action = Column(String, nullable=False)
    # e.g. "financial_access", "payout_message", "payout_mark_paid",
    # "event_revoke", "broadcast_sent", "host_verify", "login"

    detail = Column(Text, nullable=True)
    amount = Column(Float, nullable=True)  # payout amount, when relevant

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)