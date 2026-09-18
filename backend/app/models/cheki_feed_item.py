import uuid

from sqlalchemy import Column, DateTime, String, Text, Integer, Float, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

from app.core.database import Base


class ChekiFeedItem(Base):
    __tablename__ = "cheki_feed_items"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Client-generated stable identity
    reel_id = Column(String, nullable=False, unique=True, index=True)

    # host/community
    badge_type = Column(String, nullable=False, index=True)  # host | community

    # Common
    username = Column(String, nullable=True, index=True)
    media_url = Column(Text, nullable=True)
    vibe_text = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, index=True)

    # Community
    profile_picture = Column(Text, nullable=True)
    caption = Column(Text, nullable=True)

    # Host
    host_name = Column(String, nullable=True)
    event_name = Column(String, nullable=True)
    location = Column(String, nullable=True)
    date = Column(String, nullable=True)
    category = Column(String, nullable=True)

    price = Column(Float, nullable=True)
    buyer_total = Column(Float, nullable=True)
    tickets = Column(String, nullable=True)
    tickets_sold = Column(String, nullable=True)
    tickets_status = Column(String, nullable=True)

    # JSON-encoded list of confirmed BASH usernames tagged as "Artists
    artist_usernames = Column(Text, nullable=True)

    # JSON-encoded [{label, amount, capacity}] — mirrors Event.ticket_tiers
    ticket_tiers = Column(Text, nullable=True)

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # County/constituency picked from the same Kenya dataset used by the
    # Host Dashboard's County/Area selects — what the Home "Near Me" row
    # matches against.
    county = Column(String, nullable=True)
    constituency = Column(String, nullable=True)

    # --- Admin "Community Posts" moderation ---------------------------------
    # Only ever set on community (badge_type == "community") rows. Lets the
    # admin Events Uploaded > Community Posts tab track which posts still
    # need a look, and pull a revoked one out of the Cheki feed without
    # deleting the row outright (so there's still a record of it).
    seen_by_admin_id = Column(UUID(as_uuid=True), nullable=True)
    seen_by_admin_at = Column(DateTime, nullable=True)
    revoked_by_admin_id = Column(UUID(as_uuid=True), nullable=True)
    revoked_at = Column(DateTime, nullable=True)


Index("ix_cheki_feed_items_created_at_desc", ChekiFeedItem.created_at)
Index("ix_cheki_feed_items_badge_category_created", ChekiFeedItem.badge_type, ChekiFeedItem.category, ChekiFeedItem.created_at)
Index("ix_cheki_feed_items_username_created", ChekiFeedItem.username, ChekiFeedItem.created_at)
Index("ix_cheki_feed_items_location_created", ChekiFeedItem.location, ChekiFeedItem.created_at)