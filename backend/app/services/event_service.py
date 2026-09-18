"""Event creation service. NOTE: the Cheki feed (vibe_posts_stream_v1) lives
in app/api/v1/stream.py, not here — this file used to carry a duplicate,
never-included copy of that router which silently went stale; removed."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.user import User
from app.models.notification import Notification
from app.schemas.event import EventCreate


def create_event(db: Session, user_id: int, data: EventCreate) -> Event:
    """Creates a new event record in the database."""
    import json as _json

    # Only usernames that actually resolve to a real user go into the tag list.
    artist_usernames_clean = []
    for raw in (data.artist_usernames or []):
        handle = str(raw).strip().lstrip("@")
        if not handle:
            continue
        handle_lower = handle.lower()
        exists = db.query(User).filter(func.lower(User.username).in_([handle_lower, f"@{handle_lower}"])).first()
        if exists:
            artist_usernames_clean.append(exists.username.lstrip("@"))

    tiers_clean = []
    for t in (data.ticket_tiers or []):
        label = (t.label or "").strip() or "Ticket"
        amount = float(t.amount or 0)
        tiers_clean.append({"label": label, "amount": amount, "capacity": t.capacity})

    # Buyer-facing "price" pill shows the cheapest tier when tiers exist.
    flat_price = data.price
    if tiers_clean:
        flat_price = min(t["amount"] for t in tiers_clean)

    db_event = Event(
        title=data.title,
        description=data.description,
        door_notes=(data.door_notes or "").strip() or None,
        venue_name=data.venue_name,
        county=data.county,
        latitude=data.latitude,
        longitude=data.longitude,
        start_date=data.start_date,
        end_date=data.end_date,
        ticket_deadline=data.ticket_deadline,
        price=flat_price,
        capacity=data.capacity,
        category=data.category,
        poster_url=data.poster_url,
        video_url=data.video_url,
        artist_usernames=_json.dumps(artist_usernames_clean) if artist_usernames_clean else None,
        ticket_tiers=_json.dumps(tiers_clean) if tiers_clean else None,
        status="published",
        host_id=user_id,
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


def _read_notification_prefs_for(user) -> dict:
    """Local copy of app.api.v1.users._read_notification_prefs's defaults —
    not imported directly to avoid a service-importing-a-router layering
    inversion (same reasoning as booking_service._wants_ticket_confirmation
    and attendance_service._wants_still_going_check)."""
    import json as _json
    defaults = {
        "near_me": True,
        "price_alert": False,
        "price_alert_max": None,
        "location_alert": False,
        "location_alert_value": None,
    }
    raw = getattr(user, "notification_preferences", None)
    prefs = dict(defaults)
    if raw:
        try:
            stored = _json.loads(raw)
            if isinstance(stored, dict):
                prefs.update({k: v for k, v in stored.items() if k in defaults})
        except (ValueError, TypeError):
            pass
    return prefs


def notify_nearby_users_of_new_event(db: Session, event: Event) -> int:
    """Notifies users whose saved preferences match this newly-published
    event — near-me (same county), price alert (event at or under their
    max), and/or location alert (their saved text matches venue/county).
    A user can match more than one reason; they get exactly one push/
    notification either way, listing every reason that matched, rather
    than one per matched preference. Also creates an in-app Notification
    row (context="user") for everyone who matches, not just people with a
    push subscription — same pattern as _notify_ticket_confirmed in
    booking_service.py.

    Best-effort and silent: never raises, so a push failure/typo can't
    take down event creation, and it's fine to call for every event (it's
    a no-op if nothing matches).

    Returns how many users were notified, mostly for logging/tests.
    """
    from app.services.push_service import send_web_push

    candidates = (
        db.query(User)
        .filter(User.id != event.host_id)
        .all()
    )
    if not candidates:
        return 0

    event_price = event.price if event.price is not None else 0
    venue_lower = (event.venue_name or "").lower()
    county_lower = (event.county or "").lower()

    notified = 0
    for u in candidates:
        prefs = _read_notification_prefs_for(u)
        reasons = []

        if prefs["near_me"] and event.county and u.county and u.county == event.county:
            reasons.append(f"📍 Near you in {event.county}")

        if prefs["price_alert"]:
            max_price = prefs.get("price_alert_max")
            if max_price is not None and event_price <= float(max_price):
                price_label = "Free" if not event.price else f"KES {int(event.price):,}"
                reasons.append(f"💸 {price_label} — under your alert")

        if prefs["location_alert"]:
            loc_value = (prefs.get("location_alert_value") or "").strip().lower()
            if loc_value and (loc_value in venue_lower or loc_value in county_lower):
                reasons.append(f"🗺️ Matches your saved location ({prefs['location_alert_value']})")

        if not reasons:
            continue

        title = f"New event: {event.title}"
        body = "  ·  ".join(reasons)

        db.add(Notification(
            user_id=u.id,
            type="new_event_match",
            title=title,
            body=body,
            data={"event_id": str(event.id), "reasons": reasons},
            context="user",
        ))
        db.commit()
        send_web_push(
            db, u,
            title=title,
            body=body,
            data={"event_id": str(event.id), "type": "new_event_match"},
            image=event.poster_url,
            tag=f"new-event-{event.id}",
        )
        notified += 1

    return notified