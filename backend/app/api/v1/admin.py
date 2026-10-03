from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session


from app.core.database import get_db
from app.core.dependencies import require_admin
from app.schemas.admin import (
    HostVerificationActionRequest
)
from app.schemas.user import HostVerificationResponse
from app.services.admin_service import (
    log_admin_activity,
)
from app.services.auth_service import (
    list_pending_host_verifications,
    approve_or_reject_host_verification,
)
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)


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


# =============================================================================


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


