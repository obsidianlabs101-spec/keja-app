from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.event import Event
from app.models.user import User
from app.models.withdrawal import Withdrawal
from app.models.notification import Notification
from app.models.support_ticket import SupportTicket
from app.models.header_poll import HeaderPoll, HeaderPollOption, HeaderBid
from app.services.admin_service import log_admin_activity
from app.models.platform_settings import PlatformSettings, get_or_create_platform_settings
from app.api.v1.events import _invalidate_event_caches
from app.models.payment import Payment
from app.models.booking import Booking
from app.models.event import Event
from app.services.manual_payment_service import batch_match_admin_codes, force_match_payment
from app.models.cheki_feed_item import ChekiFeedItem
from app.models.cheki_like import ChekiLike
from app.models.taxonomy_entry import TaxonomyEntry

router = APIRouter(prefix="/admin", tags=["Admin"])


# =============================================================================
# TECHNICAL DIFFICULTIES SWITCH — free-events-only kill-switch
# =============================================================================
# One admin-panel subpage button. Pressed once: new events can only be
# posted as free (see events.py's create_new_event, which reads this same
# row), and the host dashboard shows the "technical difficulties" banner
# and hides its price/ticket-tier calculator (see GET /events/platform-status,
# a public no-auth endpoint the host dashboard polls). Pressed again: back
# to normal. Does NOT touch any event/booking that already exists — only
# gates the creation of *new* paid events.
@router.get("/platform-settings")
def get_platform_settings(
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    row = get_or_create_platform_settings(db)
    return {
        "free_events_only": bool(row.free_events_only),
        "updated_at": row.free_events_only_updated_at.isoformat() if row.free_events_only_updated_at else None,
        "manual_payment_mode": bool(row.manual_payment_mode),
        "manual_payment_mode_updated_at": row.manual_payment_mode_updated_at.isoformat() if row.manual_payment_mode_updated_at else None,
        "referral_gate_enabled": bool(row.referral_gate_enabled),
        "referral_gate_enabled_updated_at": row.referral_gate_enabled_updated_at.isoformat() if row.referral_gate_enabled_updated_at else None,
    }


# =============================================================================
# REFERRAL GATE SWITCH — same one-row-table pattern as the two switches
# above. OFF by default (server_default="false" on the column) — free
# events are simply bookable, no referral required, no padlocks shown
# anywhere (see referral.js's isLocked(), which polls GET
# /events/platform-status to know this). Flipping this ON brings back the
# original mechanic exactly as it was: see booking_service.
# create_free_booking_fcfs for the enforcement this actually gates.
# =============================================================================
@router.post("/platform-settings/toggle-referral-gate")
def toggle_referral_gate(
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    row = get_or_create_platform_settings(db)
    row.referral_gate_enabled = not bool(row.referral_gate_enabled)
    row.referral_gate_enabled_updated_at = datetime.utcnow()
    row.referral_gate_enabled_updated_by_admin_id = admin.id
    db.add(row)
    db.commit()
    db.refresh(row)

    log_admin_activity(
        db,
        admin.id,
        action="toggle_referral_gate",
        detail=f"Referral gate switched {'ON' if row.referral_gate_enabled else 'OFF'}",
    )

    return {
        "referral_gate_enabled": bool(row.referral_gate_enabled),
        "updated_at": row.referral_gate_enabled_updated_at.isoformat() if row.referral_gate_enabled_updated_at else None,
    }


# =============================================================================
# MANUAL PAYMENT MODE SWITCH — same one-row-table pattern as the
# free-events-only switch above. See app/services/manual_payment_service.py
# and POST /payments/mpesa/stk-push for what actually changes when this is on.
# =============================================================================
@router.post("/platform-settings/toggle-manual-payment-mode")
def toggle_manual_payment_mode(
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    row = get_or_create_platform_settings(db)
    row.manual_payment_mode = not bool(row.manual_payment_mode)
    row.manual_payment_mode_updated_at = datetime.utcnow()
    row.manual_payment_mode_updated_by_admin_id = admin.id
    db.add(row)
    db.commit()
    db.refresh(row)

    log_admin_activity(
        db,
        admin.id,
        action="toggle_manual_payment_mode",
        detail=f"Manual payment mode switched {'ON' if row.manual_payment_mode else 'OFF'}",
    )

    return {
        "manual_payment_mode": bool(row.manual_payment_mode),
        "updated_at": row.manual_payment_mode_updated_at.isoformat() if row.manual_payment_mode_updated_at else None,
    }


# =============================================================================
# MANUAL PAYMENTS — admin subpage for matching buyer-claimed M-Pesa codes
# against the real paybill statement. See manual_payment_service for the
# matching logic; this is just the admin-facing CRUD around it.
# =============================================================================
@router.get("/manual-payments/pending-count")
def admin_manual_payments_pending_count(db: Session = Depends(get_db), admin=Depends(require_admin)):
    """Badge count for the Manual Payments sidebar icon."""
    count = (
        db.query(Payment)
        .filter(
            Payment.provider == "mpesa_manual",
            Payment.status.in_(["awaiting_manual_payment", "awaiting_admin_match"]),
        )
        .count()
    )
    return {"count": count}


@router.get("/manual-payments/pending")
def admin_manual_payments_pending(db: Session = Depends(get_db), admin=Depends(require_admin)):
    """Every manual payment still waiting on either the buyer's code or an
    admin match, newest first, with enough booking/event/buyer context to
    review at a glance."""
    rows = (
        db.query(Payment, Booking, Event, User)
        .join(Booking, Booking.id == Payment.booking_id)
        .outerjoin(Event, Event.id == Booking.event_id)
        .outerjoin(User, User.id == Booking.user_id)
        .filter(
            Payment.provider == "mpesa_manual",
            Payment.status.in_(["awaiting_manual_payment", "awaiting_admin_match"]),
        )
        .order_by(Payment.created_at.desc())
        .all()
    )
    return {
        "pending": [
            {
                "payment_id": str(p.id),
                "booking_id": str(b.id),
                "booking_reference": b.booking_reference,
                "event_title": e.title if e else None,
                "buyer_name": u.full_name if u else None,
                "buyer_username": u.username if u else None,
                "amount": p.amount,
                "status": p.status,
                "buyer_claimed_code": p.buyer_claimed_code,
                "buyer_claimed_raw_message": p.buyer_claimed_raw_message,
                "buyer_claimed_at": p.buyer_claimed_at.isoformat() if p.buyer_claimed_at else None,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p, b, e, u in rows
        ]
    }


class ManualPaymentBatchMatchPayload(BaseModel):
    raw_text: str


@router.post("/manual-payments/batch-match")
def admin_manual_payments_batch_match(
    data: ManualPaymentBatchMatchPayload,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    """Admin pastes in a batch of the real confirmation messages/codes
    copied from the paybill statement — one per line, or separated by
    blank lines if pasting full SMS text. Anything that matches a pending
    buyer claim (same code, same amount) finalizes that booking's ticket
    immediately; the rest is parked for the next buyer claim to catch."""
    if not (data.raw_text or "").strip():
        raise HTTPException(status_code=400, detail="Paste at least one code or confirmation message")

    result = batch_match_admin_codes(db, data.raw_text, admin.id)

    log_admin_activity(
        db,
        admin.id,
        action="manual_payments_batch_match",
        detail=f"Matched {result['matched_count']} booking(s), pooled {result['pooled_count']} unmatched code(s)",
    )

    return result


class ManualPaymentForceMatchPayload(BaseModel):
    admin_note: Optional[str] = None


@router.post("/manual-payments/{payment_id}/force-match")
def admin_manual_payments_force_match(
    payment_id: str,
    data: ManualPaymentForceMatchPayload,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    """Escape hatch for a claim an admin has manually verified against the
    statement but that didn't auto-match (e.g. amount off by a rounding/
    fee difference). Use with care — this bypasses the code+amount check."""
    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.provider == "mpesa_manual").first()
    if not payment:
        raise HTTPException(status_code=404, detail="Manual payment not found")
    if payment.status == "paid":
        raise HTTPException(status_code=400, detail="Already matched")

    payment = force_match_payment(db, payment, admin.id, admin_note=data.admin_note)

    log_admin_activity(
        db,
        admin.id,
        action="manual_payment_force_match",
        detail=f"Force-matched payment {payment.id} for booking {payment.booking_id}" + (f" — {data.admin_note}" if data.admin_note else ""),
        amount=payment.amount,
    )

    return {"payment_id": str(payment.id), "booking_id": str(payment.booking_id), "status": payment.status}


# =============================================================================
# DUPLICATE GUARD — admin review queue for submitted verification photos.
# Approving/rejecting the photo is the only admin-gated part of this
# feature; the Live Gate toggle itself is self-service (see
# POST /users/duplicate-guard/toggle-live-gate).
# =============================================================================
@router.get("/duplicate-guard/pending")
def admin_duplicate_guard_pending(db: Session = Depends(get_db), admin=Depends(require_admin)):
    rows = (
        db.query(User)
        .filter(User.duplicate_guard_status == "pending")
        .order_by(User.duplicate_guard_submitted_at.asc())
        .all()
    )
    return {
        "pending": [
            {
                "user_id": str(u.id),
                "username": u.username,
                "full_name": u.full_name,
                "photo_url": u.duplicate_guard_photo_url,
                "submitted_at": u.duplicate_guard_submitted_at.isoformat() if u.duplicate_guard_submitted_at else None,
            }
            for u in rows
        ]
    }


class DuplicateGuardRejectPayload(BaseModel):
    reason: Optional[str] = None


@router.post("/duplicate-guard/{user_id}/approve")
def admin_duplicate_guard_approve(user_id: str, db: Session = Depends(get_db), admin=Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.duplicate_guard_status != "pending":
        raise HTTPException(status_code=400, detail="This submission isn't awaiting review")

    user.duplicate_guard_status = "approved"
    user.duplicate_guard_reviewed_at = datetime.utcnow()
    user.duplicate_guard_rejection_reason = None
    db.add(user)
    db.commit()

    log_admin_activity(db, admin.id, action="duplicate_guard_approve", detail=f"Approved verification photo for {user.username}")
    return {"user_id": str(user.id), "duplicate_guard_status": user.duplicate_guard_status}


@router.post("/duplicate-guard/{user_id}/reject")
def admin_duplicate_guard_reject(user_id: str, data: DuplicateGuardRejectPayload, db: Session = Depends(get_db), admin=Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.duplicate_guard_status != "pending":
        raise HTTPException(status_code=400, detail="This submission isn't awaiting review")

    user.duplicate_guard_status = "rejected"
    user.duplicate_guard_reviewed_at = datetime.utcnow()
    user.duplicate_guard_rejection_reason = (data.reason or "").strip() or None
    db.add(user)
    db.commit()

    log_admin_activity(db, admin.id, action="duplicate_guard_reject", detail=f"Rejected verification photo for {user.username}" + (f" — {data.reason}" if data.reason else ""))
    return {"user_id": str(user.id), "duplicate_guard_status": user.duplicate_guard_status}


@router.post("/platform-settings/toggle-free-only")
def toggle_free_events_only(
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    row = get_or_create_platform_settings(db)
    row.free_events_only = not bool(row.free_events_only)
    row.free_events_only_updated_at = datetime.utcnow()
    row.free_events_only_updated_by_admin_id = admin.id
    db.add(row)
    db.commit()
    db.refresh(row)

    log_admin_activity(
        db,
        admin.id,
        action="toggle_free_events_only",
        detail=f"Free-events-only switched {'ON' if row.free_events_only else 'OFF'}",
    )

    return {
        "free_events_only": bool(row.free_events_only),
        "updated_at": row.free_events_only_updated_at.isoformat() if row.free_events_only_updated_at else None,
    }


# SECURITY: this endpoint returns every host's email address and full
# name alongside their events, with no auth check at all previously —
# a straightforward PII leak to anyone who found the URL. Now admin-only.
@router.get("/events/all")
def admin_list_all_events(
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    reviewed: Optional[str] = None,  # "reviewed" | "unreviewed" | None (all)
    admin=Depends(require_admin),
):
    # Default: return published + ended (end_date in the past)
    # Joined against User so the Admin "Events Uploaded" subpage can show host
    # email/name without a second round-trip per row.
    query = db.query(Event, User).join(User, User.id == Event.host_id)

    if status:
        query = query.filter(Event.status == status)
    else:
        query = query.filter(
            or_(
                Event.status == "published",
                # ended events: end_date set
                (Event.end_date != None),
            )
        )

    if reviewed == "reviewed":
        query = query.filter(Event.reviewed_at != None)
    elif reviewed == "unreviewed":
        query = query.filter(Event.reviewed_at == None)

    # If end_date exists but status isn't published, still show ended.
    query = query.order_by(Event.start_date.desc())
    rows = query.all()
    return [
        {
            "id": str(e.id),
            "host_id": str(e.host_id),
            "host_email": u.email,
            "host_name": u.full_name,
            "title": e.title,
            "description": e.description,
            "category": e.category,
            "venue_name": e.venue_name,
            "county": getattr(e, "county", None),
            "price": e.price,
            "capacity": e.capacity,
            "start_date": e.start_date.isoformat() if e.start_date else None,
            "end_date": e.end_date.isoformat() if e.end_date else None,
            "ticket_deadline": e.ticket_deadline.isoformat() if getattr(e, "ticket_deadline", None) else None,
            # Event has separate poster_url/video_url columns, not a single
            # media_url — video takes priority for the admin preview since a
            # host event can only realistically have one primary media file.
            "media_url": getattr(e, "video_url", None) or getattr(e, "poster_url", None),
            "status": e.status,
            "reviewed_at": e.reviewed_at.isoformat() if getattr(e, "reviewed_at", None) else None,
            "reviewed_by_admin_id": str(e.reviewed_by_admin_id) if getattr(e, "reviewed_by_admin_id", None) else None,
        }
        for e, u in rows
    ]


@router.get("/events/reviewed-counts")
def admin_events_reviewed_counts(db: Session = Depends(get_db), admin=Depends(require_admin)):
    """Powers the Reviewed/Not Reviewed nav-tab badges on the Events
    Uploaded subpage."""
    base = db.query(Event).filter(
        or_(Event.status == "published", (Event.end_date != None))
    )
    unreviewed = base.filter(Event.reviewed_at == None).count()
    reviewed = base.filter(Event.reviewed_at != None).count()
    return {"reviewed": reviewed, "unreviewed": unreviewed}


@router.post("/events/{event_id}/mark-reviewed")
def admin_mark_event_reviewed(
    event_id: str,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    """Lets an admin tick an event off as looked-at on the Events Uploaded
    subpage, so the Not Reviewed tab only ever shows what's actually still
    outstanding for whoever logs in next."""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    now = datetime.utcnow()
    event.reviewed_by_admin_id = admin.id
    event.reviewed_at = now
    db.add(event)
    log_admin_activity(db, admin.id, "event_reviewed", detail=f"Marked \"{event.title}\" as reviewed")
    db.commit()
    return {"event_id": str(event.id), "reviewed_at": now.isoformat(), "reviewed_by_admin_id": str(admin.id)}


# SECURITY: financial data (per-host payout totals) plus host email/name,
# previously reachable with no auth at all. Now admin-only.
@router.get("/hosts/paid-summary")
def admin_hosts_paid_summary(db: Session = Depends(get_db), admin=Depends(require_admin)):
    # "paid" = the withdrawal pipeline's final settled state (mpesa code
    # logged, host notified) — this used to check "released", a status
    # nothing in the new request -> message -> confirm/deny -> paid
    # pipeline ever sets, so paid hosts never showed up here.
    released = (
        db.query(
            Withdrawal.host_id,
            func.coalesce(func.sum(Withdrawal.host_payout_amount), 0).label("released_amount"),
            func.count(Withdrawal.id).label("released_withdrawals_count"),
        )
        .filter(Withdrawal.status == "paid")
        .group_by(Withdrawal.host_id)
        .all()
    )

    by_host = {str(r.host_id): r for r in released}

    # include disallowed hosts even if no release exists? request says check paid & disallow.
    # We'll return all hosts that appear either in released set or disallowed (is_host=false).
    disallowed_hosts = db.query(User).filter(User.is_host == False).all()  # noqa

    host_ids = set(by_host.keys())
    host_ids.update([str(u.id) for u in disallowed_hosts])

    if not host_ids:
        return []

    # Safe second query
    users = db.query(User).filter(User.id.in_(list(host_ids))).all() if host_ids else []

    rows = []

    for u in users:
        key = str(u.id)
        rel = by_host.get(key)
        rows.append(
            {
                "host_id": key,
                "email": u.email,
                "full_name": u.full_name,
                "released_amount": float(rel.released_amount) if rel else 0.0,
                "released_withdrawals_count": int(rel.released_withdrawals_count) if rel else 0,
                "is_host_allowed": bool(u.is_host),
            }
        )

    return rows


@router.post("/hosts/{user_id}/revoke")
def admin_revoke_host(user_id: str, db: Session = Depends(get_db), admin=Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_host = False
    # set to rejected for onboarding status
    if getattr(user, "host_verification_status", None) in ("approved", "pending"):
        user.host_verification_status = "rejected"

    db.add(user)
    log_admin_activity(db, admin.id, "host_revoke", detail=f"Revoked host access for {user.full_name or user.email}")
    db.commit()
    db.refresh(user)
    return {
        "id": str(user.id),
        "email": user.email,
        "is_host": user.is_host,
        "host_verification_status": user.host_verification_status,
    }


# =============================================================================
# Event revoke — the admin "revoke this event" action from the expanded
# event detail view. Pulls the event out of every surface it appears on
# (ticket purchase, Cheki feed, host's own dashboard listing) and fully
# refunds any buyer who already paid (no processing-fee deduction, since
# this is a platform-side cancellation, not the buyer changing their mind).
# =============================================================================

@router.post("/events/{event_id}/revoke")
def admin_revoke_event(
    event_id: str,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    from app.models.booking import Booking
    from app.models.payment import Payment
    from app.models.ticket import Ticket
    from app.models.cheki_feed_item import ChekiFeedItem

    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    revoke_reason = (reason or "").strip() or "Removed by BASH admin"

    # 1. Pull it out of ticket purchase / listing surfaces immediately.
    event.status = "revoked"
    event.gate_unlocked = False
    db.add(event)

    # 2. Pull it out of the Cheki feed — reel_id is the raw event UUID
    #    for host-posted events (see host_dashboard.js Step 4 feed sync).
    #
    #    BUG FIX: this used to be a hard `.delete()`. cheki_comments.feed_item_id
    #    and cheki_likes.feed_item_id are both foreign keys onto
    #    cheki_feed_items.reel_id with no cascade, so deleting the row
    #    outright threw a foreign-key-violation database error the moment
    #    the event's post had a single comment or like on it — aborting
    #    this whole function before db.commit() ever ran, so *nothing*
    #    (not even event.status) was actually saved. Soft-revoke instead,
    #    matching admin_revoke_community_post below, and let the feed
    #    query's revoked_at filter (see stream.py) keep it off the feed.
    feed_item = db.query(ChekiFeedItem).filter(ChekiFeedItem.reel_id == str(event.id)).first()
    if feed_item is not None:
        feed_item.revoked_at = datetime.utcnow()
        feed_item.revoked_by_admin_id = admin.id
        db.add(feed_item)

    # 3. Fully refund every paid buyer (no fee deducted — this is a
    #    platform cancellation, not the buyer backing out).
    now = datetime.utcnow()
    paid_bookings = db.query(Booking).filter(Booking.event_id == event.id, Booking.status == "booked").all()
    refunded_count = 0
    refunded_total = 0.0
    for booking in paid_bookings:
        payment = (
            db.query(Payment)
            .filter(Payment.booking_id == booking.id, Payment.status == "paid")
            .order_by(Payment.created_at.desc())
            .first()
        )
        # Refund what the buyer actually PAID (payment.amount, or
        # buyer_total_amount as a fallback) — NOT booking.total_amount,
        # which is the host's raw pre-markup value and would shortchange
        # buyers by the 12% checkout markup on what's supposed to be a
        # full, fee-free refund. See the column comments on Booking.
        gross = float(
            (payment.amount if payment else None)
            or booking.buyer_total_amount
            or (float(booking.total_amount or 0) * 1.12)
        )
        booking.status = "refunded"
        booking.confirmation_status = "refunded"
        booking.refunded_at = now
        booking.refund_fee_amount = 0
        booking.refund_amount = gross
        booking.refund_payout_status = "requested"
        booking.updated_at = now
        db.add(booking)
        if payment:
            payment.refunded_amount = gross
            payment.refund_fee_amount = 0
            payment.refunded_at = now
            db.add(payment)
        db.query(Ticket).filter(Ticket.booking_id == booking.id).update(
            {"status": "refunded"}, synchronize_session=False
        )
        refunded_count += 1
        refunded_total += gross

        db.add(Notification(
            user_id=booking.user_id,
            type="event_revoked_refund",
            title=f"Event cancelled — {event.title}",
            body=(
                f"\"{event.title}\" was cancelled by BASH ({revoke_reason}). You've been fully "
                f"refunded KES {gross:,.2f} — no fee deducted."
            ),
            data={"event_id": str(event.id), "booking_id": str(booking.id), "refund_amount": gross},
            context="user",
        ))

    # 4. Notify the host.
    db.add(Notification(
        user_id=event.host_id,
        type="event_revoked",
        title=f"Event removed — {event.title}",
        body=(
            f"\"{event.title}\" was revoked by a BASH admin ({revoke_reason}) and removed from "
            f"the platform. {refunded_count} buyer(s) were fully refunded a total of "
            f"KES {refunded_total:,.2f}."
        ),
        data={"event_id": str(event.id), "reason": revoke_reason, "refunded_count": refunded_count},
        context="host",
    ))

    db.commit()

    log_admin_activity(
        db, admin.id, "event_revoke",
        detail=f"Revoked \"{event.title}\" ({revoke_reason}) — {refunded_count} refunded",
        amount=refunded_total,
    )
    db.commit()

    # The comment above ("pull it out of listing surfaces immediately")
    # is only true if the cache is invalidated too — otherwise a revoked
    # event stays visible/bookable in the public feed for up to
    # EVENT_LIST_CACHE_TTL_SECONDS after this returns.
    _invalidate_event_caches(event.id)

    return {
        "event_id": str(event.id),
        "status": "revoked",
        "refunded_bookings": refunded_count,
        "refunded_total": refunded_total,
    }


# =============================================================================
# Community Posts — the Events Uploaded > Community Posts tab. These are
# ChekiFeedItem rows with badge_type == "community" (as opposed to a host's
# own event post). Admins can mark one "seen" and can revoke one off the
# Cheki feed without deleting the row, so there's still a record of it.
# =============================================================================

@router.get("/community-posts")
def admin_list_community_posts(
    db: Session = Depends(get_db),
    seen: Optional[str] = None,  # "seen" | "unseen" | None (all)
    admin=Depends(require_admin),
):
    from app.models.cheki_feed_item import ChekiFeedItem

    query = db.query(ChekiFeedItem).filter(ChekiFeedItem.badge_type == "community")
    if seen == "seen":
        query = query.filter(ChekiFeedItem.seen_by_admin_at != None)
    elif seen == "unseen":
        query = query.filter(ChekiFeedItem.seen_by_admin_at == None)

    rows = query.order_by(ChekiFeedItem.created_at.desc()).limit(300).all()
    return [
        {
            "id": str(p.id),
            "reel_id": p.reel_id,
            "username": p.username,
            "profile_picture": p.profile_picture,
            "media_url": p.media_url,
            "caption": p.caption,
            "location": p.location,
            "county": p.county,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "seen_by_admin_at": p.seen_by_admin_at.isoformat() if p.seen_by_admin_at else None,
            "revoked_at": p.revoked_at.isoformat() if p.revoked_at else None,
        }
        for p in rows
    ]


@router.get("/community-posts/seen-counts")
def admin_community_posts_seen_counts(db: Session = Depends(get_db), admin=Depends(require_admin)):
    from app.models.cheki_feed_item import ChekiFeedItem

    base = db.query(ChekiFeedItem).filter(
        ChekiFeedItem.badge_type == "community", ChekiFeedItem.revoked_at == None
    )
    unseen = base.filter(ChekiFeedItem.seen_by_admin_at == None).count()
    seen = base.filter(ChekiFeedItem.seen_by_admin_at != None).count()
    return {"seen": seen, "unseen": unseen}


@router.post("/community-posts/{post_id}/mark-seen")
def admin_mark_community_post_seen(post_id: str, db: Session = Depends(get_db), admin=Depends(require_admin)):
    from app.models.cheki_feed_item import ChekiFeedItem

    post = db.query(ChekiFeedItem).filter(ChekiFeedItem.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Community post not found")
    now = datetime.utcnow()
    post.seen_by_admin_id = admin.id
    post.seen_by_admin_at = now
    db.add(post)
    db.commit()
    return {"id": str(post.id), "seen_by_admin_at": now.isoformat()}


@router.post("/community-posts/{post_id}/revoke")
def admin_revoke_community_post(post_id: str, db: Session = Depends(get_db), admin=Depends(require_admin)):
    from app.models.cheki_feed_item import ChekiFeedItem

    post = db.query(ChekiFeedItem).filter(ChekiFeedItem.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Community post not found")
    now = datetime.utcnow()
    post.revoked_at = now
    post.revoked_by_admin_id = admin.id
    # A revoke implies it's been seen, too.
    if not post.seen_by_admin_at:
        post.seen_by_admin_at = now
        post.seen_by_admin_id = admin.id
    db.add(post)
    log_admin_activity(db, admin.id, "community_post_revoke", detail=f"Revoked community post by {post.username or 'unknown'}")
    db.commit()
    return {"id": str(post.id), "revoked_at": now.isoformat()}


# =============================================================================
# Refunds — the admin Refunds subpage. "Requested" bookings are refunded
# (buyer is owed money) but the admin hasn't yet sent it back and logged the
# M-Pesa proof; "Paid" is once they have. Grouped by event so one event
# shows all of its outstanding refunds in a single list.
# =============================================================================

def _refund_bookings_query(db: Session, payout_status: str):
    from app.models.booking import Booking
    q = db.query(Booking).filter(Booking.status == "refunded")
    if payout_status == "paid":
        q = q.filter(Booking.refund_payout_status == "paid")
    else:
        # Anything not explicitly marked paid counts as still requested —
        # covers rows refunded before this column existed (NULL) too.
        q = q.filter(or_(Booking.refund_payout_status == None, Booking.refund_payout_status == "requested"))
    return q


@router.get("/refunds/pending-count")
def admin_refunds_pending_count(db: Session = Depends(get_db), admin=Depends(require_admin)):
    """Badge count for the Refunds sidebar icon — how many refunds still
    need the admin to actually send the money and log the M-Pesa code."""
    count = _refund_bookings_query(db, "requested").count()
    return {"pending": count}


@router.get("/refunds/events")
def admin_refunds_events(
    status: str = "requested",  # "requested" | "paid"
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    """One row per event that has at least one refund in this status, with
    a count, so the Refunds subpage can show 'this event has 3 refunds
    still owed' before drilling in."""
    from app.models.booking import Booking

    bookings = _refund_bookings_query(db, status).all()
    by_event = {}
    for b in bookings:
        by_event.setdefault(str(b.event_id), []).append(b)

    if not by_event:
        return []

    events = db.query(Event).filter(Event.id.in_(by_event.keys())).all()
    events_by_id = {str(e.id): e for e in events}

    out = []
    for event_id, rows in by_event.items():
        event = events_by_id.get(event_id)
        total_amount = sum(float(r.refund_amount or 0) for r in rows)
        out.append({
            "event_id": event_id,
            "event_title": event.title if event else "Unknown event",
            "media_url": (getattr(event, "video_url", None) or getattr(event, "poster_url", None)) if event else None,
            "count": len(rows),
            "total_amount": total_amount,
        })
    out.sort(key=lambda r: r["count"], reverse=True)
    return out


@router.get("/refunds/events/{event_id}")
def admin_refunds_for_event(
    event_id: str,
    status: str = "requested",
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    """The per-event list of refunds in a given status — this is what
    renders when the admin drills into one event on the Refunds subpage."""
    from app.models.booking import Booking

    rows = (
        _refund_bookings_query(db, status)
        .filter(Booking.event_id == event_id)
        .order_by(Booking.refunded_at.desc())
        .all()
    )
    event = db.query(Event).filter(Event.id == event_id).first()

    out = []
    for b in rows:
        buyer = db.query(User).filter(User.id == b.user_id).first()
        paid_by_admin = None
        if getattr(b, "refund_paid_by_admin_id", None):
            paid_by_admin = db.query(User).filter(User.id == b.refund_paid_by_admin_id).first()
        out.append({
            "booking_id": str(b.id),
            "booking_reference": b.booking_reference,
            "buyer_name": buyer.full_name if buyer else "Unknown buyer",
            "buyer_phone": buyer.phone if buyer else None,
            "buyer_username": buyer.username if buyer else None,
            "amount": b.refund_amount,
            "requested_at": b.refunded_at.isoformat() if b.refunded_at else None,
            "refund_payout_status": b.refund_payout_status or "requested",
            "refund_mpesa_code": b.refund_mpesa_code,
            "refund_paid_at": b.refund_paid_at.isoformat() if b.refund_paid_at else None,
            "refund_paid_by_admin_name": (paid_by_admin.full_name if paid_by_admin else None),
        })
    return {
        "event_id": event_id,
        "event_title": event.title if event else "Unknown event",
        "refunds": out,
    }


class RefundMarkPaidPayload(BaseModel):
    mpesa_code: str


@router.post("/refunds/bookings/{booking_id}/mark-paid")
def admin_mark_refund_paid(
    booking_id: str,
    data: RefundMarkPaidPayload,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    """The admin has manually sent the buyer their M-Pesa refund and pastes
    the confirmation code in as proof — this moves the booking from
    Requested to Paid with the code plus the exact date/time it was paid."""
    from app.models.booking import Booking

    code = (data.mpesa_code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="M-Pesa code is required")

    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Refund booking not found")
    if booking.status != "refunded":
        raise HTTPException(status_code=400, detail="This booking isn't in a refunded state")

    now = datetime.utcnow()
    booking.refund_payout_status = "paid"
    booking.refund_mpesa_code = code
    booking.refund_paid_at = now
    booking.refund_paid_by_admin_id = admin.id
    db.add(booking)

    buyer = db.query(User).filter(User.id == booking.user_id).first()
    db.add(Notification(
        user_id=booking.user_id,
        type="refund_paid",
        title="Refund sent",
        body=f"Your refund of KES {float(booking.refund_amount or 0):,.2f} has been sent via M-Pesa (code {code}).",
        data={"booking_id": str(booking.id), "mpesa_code": code},
        context="user",
    ))

    log_admin_activity(
        db, admin.id, "refund_mark_paid",
        detail=f"Paid refund to {buyer.full_name if buyer else booking.user_id} — code {code}",
        amount=booking.refund_amount,
    )
    db.commit()

    return {
        "booking_id": str(booking.id),
        "refund_payout_status": "paid",
        "refund_mpesa_code": code,
        "refund_paid_at": now.isoformat(),
    }


# =============================================================================
# Broadcasts — the admin "Broadcasts & Support" page's Issue Global Broadcast
# button. Creates one Notification per recipient. "organisers" lands in each
# host's dashboard "HQ Official Broadcasts" panel (context="host"); "community"
# lands in every account's personal profile inbox — the "Bash Updates" thread
# in Messages (context="user"), the same channel refund/payout notices use.
# "all" sends both, so a host account gets one of each: their host-dashboard
# copy and their personal-profile copy, matching how a single account can be
# both a buyer and a host with two separate inboxes (see Notification.context).
# =============================================================================

class BroadcastPayload(BaseModel):
    title: str
    body: str
    type: str = "system_alert"  # "system_alert" | "payout_processed"
    reference: Optional[str] = None
    audience: str = "organisers"  # "organisers" | "community" | "all"


@router.post("/broadcast")
def send_broadcast(
    data: BroadcastPayload,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    if not data.title.strip() or not data.body.strip():
        raise HTTPException(status_code=400, detail="Title and body are required")

    audience = (data.audience or "organisers").strip().lower()
    if audience not in ("organisers", "community", "all"):
        raise HTTPException(status_code=400, detail="audience must be organisers, community, or all")

    extra_data = {"reference": data.reference} if data.reference else None
    host_count = 0
    community_count = 0

    if audience in ("organisers", "all"):
        hosts = db.query(User).filter(User.is_host == True).all()  # noqa: E712
        for host in hosts:
            db.add(Notification(
                user_id=host.id,
                type=data.type,
                title=data.title.strip(),
                body=data.body.strip(),
                data=extra_data,
                read=False,
                context="host",
            ))
        host_count = len(hosts)

    if audience in ("community", "all"):
        everyone = db.query(User).all()
        for member in everyone:
            db.add(Notification(
                user_id=member.id,
                type=data.type,
                title=data.title.strip(),
                body=data.body.strip(),
                data=extra_data,
                read=False,
                context="user",
            ))
        community_count = len(everyone)
    db.commit()

    audience_label = {"organisers": "organiser(s)", "community": "community member(s)", "all": "organiser(s) + community member(s)"}[audience]
    total_recipients = host_count + community_count
    log_admin_activity(
        db, admin.id, "broadcast_sent",
        detail=f"\"{data.title.strip()}\" to {total_recipients} {audience_label} (audience: {audience})",
    )
    db.commit()

    return {
        "message": "Broadcast sent",
        "audience": audience,
        "recipients": total_recipients,
        "host_recipients": host_count,
        "community_recipients": community_count,
    }


# =============================================================================
# Support desk — reads/writes the same SupportTicket rows a host writes to
# via POST /users/support-chat, so admin replies show up in the host's
# dashboard chat widget.
# =============================================================================

@router.get("/support-tickets/active")
def list_active_support_threads(
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    """WhatsApp-style thread list: one row per host who has ever messaged
    support, showing their most recent message, sorted most-recent-first.
    `unread` is true when the latest message is from the host and hasn't
    been answered yet — threads don't disappear from the list just because
    they were already replied to, the way a chat app's conversation list
    wouldn't either."""
    latest_per_host = (
        db.query(
            SupportTicket.host_id,
            func.max(SupportTicket.created_at).label("latest_at"),
        )
        .group_by(SupportTicket.host_id)
        .subquery()
    )

    rows = (
        db.query(SupportTicket, User)
        .join(User, User.id == SupportTicket.host_id)
        .join(
            latest_per_host,
            (SupportTicket.host_id == latest_per_host.c.host_id)
            & (SupportTicket.created_at == latest_per_host.c.latest_at),
        )
        .order_by(latest_per_host.c.latest_at.desc())
        .all()
    )

    seen_hosts = set()
    out = []
    for ticket, host in rows:
        if host.id in seen_hosts:
            continue
        seen_hosts.add(host.id)
        out.append({
            "ticket_id": str(ticket.id),
            "host_id": str(host.id),
            "full_name": host.full_name,
            "message": ticket.message,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            "unread": bool(ticket.sender == "host" and not ticket.resolved),
        })
    return out


@router.get("/support-tickets/{host_id}/thread")
def get_support_thread_for_host(
    host_id: str,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    rows = (
        db.query(SupportTicket)
        .filter(SupportTicket.host_id == host_id)
        .order_by(SupportTicket.created_at.asc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": str(t.id),
            "sender": t.sender,
            "message": t.message,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in rows
    ]


class SupportReplyPayload(BaseModel):
    host_id: str
    message: str


@router.post("/support-tickets/reply")
def reply_to_support_thread(
    data: SupportReplyPayload,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    text = (data.message or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    db.add(SupportTicket(host_id=data.host_id, sender="admin", message=text, resolved=False))
    # Mark the host's prior messages resolved now that HQ has responded.
    db.query(SupportTicket).filter(
        SupportTicket.host_id == data.host_id, SupportTicket.sender == "host"
    ).update({"resolved": True})

    host = db.query(User).filter(User.id == data.host_id).first()
    log_admin_activity(
        db, admin.id, "support_reply",
        detail=f"Replied to {host.full_name if host else data.host_id} in Support Desk",
    )
    db.commit()

    return {"message": "Reply sent"}


# =============================================================================
# Analytics — header-space poll & bidding. Admin starts a poll for the 3
# header (home-page carousel) slots, every host is notified and can bid with
# the media they want featured, and the top bid per slot wins when the admin
# stops the poll.
# =============================================================================

@router.post("/analytics/poll/start")
def start_header_poll(
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    existing = db.query(HeaderPoll).filter(HeaderPoll.status == "active").first()
    if existing:
        raise HTTPException(status_code=400, detail="A header-space poll is already active")

    poll = HeaderPoll(status="active")
    db.add(poll)
    db.flush()  # get poll.id before commit

    for slot in (1, 2, 3):
        db.add(HeaderPollOption(poll_id=poll.id, slot_number=slot))

    hosts = db.query(User).filter(User.is_host == True).all()  # noqa: E712
    for host in hosts:
        db.add(Notification(
            user_id=host.id,
            type="header_poll",
            title="Header Space Poll — Bid Now",
            body="BASH HQ opened bidding for the 3 home-page header slots. Place your bid with your media to compete for a spot.",
            data={"poll_id": str(poll.id)},
            read=False,
            context="host",
        ))

    db.commit()
    return {"message": "Poll started", "poll_id": str(poll.id), "notified_hosts": len(hosts)}


@router.get("/analytics/poll/active")
def get_active_poll_leaderboard(
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    poll = (
        db.query(HeaderPoll)
        .filter(HeaderPoll.status == "active")
        .order_by(HeaderPoll.created_at.desc())
        .first()
    )
    if not poll:
        return {"active": False}

    options = (
        db.query(HeaderPollOption)
        .filter(HeaderPollOption.poll_id == poll.id)
        .order_by(HeaderPollOption.slot_number.asc())
        .all()
    )

    slots = []
    for opt in options:
        bids = (
            db.query(HeaderBid, User)
            .join(User, User.id == HeaderBid.host_id)
            .filter(HeaderBid.option_id == opt.id)
            .order_by(HeaderBid.amount.desc())
            .all()
        )
        top_bid = bids[0][0] if bids else None
        linked_event = db.query(Event).filter(Event.id == top_bid.event_id).first() if (top_bid and top_bid.event_id) else None
        slots.append({
            "option_id": str(opt.id),
            "slot_number": opt.slot_number,
            "bid_count": len(bids),
            "top_bid": {
                "host_id": str(bids[0][1].id),
                "host_name": bids[0][1].full_name,
                "amount": float(bids[0][0].amount),
                "media_url": bids[0][0].media_url,
                "event_title": linked_event.title if linked_event else None,
            } if bids else None,
        })

    return {"active": True, "poll_id": str(poll.id), "slots": slots}


@router.post("/analytics/poll/stop")
def stop_header_poll(
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    poll = (
        db.query(HeaderPoll)
        .filter(HeaderPoll.status == "active")
        .order_by(HeaderPoll.created_at.desc())
        .first()
    )
    if not poll:
        raise HTTPException(status_code=400, detail="No active poll to stop")

    options = (
        db.query(HeaderPollOption)
        .filter(HeaderPollOption.poll_id == poll.id)
        .order_by(HeaderPollOption.slot_number.asc())
        .all()
    )

    winners = []
    for opt in options:
        top = (
            db.query(HeaderBid, User)
            .join(User, User.id == HeaderBid.host_id)
            .filter(HeaderBid.option_id == opt.id)
            .order_by(HeaderBid.amount.desc())
            .first()
        )
        if top:
            winners.append({
                "slot_number": opt.slot_number,
                "host_id": str(top[1].id),
                "host_name": top[1].full_name,
                "amount": float(top[0].amount),
                "media_url": top[0].media_url,
            })

    poll.status = "closed"
    poll.closed_at = datetime.now(timezone.utc)
    db.commit()

    return {"message": "Poll closed", "poll_id": str(poll.id), "winners": winners}


@router.post("/header-media/publish")
def publish_header_media(
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    """No separate media table to keep in sync — the most-recently-closed
    poll's winning bids already ARE the source of truth (see GET
    /header-media below), so this just validates one exists to publish."""
    poll = (
        db.query(HeaderPoll)
        .filter(HeaderPoll.status == "closed")
        .order_by(HeaderPoll.closed_at.desc())
        .first()
    )
    if not poll:
        raise HTTPException(status_code=400, detail="No closed poll to publish from")
    return {"message": "Published", "poll_id": str(poll.id)}


@router.get("/header-media/public", tags=["Public"])
def get_public_header_media(db: Session = Depends(get_db)):
    """Public (no admin auth) — the home page reads this to populate the
    header carousel with whatever was last published from the Analytics
    poll. Kept under /admin for this file's router, but requires no auth.

    Always tries to return 3 items: any slot that didn't get a winning bid
    (poll never ran, or a slot specifically had zero bids) is backfilled
    with the platform's most-liked events, so the home page header never
    shows fewer than 3 cards regardless of how the bidding went.
    """
    poll = (
        db.query(HeaderPoll)
        .filter(HeaderPoll.status == "closed")
        .order_by(HeaderPoll.closed_at.desc())
        .first()
    )

    items = []
    used_reel_ids = set()
    filled_slots = 0

    if poll:
        options = (
            db.query(HeaderPollOption)
            .filter(HeaderPollOption.poll_id == poll.id)
            .order_by(HeaderPollOption.slot_number.asc())
            .all()
        )
        for opt in options:
            top = (
                db.query(HeaderBid, User)
                .join(User, User.id == HeaderBid.host_id)
                .filter(HeaderBid.option_id == opt.id)
                .order_by(HeaderBid.amount.desc())
                .first()
            )
            if top:
                bid, host_user = top
                linked_event = db.query(Event).filter(Event.id == bid.event_id).first() if bid.event_id else None
                items.append({
                    "slot_number": opt.slot_number,
                    "media_url": bid.media_url,
                    "host_name": host_user.full_name,
                    # Present only when the host linked a real event to this
                    # bid — lets the home page's header card be clickable
                    # (straight to that event's Cheki reel) and show a real
                    # countdown + event name instead of a bare banner.
                    "reel_id": str(linked_event.id) if linked_event else None,
                    "event_title": linked_event.title if linked_event else None,
                    "start_date": linked_event.start_date.isoformat() if (linked_event and linked_event.start_date) else None,
                    "source": "bid",
                })
                filled_slots += 1
                if linked_event:
                    used_reel_ids.add(str(linked_event.id))

    missing_slots = 3 - filled_slots
    if missing_slots > 0:
        like_counts = (
            db.query(ChekiLike.feed_item_id, func.count(ChekiLike.id).label("like_count"))
            .group_by(ChekiLike.feed_item_id)
            .subquery()
        )
        top_liked = (
            db.query(ChekiFeedItem, func.coalesce(like_counts.c.like_count, 0).label("like_count"))
            .outerjoin(like_counts, like_counts.c.feed_item_id == ChekiFeedItem.reel_id)
            .filter(ChekiFeedItem.badge_type == "host")
            .order_by(func.coalesce(like_counts.c.like_count, 0).desc(), ChekiFeedItem.created_at.desc())
            .limit(missing_slots + len(used_reel_ids) + 5)  # pad in case some get filtered out as duplicates below
            .all()
        )

        taken_slot_numbers = {i["slot_number"] for i in items}
        next_slot = 1
        for feed_item, _like_count in top_liked:
            if missing_slots <= 0:
                break
            if feed_item.reel_id in used_reel_ids:
                continue
            while next_slot in taken_slot_numbers:
                next_slot += 1
            items.append({
                "slot_number": next_slot,
                "media_url": feed_item.media_url,
                "host_name": feed_item.host_name,
                "reel_id": feed_item.reel_id,
                "event_title": feed_item.event_name,
                "start_date": feed_item.date,
                "source": "top_liked",
            })
            used_reel_ids.add(feed_item.reel_id)
            taken_slot_numbers.add(next_slot)
            missing_slots -= 1

    items.sort(key=lambda i: i["slot_number"])
    return {"items": items}


# =============================================================================
# User Growth — number of users, weekly growth (adaptive up to millions),
# and time-spent, for the admin "User Growth" analytics subpage. Weekly
# buckets come from User.created_at; time-spent comes from UserSession rows
# written by POST /users/heartbeat (see app/models/user_session.py).
# =============================================================================

@router.get("/analytics/growth")
def user_growth_analytics(
    weeks: int = 26,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    from datetime import datetime, timedelta, timezone
    from app.models.user_session import UserSession

    weeks = max(1, min(weeks, 104))  # sane bounds — up to 2 years of weekly buckets
    now = datetime.now(timezone.utc)

    total_users = db.query(func.count(User.id)).scalar() or 0
    total_hosts = db.query(func.count(User.id)).filter(User.is_host == True).scalar() or 0  # noqa: E712

    # --- Weekly signup buckets, going back `weeks` weeks from today, plus a
    # running cumulative total so the chart can show overall user-count
    # growth (the number that can climb toward millions) rather than just
    # noisy per-week deltas.
    week_starts = []
    today_week_start = now - timedelta(days=now.weekday())
    today_week_start = today_week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    for i in range(weeks - 1, -1, -1):
        week_starts.append(today_week_start - timedelta(weeks=i))

    # Aggregate signups per week in SQL (date_trunc), not by pulling every
    # user row into Python — this is the part that has to stay cheap even
    # once there are millions of rows.
    week_counts_rows = (
        db.query(
            func.date_trunc("week", User.created_at).label("week"),
            func.count(User.id),
        )
        .filter(User.created_at.isnot(None))
        .group_by("week")
        .all()
    )
    week_counts = {_as_aware(row[0]).date().isoformat(): int(row[1]) for row in week_counts_rows if row[0] is not None}

    baseline_count = (
        db.query(func.count(User.id))
        .filter(User.created_at.isnot(None), User.created_at < week_starts[0])
        .scalar() or 0
    )

    series = []
    running_total = baseline_count
    for w_start in week_starts:
        new_this_week = week_counts.get(w_start.date().isoformat(), 0)
        running_total += new_this_week
        series.append({
            "week_start": w_start.date().isoformat(),
            "new_users": new_this_week,
            "cumulative_users": running_total,
        })

    # --- Time spent: derive per-session durations from UserSession, only
    # counting sessions with more than one heartbeat (a lone ping has no
    # measurable duration and would just drag the average toward zero).
    cutoff = now - timedelta(weeks=weeks)
    sessions = (
        db.query(UserSession)
        .filter(UserSession.last_seen_at >= cutoff, UserSession.last_seen_at > UserSession.started_at)
        .all()
    )
    if sessions:
        total_minutes = sum(
            (_as_aware(s.last_seen_at) - _as_aware(s.started_at)).total_seconds() / 60.0
            for s in sessions
        )
        avg_session_minutes = round(total_minutes / len(sessions), 1)
    else:
        avg_session_minutes = 0.0

    active_last_7_days = (
        db.query(func.count(func.distinct(UserSession.user_id)))
        .filter(UserSession.last_seen_at >= now - timedelta(days=7))
        .scalar() or 0
    )
    active_last_30_days = (
        db.query(func.count(func.distinct(UserSession.user_id)))
        .filter(UserSession.last_seen_at >= now - timedelta(days=30))
        .scalar() or 0
    )

    return {
        "total_users": int(total_users),
        "total_hosts": int(total_hosts),
        "active_last_7_days": int(active_last_7_days),
        "active_last_30_days": int(active_last_30_days),
        "avg_session_minutes": avg_session_minutes,
        "weekly_series": series,
    }


def _as_aware(dt):
    """Normalizes a naive DateTime (as some older rows/servers may return)
    to UTC-aware, so subtraction/comparison against `now` never raises."""
    from datetime import timezone
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# =============================================================================
# ADDER — admin-managed additions to the category/town/location pickers
# shown across the app. The Adder admin page (and its "Not Found" errors)
# already existed on the frontend calling these exact routes; nothing on
# the backend ever answered them until now. This never touches or
# replaces the frontend's own built-in lists (cheki.html's hardcoded
# category pills; kenya-locations.js's official county/constituency data)
# — it only stores the supplementary entries admins add on top, and
# GET /admin/taxonomy/public is what cheki.js's loadAdderCategoryPills
# reads to merge them into the category picker everyone sees.
# =============================================================================
class TaxonomyAddRequest(BaseModel):
    entry_type: str
    value: str
    parent_town: Optional[str] = None


def _serialize_taxonomy_entry(e: TaxonomyEntry) -> dict:
    return {
        "id": str(e.id),
        "entry_type": e.entry_type,
        "value": e.value,
        "parent_town": e.parent_town,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


@router.get("/taxonomy")
def list_taxonomy_entries(
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    entries = db.query(TaxonomyEntry).order_by(TaxonomyEntry.created_at.desc()).all()
    return {"entries": [_serialize_taxonomy_entry(e) for e in entries]}


@router.post("/taxonomy/add")
def add_taxonomy_entry(
    data: TaxonomyAddRequest,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    entry_type = (data.entry_type or "").strip().lower()
    if entry_type not in ("category", "town", "location"):
        raise HTTPException(status_code=400, detail="entry_type must be category, town, or location")
    value = (data.value or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="Enter a value first.")
    parent_town = (data.parent_town or "").strip() or None if entry_type == "location" else None

    # Case-insensitive dedupe against whatever's already been admin-added
    # for this type — matches admin.js's own "That's already on the
    # list." messaging. Dedupe against the frontend's BUILT-IN lists
    # (category pills, official Kenya towns) deliberately isn't done here:
    # this endpoint only knows about its own table, and duplicating either
    # list into the backend just to check against it would mean keeping
    # two copies in sync forever. A duplicate here just means the option
    # shows up twice in a picker — harmless — not a data integrity issue.
    existing = (
        db.query(TaxonomyEntry)
        .filter(TaxonomyEntry.entry_type == entry_type, func.lower(TaxonomyEntry.value) == value.lower())
        .first()
    )
    if existing:
        return {"already_existed": True, "entry": _serialize_taxonomy_entry(existing)}

    entry = TaxonomyEntry(
        entry_type=entry_type,
        value=value,
        parent_town=parent_town,
        created_by_admin_id=getattr(admin, "id", None),
    )
    db.add(entry)
    try:
        db.commit()
    except Exception:
        # Two admins submitting the identical value at once — the
        # case-insensitive check above already covers everything except
        # this exact race, so this is the DB-level backstop, not the
        # normal path.
        db.rollback()
        existing = (
            db.query(TaxonomyEntry)
            .filter(TaxonomyEntry.entry_type == entry_type, func.lower(TaxonomyEntry.value) == value.lower())
            .first()
        )
        if existing:
            return {"already_existed": True, "entry": _serialize_taxonomy_entry(existing)}
        raise HTTPException(status_code=400, detail="Couldn't add that.")
    db.refresh(entry)
    log_admin_activity(db, getattr(admin, "id", None), "taxonomy_add", detail=f"{entry_type}: {value}")
    db.commit()
    return {"already_existed": False, "entry": _serialize_taxonomy_entry(entry)}


@router.delete("/taxonomy/{entry_id}")
def delete_taxonomy_entry(
    entry_id: str,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    entry = db.query(TaxonomyEntry).filter(TaxonomyEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Couldn't find that entry.")
    detail = f"{entry.entry_type}: {entry.value}"
    db.delete(entry)
    log_admin_activity(db, getattr(admin, "id", None), "taxonomy_remove", detail=detail)
    db.commit()
    return {"deleted": True}


@router.get("/taxonomy/public")
def list_taxonomy_public(
    db: Session = Depends(get_db),
):
    """No auth — read straight from the feed/event pickers on every page
    load (cheki.js's loadAdderCategoryPills, and any future town/location
    picker that wants the same admin-added supplements). Categories only
    for now since that's the only picker actually consuming this; towns/
    locations are already stored and served the same way, ready for a
    picker to read them the moment one wants to."""
    entries = (
        db.query(TaxonomyEntry)
        .filter(TaxonomyEntry.entry_type == "category")
        .order_by(TaxonomyEntry.value.asc())
        .all()
    )
    return {"categories": [e.value for e in entries]}