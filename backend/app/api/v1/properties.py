# app/api/v1/properties.py
import os
import uuid
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_user_optional, require_landlord
from app.models.property import Property
from app.schemas.property import LandlordPropertiesResponse, PropertyCreate, PropertyFilters, PropertyRead, PropertyUpdate
from app.services import property_service

router = APIRouter(prefix="/properties", tags=["properties"])

STATIC_DIR = "static"
PROPERTIES_DIR = os.path.join(STATIC_DIR, "properties")


def _ensure_dir():
    os.makedirs(PROPERTIES_DIR, exist_ok=True)


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
    q: Optional[str] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    filters = PropertyFilters(
        county=county, area=area, min_price=min_price, max_price=max_price,
        bedrooms=bedrooms, property_type=property_type, q=q,
    )
    return property_service.search_properties(db, filters, limit=limit, offset=offset)


@router.get("/discover", response_model=List[PropertyRead])
def discover(
    county: Optional[str] = None,
    area: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    bedrooms: Optional[int] = None,
    property_type: Optional[str] = None,
    limit: int = Query(20, le=50),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = PropertyFilters(
        county=county, area=area, min_price=min_price, max_price=max_price,
        bedrooms=bedrooms, property_type=property_type,
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
    return {"landlord": landlord, "properties": listings}


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
    _ensure_dir()

    _, ext = os.path.splitext(file.filename or "")
    ext = ext.lower() if ext.lower() in {".png", ".jpg", ".jpeg", ".webp"} else ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    local_path = os.path.join(PROPERTIES_DIR, filename)

    max_bytes = 15 * 1024 * 1024
    total = 0
    with open(local_path, "wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                out.close()
                os.remove(local_path)
                raise HTTPException(status_code=400, detail="Image too large (15MB max)")
            out.write(chunk)

    url = f"static/properties/{filename}"
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
