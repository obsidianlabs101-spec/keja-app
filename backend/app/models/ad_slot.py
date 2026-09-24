# app/models/ad_slot.py
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class AdSlot(Base):
    """One uploaded ad creative for a placement ("home" or "interested").

    Rule enforced in ad_service: at most ONE active row per placement —
    activating/creating a new ad deactivates the previous one. Old rows are
    kept (is_active=False) so an admin can re-activate a previous creative.

    owner_id is nullable on purpose: today only admins create ads (owner_id
    stays NULL or is the admin's user id); if landlords ever buy slots later
    it already has somewhere to live without a migration. Points at
    users.id (NOT admins.id — that table is unused legacy auth).
    """

    __tablename__ = "ad_slots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    placement = Column(String, nullable=False, index=True)  # "home" | "interested"
    image_url = Column(String, nullable=False)
    link_url = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=False, server_default="false", index=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
