from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_user_optional, require_host

from app.models.event import Event
from app.models.user import User
from app.models.cheki_feed_item import ChekiFeedItem
from app.models.booking import Booking


from app.models.cheki_comment import ChekiComment
from app.models.cheki_like import ChekiLike

router = APIRouter(prefix="", tags=["Stream"])

from fastapi import Request

import logging
from fastapi import HTTPException, Depends
from typing import List

from sqlalchemy import func

class ReelPostResponse(BaseModel):
    reelId: str
    username: str

    # Host-side fields
    hostName: Optional[str] = None
    badgeType: str = "host"  # "host" | "community"

    # Media + text
    mediaUrl: Optional[str] = None
    vibeText: Optional[str] = None

    # Metadata
    eventName: Optional[str] = None
    location: Optional[str] = None
    county: Optional[str] = None
    constituency: Optional[str] = None
    date: Optional[str] = None
    category: Optional[str] = None

    price: Optional[str] = None
    buyerTotal: Optional[str] = None
    tickets: Optional[str] = None
    ticketsSold: str = "0"
    ticketsStatus: str = "available"
    priceTiers: Optional[List[dict]] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Community-side fields (optional)
    profilePicture: Optional[str] = None
    caption: Optional[str] = None

    # Always present
    timestamp: int
    is_liked: bool = False
    likes: int = 0
    comment_count: int = 0

    # Confirmed BASH usernames tagged as "Artists Joining" on the Event
    artistUsernames: Optional[List[str]] = None

    # Live Gate is only meant to show up once an admin has pressed "Send
    gateUnlocked: bool = False
    finalTicketTally: Optional[int] = None

    # True once this host qualifies for the Gold Organiser badge (rolling
    # average >= 4.5 across their last 5 rated events) — see
    # rating_service.recompute_host_gold_status. Only ever set on
    # badgeType == "host" posts; swaps the feed badge from red to gold.
    goldOrganiser: bool = False

    # Author's current Saka discoverability status ("friends" | "dating" |
    # "available" | "casual" | "invisible" | None), already expiry-checked
    # (see users.py's _effective_saka_status — same rule, duplicated here
    # as _saka_status_for_username since this is a different query path).
    # frontend/saka.js uses this to decide which browse tab (if any) this
    # person's card belongs under, instead of guessing from post content.
    sakaStatus: Optional[str] = None

    # Duplicate Guard — required to appear in Saka's roulette/swipe deck
    # (not the grid, which keeps using the post's own media). See
    # frontend/saka.js's enterRoulette() and User.duplicate_guard_photo_url.
    duplicateGuardApproved: bool = False
    duplicateGuardPhotoUrl: Optional[str] = None

def _username(user: Optional[User]) -> str:
    if user is None or not getattr(user, "username", None):
        return "@anonymous"
    u = user.username
    return u if u.startswith("@") else f"@{u}"


def _saka_status_from_row(row) -> Optional[str]:
    """Shared expiry logic for a saka_status/saka_status_expires_at pair —
    used by both the unbatched per-username lookup below and the batched
    precompute path in _batch_feed_precompute, so a lapsed timed status
    (e.g. "available for 6 hours") is treated identically either way."""
    if not row:
        return None
    raw_status, expires_at = row.saka_status, row.saka_status_expires_at
    if not raw_status:
        return None
    if expires_at is not None:
        now = datetime.now(timezone.utc) if expires_at.tzinfo else datetime.utcnow()
        if now >= expires_at:
            return None
    return raw_status


def _saka_status_for_username(db: Optional[Session], username: Optional[str]) -> Optional[str]:
    """Same expiry rule as users.py's _effective_saka_status, but keyed off
    a raw username string since that's all a feed item stores — a lapsed
    timed status (e.g. "available for 6 hours") comes back as None here
    too, so it silently drops off Saka the moment it's next read rather
    than needing a background job to clear it."""
    if not db or not username:
        return None
    bare = (username or "").strip().lstrip("@").lower()
    if not bare:
        return None
    row = (
        db.query(User.saka_status, User.saka_status_expires_at)
        .filter(func.lower(User.username).in_([bare, f"@{bare}"]))
        .first()
    )
    return _saka_status_from_row(row)


