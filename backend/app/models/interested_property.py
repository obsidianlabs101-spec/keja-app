# app/models/interested_property.py
"""
Two related but distinct records:

- PropertySwipe: every swipe decision (left/right), so the Discover queue
  never re-serves a card the user already decided on.
- InterestedProperty: the subset of right-swipes that make up the
  "Interested" list (spec section: swipe right to save a property).
  Kept as its own table rather than filtering PropertySwipe on every read,
  since "Interested" is read far more often than swipes are recorded, and
  a landlord marking a property booked/removed shouldn't require rewriting
  swipe history.
"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class PropertySwipe(Base):
    __tablename__ = "property_swipes"
    __table_args__ = (
        UniqueConstraint("user_id", "property_id", name="uq_property_swipe_user_property"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False, index=True)
    direction = Column(String, nullable=False)  # "right" (interested) | "left" (skip)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)


class InterestedProperty(Base):
    __tablename__ = "interested_properties"
    __table_args__ = (
        UniqueConstraint("user_id", "property_id", name="uq_interested_user_property"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)

    property = relationship("Property")
