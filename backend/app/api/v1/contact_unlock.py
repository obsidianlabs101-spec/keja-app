# app/api/v1/contact_unlock.py
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.contact_unlock import ContactUnlock, CONTACT_UNLOCK_FEE_KES
from app.schemas.contact_unlock import AdminBatchMatchRequest, BuyerClaimRequest, ContactUnlockStatus
from app.services import contact_unlock_service, property_service

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
    return _to_status(unlock, prop, current_user)


@router.get("/admin/pending")
def list_pending(current_admin=Depends(require_admin), db: Session = Depends(get_db)):
    rows = (
        db.query(ContactUnlock)
        .filter(ContactUnlock.status == "awaiting_admin_match")
        .order_by(ContactUnlock.buyer_claimed_at.asc())
        .all()
    )
    return [
        {
            "id": str(r.id),
            "user_id": str(r.user_id),
            "property_id": str(r.property_id),
            "amount": r.amount,
            "buyer_claimed_code": r.buyer_claimed_code,
            "buyer_claimed_raw_message": r.buyer_claimed_raw_message,
            "buyer_claimed_at": r.buyer_claimed_at,
        }
        for r in rows
    ]


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
