"""
app/models/support_ticket.py

Persists the two-way "Admin & Support Hub" chat between a host and BASH HQ.
Each row is a single message; `sender` marks who wrote it so both the host
dashboard chat widget and the admin "Broadcasts & Support" desk can render
a shared, ordered thread per host.

Drop this file at app/models/support_ticket.py, then make sure it's created
via your migration tool (Alembic) or Base.metadata.create_all(), matching
however the other models (Booking, Payment, Withdrawal, etc.) are managed.
"""
import uuid

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    host_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # "host" or "admin" — identifies who sent this particular message.
    sender = Column(String, nullable=False, default="host")
    message = Column(String, nullable=False)

    # Lets the admin desk mark a host's thread as handled.
    resolved = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    host = relationship("User", foreign_keys=[host_id])