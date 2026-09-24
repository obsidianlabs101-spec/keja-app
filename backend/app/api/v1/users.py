from typing import Optional
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.dependencies import get_current_user, get_current_user_optional
from app.core.security import create_access_token
from app.schemas.user import (
    HostProfileUpdate,
    HostVerificationResponse,
    UserProfile,
    SakaStatusUpdate,
)
from app.core.database import get_db
from app.services.auth_service import (
    update_user_profile,
    request_host_verification,
)
from app.models.booking import Booking
from app.models.payment import Payment
from app.models.withdrawal import Withdrawal
from app.models.notification import Notification
from app.models.event import Event
from app.models.support_ticket import SupportTicket
from app.models.header_poll import HeaderPoll, HeaderPollOption, HeaderBid
from app.models.user import User   # <-- THIS LINE IS THE FIX
from app.models.user_follow import UserFollow
from app.models.user_block import UserBlock
from app.models.cheki_feed_item import ChekiFeedItem
from app.services import withdrawal_service
from app.schemas.withdrawal import PayoutRequestCreate, PayoutRespond

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

ALLOWED_SAKA_STATUSES = {"friends", "dating", "available", "casual", "invisible"}


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


@router.put("/me/saka-status")
def set_saka_status(
    data: SakaStatusUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sets (or clears, via 'invisible') this user's Saka discoverability
    status. See SakaStatusUpdate's docstring in schemas/user.py for the
    duration rules — this is what frontend/profile.js's Status section in
    Personalisation calls, and stream.py reads the result back out via
    _effective_saka_status to decide which Saka tab (if any) this
    person's card shows up under."""
    status_value = (data.status or "").strip().lower()
    if status_value not in ALLOWED_SAKA_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(ALLOWED_SAKA_STATUSES)}",
        )

    unit = (data.duration_unit or "off").strip().lower()
    expires_at = None
    # "invisible" never expires on its own — it's a privacy choice, not a
    # browsing mode, so there's nothing to "expire back" out of.
    if status_value != "invisible" and unit != "off":
        if unit not in ("hours", "days"):
            raise HTTPException(status_code=400, detail="duration_unit must be 'hours', 'days', or 'off'")
        value = data.duration_value or 0
        if value <= 0:
            raise HTTPException(status_code=400, detail="duration_value must be a positive number")
        delta = timedelta(hours=value) if unit == "hours" else timedelta(days=value)
        expires_at = datetime.utcnow() + delta

    current_user.saka_status = status_value
    current_user.saka_status_expires_at = expires_at
    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return {
        "saka_status": current_user.saka_status,
        "saka_status_expires_at": current_user.saka_status_expires_at.isoformat() if current_user.saka_status_expires_at else None,
    }


class DuplicateGuardSubmitRequest(BaseModel):
    photo_url: str


