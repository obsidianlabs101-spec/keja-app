# app/api/v1/contact_unlock.py
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.contact_unlock import ContactUnlock, CONTACT_UNLOCK_FEE_KES
from app.schemas.contact_unlock import AdminBatchMatchRequest, BuyerClaimRequest, ContactUnlockStatus
from app.services import contact_unlock_service, property_service
from app.services.notify_service import notify, notify_contact_ready
from pydantic import BaseModel

router = APIRouter(prefix="/contact-unlock", tags=["contact-unlock"])


def _to_status(unlock: ContactUnlock, prop=None, current_user=None) -> ContactUnlockStatus:
    phone = whatsapp = None
    if unlock.status == "unlocked" and prop and prop.landlord:
        phone = prop.landlord.phone
        whatsapp = prop.landlord.phone
    return ContactUnlockStatus(
        property_id=unlock.property_id,
        status=unlock.status,
        amount=unlock.amount,
        phone=phone,
        whatsapp=whatsapp,
        unlocked_at=unlock.unlocked_at,
        free_credits_available=int(getattr(current_user, "free_contact_credits", 0) or 0) if current_user else 0,
    )


@router.get("/{property_id}", response_model=ContactUnlockStatus)
def get_status(property_id: UUID, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    prop = property_service.get_property(db, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    unlock = contact_unlock_service.get_or_create_unlock(db, current_user.id, property_id)
    return _to_status(unlock, prop, current_user)


@router.post("/{property_id}/use-free-credit", response_model=ContactUnlockStatus)
def use_free_credit(property_id: UUID, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    prop = property_service.get_property(db, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    unlock = contact_unlock_service.get_or_create_unlock(db, current_user.id, property_id)
    try:
        unlock = contact_unlock_service.use_free_credit(db, unlock, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.refresh(current_user)
    return _to_status(unlock, prop, current_user)


@router.post("/{property_id}/claim", response_model=ContactUnlockStatus)
def submit_claim(
    property_id: UUID,
    payload: BuyerClaimRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prop = property_service.get_property(db, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    unlock = contact_unlock_service.get_or_create_unlock(db, current_user.id, property_id)
    if unlock.status == "unlocked":
        return _to_status(unlock, prop, current_user)
    unlock = contact_unlock_service.submit_buyer_claim(db, unlock, payload.raw_text)
    if unlock.status == "unlocked":
        notify_contact_ready(db, unlock, prop)
    else:
        notify(
            db, current_user.id, "payment_received", f"We got your payment message for {prop.title}",
            "An admin is checking it now. The landlord's number will arrive here in Alerts as soon as it's verified.",
            {"property_id": str(prop.id)},
        )
    return _to_status(unlock, prop, current_user)


@router.post("/{property_id}/request-referral")
def request_referral_unlock(property_id: UUID, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """The renter chose "share & unlock free" for this property. We remember
    that; the moment a friend signs up through their link (auth_service),
    the landlord's number is sent to their Alerts automatically."""
    prop = property_service.get_property(db, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    unlock = contact_unlock_service.get_or_create_unlock(db, current_user.id, property_id)
    if unlock.status == "unlocked":
        return _to_status(unlock, prop, current_user)
    if (current_user.free_contact_credits or 0) > 0:
        # Already earned: spend it right now.
        unlock = contact_unlock_service.use_free_credit(db, unlock, current_user)
        notify_contact_ready(db, unlock, prop)
        db.refresh(current_user)
        return _to_status(unlock, prop, current_user)
    if unlock.status == "pending":
        unlock.status = "awaiting_referral"
        db.add(unlock)
        db.commit()
        db.refresh(unlock)
    return _to_status(unlock, prop, current_user)


@router.get("/admin/pending")
def list_pending(current_admin=Depends(require_admin), db: Session = Depends(get_db)):
    from app.models.user import User
    rows = (
        db.query(ContactUnlock)
        .filter(ContactUnlock.status == "awaiting_admin_match")
        .order_by(ContactUnlock.buyer_claimed_at.asc())
        .all()
    )
    out = []
    for r in rows:
        buyer = db.query(User).filter(User.id == r.user_id).first()
        prop = r.property
        landlord = prop.landlord if prop else None
        out.append({
            "id": str(r.id),
            "user_id": str(r.user_id),
            "property_id": str(r.property_id),
            "amount": r.amount,
            "buyer_claimed_code": r.buyer_claimed_code,
            "buyer_claimed_raw_message": r.buyer_claimed_raw_message,
            "buyer_claimed_at": r.buyer_claimed_at,
            "buyer_name": (buyer.full_name or buyer.username or buyer.email) if buyer else None,
            "buyer_phone": buyer.phone if buyer else None,
            "property_title": prop.title if prop else None,
            "landlord_name": landlord.full_name if landlord else None,
            "landlord_phone": landlord.phone if landlord else None,
        })
    return out


class RejectPaymentRequest(BaseModel):
    reason: Optional[str] = None


@router.post("/admin/{unlock_id}/show")
def admin_show_contact(unlock_id: UUID, current_admin=Depends(require_admin), db: Session = Depends(get_db)):
    """Admin reviewed the pasted M-Pesa message and clicked Show: unlock the
    contact and send the landlord's number to the renter's Alerts."""
    unlock = db.query(ContactUnlock).filter(ContactUnlock.id == unlock_id).first()
    if not unlock:
        raise HTTPException(status_code=404, detail="Request not found")
    if unlock.status != "unlocked":
        contact_unlock_service._finalize_unlock(db, unlock, unlock.buyer_claimed_code or "ADMIN_APPROVED")
    notify_contact_ready(db, unlock)
    return {"detail": "Number sent to the user's Alerts", "id": str(unlock.id)}


@router.post("/admin/{unlock_id}/reject")
def admin_reject_claim(unlock_id: UUID, payload: RejectPaymentRequest, current_admin=Depends(require_admin), db: Session = Depends(get_db)):
    unlock = db.query(ContactUnlock).filter(ContactUnlock.id == unlock_id).first()
    if not unlock:
        raise HTTPException(status_code=404, detail="Request not found")
    if unlock.status == "unlocked":
        raise HTTPException(status_code=400, detail="Already unlocked")
    unlock.status = "pending"
    db.add(unlock)
    db.commit()
    title = unlock.property.title if unlock.property else "the property"
    notify(
        db, unlock.user_id, "payment_rejected", f"We couldn't verify your payment for {title}",
        (payload.reason or "The message didn't match a KES 50 payment to Obsidian Labs.") + " You can paste the message again.",
        {"property_id": str(unlock.property_id)},
    )
    return {"detail": "Rejected and user notified"}


@router.post("/admin/batch-match")
def batch_match(
    payload: AdminBatchMatchRequest,
    current_admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    result = contact_unlock_service.batch_match_admin_codes(db, payload.raw_text, current_admin.id)
    return {
        "matched_count": len(result["matched"]),
        "pooled_count": len(result["pooled"]),
    }
