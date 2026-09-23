# app/api/v1/ads.py
import io
import uuid
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.services import ad_service

# Public read (no auth): clients ask "what's the active ad for Home?".
public_router = APIRouter(prefix="/ads", tags=["ads"])
# Admin-only management, same require_admin dependency as /admin/platform-stats.
admin_router = APIRouter(prefix="/admin/ads", tags=["admin-ads"])

MAX_BYTES = 5 * 1024 * 1024
_TYPES = {"JPEG": (".jpg", "image/jpeg"), "PNG": (".png", "image/png"), "WEBP": (".webp", "image/webp")}


def _bad(msg: str):
    raise HTTPException(status_code=400, detail=msg)


@public_router.get("/{placement}")
def get_active_ad(placement: str, db: Session = Depends(get_db)):
    try:
        placement = ad_service.validate_placement(placement)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    ad = ad_service.active_ad(db, placement)
    # Always 200; {"ad": null} means "show the fallback placeholder".
    return {"ad": ad_service.serialize(ad) if ad else None}


@admin_router.get("")
def admin_list_ads(db: Session = Depends(get_db), admin=Depends(require_admin)):
    return {"ads": [ad_service.serialize(a) for a in ad_service.list_ads(db)]}


@admin_router.post("")
async def admin_create_ad(
    placement: str = Form(...),
    link_url: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    """Uploads the image and makes it THE active ad for that placement
    (any previously active ad for the placement is deactivated)."""
    try:
        placement = ad_service.validate_placement(placement)
        link = ad_service.clean_link_url(link_url)
    except ValueError as e:
        _bad(str(e))

    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        _bad("Image too large (5MB max)")
    if not data:
        _bad("Empty file")

    # Validate real content, not the filename (same reasoning as
    # services/media_validation.py). Pillow is already a dependency.
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        fmt = (img.format or "").upper()
        img.verify()
    except Exception:
        _bad("File is not a valid image")
    if fmt not in _TYPES:
        _bad("Only JPG, PNG or WEBP images are allowed")
    ext, content_type = _TYPES[fmt]

    try:
        url = ad_service.upload_ad_image(f"{uuid.uuid4().hex}{ext}", data, content_type)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    ad = ad_service.create_ad(db, placement, url, link, owner_id=admin.id, activate=True)
    return ad_service.serialize(ad)


class AdUpdate(BaseModel):
    link_url: Optional[str] = None
    is_active: Optional[bool] = None


@admin_router.patch("/{ad_id}")
def admin_update_ad(ad_id: UUID, body: AdUpdate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    ad = ad_service.get_ad(db, ad_id)
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    link_set = "link_url" in body.model_fields_set
    try:
        link = ad_service.clean_link_url(body.link_url) if link_set else None
    except ValueError as e:
        _bad(str(e))
    ad = ad_service.update_ad(db, ad, link_set, link, body.is_active)
    return ad_service.serialize(ad)


@admin_router.delete("/{ad_id}")
def admin_delete_ad(ad_id: UUID, db: Session = Depends(get_db), admin=Depends(require_admin)):
    """Soft-remove: deactivates so clients fall back to the placeholder."""
    ad = ad_service.get_ad(db, ad_id)
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    ad_service.update_ad(db, ad, False, None, False)
    return {"detail": "Ad deactivated"}
