# app/services/property_service.py
from typing import List, Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models.property import Property
from app.models.property_image import PropertyImage
from app.models.interested_property import InterestedProperty, PropertySwipe
from app.schemas.property import PropertyCreate, PropertyFilters, PropertyUpdate


def _base_query(db: Session):
    return (
        db.query(Property)
        .options(joinedload(Property.images))
        .filter(Property.is_removed == False)  # noqa: E712
    )


def create_property(db: Session, landlord_id: UUID, data: PropertyCreate) -> Property:
    prop = Property(landlord_id=landlord_id, **data.model_dump())
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return prop


def update_property(db: Session, prop: Property, data: PropertyUpdate) -> Property:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(prop, field, value)
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return prop


def soft_delete_property(db: Session, prop: Property) -> None:
    prop.is_removed = True
    prop.is_available = False
    db.add(prop)
    db.commit()


def get_property(db: Session, property_id: UUID) -> Optional[Property]:
    return _base_query(db).filter(Property.id == property_id).first()


def list_landlord_properties(db: Session, landlord_id: UUID) -> List[Property]:
    return (
        _base_query(db)
        .filter(Property.landlord_id == landlord_id)
        .order_by(Property.created_at.desc())
        .all()
    )


def list_public_landlord_properties(db: Session, landlord_id: UUID) -> List[Property]:
    """Same as list_landlord_properties but for the PUBLIC "view this
    landlord's other listings" page — only ever shows properties that
    are actually available, unlike the landlord's own dashboard which
    shows everything including booked/unavailable ones."""
    return (
        _base_query(db)
        .filter(Property.landlord_id == landlord_id)
        .filter(Property.is_available == True)  # noqa: E712
        .order_by(Property.created_at.desc())
        .all()
    )


def upload_to_supabase_storage(filename: str, data: bytes, content_type: str) -> str:
    """Uploads a property photo to Supabase Storage and returns its
    public URL. Deliberately NOT saved to local disk — Render's free
    web-service filesystem is ephemeral and is wiped on every deploy or
    restart, which is exactly why previously-uploaded photos stopped
    rendering after the next deploy."""
    import requests
    from app.core.config import settings

    if not settings.SUPABASE_ANON_KEY:
        raise RuntimeError("SUPABASE_ANON_KEY is not configured — image uploads are disabled until it is set")

    bucket = "property-images"
    upload_url = f"{settings.SUPABASE_URL}/storage/v1/object/{bucket}/{filename}"
    resp = requests.post(
        upload_url,
        data=data,
        headers={
            "apikey": settings.SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_ANON_KEY}",
            "Content-Type": content_type,
            "x-upsert": "true",
        },
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Supabase Storage upload failed ({resp.status_code}): {resp.text[:300]}")

    return f"{settings.SUPABASE_URL}/storage/v1/object/public/{bucket}/{filename}"


def add_image(db: Session, prop: Property, url: str, is_main: bool = False) -> PropertyImage:
    if is_main:
        for existing in prop.images:
            existing.is_main = False
        prop.main_image_url = url
    image = PropertyImage(
        property_id=prop.id,
        url=url,
        is_main=is_main or not prop.images,
        sort_order=len(prop.images),
    )
    if image.is_main:
        prop.main_image_url = url
    db.add(image)
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return image


def search_properties(db: Session, filters: PropertyFilters, limit: int = 50, offset: int = 0) -> List[Property]:
    query = _base_query(db).filter(Property.is_available == True)  # noqa: E712

    if filters.county:
        query = query.filter(Property.county.ilike(filters.county))
    if filters.area:
        query = query.filter(Property.area.ilike(f"%{filters.area}%"))
    if filters.min_price is not None:
        query = query.filter(Property.price >= filters.min_price)
    if filters.max_price is not None:
        query = query.filter(Property.price <= filters.max_price)
    if filters.bedrooms is not None:
        query = query.filter(Property.bedrooms == filters.bedrooms)
    if filters.property_type:
        query = query.filter(Property.property_type.ilike(filters.property_type))
    if filters.q:
        like = f"%{filters.q}%"
        query = query.filter(
            or_(
                Property.title.ilike(like),
                Property.area.ilike(like),
                Property.county.ilike(like),
                Property.proximity_note.ilike(like),
            )
        )

    return query.order_by(Property.created_at.desc()).offset(offset).limit(limit).all()


