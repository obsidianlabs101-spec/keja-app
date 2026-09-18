"""
UserBlock — one row per "A blocked B". Blocking also tears down any
follow relationship between the two (see users.block_user in
api/v1/users.py), so a block always implies "not following each other"
too, not just a separate flag layered on top of an existing follow.
"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.database import Base


class UserBlock(Base):
    __tablename__ = "user_blocks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    blocker_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    blocked_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id", name="uq_user_blocks_pair"),
    )


Index("ix_user_blocks_blocker", UserBlock.blocker_id)