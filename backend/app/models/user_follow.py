"""
UserFollow — persists follow requests/relationships between users so
"follow requests" show up for the target user (in their Messages/inbox)
across devices and browsers, instead of living only in one browser's
localStorage (which is why they never actually reached the other person).

status: "pending" -> awaiting the target's accept/deny
        "accepted" -> active follow relationship
(a decline simply deletes the row, so the requester can try again later)
"""
import uuid

from sqlalchemy import Column, DateTime, String, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.database import Base


class UserFollow(Base):
    __tablename__ = "user_follows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    follower_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    followee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    status = Column(String, nullable=False, default="pending")  # "pending" | "accepted"

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    responded_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("follower_id", "followee_id", name="uq_user_follows_pair"),
    )


Index("ix_user_follows_followee_status", UserFollow.followee_id, UserFollow.status)
