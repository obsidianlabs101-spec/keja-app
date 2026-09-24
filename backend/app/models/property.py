# app/models/property.py
"""
Keja's core listing. Repurposes the same patterns Bash's Event model used
(landlord = old "host"/is_host user flag; see app/core/dependencies.py's
require_host, which Keja's require_landlord alias wraps unchanged) —
matches the modification spec's "reuse before rebuild" rule.
"""
import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Property(Base):
    __tablename__ = "properties"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    landlord_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # KES / month. Kept as Float to match the rest of the codebase's money
    # columns (see Event.price) rather than introducing Numeric here alone.
    price = Column(Float, nullable=False)

    property_type = Column(String, nullable=False)  # e.g. "Bedsitter", "1 Bedroom", "2 Bedroom", "Studio"
    bedrooms = Column(Integer, nullable=True)
    bathrooms = Column(Integer, nullable=True)

    # Structured location, same shape as Event.county for "Near Me"-style
    # matching — see kenya-locations.js (kept from Bash) for the picker.
    county = Column(String, nullable=False, index=True)
    area = Column(String, nullable=True, index=True)  # e.g. "Kasarani", "Kilimani"

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # Free-text proximity/landmark description — spec section "Let
    # landlords describe proximity to campuses and landmarks."
    proximity_note = Column(String, nullable=True)  # e.g. "5 min walk to USIU gate"

    main_image_url = Column(String, nullable=True)

    # Landlord-chosen feature tags shown as small icon cards on the listing
    # (keys come from app.schemas.property.ALLOWED_AMENITIES). Stored as a
    # JSON list; NULL on older rows and treated as [] everywhere.
    amenities = Column(JSON, nullable=True)

    is_available = Column(Boolean, default=True, nullable=False)
    is_booked = Column(Boolean, default=False, nullable=False)

    # Soft-hide instead of hard delete, so a removed listing doesn't orphan
    # existing InterestedProperty/ContactUnlock rows referencing it.
    is_removed = Column(Boolean, default=False, nullable=False)

    # Admin moderation. New listings go live immediately but appear in the
    # admin "New listings" queue as "unreviewed"; the admin can approve them
    # or reject (hides the listing and tells the landlord why).
    review_status = Column(String, default="unreviewed", server_default="unreviewed", nullable=True)
    review_note = Column(String, nullable=True)

    view_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)

    landlord = relationship("User", foreign_keys=[landlord_id])
    images = relationship(
        "PropertyImage",
        back_populates="property",
        cascade="all, delete-orphan",
        order_by="PropertyImage.sort_order",
    )
