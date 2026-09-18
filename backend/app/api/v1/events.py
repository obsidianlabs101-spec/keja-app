from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel, Field

from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_host, get_current_user
from app.core import cache as cache_module

from app.models.event import Event
from app.models.booking import Booking
from app.models.ticket import Ticket
from app.models.payment import Payment
from app.models.checkin import CheckIn
from app.models.ticket_waitlist import TicketWaitlist
from app.models.platform_settings import get_or_create_platform_settings
from app.schemas.event import EventCreate, EventRead
from app.services.attendance_service import purchase_window_phase

from app.services.event_service import create_event, notify_nearby_users_of_new_event

router = APIRouter(
    prefix="/events",
    tags=["Events"]
)

# The free-events-only restriction (and this message) was retired — see
# GET /platform-status below. The admin switch that used to drive it now
# controls manual payment mode instead (app/api/v1/payments.py).

# --- Caching: public event feed + detail --------------------------------
# Cache-aside with a short TTL. Safe because EventRead never includes
# live figures like tickets-sold/remaining (see app/schemas/event.py) —
# only fields a host sets when creating/editing an event — so a 45s-old
# cached response can't show a stale ticket count. It CAN briefly show a
# just-edited title/price, which is why every write path that touches an
# Event below explicitly invalidates rather than just waiting out the TTL.
EVENT_LIST_CACHE_PREFIX = "events:list:"
EVENT_DETAIL_CACHE_PREFIX = "events:detail:"
EVENT_LIST_CACHE_TTL_SECONDS = 45
EVENT_DETAIL_CACHE_TTL_SECONDS = 60


def _event_list_cache_key(q: Optional[str], category: Optional[str]) -> str:
    return f"{EVENT_LIST_CACHE_PREFIX}{(q or '').strip().lower()}:{(category or '').strip().lower()}"


def _event_detail_cache_key(event_id) -> str:
    return f"{EVENT_DETAIL_CACHE_PREFIX}{event_id}"


def _invalidate_event_caches(event_id=None) -> None:
    """Call from any write path that changes a published event's public
    fields (create, edit, revoke, etc). Clears every list-filter combo
    (we don't know which ones this event appeared under) plus that
    event's own detail entry."""
    cache_module.delete_by_prefix(EVENT_LIST_CACHE_PREFIX)
    if event_id is not None:
        cache_module.delete(_event_detail_cache_key(event_id))


@router.get("/platform-status")
def get_platform_status(db: Session = Depends(get_db)):
    """Public, no-auth status check the host dashboard used to poll before/
    while the Event Creator is open to decide whether to hide the price/
    ticket-tier calculator and show a technical-difficulties banner.
    Also now the read referral.js polls to know whether the referral gate
    is on — see PlatformSettings.referral_gate_enabled and the "Referral
    Gate" admin page.

    RETIRED: the admin switch that used to drive free_events_only (PlatformSettings.
    free_events_only) has been repurposed to control manual payment mode
    instead (see POST /payments/mpesa/stk-push and the "Manual Payments"
    admin page) — hosts can now always post paid events. free_events_only
    is kept, always reporting "no restriction", purely so any client still
    polling it (old cached frontend, etc) degrades safely instead of 404ing.
    """
    settings_row = get_or_create_platform_settings(db)
    return {
        "free_events_only": False,
        "message": None,
        "referral_gate_enabled": bool(settings_row.referral_gate_enabled),
    }


@router.get("/mine", response_model=List[EventRead])
def list_my_events(
    db: Session = Depends(get_db),
    current_user=Depends(require_host),
):
    """A host's own events, straight from the `events` table — every event
    this host has ever created, any status (draft/published/live/past).

    This exists because the host dashboard's sync used to rely solely on
    GET /admin/host_events, which actually reads from `cheki_feed_items`
    (a separate, derived table used to show a host's posts in the Cheki
    feed) rather than `events` directly. A freshly-published event only
    gets a matching cheki_feed_items row once it's also pushed to the
    feed sync endpoint — which can lag behind, or never happen for a
    given event — so relying on that alone as "the full list of this
    host's events" meant a brand-new event could be correctly created
    here, be visible in the admin panel (which reads `events` directly),
    and still vanish from the host's own dashboard on refresh. This
    endpoint gives the dashboard the same ground truth the admin panel
    already uses.
    """
    events = (
        db.query(Event)
        .filter(Event.host_id == current_user.id)
        .order_by(Event.start_date.desc().nullslast())
        .all()
    )
    return events


