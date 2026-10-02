# app/models/host_comment.py
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class HostComment(Base):
    """A renter's comment on a landlord's public profile ("What renters
    say"). One comment per (user, landlord) pair — posting again replaces
    the old one, the same pattern used for PropertyAlert.
    """

    __tablename__ = "host_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    landlord_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    body = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
