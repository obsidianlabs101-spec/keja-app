# app/services/ad_service.py
import re
from typing import List, Optional
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.ad_slot import AdSlot

PLACEMENTS = ("home", "interested")
AD_BUCKET = "ad-images"


def validate_placement(placement: str) -> str:
    p = (placement or "").strip().lower()
    if p not in PLACEMENTS:
        raise ValueError(f"placement must be one of: {', '.join(PLACEMENTS)}")
    return p


def clean_link_url(link_url: Optional[str]) -> Optional[str]:
    """Accepts a full URL OR a bare site name like "bash.co.ke" (https://
    is added). Any other scheme (javascript:, data:, ftp: ...) is rejected —
    a javascript:/data: link in an ad would be an XSS hole the moment a
    client renders it as an href."""
    link = (link_url or "").strip()
    if not link:
        return None
    if len(link) > 2000 or re.search(r"\s", link):
        raise ValueError("Enter a valid website, e.g. bash.co.ke")
    if re.match(r"^https?://", link, re.I):
        candidate = link
    elif re.match(r"^[a-z][a-z0-9+.\-]*:(?!\d)", link, re.I) or "://" in link:
        raise ValueError("Only website links are allowed, e.g. bash.co.ke")
    else:
        candidate = "https://" + link.lstrip("/")
    parsed = urlparse(candidate)
    host = parsed.hostname or ""
    if not re.match(r"^([a-z0-9]([a-z0-9\-]*[a-z0-9])?\.)+[a-z]{2,}$", host, re.I):
        raise ValueError("Enter a valid website, e.g. bash.co.ke")
    return candidate


def upload_ad_image(filename: str, data: bytes, content_type: str) -> str:
    """Same pattern as property_service.upload_to_supabase_storage (never
    local disk — Render's disk is ephemeral) but into the separate
    `ad-images` bucket. Prefers the service-role key (bypasses RLS, backend
    only) and falls back to the anon key so it still works where only the
    anon key is configured."""
    import requests
    from app.core.config import settings

    key = getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "") or settings.SUPABASE_ANON_KEY
    if not key:
        raise RuntimeError("No Supabase key configured — ad uploads are disabled until one is set")

    base = settings.SUPABASE_URL
    resp = requests.post(
        f"{base}/storage/v1/object/{AD_BUCKET}/{filename}",
        data=data,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": content_type,
            "x-upsert": "true",
        },
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Ad image upload failed ({resp.status_code}): {resp.text[:300]}")
    return f"{base}/storage/v1/object/public/{AD_BUCKET}/{filename}"


def _deactivate_others(db: Session, placement: str, keep_id=None) -> None:
    q = db.query(AdSlot).filter(AdSlot.placement == placement, AdSlot.is_active == True)  # noqa: E712
    if keep_id is not None:
        q = q.filter(AdSlot.id != keep_id)
    for row in q.all():
        row.is_active = False


def create_ad(db: Session, placement: str, image_url: str, link_url: Optional[str], owner_id, activate: bool = True) -> AdSlot:
    ad = AdSlot(placement=placement, image_url=image_url, link_url=link_url, owner_id=owner_id, is_active=False)
    db.add(ad)
    db.flush()
    if activate:
        _deactivate_others(db, placement, keep_id=ad.id)
        ad.is_active = True
    db.commit()
    db.refresh(ad)
    return ad


def get_ad(db: Session, ad_id: UUID) -> Optional[AdSlot]:
    return db.query(AdSlot).filter(AdSlot.id == ad_id).first()


def update_ad(db: Session, ad: AdSlot, link_url_set: bool, link_url: Optional[str], is_active: Optional[bool]) -> AdSlot:
    if link_url_set:
        ad.link_url = link_url
    if is_active is not None:
        if is_active:
            _deactivate_others(db, ad.placement, keep_id=ad.id)
        ad.is_active = is_active
    db.commit()
    db.refresh(ad)
    return ad


def active_ad(db: Session, placement: str) -> Optional[AdSlot]:
    return (
        db.query(AdSlot)
        .filter(AdSlot.placement == placement, AdSlot.is_active == True)  # noqa: E712
        .order_by(AdSlot.created_at.desc())
        .first()
    )


def list_ads(db: Session) -> List[AdSlot]:
    return db.query(AdSlot).order_by(AdSlot.created_at.desc()).limit(200).all()


def serialize(ad: AdSlot) -> dict:
    return {
        "id": str(ad.id),
        "placement": ad.placement,
        "image_url": ad.image_url,
        "link_url": ad.link_url,
        "is_active": bool(ad.is_active),
        "created_at": ad.created_at.isoformat() if ad.created_at else None,
    }
