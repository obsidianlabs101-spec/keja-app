"""
app/models/user_session.py

Backs the admin "User Growth" analytics subpage — tracks how much time
people actually spend in the app. The frontend pings POST /users/heartbeat
every ~60s while a page is open (wired once in api-config.js, so it covers
every page — buyer and host — without touching each page individually).

Each row is one continuous session: `started_at` is the first heartbeat,
`last_seen_at` is bumped on every subsequent heartbeat as long as the gap
since the previous one is under HEARTBEAT_SESSION_GAP_MINUTES. Once a gap
is bigger than that (tab closed, phone locked, etc.), the next heartbeat
starts a new session row instead of extending the old one. Summing
(last_seen_at - started_at) across a user's sessions in a period gives a
reasonable "time spent" estimate without needing a client-side timer that
has to survive tab closes/refreshes/crashes.
"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

# If the gap between heartbeats exceeds this, treat it as a new session
# rather than extending the previous one.
HEARTBEAT_SESSION_GAP_MINUTES = 15


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)