def _duplicate_guard_for_username(db: Optional[Session], username: Optional[str]):
    """Returns (approved: bool, photo_url: str|None) for whoever posted
    this feed item — same username-keyed lookup pattern as
    _saka_status_for_username above."""
    if not db or not username:
        return False, None
    bare = (username or "").strip().lstrip("@").lower()
    if not bare:
        return False, None
    row = (
        db.query(User.duplicate_guard_status, User.duplicate_guard_photo_url)
        .filter(func.lower(User.username).in_([bare, f"@{bare}"]))
        .first()
    )
    if not row:
        return False, None
    dg_status, dg_photo = row
    return (dg_status == "approved" and bool(dg_photo)), dg_photo


def _event_to_host_reel(event: Event, host: Optional[User]) -> ReelPostResponse:
    host_price = event.price or 0
    fee = round(float(host_price) * 0.12)
    buyer_total = float(host_price) + float(fee)

    event_date: Optional[str] = None
    if getattr(event, "start_date", None) is not None:
        try:
            event_date = event.start_date.date().isoformat()
        except Exception:
            event_date = str(event.start_date)

    parsed_tiers = None
    if getattr(event, "ticket_tiers", None):
        try:
            import json as _json
            parsed_tiers = _json.loads(event.ticket_tiers)
        except Exception:
            parsed_tiers = None

    return ReelPostResponse(
        reelId=f"host_event_{event.id}",
        username=_username(host),
        hostName=getattr(host, "username", None) or _username(host),
        badgeType="host",
        mediaUrl=event.video_url or event.poster_url,
        goldOrganiser=bool(getattr(host, "gold_organiser", False)),
        vibeText=event.description or "",
        eventName=event.title,
        location=event.venue_name,
        county=getattr(event, "county", None),
        date=event_date,
        category=(event.category or "event").lower().replace(" ", ""),
        price=str(host_price),
        buyerTotal=str(buyer_total),
        tickets=str(event.capacity or 0),
        ticketsSold="0",
        ticketsStatus="available" if event.status == "published" else "soldout",
        timestamp=int(datetime.utcnow().timestamp() * 1000),
        priceTiers=parsed_tiers,
        latitude=event.latitude,
        longitude=event.longitude,
    )


def _parse_timestamp_ms(v: Any) -> int:
    try:
        if v is None:
            return int(datetime.utcnow().timestamp() * 1000)
        if isinstance(v, (int, float)):
            return int(v)
        return int(float(str(v)))
    except Exception:
        return int(datetime.utcnow().timestamp() * 1000)


