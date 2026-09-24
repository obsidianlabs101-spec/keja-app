# app/api/v1/keja_admin.py
"""Keja-specific admin endpoints: listing moderation, force-booking, ID photo
viewing and a small overview for the dashboard badges."""
import base64
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.contact_unlock import ContactUnlock
from app.models.landlord_id_document import LandlordIdDocument
from app.models.property import Property
from app.models.user import User
from app.services.notify_service import notify

router = APIRouter(prefix="/admin/keja", tags=["admin-keja"])


def _prop_row(p: Property) -> dict:
    ll = p.landlord
    return {
        "id": str(p.id),
        "title": p.title,
        "price": p.price,
        "property_type": p.property_type,
        "county": p.county,
        "area": p.area,
        "main_image_url": p.main_image_url,
        "image_count": len(p.images or []),
        "is_available": bool(p.is_available),
        "is_booked": bool(p.is_booked),
        "is_removed": bool(p.is_removed),
        "review_status": p.review_status or "unreviewed",
        "review_note": p.review_note,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "landlord_id": str(p.landlord_id),
        "landlord_name": (ll.full_name or ll.username or ll.email) if ll else None,
        "landlord_phone": ll.phone if ll else None,
    }


@router.get("/overview")
def overview(db: Session = Depends(get_db), admin=Depends(require_admin)):
    from app.services.auth_service import list_pending_host_verifications
    return {
        "pending_landlords": len(list_pending_host_verifications(db)),
        "unreviewed_properties": db.query(Property).filter(
            Property.is_removed == False, (Property.review_status == "unreviewed") | (Property.review_status == None)  # noqa: E711,E712
        ).count(),
        "pending_payments": db.query(ContactUnlock).filter(ContactUnlock.status == "awaiting_admin_match").count(),
        "total_properties": db.query(Property).filter(Property.is_removed == False).count(),  # noqa: E712
        "total_users": db.query(User).count(),
    }


@router.get("/properties")
def list_properties(
    review: str = "all",  # unreviewed | rejected | approved | all
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    q = db.query(Property).options(joinedload(Property.images)).filter(Property.is_removed == False)  # noqa: E712
    if review == "unreviewed":
        q = q.filter((Property.review_status == "unreviewed") | (Property.review_status == None))  # noqa: E711
    elif review in ("rejected", "approved"):
        q = q.filter(Property.review_status == review)
    rows = q.order_by(Property.created_at.desc()).limit(300).all()
    return [_prop_row(p) for p in rows]


class ReviewRequest(BaseModel):
    action: str  # approve | reject
    note: Optional[str] = None


@router.post("/properties/{property_id}/review")
def review_property(property_id: UUID, body: ReviewRequest, db: Session = Depends(get_db), admin=Depends(require_admin)):
    p = db.query(Property).filter(Property.id == property_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Property not found")
    if body.action == "approve":
        p.review_status, p.review_note = "approved", None
        p.is_available = not p.is_booked
        db.add(p)
        db.commit()
        notify(db, p.landlord_id, "listing_approved", f"Your listing was approved: {p.title}", "It is live on Keja.", {"property_id": str(p.id)})
    elif body.action == "reject":
        p.review_status, p.review_note = "rejected", (body.note or "").strip() or "It didn't meet our listing guidelines."
        p.is_available = False
        db.add(p)
        db.commit()
        notify(db, p.landlord_id, "listing_rejected", f"Your listing was rejected: {p.title}", p.review_note, {"property_id": str(p.id)})
    else:
        raise HTTPException(status_code=400, detail="action must be approve or reject")
    db.refresh(p)
    return _prop_row(p)


class ForceBookedRequest(BaseModel):
    booked: bool = True


@router.post("/properties/{property_id}/force-booked")
def force_booked(property_id: UUID, body: ForceBookedRequest, db: Session = Depends(get_db), admin=Depends(require_admin)):
    """Admin overrides a listing as booked (or reopens it)."""
    p = db.query(Property).filter(Property.id == property_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Property not found")
    p.is_booked = body.booked
    p.is_available = (not body.booked) and p.review_status != "rejected"
    db.add(p)
    db.commit()
    db.refresh(p)
    if body.booked:
        notify(db, p.landlord_id, "listing_booked", f"Marked as booked: {p.title}", "An admin marked this listing as booked, so it no longer shows to renters.", {"property_id": str(p.id)})
    return _prop_row(p)


@router.get("/landlords/{user_id}/id-image")
def landlord_id_image(user_id: UUID, db: Session = Depends(get_db), admin=Depends(require_admin)):
    doc = db.query(LandlordIdDocument).filter(LandlordIdDocument.user_id == user_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="No ID photo on file")
    return {"content_type": doc.content_type, "data_base64": base64.b64encode(doc.data).decode()}