@router.post("/create")
def create_new_event(
    data: EventCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_host),
):
    event = create_event(db, current_user.id, data)

    # --- Ticket-deadline persistence fix -----------------------------------
    # The Event Creator form has always sent `ticket_deadline` in the create
    # payload, but it was never landing in the database: create_event() /
    # EventCreate silently dropped it if the schema/service pair wasn't
    # updated together. Rather than relying on that plumbing being correct
    # everywhere, set + commit it explicitly here so publishing an event
    # always persists whatever deadline the host picked, no matter what the
    # service layer does internally.
    incoming_deadline = getattr(data, "ticket_deadline", None)
    if incoming_deadline is not None and getattr(event, "ticket_deadline", None) != incoming_deadline:
        event.ticket_deadline = incoming_deadline
        db.add(event)
        db.commit()
        db.refresh(event)

    # Best-effort — a push failure here should never turn a successful
    # event creation into a 500 for the host.
    try:
        notify_nearby_users_of_new_event(db, event)
    except Exception as e:
        print(f"⚠️  notify_nearby_users_of_new_event failed for event {event.id}: {e}")

    # A freshly-published event needs to show up in the feed immediately,
    # not up to EVENT_LIST_CACHE_TTL_SECONDS later.
    _invalidate_event_caches(event.id)

    return {
        "message": "Event created",
        "event_id": str(event.id)
    }


class TicketDeadlineUpdate(BaseModel):
    ticket_deadline: Optional[datetime] = None


