import uuid

from sqlalchemy import Column, DateTime, String, Integer, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.database import Base


class ChekiLike(Base):
    __tablename__ = "cheki_likes"

    id = Column(Integer, primary_key=True, autoincrement=True)

    feed_item_id = Column(String, ForeignKey("cheki_feed_items.reel_id"), nullable=False, index=True)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("feed_item_id", "user_id", name="uq_cheki_likes_feed_user"),
    )

    # NOTE: feed_item_id already has index=True above, which makes
    # SQLAlchemy auto-create an index named "ix_cheki_likes_feed_item_id".
    # This file used to ALSO declare that exact same index name explicitly
    # below — a harmless-looking duplicate that is actually fatal on a
    # genuinely fresh/empty database: Base.metadata.create_all() emits
    # both CREATE INDEX statements, the second one fails with "relation
    # ... already exists", and that exception aborts create_all() entirely
    # — including every table that hadn't been created yet at that point
    # (this is exactly what caused "relation events/bookings does not
    # exist" errors after pointing the app at a new database). Removed.