"""
NEW FILE — save as app/models/checkin.py

Stores every door-check attempt (M-Pesa code typed by staff, or QR payload
scanned off a ticket) so the Live Gate has a durable, replay-safe audit
trail. A unique constraint on (event_id, code) is what makes it safe to
resubmit a batch of offline-captured scans after reconnecting: the second
attempt at the same code always comes back "duplicate" instead of
double-counting a guest.

Requires a migration:
    alembic revision --autogenerate -m "add checkins table"
    alembic upgrade head
"""
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.database import Base


class CheckIn(Base):
    __tablename__ = "checkins"
    __table_args__ = (
        UniqueConstraint("event_id", "code", name="uq_checkin_event_code"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False, index=True)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=True)

    code = Column(String, nullable=False, index=True)        # normalized (upper, trimmed) M-Pesa code or QR payload
    method = Column(String, nullable=False, default="mpesa")  # "mpesa" | "qr"
    status = Column(String, nullable=False, default="unmatched")  # "verified" | "unmatched" | "duplicate"
    device_id = Column(String, nullable=True)                 # which gate device/phone captured this

    scanned_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())