import uuid

from sqlalchemy import Column, DateTime, String, Text, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.database import Base


class ChekiComment(Base):
    __tablename__ = "cheki_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Post/feed relationship
    feed_item_id = Column(String, ForeignKey("cheki_feed_items.reel_id"), nullable=False, index=True)

    # Auth relationship
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    content = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


Index("ix_cheki_comments_feed_item_id_created_at", ChekiComment.feed_item_id, ChekiComment.created_at.desc())