@router.patch("/{event_id}/ticket-deadline")
def update_ticket_deadline(
    event_id: str,
    payload: TicketDeadlineUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(require_host),
):
    """Lets a host fix/set the ticket deadline after the fact — a safety
    valve for events that were published before the create-time bug above
    was patched, or whose deadline needs to move."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if str(event.host_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="You do not own this event")

    event.ticket_deadline = payload.ticket_deadline
    db.add(event)
    db.commit()
    db.refresh(event)
    _invalidate_event_caches(event.id)
    return {"event_id": str(event.id), "ticket_deadline": event.ticket_deadline}


@router.get("/", response_model=List[EventRead])
def list_events(
    response: Response,
    q: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    # Cache-aside: this is the public feed hit by every visitor
    # (including logged-out ones), so it's the single highest-traffic
    # read in the app. A cache hit skips Postgres entirely.
    #
    # X-Cache: a plain HIT/MISS response header so caching can be
    # verified with `curl -I` or a browser's Network tab — no server
    # shell or Render CLI access needed. Also reports whether Valkey is
    # even reachable right now, which is otherwise invisible from the
    # outside (the app deliberately fails silently to Postgres).
    cache_key = _event_list_cache_key(q, category)
    response.headers["X-Cache-Backend"] = "valkey" if cache_module.get_client() is not None else "unavailable"
    cached = cache_module.get_json(cache_key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return cached
    response.headers["X-Cache"] = "MISS"

    query = db.query(Event).filter(Event.status == "published")

    if q:
        search_term = f"%{q}%"
        query = query.filter(
            or_(
                Event.title.ilike(search_term),
                Event.description.ilike(search_term),
                Event.venue_name.ilike(search_term),
                Event.category.ilike(search_term),
            )
        )

    if category:
        query = query.filter(Event.category == category)

    events = query.order_by(Event.start_date).all()

    # Serialize through EventRead ourselves so what we cache is exactly
    # what a client would receive (response_model does this again on the
    # way out, which is harmless/idempotent).
    payload = [EventRead.model_validate(e, from_attributes=True).model_dump(mode="json") for e in events]
    cache_module.set_json(cache_key, payload, EVENT_LIST_CACHE_TTL_SECONDS)
    return events


@router.get("/{event_id}", response_model=EventRead)
def get_event(
    event_id: UUID,
    response: Response,
    db: Session = Depends(get_db),
):
    cache_key = _event_detail_cache_key(event_id)
    response.headers["X-Cache-Backend"] = "valkey" if cache_module.get_client() is not None else "unavailable"
    cached = cache_module.get_json(cache_key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return cached
    response.headers["X-Cache"] = "MISS"

    event = db.query(Event).filter(Event.id == event_id, Event.status == "published").first()
    if event is None:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    payload = EventRead.model_validate(event, from_attributes=True).model_dump(mode="json")
    cache_module.set_json(cache_key, payload, EVENT_DETAIL_CACHE_TTL_SECONDS)
    return event


# =============================================================================
# LIVE GATE — check-in (M-Pesa code or QR), offline-safe, and gate telemetry
# =============================================================================

def _expected_and_checked_in(db: Session, event_id: str):
    """'Expected' = paid tickets sold for the event (what the host was told to
    expect at the door). 'Checked in' = tickets whose status is checked_in.
    Awaiting = expected - checked_in, floored at 0."""
    expected = (
        db.query(func.coalesce(func.sum(Booking.quantity), 0))
        .filter(Booking.event_id == event_id, Booking.status == "booked")
        .scalar()
    ) or 0
    checked_in = (
        db.query(func.count(Ticket.id))
        .join(Booking, Booking.id == Ticket.booking_id)
        .filter(Booking.event_id == event_id, Ticket.status == "checked_in")
        .scalar()
    ) or 0
    return int(expected), int(checked_in)


class CheckInRequest(BaseModel):
    code: str = Field(..., description="M-Pesa code typed by staff, or the raw QR payload scanned off a ticket")
    method: str = Field("mpesa", description="'mpesa' or 'qr'")
    device_id: Optional[str] = None
    scanned_at: Optional[datetime] = None  # set by the client when the scan happened offline


def _find_ticket_for_code(db: Session, event_id: str, raw_code: str):
    code = (raw_code or "").strip().upper()
    if not code:
        return None
    # A ticket may carry its own QR code, or the buyer's M-Pesa receipt code
    # can be looked up through its Payment -> Booking chain. Try both so the
    # gate works whether staff typed an M-Pesa code or scanned a ticket QR.
    ticket = (
        db.query(Ticket)
        .join(Booking, Booking.id == Ticket.booking_id)
        .filter(Booking.event_id == event_id, func.upper(Ticket.ticket_code) == code)
        .first()
    )
    if ticket:
        return ticket

    payment = (
        db.query(Payment)
        .join(Booking, Booking.id == Payment.booking_id)
        .filter(Booking.event_id == event_id, func.upper(Payment.mpesa_receipt_number) == code)
        .first()
    )
    if payment:
        return (
            db.query(Ticket)
            .filter(Ticket.booking_id == payment.booking_id)
            .first()
        )

    # Free (KES 0) bookings never have an M-Pesa receipt to look up above —
    # their booking_reference (assigned the moment they're created, well
    # before any QR/ticket_code is issued) is what the gate scans/types
    # instead. Kept as a general fallback (harmless for paid bookings too,
    # since a booking_reference alone is never enough to buy a ticket) but
    # this is the path that actually matters for free events.
    booking_by_ref = (
        db.query(Booking)
        .filter(Booking.event_id == event_id, func.upper(Booking.booking_reference) == code)
        .first()
    )
    if booking_by_ref and booking_by_ref.status == "booked":
        return (
            db.query(Ticket)
            .filter(Ticket.booking_id == booking_by_ref.id)
            .first()
        )

    # BUG FIX: a scanned ticket QR is a signed JWT (see
    # qr_service.generate_encrypted_qr / issue_qr_ticket), not a short
    # code — it was never tried here at all, so every QR scan fell
    # through to "unmatched" no matter how valid the ticket was. This
    # must run against the ORIGINAL, case-preserved text (raw_code, not
    # the uppercased `code` above): JWTs are base64url and
    # case-sensitive, so uppercasing one corrupts its signature
    # irrecoverably — that's also why this can't just reuse `code`.
    stripped_raw = (raw_code or "").strip()
    if stripped_raw.count(".") == 2:
        try:
            from app.services.qr_service import decrypt_and_validate_qr
            decoded = decrypt_and_validate_qr(stripped_raw)
        except Exception:
            return None  # not a valid/signed ticket QR either — genuinely unmatched

        # SECURITY: the QR's own embedded event_id must match the event
        # this gate is scanning for. This is what actually stops a
        # ticket issued for one event from ever verifying at a
        # different event's Live Gate — the event_id filter used by
        # the two SQL lookups above doesn't apply to a signed blob, so
        # this check is doing that same job for this path.
        if str(decoded.get("event_id")) != str(event_id):
            return None

        try:
            decoded_booking_id = UUID(str(decoded.get("booking_id")))
        except (ValueError, TypeError, AttributeError):
            return None
        booking = db.query(Booking).filter(Booking.id == decoded_booking_id).first()
        # Also re-check paid status here rather than trusting the QR's
        # claims — mirrors the same defense-in-depth check
        # checkin.py's /checkin/validate already does for its own,
        # separate JWT-based flow.
        if not booking or str(booking.event_id) != str(event_id) or booking.status != "booked":
            return None
        return db.query(Ticket).filter(Ticket.booking_id == booking.id).first()

    return None


@router.post("/{event_id}/checkin")
def gate_checkin(
    event_id: str,
    payload: CheckInRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_host),
):
    """Verifies a ticket at the door via M-Pesa code or QR scan. Every
    attempt — matched, unmatched, or duplicate — is written to CheckIn so the
    gate has a durable audit trail even if the code turns out to be bad.
    Designed to be safe to call from an offline queue: duplicates are
    detected server-side by (event_id, code), so replaying a batch after
    reconnecting never double-counts a guest."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    # SECURITY: require_host only confirms the caller is *a* host somewhere
    # on the platform, not that they own *this* event. Without this check,
    # any host could scan/check in guests at any other host's event.
    if str(event.host_id) != str(current_user.id) and not getattr(current_user, "is_admin", False):
        raise HTTPException(status_code=403, detail="You do not own this event")

    if not getattr(event, "gate_unlocked", False):
        # Self-heal before hard-blocking: this event may simply be due for
        # its T-1hr auto-unlock and the 5-min scheduler hasn't caught up
        # yet. Same idempotent check as live_gate_summary/stream.py — safe
        # to call here too.
        try:
            from app.services.attendance_service import freeze_and_open_gate_for_event
            freeze_and_open_gate_for_event(db, event)
        except Exception as e:
            print(f"⚠️ On-demand Live Gate check failed for event {event_id}: {e}")

    if not getattr(event, "gate_unlocked", False):
        raise HTTPException(
            status_code=403,
            detail="Live Gate isn't open yet — it unlocks automatically about an hour before doors open. Try again shortly.",
        )

    raw_code = (payload.code or "").strip()
    if not raw_code:
        raise HTTPException(status_code=400, detail="Code is required")

    # Resolve the ticket BEFORE the duplicate check (previously this ran
    # the duplicate check first, keyed on whatever string was submitted
    # this specific time). Now that a scanned QR and a typed M-Pesa code
    # can both resolve to the SAME ticket, dedup has to key off the
    # ticket's own stable ticket_code once one is found — otherwise the
    # same guest could be checked in once via M-Pesa code and a second
    # time via their QR, since those two input strings never look alike.
    # Genuinely unmatched attempts still dedup by their literal (upper-
    # cased) text, so retyping the same bad code repeatedly doesn't spam
    # the audit log.
    ticket = _find_ticket_for_code(db, event_id, raw_code)
    dedup_code = ticket.ticket_code if (ticket and ticket.ticket_code) else raw_code.upper()

    existing = (
        db.query(CheckIn)
        .filter(CheckIn.event_id == event_id, CheckIn.code == dedup_code)
        .first()
    )
    if existing:
        expected, checked_in = _expected_and_checked_in(db, event_id)
        response = {
            "ok": False,
            "status": "duplicate",
            "message": "This code was already checked in.",
            "checked_in": checked_in,
            "awaiting": max(expected - checked_in, 0),
            "expected": expected,
        }
        # Duplicate Guard is a host-level self-service toggle (one setting
        # covers every event they run — see
        # POST /users/duplicate-guard/toggle-live-gate). When on, surface
        # who actually paid for THIS ticket so the host can compare faces
        # at the door — this is what it's for: catching a shared/resold
        # ticket, not just logging that a duplicate happened.
        if getattr(current_user, "duplicate_guard_enabled", False):
            from app.models.user import User
            original_ticket = existing.ticket_id and db.query(Ticket).filter(Ticket.id == existing.ticket_id).first()
            buyer = None
            if original_ticket:
                original_booking = db.query(Booking).filter(Booking.id == original_ticket.booking_id).first()
                if original_booking:
                    buyer = db.query(User).filter(User.id == original_booking.user_id).first()
            if buyer and buyer.duplicate_guard_status == "approved" and buyer.duplicate_guard_photo_url:
                response["duplicate_guard_photo_url"] = buyer.duplicate_guard_photo_url
                response["duplicate_guard_buyer_name"] = buyer.full_name
            else:
                response["duplicate_guard_photo_url"] = None
                response["duplicate_guard_no_photo"] = True
        return response

    checkin = CheckIn(
        event_id=event_id,
        code=dedup_code,
        method=payload.method or "mpesa",
        device_id=payload.device_id,
        scanned_at=payload.scanned_at or datetime.now(timezone.utc),
        ticket_id=ticket.id if ticket else None,
        status="verified" if ticket else "unmatched",
    )
    db.add(checkin)

    guest_name = None
    if ticket:
        ticket.status = "checked_in"
        db.add(ticket)
        booking = db.query(Booking).filter(Booking.id == ticket.booking_id).first()
        guest_name = getattr(booking, "buyer_name", None) or getattr(booking, "full_name", None)

    db.commit()

    expected, checked_in = _expected_and_checked_in(db, event_id)
    return {
        "ok": bool(ticket),
        "status": "verified" if ticket else "unmatched",
        "message": "Verified · welcome in." if ticket else "No matching ticket found — flagged for host review.",
        "guest_name": guest_name,
        "checked_in": checked_in,
        "awaiting": max(expected - checked_in, 0),
        "expected": expected,
    }


