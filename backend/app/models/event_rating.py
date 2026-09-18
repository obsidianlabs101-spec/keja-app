"""
Event ratings — a buyer with a paid ticket can leave a 1-5 star rating on
an event once it has started. One rating per (event, user), enforced by
the unique constraint below; resubmitting updates the existing row rather
than creating a duplicate (see rating_service.submit_rating).

These feed directly into a host's Gold Organiser badge eligibility — see
rating_service.recompute_host_gold_status.
"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.database import Base


class EventRating(Base):
    __tablename__ = "event_ratings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    rating = Column(Integer, nullable=False)  # 1-5

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_rating_user"),
    )