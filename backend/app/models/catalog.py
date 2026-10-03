import uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class HousingCategory(Base):
    """An admin-managed property type shown in the "add listing" picker and
    used to group listings on Home (e.g. Bungalow, Maisonette, Bedsitter).

    `group_key` says which Home chip it belongs to: apartments | hostels |
    airbnb | commercial. Listings store the category NAME in
    properties.property_type, so hiding a category never breaks old listings.
    """

    __tablename__ = "housing_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(60), nullable=False, unique=True)
    group_key = Column(String(20), nullable=False, default="apartments", index=True)
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)


class LocationKeyword(Base):
    """An admin-managed "keyword location" (e.g. Kilimani, Ruaka): shown as the
    Popular-areas chips on Home and offered as suggestions when a landlord
    types a listing's area."""

    __tablename__ = "location_keywords"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(60), nullable=False, unique=True)
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
