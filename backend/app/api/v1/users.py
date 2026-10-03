from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from app.core.limiter import limiter
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.security import create_access_token
from app.schemas.user import (
    HostProfileUpdate,
    HostVerificationResponse,
    UserProfile,
)
from app.core.database import get_db
from app.services.auth_service import (
    request_host_verification,
)
from app.models.notification import Notification
from app.models.user import User   # <-- THIS LINE IS THE FIX

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


def _effective_saka_status(user) -> "tuple[Optional[str], Optional[datetime]]":
    """Returns (status, expires_at), auto-treating a lapsed timed status as
    unset rather than needing a background job to clear it. Every place
    that reads saka_status (this file + stream.py) should go through this
    instead of the raw column, so an expired status disappears everywhere
    at once the moment it's next read."""
    raw_status = getattr(user, "saka_status", None)
    if not raw_status:
        return None, None
    expires_at = getattr(user, "saka_status_expires_at", None)
    if expires_at is not None:
        now = datetime.now(timezone.utc) if expires_at.tzinfo else datetime.utcnow()
        if now >= expires_at:
            return None, None
    return raw_status, expires_at


@router.get("/me", response_model=UserProfile)
def get_profile(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    # Accounts created before the referral feature shipped won't have a
    # code yet — generate one on first fetch rather than needing a backfill
    # migration.
    if not getattr(current_user, "referral_code", None):
        from app.services.auth_service import _generate_referral_code
        current_user.referral_code = _generate_referral_code(db, current_user.username or "")
        db.add(current_user)
        db.commit()
        db.refresh(current_user)

    saka_status, saka_status_expires_at = _effective_saka_status(current_user)

    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "name": current_user.full_name,
        "username": current_user.username,
        "profile_pic_url": getattr(current_user, "profile_picture", None),
        "bio": getattr(current_user, "bio", None),
        "location": getattr(current_user, "location", None),
        "county": getattr(current_user, "county", None),
        "town": getattr(current_user, "town", None),
        "referral_code": getattr(current_user, "referral_code", None),
        "free_events_unlocked": bool(getattr(current_user, "free_events_unlocked", False)),
        "referral_credits": int(getattr(current_user, "referral_credits", 0) or 0),
        "host_pin": getattr(current_user, "host_pin", None),
        "is_host": current_user.is_host,
        "is_admin": getattr(current_user, "is_admin", False),   # <-- add this
        "host_verification_status": current_user.host_verification_status,
        "free_contact_credits": int(getattr(current_user, "free_contact_credits", 0) or 0),
        "referral_bonus_granted": bool(getattr(current_user, "referral_bonus_granted", False)),
        "saka_status": saka_status,
        "saka_status_expires_at": saka_status_expires_at.isoformat() if saka_status_expires_at else None,
    }


