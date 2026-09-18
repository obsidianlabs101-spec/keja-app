"""
NEW FILE — save as app/models/notification.py

Lightweight host-facing notification, used to deliver the ticket-sales tally
when the admin closes sales at the deadline, and payout status updates.

Requires a migration:
    alembic revision --autogenerate -m "add notifications table"
    alembic upgrade head
"""
import uuid
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    type = Column(String, nullable=False)   # "ticket_tally" | "payout_status" | ...
    title = Column(String, nullable=False)
    body = Column(String, nullable=True)
    data = Column(JSON, nullable=True)      # e.g. {"event_id": ..., "tickets_sold": 812}

    # "user" (personal/profile inbox) or "host" (host-dashboard inbox) —
    # same split as Message.context. A single account can be both a buyer
    # and a host, so this is what keeps a host's payout/broadcast/gate
    # notifications from bleeding into their personal profile notification
    # bell, and vice versa (e.g. a buyer's refund notice showing up in
    # their own host dashboard).
    context = Column(String, nullable=False, default="user", server_default="user")

    read = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())