@router.post("/duplicate-guard/submit")
def submit_duplicate_guard_photo(
    data: DuplicateGuardSubmitRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Frontend flow: POST /media/upload (file_type=duplicate_guard) first
    to get a URL, then this to register it. Always resets to 'pending' —
    including on a resubmission after a rejection, since that's the whole
    point of allowing someone to try again with a clearer photo."""
    photo_url = (data.photo_url or "").strip()
    if not photo_url:
        raise HTTPException(status_code=400, detail="photo_url is required")

    current_user.duplicate_guard_photo_url = photo_url
    current_user.duplicate_guard_status = "pending"
    current_user.duplicate_guard_submitted_at = datetime.utcnow()
    current_user.duplicate_guard_reviewed_at = None
    current_user.duplicate_guard_rejection_reason = None
    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return {
        "duplicate_guard_status": current_user.duplicate_guard_status,
        "duplicate_guard_photo_url": current_user.duplicate_guard_photo_url,
    }


@router.get("/duplicate-guard/me")
def get_my_duplicate_guard_status(
    current_user=Depends(get_current_user),
):
    return {
        "duplicate_guard_status": current_user.duplicate_guard_status,
        "duplicate_guard_photo_url": current_user.duplicate_guard_photo_url,
        "duplicate_guard_rejection_reason": current_user.duplicate_guard_rejection_reason,
        "duplicate_guard_submitted_at": current_user.duplicate_guard_submitted_at.isoformat() if current_user.duplicate_guard_submitted_at else None,
        "duplicate_guard_enabled": bool(current_user.duplicate_guard_enabled),
    }


@router.post("/duplicate-guard/toggle-live-gate")
def toggle_duplicate_guard_live_gate(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Self-service — no admin approval needed for this part (only the
    photo itself gets admin-reviewed). One setting covers every event this
    host runs. See POST /events/{id}/checkin's duplicate-scan branch for
    where this actually gets read."""
    current_user.duplicate_guard_enabled = not bool(current_user.duplicate_guard_enabled)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return {"duplicate_guard_enabled": bool(current_user.duplicate_guard_enabled)}


# =============================================================================
# NOTIFICATION PREFERENCES — reuses the existing User.notification_preferences
# JSON column (previously write-only from a host-profile endpoint, nothing
# ever read or acted on it). All five toggles are now real, stored
# preferences and at least one must be on. near_me/price_alert/location_alert
# are matched against every newly-published event by
# event_service.notify_nearby_users_of_new_event (called from
# POST /events/create) — a user can match more than one and gets a single
# combined notification. ticket_confirmation and still_going_check have
# real 1-to-1 triggers in booking_service.py and attendance_service.py
# respectively. All five now actually honor this setting.
# =============================================================================
_NOTIF_PREF_DEFAULTS = {
    "near_me": True,
    "price_alert": False,
    "price_alert_max": None,
    "location_alert": False,
    "location_alert_value": None,
    "ticket_confirmation": True,
    "still_going_check": True,
}


def _read_notification_prefs(user) -> dict:
    import json as _json
    raw = getattr(user, "notification_preferences", None)
    prefs = dict(_NOTIF_PREF_DEFAULTS)
    if raw:
        try:
            stored = _json.loads(raw)
            if isinstance(stored, dict):
                prefs.update({k: v for k, v in stored.items() if k in _NOTIF_PREF_DEFAULTS})
        except (ValueError, TypeError):
            pass
    return prefs


@router.get("/notification-preferences/me")
def get_my_notification_preferences(current_user=Depends(get_current_user)):
    return _read_notification_prefs(current_user)


class NotificationPreferencesRequest(BaseModel):
    near_me: bool = False
    price_alert: bool = False
    price_alert_max: Optional[float] = None
    location_alert: bool = False
    location_alert_value: Optional[str] = None
    ticket_confirmation: bool = False
    still_going_check: bool = False


@router.put("/notification-preferences")
def set_my_notification_preferences(
    data: NotificationPreferencesRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not any([
        data.near_me,
        data.price_alert,
        data.location_alert,
        data.ticket_confirmation,
        data.still_going_check,
    ]):
        raise HTTPException(status_code=400, detail="Pick at least one notification type")

    import json as _json
    prefs = {
        "near_me": bool(data.near_me),
        "price_alert": bool(data.price_alert),
        "price_alert_max": data.price_alert_max if data.price_alert else None,
        "location_alert": bool(data.location_alert),
        "location_alert_value": (data.location_alert_value or "").strip() or None if data.location_alert else None,
        "ticket_confirmation": bool(data.ticket_confirmation),
        "still_going_check": bool(data.still_going_check),
    }
    current_user.notification_preferences = _json.dumps(prefs)
    db.add(current_user)
    db.commit()

    return prefs


@router.patch("/profile")
def update_profile(
    data: HostProfileUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    updated_user = update_user_profile(db, current_user, data)
    return {
        "message": "Profile updated successfully",
        "user_id": str(updated_user.id),
    }


@router.post("/host-verification/request")
def request_host_verify(
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

class HostProfileFullUpdate(BaseModel):
    # Was a required `str` — meant saving just a county/town/bio silently
    # 400'd for anyone who hadn't already set a profile picture, since
    # the frontend sends this whole payload as one PATCH. Now optional:
    # omit it (or send null) to leave the existing picture untouched.
    profile_pic_url: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    county: Optional[str] = None
    town: Optional[str] = None
    social_link: Optional[str] = None
    notification_prefs: Optional[dict] = None


@router.patch("/profile/host")
def update_host_profile_full(
    data: HostProfileFullUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # NOTE: the User model's real columns are `profile_picture`,
    # `social_links` and `notification_preferences` — earlier code here
    # wrote to `profile_pic_url` / `social_link` / `notification_prefs`,
    # attribute names that don't exist as mapped columns. That meant the
    # write silently vanished on refresh/reload (worked for the rest of
    # this one request, then 404'd/AttributeError'd — or just quietly
    # never persisted — on the next), which is why avatars, bios and
    # profile edits kept "disappearing" after login. Map to the real
    # columns instead.
    if data.profile_pic_url is not None and data.profile_pic_url.strip():
        current_user.profile_picture = data.profile_pic_url

    if data.full_name is not None and data.full_name.strip():
        current_user.full_name = data.full_name.strip()

    # Email, like username, is permanent once set at signup — intentionally
    # NOT editable from the host profile modal (or anywhere else). An
    # `email` field may still arrive on this payload from older frontend
    # builds; it's ignored here on purpose.

    if data.bio is not None:
        current_user.bio = data.bio
    if data.location is not None:
        current_user.location = data.location
    if data.county is not None:
        current_user.county = data.county
    if data.town is not None:
        current_user.town = data.town
    if data.social_link is not None:
        current_user.social_links = data.social_link
    if data.notification_prefs is not None:
        import json as _json
        current_user.notification_preferences = _json.dumps(data.notification_prefs)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return {
        "message": "Profile updated",
        "profile_pic_url": current_user.profile_picture,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "bio": getattr(current_user, "bio", None),
        "location": getattr(current_user, "location", None),
        "county": getattr(current_user, "county", None),
        "town": getattr(current_user, "town", None),
        "social_link": getattr(current_user, "social_links", None),
        "notification_prefs": getattr(current_user, "notification_preferences", None),
    }


class HostPinChange(BaseModel):
    current_pin: Optional[str] = None
    new_pin: str


@router.post("/host-pin")
def change_host_pin(
    data: HostPinChange,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not data.new_pin or len(data.new_pin.strip()) < 4:
        raise HTTPException(status_code=400, detail="New PIN must be at least 4 characters")

    if current_user.host_pin and data.current_pin != current_user.host_pin:
        raise HTTPException(status_code=403, detail="Current PIN is incorrect")

    current_user.host_pin = data.new_pin.strip()
    db.add(current_user)
    db.commit()

    return {"message": "Host PIN updated"}


class PayoutBankDetailsUpdate(BaseModel):
    mpesa_paybill: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    account_name: Optional[str] = None


@router.patch("/payout/bank-details")
def update_payout_bank_details(
    data: PayoutBankDetailsUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Used only by the payout Deny -> edit -> resubmit flow. Deliberately
    narrow (bank/M-Pesa fields only, no is_host gate) since /host-
    verification/request rejects anyone who's already an approved host —
    this is specifically for an approved host correcting their payout
    details after a denial, not re-applying."""
    current_user.mpesa_paybill = data.mpesa_paybill
    current_user.bank_name = data.bank_name
    current_user.account_number = data.account_number
    current_user.account_name = data.account_name
    db.add(current_user)
    db.commit()
    return {"message": "Bank/M-Pesa details updated"}


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

@router.get("/payout/events")
def list_payout_events(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Every one of the host's events that's had its final list sent to
    the Live Gate, with attendance tally, revenue breakdown, and payout
    status. Powers both the Payout Ledger (unpaid events with a Request
    Payout button) and the Past Events card's real supposed-vs-came
    numbers — paid ones simply don't show a Request Payout button here
    anymore and instead read as "Settled" wherever the past card renders."""
    return withdrawal_service.get_host_payout_events(db, current_user.id)


@router.post("/payout/request")
def request_payout(
    data: PayoutRequestCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        withdrawal = withdrawal_service.create_event_payout_request(db, current_user, data.event_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "message": "Payout requested — pending admin review",
        "withdrawal_id": str(withdrawal.id),
        "amount": withdrawal.host_payout_amount,
        "status": withdrawal.status,
    }


@router.get("/payout/mine")
def list_my_payouts(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """All of this host's withdrawal requests (any status) — used to show
    the confirm/deny prompt once admin has messaged, and to know which
    events have already settled."""
    rows = (
        db.query(Withdrawal)
        .filter(Withdrawal.host_id == current_user.id)
        .order_by(Withdrawal.requested_at.desc())
        .all()
    )
    return [
        {
            "id": str(w.id),
            "event_id": str(w.event_id) if w.event_id else None,
            "status": w.status,
            "gross_revenue": w.gross_revenue,
            "platform_cut": w.platform_cut,
            "host_payout_amount": w.host_payout_amount,
            "bank_name": w.bank_name,
            "account_number": w.account_number,
            "account_name": w.account_name,
            "bank_business_number": w.bank_business_number,
            "mpesa_paybill": w.mpesa_paybill,
            "mpesa_code": w.mpesa_code,
            "requested_at": w.requested_at.isoformat() if w.requested_at else None,
            "messaged_at": w.messaged_at.isoformat() if w.messaged_at else None,
            "paid_at": w.paid_at.isoformat() if w.paid_at else None,
        }
        for w in rows
    ]


@router.post("/payout/{withdrawal_id}/respond")
def respond_to_payout(
    withdrawal_id: str,
    data: PayoutRespond,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    withdrawal = db.query(Withdrawal).filter(
        Withdrawal.id == withdrawal_id, Withdrawal.host_id == current_user.id
    ).first()
    if not withdrawal:
        raise HTTPException(status_code=404, detail="Payout request not found")
    try:
        withdrawal = withdrawal_service.respond_to_payout_message(db, withdrawal, data.confirm)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Confirmed — awaiting M-Pesa payment" if data.confirm else "Denied — update your bank details and resubmit", "status": withdrawal.status}


@router.post("/payout/{withdrawal_id}/resubmit")
def resubmit_payout(
    withdrawal_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    withdrawal = db.query(Withdrawal).filter(
        Withdrawal.id == withdrawal_id, Withdrawal.host_id == current_user.id
    ).first()
    if not withdrawal:
        raise HTTPException(status_code=404, detail="Payout request not found")
    try:
        withdrawal = withdrawal_service.resubmit_payout_request(db, current_user, withdrawal)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Payout re-requested with updated bank details", "status": withdrawal.status}


# =============================================================================
# Notifications — delivers the ticket-tally result (and future payout status
# updates) to the host.
# =============================================================================

def _clean_notification_context(context: str) -> str:
    context = (context or "user").strip().lower()
    return context if context in ("user", "host") else "user"


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


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = db.query(Notification).filter(
        Notification.id == notification_id, Notification.user_id == current_user.id
    ).first()
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.read = True
    db.add(n)
    db.commit()
    return {"message": "Marked as read"}


class PushSubscriptionIn(BaseModel):
    endpoint: str
    keys: dict


@router.post("/push-subscription")
def save_push_subscription(
    payload: PushSubscriptionIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Called by the frontend once the browser grants notification
    permission and registers a PushSubscription — stores it so backend
    events (starting with the T-2h attendance check) can push a real
    notification-tray alert to this user's phone."""
    import json
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.push_subscription = json.dumps({"endpoint": payload.endpoint, "keys": payload.keys})
    db.add(user)
    db.commit()
    return {"message": "Push subscription saved"}


@router.delete("/push-subscription")
def clear_push_subscription(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if user:
        user.push_subscription = None
        db.add(user)
        db.commit()
    return {"message": "Push subscription cleared"}

# =============================================================================
# Support chat — persists host <-> admin messages so the "Admin & Support Hub"
# chat widget on the host dashboard shows a real, durable conversation instead
# of a canned one-off reply. Messages are stored on SupportTicket rows keyed
# by host_id, with `sender` set to "host" or "admin". The admin side reads/
# writes this same table via /admin/support-tickets/active and
# /admin/support-tickets/reply.
# =============================================================================

class SupportChatMessage(BaseModel):
    message: str


@router.post("/support-chat")
def send_host_support_message(
    payload: SupportChatMessage,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    text = (payload.message or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    ticket = SupportTicket(
        host_id=current_user.id,
        sender="host",
        message=text,
        resolved=False,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return {
        "status": "delivered",
        "id": str(ticket.id),
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
    }


@router.get("/support-chat/messages")
def get_host_support_thread(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(SupportTicket)
        .filter(SupportTicket.host_id == current_user.id)
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


# =============================================================================
# Heartbeat — powers the admin "User Growth" analytics subpage (active-user
# counts + time-spent). api-config.js fires this once on load and every ~60s
# while any page is open, for both buyers and hosts, so it covers the whole
# app from one place. See app/models/user_session.py for how sessions/time
# spent are derived from these pings.
# =============================================================================

@router.post("/heartbeat")
def record_heartbeat(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import datetime, timedelta, timezone
    from app.models.user_session import UserSession, HEARTBEAT_SESSION_GAP_MINUTES

    now = datetime.now(timezone.utc)
    session = (
        db.query(UserSession)
        .filter(UserSession.user_id == current_user.id)
        .order_by(UserSession.last_seen_at.desc())
        .first()
    )

    last_seen = session.last_seen_at if session else None
    if last_seen and last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)

    if session and last_seen and (now - last_seen) <= timedelta(minutes=HEARTBEAT_SESSION_GAP_MINUTES):
        session.last_seen_at = now
    else:
        session = UserSession(user_id=current_user.id, started_at=now, last_seen_at=now)
        db.add(session)

    db.commit()
    return {"status": "ok"}


# =============================================================================
# Header-space bidding — the host-facing side of an admin-run "Analytics"
# poll. Admin starts a poll with 3 slots (the home page header carousel
# positions). Every host is notified and can place a bid on any slot with the
# media they want featured. When admin stops the poll, the top bid per slot
# wins and its media gets published to the public header space.
# =============================================================================

@router.get("/header-poll/active")
def get_active_header_poll(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
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

    result_options = []
    for opt in options:
        top_bid = (
            db.query(HeaderBid)
            .filter(HeaderBid.option_id == opt.id)
            .order_by(HeaderBid.amount.desc())
            .first()
        )
        my_bid = (
            db.query(HeaderBid)
            .filter(HeaderBid.option_id == opt.id, HeaderBid.host_id == current_user.id)
            .first()
        )
        my_event = None
        if my_bid and my_bid.event_id:
            my_event = db.query(Event).filter(Event.id == my_bid.event_id).first()
        result_options.append({
            "option_id": str(opt.id),
            "slot_number": opt.slot_number,
            "top_bid_amount": float(top_bid.amount) if top_bid else 0,
            "my_bid_amount": float(my_bid.amount) if my_bid else None,
            "my_media_url": my_bid.media_url if my_bid else None,
            "my_event_id": str(my_bid.event_id) if (my_bid and my_bid.event_id) else None,
            "my_event_title": my_event.title if my_event else None,
        })

    return {
        "active": True,
        "poll_id": str(poll.id),
        "created_at": poll.created_at.isoformat() if poll.created_at else None,
        "options": result_options,
    }


class HeaderPollBid(BaseModel):
    option_id: str
    amount: float
    media_url: str
    event_id: Optional[str] = None


@router.post("/header-poll/bid")
def place_header_poll_bid(
    data: HeaderPollBid,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Bid amount must be greater than zero")
    if not data.media_url or not data.media_url.strip():
        raise HTTPException(status_code=400, detail="Media is required for your bid")

    option = db.query(HeaderPollOption).filter(HeaderPollOption.id == data.option_id).first()
    if not option:
        raise HTTPException(status_code=404, detail="This header slot no longer exists")

    poll = db.query(HeaderPoll).filter(HeaderPoll.id == option.poll_id).first()
    if not poll or poll.status != "active":
        raise HTTPException(status_code=400, detail="This poll is no longer accepting bids")

    event_id = None
    if data.event_id:
        owned_event = (
            db.query(Event)
            .filter(Event.id == data.event_id, Event.host_id == current_user.id)
            .first()
        )
        if not owned_event:
            raise HTTPException(status_code=404, detail="Pick one of your own events to feature")
        event_id = owned_event.id

    existing = (
        db.query(HeaderBid)
        .filter(HeaderBid.option_id == option.id, HeaderBid.host_id == current_user.id)
        .first()
    )
    if existing:
        existing.amount = data.amount
        existing.media_url = data.media_url
        existing.event_id = event_id
        db.add(existing)
    else:
        db.add(HeaderBid(
            option_id=option.id,
            host_id=current_user.id,
            amount=data.amount,
            media_url=data.media_url,
            event_id=event_id,
        ))
    db.commit()

    return {"message": "Bid placed", "option_id": str(option.id), "amount": data.amount}

# =============================================================================
# Public profile lookup for Cheki (read‑only)
# =============================================================================

def _username(user: Optional[User]) -> str:
    if user is None or not getattr(user, "username", None):
        return "@anonymous"
    u = user.username
    return u if u.startswith("@") else f"@{u}"


def _norm_username(u: str) -> str:
    u = (u or "").strip()
    return u if u.startswith("@") else f"@{u}"


def _find_user_by_username(db: Session, username: str) -> Optional[User]:
    """Username match, tolerant of the leading '@' being present or absent
    in the DB — signup, host application, and older records have all
    stored it differently, so a strict `== "@handle"` filter here was
    causing profile lookups and follow requests to 404 for accounts
    whose username was stored without the '@'.

    Also case-insensitive: accounts with a capital letter in their
    username (e.g. "@Jamie_boy") were 404ing on public-profile lookups
    while all-lowercase usernames worked fine — some code path between
    a post being displayed and its author's @handle being clicked isn't
    preserving the original case, so an exact-case match was too
    strict. Comparing lowercased is the standard fix for username
    lookups generally, rather than chasing down every place case might
    drift before this function ever sees it."""
    bare = (username or "").strip().lstrip("@")
    if not bare:
        return None
    bare_lower = bare.lower()
    return db.query(User).filter(
        func.lower(User.username).in_([bare_lower, f"@{bare_lower}"])
    ).first()


@router.get("/search")
def search_users(
    q: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Partial, case-insensitive username match — used by Saka's search
    bar. This is distinct from GET /public/{username} (an exact lookup);
    that endpoint alone is why searching for a partial name someone
    hasn't posted anything under used to come up empty even when the
    account exists."""
    bare = (q or "").strip().lstrip("@")
    if not bare or len(bare) < 2:
        return {"results": []}

    rows = (
        db.query(User)
        .filter(User.username.ilike(f"%{bare}%"))
        .order_by(User.username.asc())
        .limit(20)
        .all()
    )
    return {
        "results": [
            {
                "username": u.username,
                "full_name": u.full_name,
                "profile_pic_url": u.profile_picture,
                "location": u.location,
                "is_host": bool(u.is_host),
            }
            for u in rows
        ]
    }


@router.get("/public/{username}")
def get_public_profile(
    username: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    user = _find_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    followers_count = db.query(UserFollow).filter(
        UserFollow.followee_id == user.id, UserFollow.status == "accepted"
    ).count()
    following_count = db.query(UserFollow).filter(
        UserFollow.follower_id == user.id, UserFollow.status == "accepted"
    ).count()
    # Posts store the author's handle as a string (`@bob` or `bob`
    # depending on when the account signed up), so match both forms —
    # a strict `== user.username` was returning 0 whenever the DB user
    # row and the feed row disagreed on the leading '@'.
    _bare = (user.username or "").lstrip("@")
    _bare_lower = _bare.lower()
    posts_count = db.query(ChekiFeedItem).filter(
        func.lower(ChekiFeedItem.username).in_([_bare_lower, f"@{_bare_lower}"])
    ).count()

    is_following = False
    follow_status = None
    is_followed_by = False
    if current_user and current_user.id != user.id:
        rel = db.query(UserFollow).filter(
            UserFollow.follower_id == current_user.id,
            UserFollow.followee_id == user.id,
        ).first()
        if rel:
            follow_status = rel.status
            is_following = rel.status == "accepted"
        back_rel = db.query(UserFollow).filter(
            UserFollow.follower_id == user.id,
            UserFollow.followee_id == current_user.id,
            UserFollow.status == "accepted",
        ).first()
        is_followed_by = back_rel is not None

    return {
        "username": user.username,
        # `profile_pic_url` here was previously read from a column
        # (`user.profile_pic_url`) that doesn't exist on the User model —
        # the real column is `profile_picture` — so this endpoint 500'd
        # every time. Kept the response key the same for the frontend.
        "profile_pic_url": getattr(user, "profile_picture", None),
        "bio": getattr(user, "bio", None),
        "full_name": user.full_name,
        "location": getattr(user, "location", None),
        "followers_count": followers_count,
        "following_count": following_count,
        "posts_count": posts_count,
        "is_following": is_following,
        "follow_status": follow_status,  # None | "pending" | "accepted"
        "is_followed_by": is_followed_by,
        "is_squad": is_following and is_followed_by,  # mutual follow
        "is_host": bool(getattr(user, "is_host", False)),
        "gold_organiser": bool(getattr(user, "gold_organiser", False)),
        "saka_status": _effective_saka_status(user)[0],
    }


@router.get("/public/{username}/followers")
def get_public_followers(username: str, db: Session = Depends(get_db)):
    user = _find_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    rows = (
        db.query(User)
        .join(UserFollow, UserFollow.follower_id == User.id)
        .filter(UserFollow.followee_id == user.id, UserFollow.status == "accepted")
        .all()
    )
    return [
        {"username": u.username, "profile_pic_url": getattr(u, "profile_picture", None)}
        for u in rows
    ]


@router.get("/public/{username}/following")
def get_public_following(username: str, db: Session = Depends(get_db)):
    user = _find_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    rows = (
        db.query(User)
        .join(UserFollow, UserFollow.followee_id == User.id)
        .filter(UserFollow.follower_id == user.id, UserFollow.status == "accepted")
        .all()
    )
    return [
        {"username": u.username, "profile_pic_url": getattr(u, "profile_picture", None)}
        for u in rows
    ]


# =============================================================================
# Follow requests — persisted server-side (not just localStorage) so a
# follow actually reaches the other person's account, on any device, and
# shows up in their Messages/inbox for accept/deny.
# =============================================================================

@router.post("/follow/{username}")
def send_follow_request(
    username: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = _find_user_by_username(db, username)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="You can't follow yourself")

    existing = db.query(UserFollow).filter(
        UserFollow.follower_id == current_user.id,
        UserFollow.followee_id == target.id,
    ).first()
    if existing:
        return {"status": existing.status, "message": "Already requested/following"}

    rel = UserFollow(follower_id=current_user.id, followee_id=target.id, status="pending")
    db.add(rel)

    db.add(Notification(
        user_id=target.id,
        type="follow_request",
        title="New follow request",
        body=f"{_username(current_user)} wants to follow you",
        data={"from_username": current_user.username, "from_user_id": str(current_user.id)},
        context="user",
    ))
    db.commit()
    return {"status": "pending", "message": "Follow request sent"}


@router.delete("/follow/{username}")
def unfollow_or_cancel_request(
    username: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = _find_user_by_username(db, username)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    rel = db.query(UserFollow).filter(
        UserFollow.follower_id == current_user.id,
        UserFollow.followee_id == target.id,
    ).first()
    if rel:
        db.delete(rel)
        db.commit()
    return {"message": "Unfollowed"}


@router.post("/block/{username}")
def block_user(
    username: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The @username profile view's Block button. Per UserBlock's own
    docstring (which pre-dated this route existing), blocking also tears
    down any follow relationship between the two accounts in either
    direction — a block should never leave a stale mutual-follow behind."""
    target = _find_user_by_username(db, username)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="You can't block yourself")

    existing = db.query(UserBlock).filter(
        UserBlock.blocker_id == current_user.id,
        UserBlock.blocked_id == target.id,
    ).first()
    if not existing:
        db.add(UserBlock(blocker_id=current_user.id, blocked_id=target.id))

    db.query(UserFollow).filter(
        ((UserFollow.follower_id == current_user.id) & (UserFollow.followee_id == target.id))
        | ((UserFollow.follower_id == target.id) & (UserFollow.followee_id == current_user.id))
    ).delete(synchronize_session=False)

    db.commit()
    return {"message": f"{username} blocked"}


@router.delete("/block/{username}")
def unblock_user(
    username: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = _find_user_by_username(db, username)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    rel = db.query(UserBlock).filter(
        UserBlock.blocker_id == current_user.id,
        UserBlock.blocked_id == target.id,
    ).first()
    if rel:
        db.delete(rel)
        db.commit()
    return {"message": "Unblocked"}


@router.get("/follow-requests")
def list_incoming_follow_requests(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(UserFollow, User)
        .join(User, User.id == UserFollow.follower_id)
        .filter(UserFollow.followee_id == current_user.id, UserFollow.status == "pending")
        .order_by(UserFollow.created_at.desc())
        .all()
    )
    return [
        {
            "id": str(rel.id),
            "username": u.username,
            "profile_pic_url": getattr(u, "profile_picture", None),
            "bio": getattr(u, "bio", None),
            "created_at": rel.created_at.isoformat() if rel.created_at else None,
        }
        for rel, u in rows
    ]


class FollowRequestRespond(BaseModel):
    accept: bool


@router.post("/follow-requests/{request_id}/respond")
def respond_to_follow_request(
    request_id: str,
    data: FollowRequestRespond,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import datetime as _dt

    rel = db.query(UserFollow).filter(
        UserFollow.id == request_id, UserFollow.followee_id == current_user.id
    ).first()
    if not rel:
        raise HTTPException(status_code=404, detail="Follow request not found")

    # Either way, the requester stays following current_user — "Naah" only
    # declines following them *back* (no squad), it doesn't remove them as
    # a follower.
    rel.status = "accepted"
    rel.responded_at = _dt.utcnow()
    db.add(rel)

    if data.accept:
        # "Follow Back" — also follow the requester back, so the pair
        # becomes mutual (a squad), not just a one-way follow.
        reciprocal = db.query(UserFollow).filter(
            UserFollow.follower_id == current_user.id,
            UserFollow.followee_id == rel.follower_id,
        ).first()
        if reciprocal:
            reciprocal.status = "accepted"
            reciprocal.responded_at = _dt.utcnow()
            db.add(reciprocal)
        else:
            db.add(UserFollow(
                follower_id=current_user.id,
                followee_id=rel.follower_id,
                status="accepted",
                responded_at=_dt.utcnow(),
            ))
        db.add(Notification(
            user_id=rel.follower_id,
            type="follow_accepted",
            title="Followed back — you're squad now",
            body=f"{_username(current_user)} followed you back. You're in each other's squad now.",
            data={"username": current_user.username},
            context="user",
        ))
    else:
        db.add(Notification(
            user_id=rel.follower_id,
            type="follow_accepted",
            title="Follow request accepted",
            body=f"{_username(current_user)} accepted your follow request",
            data={"username": current_user.username},
            context="user",
        ))

    db.commit()
    return {"message": "Followed back" if data.accept else "Kept as follower"}