def _batch_feed_precompute(db: Optional[Session], items: list, current_user_id=None) -> dict:
    """Runs the handful of lookups _map_feed_item_to_reel needs ONCE for
    the whole batch of feed items, instead of once PER item — this is the
    actual fix for a real N+1 query bug: the unbatched version ran 5-9
    separate database round trips for every single feed item (likes
    count, comment count, is_liked, saka status, duplicate-guard status,
    plus 4 more for host/event items), unconditionally, on every load of
    Home, Cheki, or Saka. With a feed of even a few hundred posts that's
    thousands of sequential DB round trips on one page load — the actual
    cause of "new phones are too slow to load the app", since a
    first-time visitor has no local cache to paint from while this runs
    (see cheki.js/saka.js's cache-first painting, which only helps
    RETURNING visitors).

    Returns a dict of precomputed lookups; _map_feed_item_to_reel uses
    these when passed a `precomputed` argument instead of hitting the DB
    itself. freeze_and_open_gate_for_event is deliberately NOT batched
    here — it already short-circuits near-instantly for any event that
    isn't imminently starting (see its own docstring), so it was never a
    meaningful contributor to this slowness and touching it isn't worth
    the risk.
    """
    empty = {
        "likes_count_by_reel": {}, "liked_reel_ids": set(), "comment_count_by_reel": {},
        "live_sold_by_event": {}, "user_info_by_username": {}, "events_by_id": {},
    }
    if not db or not items:
        return empty

    reel_ids = [it.reel_id for it in items if it.reel_id]
    usernames_bare = sorted({
        (it.username or "").strip().lstrip("@").lower()
        for it in items if it.username
    })
    host_reel_ids = [it.reel_id for it in items if it.reel_id and (it.badge_type or "").lower().strip() == "host"]

    likes_count_by_reel = {}
    liked_reel_ids = set()
    comment_count_by_reel = {}
    live_sold_by_event = {}
    user_info_by_username = {}
    events_by_id = {}

    if reel_ids:
        for reel_id, count in (
            db.query(ChekiLike.feed_item_id, func.count(ChekiLike.id))
            .filter(ChekiLike.feed_item_id.in_(reel_ids))
            .group_by(ChekiLike.feed_item_id)
            .all()
        ):
            likes_count_by_reel[reel_id] = count

        if current_user_id:
            liked_reel_ids = {
                row[0] for row in
                db.query(ChekiLike.feed_item_id)
                .filter(ChekiLike.feed_item_id.in_(reel_ids), ChekiLike.user_id == current_user_id)
                .all()
            }

        for reel_id, count in (
            db.query(ChekiComment.feed_item_id, func.count(ChekiComment.id))
            .filter(ChekiComment.feed_item_id.in_(reel_ids))
            .group_by(ChekiComment.feed_item_id)
            .all()
        ):
            comment_count_by_reel[reel_id] = count

    if host_reel_ids:
        for event_id, total in (
            db.query(Booking.event_id, func.coalesce(func.sum(Booking.quantity), 0))
            .filter(Booking.event_id.in_(host_reel_ids), Booking.status == "booked")
            .group_by(Booking.event_id)
            .all()
        ):
            live_sold_by_event[event_id] = int(total or 0)

        for ev in db.query(Event).filter(Event.id.in_(host_reel_ids)).all():
            events_by_id[ev.id] = ev

    if usernames_bare:
        # Both "@handle" and "handle" forms are checked because that's
        # what the original per-item lookups did — feed items store
        # usernames inconsistently (with or without the leading @) and
        # this keeps matching either form without needing a data cleanup.
        variants = usernames_bare + [f"@{u}" for u in usernames_bare]
        for row in (
            db.query(
                User.username, User.saka_status, User.saka_status_expires_at,
                User.duplicate_guard_status, User.duplicate_guard_photo_url,
                User.gold_organiser,
            )
            .filter(func.lower(User.username).in_(variants))
            .all()
        ):
            bare = (row.username or "").strip().lstrip("@").lower()
            user_info_by_username[bare] = row

    return {
        "likes_count_by_reel": likes_count_by_reel,
        "liked_reel_ids": liked_reel_ids,
        "comment_count_by_reel": comment_count_by_reel,
        "live_sold_by_event": live_sold_by_event,
        "user_info_by_username": user_info_by_username,
        "events_by_id": events_by_id,
    }


