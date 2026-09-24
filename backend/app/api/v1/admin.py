from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_admin, require_admin
from app.schemas.admin import (
    AdminProfile,
    HostVerificationActionRequest
)
from app.schemas.user import HostVerificationResponse
from app.services.admin_service import (
    log_admin_activity,
)
from app.services import withdrawal_service
from app.schemas.withdrawal import AdminWithdrawalAction, WithdrawalResponse
from app.services.auth_service import (
    list_pending_host_verifications,
    approve_or_reject_host_verification,
)
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.security import verify_password
from app.models.payment import Payment
from app.models.event import Event
from app.models.booking import Booking
from app.models.ticket import Ticket
from app.models.withdrawal import Withdrawal
from app.models.notification import Notification
from app.models.admin_activity_log import AdminActivityLog

router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)


def require_finance_admin(admin=Depends(require_admin)):
    """Extra gate on top of require_admin — only admins with
    is_finance_verified can see the Financials page. Separate from the
    password check (POST /admin/financials/verify-password), which the
    frontend calls once per page-open before rendering anything; this
    dependency additionally protects the underlying data endpoints
    directly, so the gate can't be bypassed by skipping the frontend
    prompt."""
    if not getattr(admin, "is_finance_verified", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You're not cleared for financial access. Ask another admin to grant it, "
                   "or use the admin creation secret via /admin/financials/grant-access.",
        )
    return admin


# NOTE: this router previously had /register and /login endpoints backed
# by a separate `admins` database table. They're removed: every protected
# route below gates on require_admin -> get_current_admin, which checks
# User.is_admin on the *users* table — a completely different ID space
# from that old `admins` table, so a token minted by the old /login could
# never actually pass require_admin in the first place. They were dead
# code sitting behind a secret (ADMIN_CREATION_SECRET) for no working
# benefit. The one real path to admin access is a `users` row with
# is_admin=True, set directly at the database level — deliberately not
# exposed over the API, since admin access is exactly the kind of thing
# that should require more friction than a signup form, not less.


@router.get("/me", response_model=AdminProfile)
def get_admin_profile(
    current_admin=Depends(get_current_admin),
):
    return current_admin


@router.get("/platform-stats")
def platform_stats(db: Session = Depends(get_db), admin=Depends(require_admin)):
    """Real counts for the admin dashboard's top stat tiles. Kept
    deliberately simple (no revenue/growth breakdowns) — this is just
    enough to replace the old UI's hardcoded placeholder numbers with
    numbers that are actually true."""
    from app.models.user import User
    from app.models.property import Property

    total_properties = db.query(Property).filter(Property.is_removed == False).count()  # noqa: E712
    active_landlords = (
        db.query(Property.landlord_id)
        .filter(Property.is_removed == False)  # noqa: E712
        .distinct()
        .count()
    )
    total_users = db.query(User).count()
    pending_verifications = len(list_pending_host_verifications(db))

    return {
        "total_properties": total_properties,
        "active_landlords": active_landlords,
        "total_users": total_users,
        "pending_verifications": pending_verifications,
    }


import logging as _logging
_logger = _logging.getLogger("bash.admin")


@router.get("/withdrawals/pending")
def pending_withdrawals(db: Session = Depends(get_db), admin=Depends(require_admin)):
    """Everything still moving through the payout pipeline (requested,
    awaiting the host's confirmation, or confirmed and waiting on us to
    send the M-Pesa payment and log the code)."""
    try:
        rows = withdrawal_service.list_pending_withdrawals(db)
        return [_serialize_withdrawal(db, w) for w in rows]
    except Exception as e:
        db.rollback()
        _logger.exception("Failed to load pending withdrawals")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Couldn't load pending payout requests: {e}"
        )


@router.get("/withdrawals/paid")
def paid_withdrawals(db: Session = Depends(get_db), admin=Depends(require_finance_admin)):
    """Settled payouts — feeds both the Host Financials and Bash
    Financials cards on the admin Financials page."""
    try:
        rows = withdrawal_service.list_paid_withdrawals(db)
        return [_serialize_withdrawal(db, w) for w in rows]
    except Exception as e:
        db.rollback()
        _logger.exception("Failed to load paid withdrawals")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Couldn't load paid payouts: {e}"
        )


