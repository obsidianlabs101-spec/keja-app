import uuid

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import ForeignKey
from sqlalchemy import DateTime
from sqlalchemy import Text
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import Index
from sqlalchemy import Boolean

from sqlalchemy.orm import relationship

from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Event(Base):

    __tablename__ = "events"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    host_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )

    title = Column(
        String,
        nullable=False
    )

    description = Column(
        Text
    )

    # Shown ONLY to people holding a booked ticket for this event (see
    # BookingResponse.door_notes in app/schemas/booking.py, which only
    # populates this for bookings with status == "booked"). Deliberately
    # kept OUT of EventRead so it never leaks through the public feed —
    # this is for things like parking directions, a gate password, or a
    # dress code that only matters once someone has actually paid.
    door_notes = Column(
        Text,
        nullable=True,
    )

    venue_name = Column(
        String
    )

    # Structured county, set from the same County dropdown the host uses
    # for venue_name — powers the home page "Near Me" card by matching
    # against the buyer's own county (set on their profile), instead of
    # GPS. latitude/longitude are kept for any future map use but are no
    # longer read by "Near Me".
    county = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    category = Column(
        String
    )

    price = Column(
        Float,
        nullable=True
    )

    capacity = Column(
        Integer,
        nullable=True
    )

    start_date = Column(
        DateTime
    )

    end_date = Column(
        DateTime
    )

    # New — required for the Admin countdown-button feature. This is a plain
    ticket_deadline = Column(
        DateTime,
        nullable=True
    )

    # Set once send_ticket_deadline_notice (attendance_service.py) has
    ticket_deadline_notified_at = Column(
        DateTime,
        nullable=True
    )

    # Tickets freed up by a decline/no-show refund between T-2 and T-1.
    reclaimed_capacity = Column(
        Integer,
        default=0,
        server_default="0",
    )

    status = Column(
        String,
        default="draft"
    )

    poster_url = Column(
        String,
        nullable=True
    )

    video_url = Column(
        String,
        nullable=True
    )

    # --- Ticket-deadline tally (admin "close ticket sales" action) --------
    final_ticket_tally = Column(Integer, nullable=True)
    ticket_sales_closed = Column(Boolean, default=False)
    ticket_sales_closed_at = Column(DateTime, nullable=True)

    # --- Admin "Send Tickets" -> host's Live Gate ---------------------------
    final_list_locked_at = Column(DateTime, nullable=True)
    gate_unlocked = Column(Boolean, default=False)
    tickets_sent_at = Column(DateTime, nullable=True)
    final_tally_amount = Column(Float, nullable=True)

    # Set once send_rate_event_prompts (attendance_service.py) has notified
    # every paid buyer to rate this event — guards against re-notifying on
    # every 5-minute sweep. Mirrors ticket_deadline_notified_at's pattern.
    rating_prompts_sent_at = Column(DateTime, nullable=True)


    # JSON-encoded list of confirmed BASH usernames the host tagged as
    artist_usernames = Column(Text, nullable=True)

    # JSON-encoded list of {label, amount, capacity} — the host's custom
    ticket_tiers = Column(Text, nullable=True)

    # --- Admin "Events Uploaded" review tracking ---------------------------
    # Set the first time any admin opens/marks this event on the Events
    # Uploaded subpage, so the Reviewed / Not Reviewed nav tabs there can
    # show which listings still need a look.
    reviewed_by_admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    # Keja rebrand: back_populates="events" removed along with
    # User.events (see models/user.py) — Event is still imported
    # transitively by the (untouched-this-phase) admin panel, so this
    # stays a plain one-way relationship rather than being deleted
    # outright.
    host = relationship(
        "User",
        foreign_keys=[host_id]
    )
Index("ix_events_host_status_start", Event.host_id, Event.status, Event.start_date)
Index("ix_events_category_status_start", Event.category, Event.status, Event.start_date)