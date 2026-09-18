from datetime import datetime
import uuid
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

class Message(Base):
    __tablename__ = "messages"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sender_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    receiver_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    read = Column(Boolean, default=False)
    # "user" (personal/profile inbox) or "host" (host-dashboard inbox). A
    # single account can be both a regular user and a host, so this is what
    # keeps the two message lists from bleeding into each other — the
    # sender picks which "hat" they're messaging as, and each side's inbox
    # only ever shows threads tagged for that context.
    context = Column(String, default="user", nullable=False)

    # Relationships (add these to User model as well)
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")

    # Every read path in app/api/v1/messages.py filters by these columns
    # (thread lookup, thread list, unread count) and every write is an
    # insert-only new row — so without indexes each of those becomes a
    # full-table scan that gets linearly slower as the table grows, no
    # matter how many users are actually online at once. These make the
    # common queries index scans instead. database.py's
    # ensure_schema_upgrades() creates any of these that are missing on an
    # existing database automatically on next boot — no manual migration
    # needed.
    __table_args__ = (
        Index("ix_messages_sender_context_created", "sender_id", "context", "created_at"),
        Index("ix_messages_receiver_context_created", "receiver_id", "context", "created_at"),
        Index("ix_messages_receiver_unread", "receiver_id", "read", "context"),
    )