def _serialize_withdrawal(db: Session, w: Withdrawal) -> dict:
    event = db.query(Event).filter(Event.id == w.event_id).first() if w.event_id else None
    host = db.query(User).filter(User.id == w.host_id).first()
    return {
        "id": str(w.id),
        "event_id": str(w.event_id) if w.event_id else None,
        "event_title": event.title if event else None,
        "event_poster_url": (event.poster_url or event.video_url) if event else None,
        "host_id": str(w.host_id),
        "host_name": host.full_name if host else None,
        "host_username": host.username if host else None,
        "host_email": host.email if host else None,
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
        "host_responded_at": w.host_responded_at.isoformat() if w.host_responded_at else None,
        "paid_at": w.paid_at.isoformat() if w.paid_at else None,
    }


@router.post("/withdrawals/{withdrawal_id}/message")
def message_host_about_payout(withdrawal_id: str, db: Session = Depends(get_db), admin=Depends(require_admin)):
    """The "Message" button on a pending payout request — sends the host
    the event name, expected payment, and bank/M-Pesa details on file,
    with Confirm/Deny."""
    w = db.query(Withdrawal).filter(Withdrawal.id == withdrawal_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Payout request not found")
    try:
        w = withdrawal_service.message_host_for_payout(db, w, admin.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    log_admin_activity(db, admin.id, "payout_message", detail=f"Messaged host about payout for withdrawal {w.id}", amount=w.host_payout_amount)
    db.commit()
    return _serialize_withdrawal(db, w)


class MarkPaidRequest(BaseModel):
    mpesa_code: str


@router.post("/withdrawals/{withdrawal_id}/mark-paid")
def mark_withdrawal_paid(withdrawal_id: str, action: MarkPaidRequest, db: Session = Depends(get_db), admin=Depends(require_admin)):
    """Once the host has confirmed and we've manually sent the M-Pesa
    payment ourselves, log the resulting confirmation code here. This is
    what creates the Host Financials / Bash Financials record and sends
    the code to the host as proof of payment."""
    w = db.query(Withdrawal).filter(Withdrawal.id == withdrawal_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Payout request not found")
    try:
        w = withdrawal_service.mark_payout_paid(db, w, admin.id, action.mpesa_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    log_admin_activity(db, admin.id, "payout_mark_paid", detail=f"Marked withdrawal {w.id} paid — M-Pesa {w.mpesa_code}", amount=w.host_payout_amount)
    db.commit()
    return _serialize_withdrawal(db, w)


@router.get("/dashboard/financials")
def financial_overview(db: Session = Depends(get_db), admin=Depends(require_finance_admin)):
    # Total gross sales (paid payments)
    gross = db.query(func.coalesce(func.sum(func.cast(Payment.amount, func.numeric)), 0)).filter(Payment.status == "paid").scalar() or 0

    # Payment.amount is the buyer's TOTAL paid — it already has the 12%
    # checkout markup (10% platform + 2% mpesa) baked in. Back that out to
    # the host's pre-markup ticket value before splitting the fee, so this
    # matches withdrawal_service's PLATFORM_CUT_RATE model exactly instead
    # of applying 12% a second time on top of an already-marked-up total.
    host_value = float(gross) / 1.12
    platform_fee = host_value * 0.10
    mpesa_fees = host_value * 0.02
    net_payout = host_value

    # BUG FIX: "approved" is not a status this pipeline ever sets (see
    # withdrawal_service.py) — the real in-flight states between a host
    # asking for payout and it being marked "paid" are "requested",
    # "awaiting_host_confirmation", and "confirmed_by_host". Filtering on
    # the nonexistent "approved" instead of the latter two silently
    # undercounted this dashboard stat, hiding most of the platform's
    # actual pending-payout liability.
    pending_payouts = db.query(func.coalesce(func.sum(Withdrawal.amount), 0)).filter(
        Withdrawal.status.in_(["requested", "awaiting_host_confirmation", "confirmed_by_host"])
    ).scalar() or 0

    return {
        "gross_revenue": float(gross),
        "platform_fee": float(platform_fee),
        "mpesa_fees": float(mpesa_fees),
        "net_payout": float(net_payout),
        "pending_payouts_estimate": float(pending_payouts),
    }


class FinancePasswordCheck(BaseModel):
    password: str


@router.post("/financials/verify-password")
def verify_financials_password(
    body: FinancePasswordCheck,
    db: Session = Depends(get_db),
    admin=Depends(require_finance_admin),
):
    """Called once each time the Financials page is opened. Requires both
    is_finance_verified (checked by require_finance_admin above) AND this
    dedicated financial-page password — two layers, so a compromised
    account alone isn't enough to see payout/revenue data."""
    if not settings.FINANCE_ACCESS_PASSWORD or body.password != settings.FINANCE_ACCESS_PASSWORD:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect financial access password")

    admin.last_financial_access_at = datetime.utcnow()
    db.add(admin)
    log_admin_activity(db, admin.id, "financial_access", detail=f"{admin.username or admin.full_name} opened the Financials page")
    db.commit()
    return {"granted": True}


class FinanceGrantAccess(BaseModel):
    admin_creation_secret: str


@router.post("/financials/grant-access")
def grant_finance_access(
    body: FinanceGrantAccess,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    """Self-service bootstrap for the first finance-cleared admin(s) —
    uses the same master secret as admin account creation, so there's no
    lockout requiring direct DB access."""
    if not settings.ADMIN_CREATION_SECRET or body.admin_creation_secret != settings.ADMIN_CREATION_SECRET:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin creation secret")

    admin.is_finance_verified = True
    db.add(admin)
    log_admin_activity(db, admin.id, "finance_access_granted", detail=f"{admin.username or admin.full_name} was granted financial access")
    db.commit()
    return {"is_finance_verified": True}


@router.get("/financials/activity")
def financial_activity_log(db: Session = Depends(get_db), admin=Depends(require_finance_admin), limit: int = 100):
    """The 'Cuto' card — every admin's logged activity across the panel:
    payouts they processed (with amounts), events they revoked, broadcasts
    they sent, financial-page visits, plus an approximate session-time
    estimate per admin per day (first-to-last logged action that day)."""
    rows = (
        db.query(AdminActivityLog, User)
        .join(User, User.id == AdminActivityLog.admin_id)
        .order_by(AdminActivityLog.created_at.desc())
        .limit(limit)
        .all()
    )

    entries = [
        {
            "id": str(log.id),
            "admin_id": str(log.admin_id),
            "admin_name": u.full_name or u.username,
            "action": log.action,
            "detail": log.detail,
            "amount": log.amount,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log, u in rows
    ]

    # Session-time estimate: group by (admin, calendar day), first->last
    from collections import defaultdict
    by_admin_day = defaultdict(list)
    for log, u in rows:
        if not log.created_at:
            continue
        key = (str(log.admin_id), u.full_name or u.username, log.created_at.date().isoformat())
        by_admin_day[key].append(log.created_at)

    sessions = []
    for (admin_id, admin_name, day), times in by_admin_day.items():
        times.sort()
        span_minutes = round((times[-1] - times[0]).total_seconds() / 60, 1)
        sessions.append({
            "admin_id": admin_id,
            "admin_name": admin_name,
            "date": day,
            "actions_count": len(times),
            "estimated_minutes_active": span_minutes,
        })
    sessions.sort(key=lambda s: s["date"], reverse=True)

    payouts_processed = (
        db.query(
            AdminActivityLog.admin_id,
            func.coalesce(func.sum(AdminActivityLog.amount), 0).label("total"),
            func.count(AdminActivityLog.id).label("count"),
        )
        .filter(AdminActivityLog.action == "payout_mark_paid")
        .group_by(AdminActivityLog.admin_id)
        .all()
    )
    payouts_by_admin = {str(r.admin_id): {"total_paid_out": float(r.total), "payouts_processed": int(r.count)} for r in payouts_processed}

    return {
        "entries": entries,
        "sessions": sessions,
        "payouts_by_admin": payouts_by_admin,
    }


@router.get("/events/{event_id}/financials")
def event_financials(event_id: str, db: Session = Depends(get_db), admin=Depends(require_admin)):
    # Sum of paid payments for bookings associated with the event
    total = (
        db.query(func.coalesce(func.sum(Payment.amount), 0.0))
        .join(Booking, Booking.id == Payment.booking_id)
        .filter(Booking.event_id == event_id, Payment.status == "paid")
        .scalar()
    ) or 0.0

    # Payment.amount is the buyer's TOTAL paid, which already includes the
    # 12% markup added at checkout (10% platform + 2% mpesa, see
    # bookings.py). Back that out to get the host's pre-markup ticket
    # value, then split the markup the same way withdrawal_service does —
    # otherwise this would apply another 12% on top of an amount that
    # already has it baked in.
    host_value = float(total) / 1.12
    platform_fee = host_value * 0.10
    mpesa_fees = host_value * 0.02
    net = host_value  # what the host is actually owed — see PLATFORM_CUT_RATE notes in withdrawal_service.py

    return {
        "event_id": event_id,
        "gross_revenue": float(total),
        "platform_fee": platform_fee,
        "mpesa_fees": mpesa_fees,
        "net_payout": net,
    }


@router.get("/events/{event_id}/analytics")
def event_analytics(event_id: str, db: Session = Depends(get_db), admin=Depends(require_admin)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    paid_bookings = db.query(Booking).filter(Booking.event_id == event_id, Booking.status == "booked").all()
    total_tickets_sold = sum(b.quantity or 0 for b in paid_bookings)
    # gross_revenue = what buyers actually paid (host price + 12% markup).
    # host_value = Booking.total_amount, the host's raw pre-markup value —
    # this NEVER has the markup baked in (see Booking model comments), so
    # unlike the old code here, we must NOT divide it by 1.12 again; that
    # was double-applying the same error financial_overview/event_financials
    # guard against. buyer_total_amount is the correct source for the
    # marked-up figure, with a *1.12 fallback only for pre-fix legacy rows
    # that never got buyer_total_amount populated.
    gross_revenue = sum(
        float(b.buyer_total_amount or (float(b.total_amount or 0) * 1.12))
        for b in paid_bookings
    )
    host_value = sum(float(b.total_amount or 0) for b in paid_bookings)

    capacity = event.capacity or 0
    remaining_seats = None if event.capacity is None else max(capacity - total_tickets_sold, 0)

    checked_in = db.query(func.count(Ticket.id)).join(Booking, Booking.id == Ticket.booking_id).filter(Booking.event_id == event_id, Ticket.status == "checked_in").scalar() or 0
    not_arrived = max(total_tickets_sold - checked_in, 0)
    checkin_rate = (checked_in / total_tickets_sold * 100.0) if total_tickets_sold else 0.0

    tier_rows = (
        db.query(
            Booking.ticket_tier,
            func.coalesce(func.sum(Booking.quantity), 0),
            func.coalesce(func.sum(Booking.buyer_total_amount), 0.0),
            func.coalesce(func.sum(Booking.total_amount), 0.0),
        )
        .filter(Booking.event_id == event_id, Booking.status == "booked")
        .group_by(Booking.ticket_tier)
        .all()
    )

    tier_breakdown = [
        {
            "ticket_tier": row[0] or "Standard",
            "sold_quantity": int(row[1]),
            # Prefer the summed buyer_total_amount; fall back to the raw
            # total*1.12 only for legacy rows summed into row[3] (pre-fix
            # bookings never had buyer_total_amount set, so their
            # contribution to row[2] is 0 — approximate those with *1.12).
            "revenue": float(row[2]) if row[2] else float(row[3]) * 1.12,
        }
        for row in tier_rows
    ]

    return {
        "event_id": event_id,
        "title": event.title,
        "host_id": str(event.host_id),
        "capacity": capacity,
        "tickets_sold": total_tickets_sold,
        "remaining_seats": remaining_seats,
        "gross_revenue": float(gross_revenue),
        "platform_fee": host_value * 0.10,
        "mpesa_fees": host_value * 0.02,
        "net_payout": host_value,  # host is paid the pre-markup ticket value — see withdrawal_service.PLATFORM_CUT_RATE notes
        "checkin_count": int(checked_in),
        "not_arrived": int(not_arrived),
        "checkin_rate": checkin_rate,
        "tier_breakdown": tier_breakdown,
    }


from app.schemas.user import HostVerificationResponse
from app.services.auth_service import (
    list_pending_host_verifications,
    approve_or_reject_host_verification
)



@router.get("/hosts/pending", response_model=list[HostVerificationResponse])
def list_pending_hosts(db: Session = Depends(get_db), admin=Depends(require_admin)):
    pending_users = list_pending_host_verifications(db)
    result = []
    for user in pending_users:
        result.append({
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "host_verification_status": user.host_verification_status,
            "verification_requested_at": user.verification_requested_at.isoformat() if user.verification_requested_at else None,
            "verification_approved_at": user.verification_approved_at.isoformat() if user.verification_approved_at else None,
            "government_id": user.government_id,
            "government_id_image_url": getattr(user, "government_id_image_url", None),
            "business_registration": user.business_registration,
            "business_registration_image_url": getattr(user, "business_registration_image_url", None),
            "bank_name": user.bank_name,
            "mpesa_paybill": user.mpesa_paybill,
            "kra_pin": user.kra_pin,
        })
    return result


@router.post("/hosts/{user_id}/verify", response_model=HostVerificationResponse)
def verify_host(
    user_id: str,
    action: HostVerificationActionRequest,
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):
    user = approve_or_reject_host_verification(
        db,
        user_id,
        action.approve,
        action.note
    )
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    log_admin_activity(
        db, admin.id,
        "host_verify",
        detail=f"{'Approved' if action.approve else 'Rejected'} host verification for {user.full_name or user.email}"
               + (f" — {action.note}" if action.note else ""),
    )
    db.commit()

    from app.services.notify_service import notify
    if action.approve:
        notify(db, user.id, "landlord_approved", "You're approved as a landlord 🎉", "You can now add properties from the My listings page.")
    else:
        notify(db, user.id, "landlord_rejected", "Your landlord application wasn't approved", action.note or "Please check your details and ID photo and apply again.")

    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "host_verification_status": user.host_verification_status,
        "verification_requested_at": user.verification_requested_at.isoformat() if user.verification_requested_at else None,
        "verification_approved_at": user.verification_approved_at.isoformat() if user.verification_approved_at else None,
        "government_id": user.government_id,
        "government_id_image_url": getattr(user, "government_id_image_url", None),
        "business_registration": user.business_registration,
        "business_registration_image_url": getattr(user, "business_registration_image_url", None),
        "bank_name": user.bank_name,
        "mpesa_paybill": user.mpesa_paybill,
        "kra_pin": user.kra_pin,
    }

from app.models.user import User  # Ensure User model is imported

@router.get("/hosts/approved", response_model=list[HostVerificationResponse])
def list_approved_hosts(db: Session = Depends(get_db), admin=Depends(require_admin)):
    # Query users whose verification status is explicitly approved
    approved_users = db.query(User).filter(User.host_verification_status == "approved").all()
    result = []
    for user in approved_users:
        result.append({
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "host_verification_status": user.host_verification_status,
            "verification_requested_at": user.verification_requested_at.isoformat() if user.verification_requested_at else None,
            "verification_approved_at": user.verification_approved_at.isoformat() if user.verification_approved_at else None,
            "government_id": user.government_id,
            "government_id_image_url": getattr(user, "government_id_image_url", None),
            "business_registration": user.business_registration,
            "business_registration_image_url": getattr(user, "business_registration_image_url", None),
            "bank_name": user.bank_name,
            "mpesa_paybill": user.mpesa_paybill,
            "kra_pin": user.kra_pin,
        })
    return result


@router.get("/hosts/rejected", response_model=list[HostVerificationResponse])
def list_rejected_hosts(db: Session = Depends(get_db), admin=Depends(require_admin)):
    # Query users whose verification status is explicitly rejected
    rejected_users = db.query(User).filter(User.host_verification_status == "rejected").all()
    result = []
    for user in rejected_users:
        result.append({
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "phone": user.phone,
            "host_verification_status": user.host_verification_status,
            "verification_requested_at": user.verification_requested_at.isoformat() if user.verification_requested_at else None,
            "verification_approved_at": user.verification_approved_at.isoformat() if user.verification_approved_at else None,
            "government_id": user.government_id,
            "government_id_image_url": getattr(user, "government_id_image_url", None),
            "business_registration": user.business_registration,
            "business_registration_image_url": getattr(user, "business_registration_image_url", None),
            "bank_name": user.bank_name,
            "mpesa_paybill": user.mpesa_paybill,
            "kra_pin": user.kra_pin,
        })
    return result


# 1. Note the response_model restriction has been completely removed here
@router.post("/hosts/{user_id}/reverse-status", response_model=HostVerificationResponse)
def reverse_host_status(
    user_id: str,
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User record not found"
        )
    
    # Reset the profile flags back to their default review states
    user.host_verification_status = "pending"
    user.is_host = False
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # 2. Return clean Python None values so they translate perfectly to JSON 'null'
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone if user.phone else None,
        "host_verification_status": user.host_verification_status,
        "verification_requested_at": user.verification_requested_at.isoformat() if user.verification_requested_at else None,
        "verification_approved_at": user.verification_approved_at.isoformat() if user.verification_approved_at else None,
        "government_id": user.government_id if user.government_id else None,
        "government_id_image_url": getattr(user, "government_id_image_url", None),
        "business_registration": user.business_registration if user.business_registration else None,
        "business_registration_image_url": getattr(user, "business_registration_image_url", None),
        "bank_name": user.bank_name if user.bank_name else None,
        "mpesa_paybill": user.mpesa_paybill if user.mpesa_paybill else None,
        "kra_pin": user.kra_pin if user.kra_pin else None,
    }



@router.get("/withdrawals/{withdrawal_id}", response_model=WithdrawalResponse)
def get_withdrawal(withdrawal_id: str, db: Session = Depends(get_db), admin=Depends(require_admin)):
    w = db.query(Withdrawal).filter(Withdrawal.id == withdrawal_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Withdrawal not found")
    return w


# =============================================================================

@router.get("/events/{event_id}/final-list")
def preview_final_list(event_id: str, db: Session = Depends(get_db), admin=Depends(require_admin)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    confirmed = (
        db.query(Booking)
        .filter(Booking.event_id == event_id, Booking.confirmation_status == "confirmed")
        .all()
    )
    still_pending = (
        db.query(Booking)
        .filter(
            Booking.event_id == event_id,
            Booking.status == "booked",
            Booking.confirmation_status.in_(["not_due", "awaiting_response"]),
        )
        .count()
    )

    return {
        "event_id": event_id,
        "final_list_locked_at": event.final_list_locked_at.isoformat() if getattr(event, "final_list_locked_at", None) else None,
        "confirmed_count": sum(b.quantity or 0 for b in confirmed),
        "confirmed_amount": sum(float(b.total_amount or 0) for b in confirmed),
        "still_pending_response": still_pending,
        "gate_unlocked": bool(getattr(event, "gate_unlocked", False)),
        "tickets_sent_at": event.tickets_sent_at.isoformat() if getattr(event, "tickets_sent_at", None) else None,
    }


# The manual "send tickets now" override that used to live here has been
# removed on purpose. Opening the Live Gate at T-1hr is now fully
# automatic — both the scheduled sweep (attendance_service.
# send_t1_final_list, every 5 min) and an on-demand check that runs
# whenever the event is viewed (see stream.py's _map_feed_item_to_reel ->
# freeze_and_open_gate_for_event) handle it. There is intentionally no
# admin action anywhere in this flow anymore.


# NOTE: the real, working versions of "active support threads" and
# "broadcast" live in admin_extra.py (GET /admin/support-tickets/active,
# GET /admin/support-tickets/{host_id}/thread, POST
# /admin/support-tickets/reply, POST /admin/broadcast) and are what the
# admin frontend actually calls. This file used to also define a
# GET /admin/support-tickets/active route returning hardcoded mock data —
# since both routers mount at the same prefix and this one loaded first,
# it silently shadowed the real endpoint on every request, so the Support
# Desk always showed one fake "Samson Muiruri" ticket no matter what was
# really in the database. Removed, along with the matching no-op
# /admin/notifications/broadcast stub that nothing in the frontend calls.


# =============================================================================
# Refunds archive — the admin pastes the M-Pesa confirmation message a buyer
# sent when asking for a refund; we log it (with best-effort parsed name/
# phone/code/amount) so any admin can later search by BASH username or name
# to see whether — and exactly when — that refund message came in.
# =============================================================================
from app.services import refund_service


class RefundArchiveCreate(BaseModel):
    raw_message: str
    matched_username: Optional[str] = None


def _serialize_refund_entry(e) -> dict:
    return {
        "id": str(e.id),
        "raw_message": e.raw_message,
        "payer_name": e.payer_name,
        "phone": e.phone,
        "mpesa_code": e.mpesa_code,
        "amount": e.amount,
        "matched_username": e.matched_username,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


@router.post("/refunds/archive")
def archive_refund(
    data: RefundArchiveCreate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    if not data.raw_message or not data.raw_message.strip():
        raise HTTPException(status_code=400, detail="Paste the M-Pesa message first")
    entry = refund_service.archive_refund_message(
        db, data.raw_message.strip(), admin.id, matched_username=data.matched_username
    )
    log_admin_activity(db, admin.id, "refund_archived", detail=f"Archived refund message ({entry.payer_name or 'unnamed'})")
    db.commit()
    return _serialize_refund_entry(entry)


@router.get("/refunds/search")
def search_refunds(
    q: str = "",
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    rows = refund_service.search_refund_archive(db, q)
    return [_serialize_refund_entry(e) for e in rows]