def discover_queue(db: Session, user_id: UUID, filters: PropertyFilters, limit: int = 20) -> List[Property]:
    """Properties the user hasn't swiped on yet, newest first — the
    Tinder-style Discover deck."""
    already_swiped_ids = [
        row[0] for row in db.query(PropertySwipe.property_id).filter(PropertySwipe.user_id == user_id).all()
    ]

    query = (
        _base_query(db)
        .filter(Property.is_available == True)  # noqa: E712
        .filter(Property.landlord_id != user_id)
    )
    if already_swiped_ids:
        query = query.filter(~Property.id.in_(already_swiped_ids))

    if filters.county:
        query = query.filter(Property.county.ilike(filters.county))
    if filters.area:
        query = query.filter(Property.area.ilike(f"%{filters.area}%"))
    if filters.min_price is not None:
        query = query.filter(Property.price >= filters.min_price)
    if filters.max_price is not None:
        query = query.filter(Property.price <= filters.max_price)
    if filters.bedrooms is not None:
        query = query.filter(Property.bedrooms == filters.bedrooms)
    if filters.property_type:
        query = query.filter(Property.property_type.ilike(filters.property_type))

    return query.order_by(Property.created_at.desc()).limit(limit).all()


def record_swipe(db: Session, user_id: UUID, property_id: UUID, direction: str) -> None:
    existing = (
        db.query(PropertySwipe)
        .filter(PropertySwipe.user_id == user_id, PropertySwipe.property_id == property_id)
        .first()
    )
    if existing:
        existing.direction = direction
    else:
        db.add(PropertySwipe(user_id=user_id, property_id=property_id, direction=direction))
    db.commit()

    if direction == "right":
        already = (
            db.query(InterestedProperty)
            .filter(InterestedProperty.user_id == user_id, InterestedProperty.property_id == property_id)
            .first()
        )
        if not already:
            db.add(InterestedProperty(user_id=user_id, property_id=property_id))
            db.commit()


def list_interested(db: Session, user_id: UUID) -> List[Property]:
    rows = (
        db.query(InterestedProperty)
        .options(joinedload(InterestedProperty.property).joinedload(Property.images))
        .filter(InterestedProperty.user_id == user_id)
        .order_by(InterestedProperty.created_at.desc())
        .all()
    )
    return [r.property for r in rows if r.property and not r.property.is_removed]


def remove_interested(db: Session, user_id: UUID, property_id: UUID) -> None:
    (
        db.query(InterestedProperty)
        .filter(InterestedProperty.user_id == user_id, InterestedProperty.property_id == property_id)
        .delete()
    )
    db.commit()


def landlord_stats(db: Session, landlord_id) -> dict:
    """Real numbers for the landlord dashboard stat tiles — no
    placeholders. Computed straight from Property/InterestedProperty/
    ContactUnlock rather than faked, since a landlord seeing invented
    view/interest counts would be actively misleading."""
    from sqlalchemy import func as sa_func
    from app.models.interested_property import InterestedProperty
    from app.models.contact_unlock import ContactUnlock

    mine = _base_query(db).filter(Property.landlord_id == landlord_id)
    active_listings = mine.filter(Property.is_available == True).count()  # noqa: E712
    total_views = db.query(sa_func.coalesce(sa_func.sum(Property.view_count), 0)).filter(
        Property.landlord_id == landlord_id, Property.is_removed == False  # noqa: E712
    ).scalar() or 0

    my_property_ids = [p.id for p in mine.all()]
    interested_count = 0
    unlocks_count = 0
    unlocks_revenue = 0.0
    if my_property_ids:
        interested_count = (
            db.query(InterestedProperty).filter(InterestedProperty.property_id.in_(my_property_ids)).count()
        )
        unlocked = (
            db.query(ContactUnlock)
            .filter(ContactUnlock.property_id.in_(my_property_ids), ContactUnlock.status == "unlocked")
            .all()
        )
        unlocks_count = len(unlocked)
        unlocks_revenue = sum(u.amount for u in unlocked)

    return {
        "active_listings": active_listings,
        "total_views": int(total_views),
        "interested_count": interested_count,
        "contact_unlocks": unlocks_count,
        "contact_unlocks_revenue": unlocks_revenue,
    }


def increment_view_count(db: Session, prop: Property) -> None:
    prop.view_count = (prop.view_count or 0) + 1
    db.add(prop)
    db.commit()