class BatchCheckInEntry(BaseModel):
    code: str
    method: str = "mpesa"
    device_id: Optional[str] = None
    scanned_at: Optional[datetime] = None


class BatchCheckInRequest(BaseModel):
    entries: List[BatchCheckInEntry]


@router.post("/{event_id}/checkin/batch")
def gate_checkin_batch(
    event_id: str,
    payload: BatchCheckInRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_host),
):
    """Flushes a queue of check-ins captured while the gate device was
    offline. Processed in the order they happened; each entry reuses the
    same duplicate-safe logic as the single check-in endpoint."""
    results = []
    for entry in payload.entries:
        result = gate_checkin(
            event_id,
            CheckInRequest(
                code=entry.code,
                method=entry.method,
                device_id=entry.device_id,
                scanned_at=entry.scanned_at,
            ),
            db=db,
            current_user=current_user,
        )
        results.append({"code": entry.code, **result})
    return {"results": results}


@router.get("/{event_id}/live-gate")
def live_gate_summary(
    event_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_host),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    # SECURITY: same ownership gap as gate_checkin above — without this,
    # any host could view another host's live gate stats and recent scans.
    if str(event.host_id) != str(current_user.id) and not getattr(current_user, "is_admin", False):
        raise HTTPException(status_code=403, detail="You do not own this event")

    # Safety net: don't rely solely on the every-5-minutes scheduler (or a
    # random Cheki feed viewer, see stream.py's _map_feed_item_to_reel) to
    # open the Live Gate at T-1hr. The host looking at their own Live Gate
    # screen is the most natural trigger point of all — if this event is
    # due and hasn't been processed yet, unlock it right now. Same
    # idempotent check the scheduler runs, safe to call on every request.
    try:
        from app.services.attendance_service import freeze_and_open_gate_for_event, FINAL_LIST_WINDOW
        freeze_and_open_gate_for_event(db, event)
    except Exception as e:
        print(f"⚠️ On-demand Live Gate check failed for event {event_id}: {e}")

    gate_unlocked = bool(getattr(event, "gate_unlocked", False))

    # When it's still locked, say exactly why. A bare "try again shortly"
    # was indistinguishable from a real bug — this makes "not due for
    # another 40 minutes" and "something is actually wrong" look
    # different, both to a host reading the message and to anyone
    # debugging alongside them.
    unlock_reason = None
    unlocks_at = None
    if not gate_unlocked:
        if event.status != "published":
            unlock_reason = "event_not_published"
        elif not event.start_date:
            unlock_reason = "no_start_date_set"
        elif event.start_date > datetime.utcnow() + FINAL_LIST_WINDOW:
            unlock_reason = "not_due_yet"
            unlocks_at = (event.start_date - FINAL_LIST_WINDOW).isoformat() + "Z"
        else:
            # Due by every check above, but still locked — this combination
            # shouldn't be reachable given freeze_and_open_gate_for_event
            # just ran above. Naming it distinctly means it can't quietly
            # masquerade as normal "not due yet" waiting if it ever does
            # happen — that's the one case that actually needs a look.
            unlock_reason = "due_but_still_locked"

    expected, checked_in = _expected_and_checked_in(db, event_id)

    recent = (
        db.query(CheckIn)
        .filter(CheckIn.event_id == event_id, CheckIn.status == "verified")
        .order_by(CheckIn.scanned_at.desc())
        .limit(20)
        .all()
    )

    return {
        "event_id": event_id,
        "gate_unlocked": gate_unlocked,
        "unlock_reason": unlock_reason,
        "unlocks_at": unlocks_at,
        "expected": expected,
        "checked_in": checked_in,
        "awaiting": max(expected - checked_in, 0),
        "recent": [
            {
                "code": c.code,
                "method": c.method,
                "scanned_at": c.scanned_at.isoformat() if c.scanned_at else None,
            }
            for c in recent
        ],
    }

