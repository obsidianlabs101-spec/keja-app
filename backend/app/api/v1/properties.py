# app/api/v1/properties.py
import io
import uuid
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_user_optional, require_landlord
from app.core.limiter import limiter
from app.models.host_comment import HostComment
from app.models.property import Property
from app.models.property_alert import PropertyAlert
from app.models.user import User
from app.schemas.host_comment import HostCommentCreate, HostCommentRead
from app.schemas.property import (
    LandlordPropertiesResponse,
    PropertyAlertRead,
    PropertyAlertRequest,
    PropertyCreate,
    PropertyFilters,
    PropertyRead,
    PropertyUpdate,
)
from app.services import property_service

router = APIRouter(prefix="/properties", tags=["properties"])


def _own_or_404(db: Session, property_id: UUID, landlord_id: UUID) -> Property:
    prop = property_service.get_property(db, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if prop.landlord_id != landlord_id:
        raise HTTPException(status_code=403, detail="You don't own this listing")
    return prop


@router.get("/", response_model=List[PropertyRead])
def search(
    county: Optional[str] = None,
    area: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    bedrooms: Optional[int] = None,
    property_type: Optional[str] = None,
    listing_type: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    filters = PropertyFilters(
        county=county, area=area, min_price=min_price, max_price=max_price,
        bedrooms=bedrooms, property_type=property_type, listing_type=listing_type, q=q,
    )
    return property_service.search_properties(db, filters, limit=limit, offset=offset)


@router.get("/category-counts")
def category_counts(listing_type: Optional[str] = None, db: Session = Depends(get_db)):
    return property_service.category_counts(db, listing_type)


@router.get("/discover", response_model=List[PropertyRead])
def discover(
    county: Optional[str] = None,
    area: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    bedrooms: Optional[int] = None,
    property_type: Optional[str] = None,
    listing_type: Optional[str] = None,
    limit: int = Query(20, le=50),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = PropertyFilters(
        county=county, area=area, min_price=min_price, max_price=max_price,
        bedrooms=bedrooms, property_type=property_type, listing_type=listing_type,
    )
    return property_service.discover_queue(db, current_user.id, filters, limit=limit)


@router.get("/mine", response_model=List[PropertyRead])
def my_listings(current_user=Depends(require_landlord), db: Session = Depends(get_db)):
    return property_service.list_landlord_properties(db, current_user.id)


@router.get("/mine/stats")
def my_stats(current_user=Depends(require_landlord), db: Session = Depends(get_db)):
    return property_service.landlord_stats(db, current_user.id)


@router.get("/landlord/{landlord_id}", response_model=LandlordPropertiesResponse)
def public_landlord_properties(landlord_id: UUID, db: Session = Depends(get_db)):
    from app.models.user import User
    landlord = db.query(User).filter(User.id == landlord_id).first()
    if not landlord:
        raise HTTPException(status_code=404, detail="Landlord not found")
    listings = property_service.list_public_landlord_properties(db, landlord_id)
    total = len(property_service.list_landlord_properties(db, landlord_id))
    return {"landlord": landlord, "properties": listings, "property_count": total}


@router.get("/interested", response_model=List[PropertyRead])
def interested(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return property_service.list_interested(db, current_user.id)


@router.post("/create", response_model=PropertyRead)
def create(payload: PropertyCreate, current_user=Depends(require_landlord), db: Session = Depends(get_db)):
    return property_service.create_property(db, current_user.id, payload)


@router.get("/{property_id}", response_model=PropertyRead)
def get_one(
    property_id: UUID,
    current_user=Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    prop = property_service.get_property(db, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    property_service.increment_view_count(db, prop)
    return prop


@router.patch("/{property_id}", response_model=PropertyRead)
def update(
    property_id: UUID,
    payload: PropertyUpdate,
    current_user=Depends(require_landlord),
    db: Session = Depends(get_db),
):
    prop = _own_or_404(db, property_id, current_user.id)
    return property_service.update_property(db, prop, payload)


@router.delete("/{property_id}")
def delete(property_id: UUID, current_user=Depends(require_landlord), db: Session = Depends(get_db)):
    prop = _own_or_404(db, property_id, current_user.id)
    property_service.soft_delete_property(db, prop)
    return {"detail": "Listing removed"}


@router.post("/{property_id}/images")
async def upload_image(
    property_id: UUID,
    file: UploadFile = File(...),
    is_main: bool = False,
    current_user=Depends(require_landlord),
    db: Session = Depends(get_db),
):
    prop = _own_or_404(db, property_id, current_user.id)

    max_bytes = 15 * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status_code=400, detail="Image too large (15MB max)")
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    # SECURITY: the upload's declared filename/extension is attacker-controlled
    # and was previously trusted outright — a non-image file renamed to
    # "x.jpg" would have been stored and served back as image/jpeg. Verify
    # the actual bytes decode as a real image before it ever reaches storage,
    # the same check already used for ad creatives and ID photos.
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        fmt = (img.format or "").upper()
        img.verify()
    except Exception:
        raise HTTPException(status_code=400, detail="That file is not a valid image")
    ext_by_format = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
    content_type_by_format = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
    if fmt not in ext_by_format:
        raise HTTPException(status_code=400, detail="Only JPG, PNG or WEBP images are allowed")
    ext = ext_by_format[fmt]
    content_type = content_type_by_format[fmt]
    filename = f"{uuid.uuid4().hex}{ext}"

    # Render's free web-service disk is EPHEMERAL — anything saved to
    # local disk vanishes on the next deploy or restart. Property photos
    # are uploaded to Supabase Storage instead (same project as the
    # database), which is the actual persistent store.
    url = property_service.upload_to_supabase_storage(filename, data, content_type)
    image = property_service.add_image(db, prop, url, is_main=is_main)
    return {"id": str(image.id), "url": image.url, "is_main": image.is_main}


@router.post("/{property_id}/swipe")
def swipe(
    property_id: UUID,
    direction: str = Query(..., pattern="^(left|right)$"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prop = property_service.get_property(db, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    property_service.record_swipe(db, current_user.id, property_id, direction)
    return {"detail": "recorded", "direction": direction}


@router.delete("/{property_id}/interested")
def unsave(property_id: UUID, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    property_service.remove_interested(db, current_user.id, property_id)
    return {"detail": "removed"}


@router.get("/alerts/me", response_model=Optional[PropertyAlertRead])
def get_my_alert(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """The renter's saved alert, if any — see the exit-intent dialog on Home."""
    return db.query(PropertyAlert).filter(PropertyAlert.user_id == current_user.id).first()


@router.put("/alerts/me", response_model=PropertyAlertRead)
@limiter.limit("10/minute")
def set_my_alert(
    request: Request,
    payload: PropertyAlertRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Replaces the renter's alert wholesale (there's only ever one)."""
    alert = db.query(PropertyAlert).filter(PropertyAlert.user_id == current_user.id).first()
    if alert is None:
        alert = PropertyAlert(user_id=current_user.id)
        db.add(alert)
    for field, value in payload.model_dump().items():
        setattr(alert, field, value)
    db.commit()
    db.refresh(alert)
    return alert


@router.delete("/alerts/me")
def clear_my_alert(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(PropertyAlert).filter(PropertyAlert.user_id == current_user.id).delete()
    db.commit()
    return {"detail": "cleared"}


@router.get("/landlord/{landlord_id}/comments", response_model=List[HostCommentRead])
def list_host_comments(
    landlord_id: UUID,
    current_user=Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Public: what renters say about this landlord."""
    rows = (
        db.query(HostComment)
        .filter(HostComment.landlord_id == landlord_id)
        .order_by(HostComment.created_at.desc())
        .limit(100)
        .all()
    )
    out = []
    for c in rows:
        author = db.query(User).filter(User.id == c.user_id).first()
        out.append(
            HostCommentRead(
                id=c.id,
                body=c.body,
                created_at=c.created_at,
                author_name=(author.full_name or author.username or "A renter") if author else "A renter",
                author_avatar=author.profile_picture if author else None,
                is_mine=bool(current_user and current_user.id == c.user_id),
            )
        )
    return out


@router.put("/landlord/{landlord_id}/comments/me", response_model=HostCommentRead)
@limiter.limit("5/minute")
def set_my_host_comment(
    request: Request,
    landlord_id: UUID,
    payload: HostCommentCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Posting again replaces your previous comment on this landlord — one
    comment per renter per host, same pattern as the property alert."""
    if landlord_id == current_user.id:
        raise HTTPException(status_code=400, detail="You can't comment on your own profile")
    comment = (
        db.query(HostComment)
        .filter(HostComment.landlord_id == landlord_id, HostComment.user_id == current_user.id)
        .first()
    )
    if comment is None:
        comment = HostComment(landlord_id=landlord_id, user_id=current_user.id, body=payload.body)
        db.add(comment)
    else:
        comment.body = payload.body
    db.commit()
    db.refresh(comment)
    return HostCommentRead(
        id=comment.id,
        body=comment.body,
        created_at=comment.created_at,
        author_name=current_user.full_name or current_user.username or "You",
        author_avatar=current_user.profile_picture,
        is_mine=True,
    )


@router.delete("/landlord/{landlord_id}/comments/me")
def delete_my_host_comment(landlord_id: UUID, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(HostComment).filter(
        HostComment.landlord_id == landlord_id, HostComment.user_id == current_user.id
    ).delete()
    db.commit()
    return {"detail": "deleted"}