def _map_feed_item_to_reel(item: ChekiFeedItem, db: Optional[Session] = None, current_user_id: Optional[int] = None, precomputed: Optional[dict] = None) -> ReelPostResponse:
    badge = (item.badge_type or "community").lower().strip()
    bare_username = (item.username or "").strip().lstrip("@").lower()

    if precomputed is not None:
        # Batched path — see _batch_feed_precompute. All lookups below are
        # plain dict reads, no DB round trip per item.
        is_liked_status = item.reel_id in precomputed["liked_reel_ids"]
        likes_count = precomputed["likes_count_by_reel"].get(item.reel_id, 0)
        comment_count = precomputed["comment_count_by_reel"].get(item.reel_id, 0)
    else:
        # Unbatched fallback — used by call sites mapping a single item
        # (e.g. right after POST /vibe_posts_stream_v1 creates one) where
        # batching a list of 1 would just be unnecessary complexity.
        is_liked_status = False
        if db and current_user_id and item.reel_id:
            exists = db.query(ChekiLike).filter(
                ChekiLike.feed_item_id == item.reel_id,
                ChekiLike.user_id == current_user_id
            ).first()
            is_liked_status = True if exists else False

        likes_count = 0
        if db and item.reel_id:
            likes_count = db.query(ChekiLike).filter(ChekiLike.feed_item_id == item.reel_id).count()

        comment_count = 0
        if db and item.reel_id:
            comment_count = db.query(ChekiComment).filter(
                (ChekiComment.feed_item_id == item.reel_id)
            ).count()

    if badge == "host":
        # LIVE, not cached: item.tickets_sold is a snapshot string that
        # only gets written by the manual sync endpoint below (line ~464)
        # and can go stale. The host dashboard's Upcoming Events donut and
        # the Live Gate checked-in ratio both need a real-time, "booked
        # (paid) bookings only" count — pending/cancelled/expired
        # reservations must NOT inflate this number — so compute it fresh
        # from the Booking table whenever we have a db session, and only
        # fall back to the cached column if we don't (e.g. a call site
        # that maps a feed item without a db session).
        if precomputed is not None:
            tickets_sold = str(precomputed["live_sold_by_event"].get(item.reel_id, 0))
        elif db and item.reel_id:
            live_sold = (
                db.query(func.coalesce(func.sum(Booking.quantity), 0))
                .filter(Booking.event_id == item.reel_id, Booking.status == "booked")
                .scalar()
            ) or 0
            tickets_sold = str(int(live_sold))
        else:
            tickets_sold = item.tickets_sold or "0"
        tickets_status = item.tickets_status or "available"

        gate_unlocked = False
        final_ticket_tally = None
        if precomputed is not None:
            linked_event = precomputed["events_by_id"].get(item.reel_id)
        elif db and item.reel_id:
            try:
                linked_event = db.query(Event).filter(Event.id == item.reel_id).first()
            except Exception:
                linked_event = None
        else:
            linked_event = None
        if linked_event is not None and db:
            # Safety net: don't rely solely on the every-5-minutes
            # scheduler to open the Live Gate at T-1hr. If this event
            # is due and hasn't been processed yet, do it right now —
            # this is the exact idempotent check the scheduler itself
            # runs, so it's safe to call on every view. This means the
            # gate opens the moment anyone (host or otherwise) looks at
            # the event, even if the background job was delayed,
            # missed its window around a restart, or isn't running at
            # all on this server. Deliberately still called per-item even
            # in the batched path — it already short-circuits instantly
            # for any event that isn't imminently starting (see its own
            # docstring), so it was never a meaningful part of the N+1
            # slowness this function is otherwise fixing.
            try:
                from app.services.attendance_service import freeze_and_open_gate_for_event
                freeze_and_open_gate_for_event(db, linked_event)
            except Exception as e:
                print(f"⚠️ On-demand Live Gate check failed for event {item.reel_id}: {e}")
            gate_unlocked = bool(getattr(linked_event, "gate_unlocked", False))
            final_ticket_tally = getattr(linked_event, "final_ticket_tally", None)

        artist_usernames_parsed = None
        if item.artist_usernames:
            try:
                import json as _json
                parsed = _json.loads(item.artist_usernames)
                artist_usernames_parsed = parsed if isinstance(parsed, list) else None
            except Exception:
                artist_usernames_parsed = None

        parsed_tiers = None
        if getattr(item, "ticket_tiers", None):
            try:
                import json as _json
                parsed_tiers = _json.loads(item.ticket_tiers)
            except Exception:
                parsed_tiers = None

        gold_organiser = False
        if precomputed is not None:
            info = precomputed["user_info_by_username"].get(bare_username)
            gold_organiser = bool(info.gold_organiser) if info else False
        elif db and item.username:
            host_row = db.query(User.gold_organiser).filter(func.lower(User.username) == (item.username or "").lower()).first()
            gold_organiser = bool(host_row[0]) if host_row else False

        if precomputed is not None:
            info = precomputed["user_info_by_username"].get(bare_username)
            saka_status = _saka_status_from_row(info) if info else None
            dg_approved = bool(info and info.duplicate_guard_status == "approved" and info.duplicate_guard_photo_url)
            dg_photo = info.duplicate_guard_photo_url if info else None
        else:
            saka_status = _saka_status_for_username(db, item.username)
            dg_approved, dg_photo = _duplicate_guard_for_username(db, item.username)

        return ReelPostResponse(
            reelId=item.reel_id,
            username=item.username or "@anonymous",
            hostName=item.host_name,
            badgeType="host",
            mediaUrl=item.media_url,
            goldOrganiser=gold_organiser,
            sakaStatus=saka_status,
            duplicateGuardApproved=dg_approved,
            duplicateGuardPhotoUrl=dg_photo,
            vibeText=item.vibe_text,
            eventName=item.event_name,
            location=item.location,
            date=item.date,
            category=(item.category or "event").lower().replace(" ", ""),
            price=str(item.price) if item.price is not None else None,
            buyerTotal=str(item.buyer_total) if item.buyer_total is not None else None,
            tickets=item.tickets,
            ticketsSold=str(tickets_sold),
            ticketsStatus=str(tickets_status),
            artistUsernames=artist_usernames_parsed,
            timestamp=int(item.created_at.timestamp() * 1000),
            is_liked=is_liked_status,
            likes=likes_count,
            comment_count=comment_count,
            gateUnlocked=gate_unlocked,
            finalTicketTally=final_ticket_tally,
            priceTiers=parsed_tiers,
            latitude=item.latitude,
            longitude=item.longitude,
            county=getattr(linked_event, "county", None) if linked_event is not None else None,
            constituency=item.constituency,
        )

    # Community item
    if precomputed is not None:
        info = precomputed["user_info_by_username"].get(bare_username)
        saka_status = _saka_status_from_row(info) if info else None
        dg_approved = bool(info and info.duplicate_guard_status == "approved" and info.duplicate_guard_photo_url)
        dg_photo = info.duplicate_guard_photo_url if info else None
    else:
        saka_status = _saka_status_for_username(db, item.username)
        dg_approved, dg_photo = _duplicate_guard_for_username(db, item.username)
    return ReelPostResponse(
        reelId=item.reel_id,
        username=item.username or "@anonymous",
        hostName=None,
        badgeType="community",
        mediaUrl=item.media_url,
        sakaStatus=saka_status,
        duplicateGuardApproved=dg_approved,
        duplicateGuardPhotoUrl=dg_photo,
        vibeText=item.vibe_text,
        eventName=None,
        location=item.location,
        county=item.county,
        constituency=item.constituency,
        date=None,
        category=(item.category or "social").lower().replace(" ", ""),
        price="0",
        buyerTotal=None,
        tickets=None,
        ticketsSold="0",
        ticketsStatus="available",
        profilePicture=item.profile_picture,
        caption=item.caption,
        timestamp=int(item.created_at.timestamp() * 1000),
        is_liked=is_liked_status,
        likes=likes_count,
        comment_count=comment_count
    )


