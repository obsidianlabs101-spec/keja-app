"""
app/models/header_poll.py

Backs the admin "Analytics" subpage: admin starts a poll for the 3 header
(home-page carousel) slots, all hosts get notified, each host can bid on any
slot with the media they want featured there. When admin stops the poll, the
highest bid per slot wins and that media is published to the public header.

Drop this file at app/models/header_poll.py and create the tables via your
usual migration/creation path (same as your other models).
"""
import uuid

from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class HeaderPoll(Base):
    __tablename__ = "header_polls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # "active" while hosts can bid, "closed" once admin stops it and publishes.
    status = Column(String, nullable=False, default="active", index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    options = relationship("HeaderPollOption", back_populates="poll", cascade="all, delete-orphan")


class HeaderPollOption(Base):
    __tablename__ = "header_poll_options"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    poll_id = Column(UUID(as_uuid=True), ForeignKey("header_polls.id"), nullable=False, index=True)
    # 1, 2, or 3 — one of the three header carousel positions.
    slot_number = Column(Integer, nullable=False)

    poll = relationship("HeaderPoll", back_populates="options")
    bids = relationship("HeaderBid", back_populates="option", cascade="all, delete-orphan")


class HeaderBid(Base):
    __tablename__ = "header_bids"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    option_id = Column(UUID(as_uuid=True), ForeignKey("header_poll_options.id"), nullable=False, index=True)
    host_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    amount = Column(Numeric(12, 2), nullable=False)
    media_url = Column(String, nullable=False)
    # Optional — which of the host's own events this header slot should
    # promote. Without this, a winning bid was just a floating banner
    # image with nowhere to click through to and no real event date to
    # count down to.
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    option = relationship("HeaderPollOption", back_populates="bids")
    host = relationship("User", foreign_keys=[host_id])