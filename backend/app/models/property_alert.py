# app/models/property_alert.py
import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class PropertyAlert(Base):
    """A renter's "let me know when a matching property appears" request —
    set from the exit-intent dialog on Home ("Not able to find what you're
    looking for?"). One per user; saving a new one replaces the old one.
    All fields are optional filters, ANDed together; a bare row with
    everything empty matches every new listing.
    """

    __tablename__ = "property_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    location = Column(String, nullable=True)  # matched against area/county
    min_price = Column(Float, nullable=True)
    max_price = Column(Float, nullable=True)
    landlord_name = Column(String, nullable=True)  # matched against the landlord's name, loosely
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