# =============================================================================
# Purchase window status + "Notify Me" waitlist — the buyer-facing bell
# button. Between T-2 and T-1, general sales are closed but reclaimed
# capacity from declines/no-shows can be bought by whoever's subscribed
# here (see attendance_service.can_purchase / notify_waitlist_of_reopening).
# =============================================================================

@router.get("/{event_id}/purchase-window")
def get_purchase_window(event_id: UUID, db: Session = Depends(get_db)):
    """Frontend polls/checks this to decide whether to show a normal Buy
    button, a Notify Me bell, or a 'sales closed' state."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    phase = purchase_window_phase(event)
    return {
        "event_id": str(event.id),
        "phase": phase,  # "open" | "reclaim" | "closed"
        "reclaimed_available": int(getattr(event, "reclaimed_capacity", 0) or 0),
    }


@router.post("/{event_id}/notify-me")
def subscribe_waitlist(
    event_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Tap the bell — subscribes this buyer to a one-time ping the moment
    a reclaimed ticket opens up for this event before T-1."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    existing = (
        db.query(TicketWaitlist)
        .filter(TicketWaitlist.event_id == event.id, TicketWaitlist.user_id == current_user.id)
        .first()
    )
    if existing:
        return {"subscribed": True, "already_subscribed": True}

    db.add(TicketWaitlist(event_id=event.id, user_id=current_user.id))
    db.commit()
    return {"subscribed": True, "already_subscribed": False}


@router.delete("/{event_id}/notify-me")
def unsubscribe_waitlist(
    event_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    db.query(TicketWaitlist).filter(
        TicketWaitlist.event_id == event_id,
        TicketWaitlist.user_id == current_user.id,
    ).delete(synchronize_session=False)
    db.commit()
    return {"subscribed": False}


@router.get("/{event_id}/squad-attendance")
def squad_attendance(
    event_id: UUID,
    usernames: str = "",
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    BUG FIX: the ticket modal's "squad" row was showing the viewer's ENTIRE
    companions list for every event, regardless of whether any of them
    actually had a ticket to it — since that list is just their mutual
    followers (see messages.py's _is_squad), which has nothing to do with
    this specific event's bookings. This endpoint lets the frontend narrow
    that list down to just the squad members who've actually paid.
    """
    from app.models.user import User

    names = [u.strip().lstrip("@") for u in usernames.split(",") if u.strip()]
    if not names:
        return {"paid_usernames": []}

    paid_usernames = (
        db.query(User.username)
        .join(Booking, Booking.user_id == User.id)
        .filter(
            Booking.event_id == event_id,
            Booking.status == "booked",
            func.lower(User.username).in_([n.lower() for n in names]),
        )
        .distinct()
        .all()
    )
    return {"paid_usernames": [row[0] for row in paid_usernames]}


class RateEventRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)


@router.post("/{event_id}/rate")
def rate_event(
    event_id: UUID,
    payload: RateEventRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Submit (or update) a 1-5 star rating for an event you hold a paid
    ticket for. Only allowed once the event has started — see
    rating_service.submit_rating for the full eligibility check. Feeds
    directly into the host's Gold Organiser badge eligibility."""
    from app.services.rating_service import submit_rating, get_event_rating_summary, RatingError

    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    try:
        submit_rating(db, event, current_user, payload.rating)
    except RatingError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return get_event_rating_summary(db, event_id, viewer_user_id=current_user.id)


@router.get("/{event_id}/rating")
def get_event_rating(
    event_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Average rating, count, and the current viewer's own rating (if any)
    — lets the frontend show 'you rated this 4 stars' instead of a blank
    star picker once someone's already rated."""
    from app.services.rating_service import get_event_rating_summary

    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    return get_event_rating_summary(db, event_id, viewer_user_id=current_user.id)