@router.get("/vibe_posts_stream_v1", response_model=List[dict])
def vibe_posts_stream_v1_get(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Unified Cheki feed stored in DB with completely safe, optional authentication."""
    # NOTE: revoked_at is how both the "Revoke Event" (organiser) and
    # "Revoke community post" admin actions pull a post off the feed
    # without deleting the row outright (see ChekiFeedItem model comment
    # and admin_extra.py admin_revoke_event / admin_revoke_community_post).
    # This filter was previously missing entirely, so a revoked item kept
    # showing up in the public feed even though the admin panel correctly
    # showed it as revoked.
    items = (
        db.query(ChekiFeedItem)
        .filter(ChekiFeedItem.revoked_at.is_(None))
        .order_by(ChekiFeedItem.created_at.desc())
        .all()
    )

    # SECURITY: previously decoded the bearer token by hand with
    # verify_signature=False, which let anyone forge a token claiming to
    # be any user and pull back that user's per-post "liked" personalization
    # with no real credentials. get_current_user_optional performs a fully
    # signature-verified decode (and honors token_version revocation) and
    # simply returns None for a missing/invalid/expired token instead of
    # raising, which is exactly the "safe, optional auth" this endpoint
    # wants. It also fixes a second latent bug: the old code looked users
    # up by `username == payload["sub"]`, but every token in this app
    # actually carries the user's id in `sub` (see auth.py's
    # create_access_token), so that lookup could never have matched —
    # personalization here was silently always off.
    user_id = current_user.id if current_user else None

    # See _batch_feed_precompute's own docstring: this replaces what used
    # to be 5-9 separate DB queries PER ITEM (run unconditionally, for
    # every item, on every load of this endpoint) with a handful of
    # queries run ONCE for the whole feed — the actual fix for "the app
    # is too slow to load on a phone that's never used it before", since
    # a first-time visitor has no local cache to mask this with while it
    # runs (returning visitors partly hide this behind cache-first
    # painting in cheki.js/saka.js, which is why this was easy to miss).
    precomputed = _batch_feed_precompute(db, items, user_id)
    feed: List[ReelPostResponse] = [_map_feed_item_to_reel(it, db=db, current_user_id=user_id, precomputed=precomputed) for it in items]
    return [item.model_dump() for item in feed]


@router.post("/vibe_posts_stream_v1")
def vibe_posts_stream_v1_post(
    payload: List[Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist feed updates coming from the frontend (host + community).

    SECURITY: this route previously had no authentication at all, and
    upserted directly by client-supplied `reel_id` with no ownership
    check — anyone on the internet could create feed posts impersonating
    a "host" badge, or silently overwrite an existing host's/user's post
    (price, ticket counts, media, location — anything) just by re-sending
    their reel_id. Now requires a logged-in user, and:
      - a post can only claim a username matching the caller's own
      - an existing feed item can only be updated by the identity that
        already owns it (matched by username)
      - the "host" badge can only be set when the caller actually owns
        the Event that reel_id corresponds to; otherwise it's downgraded
        to "community" rather than silently trusting the client's claim
    """
    if payload is None:
        raise HTTPException(status_code=400, detail="Missing payload")

    caller_username = _username(current_user).lstrip("@").lower()

    # Frontend posts the full feed array (feeds.unshift(...)).

    now = datetime.utcnow()
    skipped = 0

    for entry in payload:
        if not isinstance(entry, dict):
            continue

        reel_id = entry.get("reelId") or entry.get("reel_id")
        if not reel_id:
            continue

        badge_type = (entry.get("badgeType") or entry.get("badge_type") or "community").lower().strip()

        # SECURITY: never trust a client-claimed username — always store
        # the authenticated caller's own username on entries they create.
        entry_username = (entry.get("username") or "").lstrip("@").lower()
        if entry_username and entry_username != caller_username:
            skipped += 1
            continue

        existing = db.query(ChekiFeedItem).filter(ChekiFeedItem.reel_id == reel_id).first()

        # SECURITY: refuse to let this caller overwrite a feed item that
        # already belongs to someone else.
        if existing is not None and existing.username:
            existing_username = existing.username.lstrip("@").lower()
            if existing_username != caller_username:
                skipped += 1
                continue

        if badge_type == "host":
            # SECURITY: only actually grant the "host" badge if the caller
            # owns the event this reel_id refers to (host-posted reels use
            # the raw event UUID as reel_id — see admin.py's send-tickets
            # comment). Otherwise downgrade to "community" so a normal
            # user can't self-assign a verified-host badge in the feed.
            owned_event = (
                db.query(Event)
                .filter(Event.id == reel_id, Event.host_id == current_user.id)
                .first()
            )
            if not owned_event:
                badge_type = "community"

        created_at_ms = _parse_timestamp_ms(entry.get("timestamp"))
        created_at_dt = datetime.utcfromtimestamp(created_at_ms / 1000.0)

        def _num_or_float(v: Any) -> Optional[float]:
            try:
                if v is None or v == "":
                    return None
                return float(v)
            except Exception:
                return None

        if existing is None:
            existing = ChekiFeedItem(
                reel_id=reel_id,
                badge_type=badge_type,
                created_at=created_at_dt,
            )
            db.add(existing)

        existing.badge_type = badge_type
        existing.username = entry.get("username")
        existing.media_url = entry.get("mediaUrl")
        existing.vibe_text = entry.get("vibeText")
        existing.profile_picture = entry.get("profilePicture")
        existing.caption = entry.get("caption")

        existing.location = entry.get("location")
        existing.date = entry.get("date")
        existing.category = entry.get("category")
        # BUG FIX: the frontend has always sent county/constituency in this
        # payload (host_dashboard.js's dashboardReel object) but nothing
        # here ever read them — every host-posted event's ChekiFeedItem.
        # county/constituency stayed permanently NULL regardless of what
        # the host actually entered. That silently broke "near me"
        # matching for it (event_service.notify_nearby_users_of_new_event
        # and any future near-me feed filtering both key off this column,
        # not the free-text `location` string set above).
        existing.county = entry.get("county")
        existing.constituency = entry.get("constituency")

        # Host specific
        existing.host_name = entry.get("hostName")
        existing.event_name = entry.get("eventName")
        existing.price = _num_or_float(entry.get("price"))
        existing.buyer_total = _num_or_float(entry.get("buyerTotal"))
        existing.tickets = entry.get("tickets")
        existing.tickets_sold = entry.get("ticketsSold") or entry.get("tickets_sold")
        existing.tickets_status = entry.get("ticketsStatus")

        incoming_artists = entry.get("artistUsernames") or entry.get("artist_usernames")
        if isinstance(incoming_artists, list):
            import json as _json
            cleaned = [str(a).strip().lstrip("@") for a in incoming_artists if str(a).strip()]
            existing.artist_usernames = _json.dumps(cleaned) if cleaned else None

        incoming_tiers = entry.get("priceTiers") or entry.get("price_tiers")
        if incoming_tiers is not None:
            import json as _json
            try:
                existing.ticket_tiers = _json.dumps(incoming_tiers)
            except Exception:
                existing.ticket_tiers = None

        if entry.get("latitude") is not None:
            existing.latitude = _num_or_float(entry.get("latitude"))
        if entry.get("longitude") is not None:
            existing.longitude = _num_or_float(entry.get("longitude"))

        # Keep creation timestamp fresh based on client payload.
        existing.created_at = created_at_dt or now
        existing.username = f"@{caller_username}" if caller_username else existing.username

    db.commit()
    return {"ok": True, "received": len(payload), "skipped": skipped}




class CommentCreateRequest(BaseModel):
    content: str


class CommentResponse(BaseModel):
    id: int
    feed_item_id: str
    user_id: str
    content: str
    created_at: datetime
    username: Optional[str] = None
    user_avatar: Optional[str] = None


class LikeToggleResponse(BaseModel):
    feed_item_id: str
    user_id: str
    active: bool
    totalLikes: int


@router.post("/vibe_posts_stream_v1/{id}/comment", response_model=CommentResponse)
def vibe_posts_stream_v1_comment_create(
    id: str,
    req: CommentCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not req.content or not req.content.strip():
        raise HTTPException(status_code=400, detail="content is required")

    post = db.query(ChekiFeedItem).filter(ChekiFeedItem.reel_id == id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    comment = ChekiComment(
        feed_item_id=id,
        user_id=current_user.id,
        content=req.content.strip(),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return CommentResponse(
        id=comment.id,
        feed_item_id=comment.feed_item_id,
        user_id=str(comment.user_id),
        content=comment.content,
        created_at=comment.created_at,
        username=_username(current_user),
        user_avatar=getattr(current_user, "profile_picture", None),
    )


@router.get("/vibe_posts_stream_v1/{id}/comments", response_model=List[CommentResponse])
def vibe_posts_stream_v1_comments_get(
    id: str,
    db: Session = Depends(get_db),
):
    # 1. Clean the ID string coming from the frontend PWA
    cleaned_id = id
    if "host_event_" in id:
        cleaned_id = id.replace("host_event_", "")
    elif "vibe_posts_str_" in id:
        cleaned_id = id.replace("vibe_posts_str_", "")

    # 2. Check if the post exists using both the raw id and the cleaned string variants
    post = db.query(ChekiFeedItem).filter(
        (ChekiFeedItem.reel_id == id) | (ChekiFeedItem.reel_id == cleaned_id)
    ).first()
    
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    # 3. Query the comments table using the sanitized ID match, joined against
    rows = (
        db.query(ChekiComment, User)
        .outerjoin(User, User.id == ChekiComment.user_id)
        .filter((ChekiComment.feed_item_id == id) | (ChekiComment.feed_item_id == cleaned_id))
        .order_by(ChekiComment.created_at.asc())
        .all()
    )

    return [
        CommentResponse(
            id=c.id,
            feed_item_id=c.feed_item_id,
            user_id=str(c.user_id) if c.user_id is not None else "",
            content=c.content if c.content else "",
            created_at=c.created_at,
            username=_username(u) if u else None,
            user_avatar=getattr(u, "profile_picture", None) if u else None,
        )
        for c, u in rows
    ]


@router.post("/vibe_posts_stream_v1/{id}/like", response_model=LikeToggleResponse)
def vibe_posts_stream_v1_like_toggle(
    id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    post = db.query(ChekiFeedItem).filter(ChekiFeedItem.reel_id == id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    existing = (
        db.query(ChekiLike)
        .filter(
            ChekiLike.feed_item_id == id,
            ChekiLike.user_id == current_user.id,
        )
        .first()
    )

    if existing is not None:
        db.delete(existing)
        db.commit()
        active = False
    else:
        new_like = ChekiLike(feed_item_id=id, user_id=current_user.id)
        db.add(new_like)
        db.commit()
        active = True

    total = db.query(ChekiLike).filter(ChekiLike.feed_item_id == id).count()

    return LikeToggleResponse(
        feed_item_id=id,
        user_id=str(current_user.id),
        active=active,
        totalLikes=total,
    )

@router.get("/admin/host_events", response_model=List[ReelPostResponse])
def get_admin_host_events(
    db: Session = Depends(get_db),
    current_user = Depends(require_host),  # enforce host authentication
):
    # Filter events belonging to this host (by username)
    username = current_user.username
    if not username.startswith("@"):
        username = f"@{username}"
    events = db.query(ChekiFeedItem).filter(
        ChekiFeedItem.badge_type == "host",
        func.lower(ChekiFeedItem.username) == username.lower()
    ).order_by(ChekiFeedItem.created_at.desc()).all()
    precomputed = _batch_feed_precompute(db, events, None)
    return [_map_feed_item_to_reel(ev, db=db, precomputed=precomputed) for ev in events]