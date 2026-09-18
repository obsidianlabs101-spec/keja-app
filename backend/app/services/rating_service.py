"""
Event ratings pipeline.

Flow:
  1. attendance_service's 5-minute sweep calls send_rate_event_prompts()
     once an event's start_date has passed. Every paid ticket-holder gets
     a one-time "rate_event" Notification (rendered in profile.js's Bash
     Updates stream as an inline 1-5 star message — see cheki.html for
     the star-rating widget of the same shape used elsewhere).
  2. The buyer taps a star count -> POST /events/{event_id}/rate ->
     submit_rating() below, which enforces: they actually hold a paid
     ticket for that event, and the event has actually started.
  3. Every successful submission recomputes the host's Gold Organiser
     eligibility (recompute_host_gold_status) — rolling average of their
     most recent 5 rated events' average ratings. >= 4.5 flips
     User.gold_organiser True, which swaps their feed badge from the
     standard red "ORGANISER" pill to gold (cheki.html).
"""
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.event import Event
from app.models.event_rating import EventRating
from app.models.booking import Booking
from app.models.user import User
from app.models.notification import Notification

GOLD_BADGE_MIN_EVENTS = 5
GOLD_BADGE_MIN_AVERAGE = 4.5


class RatingError(Exception):
    """Raised for any rating-submission rule violation; the API layer
    turns this into a 400 with the message as-is."""
    pass


def submit_rating(db: Session, event: Event, user: User, rating: int) -> EventRating:
    if rating not in (1, 2, 3, 4, 5):
        raise RatingError("Rating must be between 1 and 5 stars.")

    if event.start_date is None or event.start_date > datetime.utcnow():
        raise RatingError("You can rate this event once it has started.")

    # SECURITY: only someone holding an actual paid ticket for this event
    # can rate it — otherwise anyone could tank or inflate a host's score.
    has_paid_ticket = (
        db.query(Booking)
        .filter(Booking.event_id == event.id, Booking.user_id == user.id, Booking.status == "booked")
        .first()
        is not None
    )
    if not has_paid_ticket:
        raise RatingError("Only ticket holders can rate this event.")

    now = datetime.utcnow()
    existing = (
        db.query(EventRating)
        .filter(EventRating.event_id == event.id, EventRating.user_id == user.id)
        .first()
    )
    if existing:
        existing.rating = rating
        existing.updated_at = now
        db.add(existing)
        row = existing
    else:
        row = EventRating(event_id=event.id, user_id=user.id, rating=rating, updated_at=now)
        db.add(row)

    db.commit()
    db.refresh(row)

    recompute_host_gold_status(db, event.host_id)
    return row


def get_event_rating_summary(db: Session, event_id, viewer_user_id=None):
    avg, count = (
        db.query(func.avg(EventRating.rating), func.count(EventRating.id))
        .filter(EventRating.event_id == event_id)
        .first()
    )
    my_rating = None
    if viewer_user_id is not None:
        row = (
            db.query(EventRating)
            .filter(EventRating.event_id == event_id, EventRating.user_id == viewer_user_id)
            .first()
        )
        my_rating = row.rating if row else None
    return {
        "average": round(float(avg), 2) if avg is not None else None,
        "count": int(count or 0),
        "my_rating": my_rating,
    }


def recompute_host_gold_status(db: Session, host_id) -> bool:
    """Rolling average of a host's most recent GOLD_BADGE_MIN_EVENTS rated
    events' per-event averages. Needs at least that many rated events —
    a host with 1 great event shouldn't instantly look "amazing"; the
    badge is meant to reflect a sustained track record."""
    per_event_avgs = (
        db.query(
            EventRating.event_id,
            func.avg(EventRating.rating).label("avg_rating"),
            func.max(EventRating.created_at).label("last_rated_at"),
        )
        .join(Event, Event.id == EventRating.event_id)
        .filter(Event.host_id == host_id)
        .group_by(EventRating.event_id)
        .order_by(func.max(EventRating.created_at).desc())
        .limit(GOLD_BADGE_MIN_EVENTS)
        .all()
    )

    qualifies = False
    if len(per_event_avgs) >= GOLD_BADGE_MIN_EVENTS:
        rolling_avg = sum(float(row.avg_rating) for row in per_event_avgs) / len(per_event_avgs)
        qualifies = rolling_avg >= GOLD_BADGE_MIN_AVERAGE

    host = db.query(User).filter(User.id == host_id).first()
    if host is not None and bool(getattr(host, "gold_organiser", False)) != qualifies:
        host.gold_organiser = qualifies
        db.add(host)
        db.commit()
    return qualifies


def send_rate_event_prompts(db: Session, now=None) -> int:
    """Automatic sweep step: once an event has started, notify every paid
    ticket-holder once, asking them to rate it. Deliberately NOT windowed
    to "starting soon" like the T-2/T-1 helpers — this only cares that
    start_date has already passed and it hasn't been sent yet, so (like
    _events_due_for_final_list) it self-heals if a sweep run is ever
    missed instead of skipping an event forever."""
    now = now or datetime.utcnow()
    events = (
        db.query(Event)
        .filter(
            Event.status == "published",
            Event.start_date.isnot(None),
            Event.start_date <= now,
            Event.rating_prompts_sent_at.is_(None),
        )
        .all()
    )

    notified = 0
    for event in events:
        bookings = (
            db.query(Booking)
            .filter(Booking.event_id == event.id, Booking.status == "booked")
            .all()
        )

        event.rating_prompts_sent_at = now
        db.add(event)

        for booking in bookings:
            db.add(Notification(
                user_id=booking.user_id,
                type="rate_event",
                title=f"How was {event.title}?",
                body=f"You're in! Rate \"{event.title}\" — tap a star count below.",
                data={"event_id": str(event.id), "event_title": event.title},
                context="user",
            ))
            notified += 1

    if notified or events:
        db.commit()
    return notified