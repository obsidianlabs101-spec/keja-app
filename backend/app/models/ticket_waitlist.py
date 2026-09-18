import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class TicketWaitlist(Base):
    """A buyer who tapped the "Notify Me" bell on an event after sales
    closed at T-2. When a decline/no-show refund frees up a spot before
    T-1, everyone on this list for that event gets pinged immediately and
    can buy the reclaimed ticket — see attendance_service.py
    (_refund_booking's reclaim step) and bookings.py (can_purchase)."""

    __tablename__ = "ticket_waitlist"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_waitlist_event_user"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_notified_at = Column(DateTime, nullable=True)