@router.post("/me/avatar")
async def upload_my_avatar(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sets the caller's profile picture. Center-crops to a square JPEG and
    stores it in Supabase Storage (never local disk — Render's is wiped on
    every deploy). Used for the landlord photo shown on listings."""
    import io
    import uuid as _uuid
    from PIL import Image, ImageOps

    data = await file.read(8 * 1024 * 1024 + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (8MB max)")
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="File is not a valid image")

    w, h = img.size
    side = min(w, h)
    left, top = (w - side) // 2, (h - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((512, 512))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)

    from app.services import property_service
    try:
        url = property_service.upload_to_supabase_storage(
            f"avatar_{current_user.id.hex}_{_uuid.uuid4().hex[:8]}.jpg", buf.getvalue(), "image/jpeg"
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    current_user.profile_picture = url
    db.add(current_user)
    db.commit()
    return {"profile_pic_url": url}


@router.post("/me/logout-all-sessions")
def logout_all_sessions(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Invalidates every access token issued before this moment — the
    fix for a real gap: there was previously no way for someone to kill
    a stolen/leaked token (e.g. from a lost device, or an XSS-stolen
    localStorage token — see SESSION-001) short of waiting out its full
    lifetime, which defaults to 30 days (see ACCESS_TOKEN_EXPIRE_MINUTES
    in config.py). Comments referencing this exact endpoint already
    existed in dependencies.py and models/user.py — the checking side
    (_token_version_matches, wired into every authenticated request) was
    already correctly built and live; only this, the increment side, was
    ever missing.

    Bumping token_version invalidates the CALLER's own current token too
    (it was issued under the old version), not just other devices — so
    this immediately issues a fresh one in the response, embedding the
    new version, and the frontend swaps it into localStorage right away.
    The practical effect: every OTHER device gets logged out on its next
    request, while the device that asked for this stays signed in
    without interruption — the standard "log out all other sessions"
    pattern, not "log out of everywhere including here."
    """
    current_user.token_version = (current_user.token_version or 0) + 1
    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    fresh_token = create_access_token({
        "sub": str(current_user.id),
        "email": current_user.email,
        "is_host": current_user.is_host,
        "is_admin": current_user.is_admin,
        "token_version": current_user.token_version,
    })

    return {
        "access_token": fresh_token,
        "token_type": "bearer",
        "message": "Every other signed-in device has been logged out.",
    }


@router.post("/host-verification/request")
@limiter.limit("5/minute")
def request_host_verify(
    request: Request,
    data: HostProfileUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.host_verification_status == "pending":
        raise HTTPException(
            status_code=400,
            detail="Host verification already requested, awaiting admin review"
        )
    
    if current_user.is_host:
        raise HTTPException(
            status_code=400,
            detail="User already verified as host"
        )

    from app.models.landlord_id_document import LandlordIdDocument
    if not db.query(LandlordIdDocument).filter(LandlordIdDocument.user_id == current_user.id).first():
        raise HTTPException(
            status_code=400,
            detail="Please upload a clear photo of your ID before applying"
        )
    
    try:
        updated_user = request_host_verification(db, current_user, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "message": "Host verification request submitted",
        "status": updated_user.host_verification_status,
    }


@router.get("/host-verification/me", response_model=HostVerificationResponse)
def get_my_verification_status(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "phone": current_user.phone,
        "host_verification_status": current_user.host_verification_status,
        "verification_requested_at": current_user.verification_requested_at.isoformat() if current_user.verification_requested_at else None,
        "verification_approved_at": current_user.verification_approved_at.isoformat() if current_user.verification_approved_at else None,
        "government_id": current_user.government_id,
        "government_id_image_url": getattr(current_user, "government_id_image_url", None),
        "business_registration": current_user.business_registration,
        "business_registration_image_url": getattr(current_user, "business_registration_image_url", None),
        "bank_name": current_user.bank_name,
        "account_number": getattr(current_user, "account_number", None),
        "account_name": getattr(current_user, "account_name", None),
        "bank_business_number": getattr(current_user, "bank_business_number", None),
        "mpesa_paybill": current_user.mpesa_paybill,
        "kra_pin": current_user.kra_pin,
        "host_pin": current_user.host_pin
    }


# =============================================================================
# Host profile modal — bio / profile picture / location / social link /
# notification preferences. Profile picture is the only required field
# beyond what already exists on the account; everything else here is
# optional. Assumes User gains these columns:
#   bio (String, nullable), profile_pic_url (String, nullable),
#   location (String, nullable), social_link (String, nullable),
#   notification_prefs (JSON, nullable)
# =============================================================================


# =============================================================================
# Payout pipeline — the host-facing side of the Payout Ledger.
#
# Per-event, not a single lump "available balance": an event becomes
# payout-eligible once its final list has been sent to the Live Gate
# (Event.gate_unlocked) AND 24 hours have passed since it ended. From
# there it's request -> admin messages bank details -> host confirms/
# denies -> paid (with M-Pesa code as proof). See
# app.services.withdrawal_service for the full state machine.
# =============================================================================


# =============================================================================
# Notifications — delivers the ticket-tally result (and future payout status
# updates) to the host.
# =============================================================================

def _clean_notification_context(context: str) -> str:
    context = (context or "user").strip().lower()
    return context if context in ("user", "host") else "user"


@router.post("/me/id-image")
@limiter.limit("5/minute")
async def upload_my_id_image(
    request: Request,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Landlord applicants upload a photo of their ID. Stored privately in
    the database and only viewable by admins (see /admin/keja/landlords)."""
    import io
    from app.models.landlord_id_document import LandlordIdDocument

    data = await file.read(6 * 1024 * 1024 + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > 6 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (6MB max)")
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        fmt = (img.format or "").upper()
        img.verify()
    except Exception:
        raise HTTPException(status_code=400, detail="That file is not a valid image")
    types = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
    if fmt not in types:
        raise HTTPException(status_code=400, detail="Only JPG, PNG or WEBP photos are allowed")

    doc = db.query(LandlordIdDocument).filter(LandlordIdDocument.user_id == current_user.id).first()
    if doc:
        doc.content_type, doc.data = types[fmt], data
    else:
        doc = LandlordIdDocument(user_id=current_user.id, content_type=types[fmt], data=data)
        db.add(doc)
    current_user.government_id_image_url = f"/admin/keja/landlords/{current_user.id}/id-image"
    db.add(current_user)
    db.commit()
    return {"detail": "ID photo received"}


@router.post("/notifications/read-all")
def mark_all_notifications_read(
    context: str = "user",
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.context == _clean_notification_context(context),
        Notification.read == False,  # noqa: E712
    ).update({"read": True})
    db.commit()
    return {"message": "All marked as read"}


@router.get("/notifications")
def list_notifications(
    context: str = "user",
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Same "user" (personal profile) vs "host" (host dashboard) split as
    # /messages — a single account can be both a buyer and a host, so the
    # Profile page's bell only ever shows things like refunds, "are you
    # still going?" checks, and follow activity, while the host dashboard's
    # bell only ever shows payouts, "your list has been sent to your Live
    # Gate", and admin broadcasts/polls — even though both queries hit the
    # same table for the same account.
    context = _clean_notification_context(context)
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.context == context)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": str(n.id),
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "data": n.data,
            "read": n.read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in rows
    ]


# =============================================================================
# Support chat — persists host <-> admin messages so the "Admin & Support Hub"
# chat widget on the host dashboard shows a real, durable conversation instead
# of a canned one-off reply. Messages are stored on SupportTicket rows keyed
# by host_id, with `sender` set to "host" or "admin". The admin side reads/
# writes this same table via /admin/support-tickets/active and
# /admin/support-tickets/reply.
# =============================================================================


# =============================================================================
# Heartbeat — powers the admin "User Growth" analytics subpage (active-user
# counts + time-spent). api-config.js fires this once on load and every ~60s
# while any page is open, for both buyers and hosts, so it covers the whole
# app from one place. See app/models/user_session.py for how sessions/time
# spent are derived from these pings.
# =============================================================================


# =============================================================================
# Header-space bidding — the host-facing side of an admin-run "Analytics"
# poll. Admin starts a poll with 3 slots (the home page header carousel
# positions). Every host is notified and can place a bid on any slot with the
# media they want featured. When admin stops the poll, the top bid per slot
# wins and its media gets published to the public header space.
# =============================================================================


# =============================================================================
# Public profile lookup for Cheki (read‑only)
# =============================================================================


# =============================================================================
# Follow requests — persisted server-side (not just localStorage) so a
# follow actually reaches the other person's account, on any device, and
# shows up in their Messages/inbox for accept/deny.
# =============================================================================


