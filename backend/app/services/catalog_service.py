"""Admin-managed housing categories and keyword locations."""
from typing import Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.catalog import HousingCategory, LocationKeyword
from app.models.property import Property

GROUPS = ("apartments", "hostels", "airbnb", "commercial")

# What Keja shipped with before categories became editable.
_DEFAULT_CATEGORIES = [
    ("Bedsitter", "apartments"), ("Studio", "apartments"), ("1 Bedroom", "apartments"),
    ("2 Bedroom", "apartments"), ("3+ Bedroom", "apartments"), ("House", "apartments"),
    ("Hostel", "hostels"), ("Airbnb", "airbnb"),
    ("Shop", "commercial"), ("Office", "commercial"), ("Warehouse", "commercial"), ("Commercial", "commercial"),
]
_DEFAULT_LOCATIONS = ["Kilimani", "Westlands", "Roysambu", "Kasarani", "Kahawa", "Lavington", "Ruaka", "Juja"]


def _clean_name(raw: str, what: str) -> str:
    name = " ".join((raw or "").split())
    if not name:
        raise ValueError(f"{what} name is required")
    if len(name) > 60:
        raise ValueError(f"{what} name is too long (60 characters max)")
    if "<" in name or ">" in name:
        raise ValueError("Angle brackets are not allowed")
    return name


def seed_defaults(db: Session) -> None:
    """Fill the tables the first time only, so existing listings keep working."""
    if db.query(func.count(HousingCategory.id)).scalar() == 0:
        for i, (name, group) in enumerate(_DEFAULT_CATEGORIES):
            db.add(HousingCategory(name=name, group_key=group, sort_order=i))
    if db.query(func.count(LocationKeyword.id)).scalar() == 0:
        for i, name in enumerate(_DEFAULT_LOCATIONS):
            db.add(LocationKeyword(name=name, sort_order=i))
    db.commit()


# ------------------------------------------------------------------ reads
def list_categories(db: Session, include_inactive: bool = True):
    q = db.query(HousingCategory)
    if not include_inactive:
        q = q.filter(HousingCategory.is_active == True)  # noqa: E712
    return q.order_by(HousingCategory.sort_order, HousingCategory.name).all()


def list_locations(db: Session, include_inactive: bool = True):
    q = db.query(LocationKeyword)
    if not include_inactive:
        q = q.filter(LocationKeyword.is_active == True)  # noqa: E712
    return q.order_by(LocationKeyword.sort_order, LocationKeyword.name).all()


def serialize_category(c: HousingCategory, in_use: Optional[int] = None) -> dict:
    d = {"id": str(c.id), "name": c.name, "group": c.group_key, "active": bool(c.is_active), "sort_order": c.sort_order}
    if in_use is not None:
        d["listings"] = in_use
    return d


def serialize_location(l: LocationKeyword) -> dict:
    return {"id": str(l.id), "name": l.name, "active": bool(l.is_active), "sort_order": l.sort_order}


def usage_counts(db: Session) -> dict:
    rows = (
        db.query(Property.property_type, func.count(Property.id))
        .filter(Property.is_removed == False)  # noqa: E712
        .group_by(Property.property_type)
        .all()
    )
    return {t: n for t, n in rows}


# ------------------------------------------------------------------ categories
def add_category(db: Session, name: str, group: str) -> HousingCategory:
    name = _clean_name(name, "Category")
    if group not in GROUPS:
        raise ValueError("Group must be one of: " + ", ".join(GROUPS))
    if db.query(HousingCategory).filter(func.lower(HousingCategory.name) == name.lower()).first():
        raise ValueError(f"'{name}' already exists")
    top = db.query(func.max(HousingCategory.sort_order)).scalar() or 0
    c = HousingCategory(name=name, group_key=group, sort_order=top + 1)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def update_category(db: Session, cid: UUID, name=None, group=None, active=None) -> HousingCategory:
    c = db.query(HousingCategory).filter(HousingCategory.id == cid).first()
    if not c:
        raise LookupError("Category not found")
    if name is not None and name != c.name:
        new = _clean_name(name, "Category")
        if db.query(HousingCategory).filter(func.lower(HousingCategory.name) == new.lower(), HousingCategory.id != c.id).first():
            raise ValueError(f"'{new}' already exists")
        # Keep existing listings attached to the renamed category.
        db.query(Property).filter(Property.property_type == c.name).update({Property.property_type: new})
        c.name = new
    if group is not None:
        if group not in GROUPS:
            raise ValueError("Group must be one of: " + ", ".join(GROUPS))
        c.group_key = group
    if active is not None:
        c.is_active = bool(active)
    db.commit()
    db.refresh(c)
    return c


def delete_category(db: Session, cid: UUID) -> None:
    c = db.query(HousingCategory).filter(HousingCategory.id == cid).first()
    if not c:
        raise LookupError("Category not found")
    n = usage_counts(db).get(c.name, 0)
    if n:
        raise ValueError(f"{n} listing(s) use '{c.name}'. Hide it instead of deleting it.")
    db.delete(c)
    db.commit()


# ------------------------------------------------------------------ locations
def add_location(db: Session, name: str) -> LocationKeyword:
    name = _clean_name(name, "Location")
    if db.query(LocationKeyword).filter(func.lower(LocationKeyword.name) == name.lower()).first():
        raise ValueError(f"'{name}' already exists")
    top = db.query(func.max(LocationKeyword.sort_order)).scalar() or 0
    l = LocationKeyword(name=name, sort_order=top + 1)
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def update_location(db: Session, lid: UUID, name=None, active=None) -> LocationKeyword:
    l = db.query(LocationKeyword).filter(LocationKeyword.id == lid).first()
    if not l:
        raise LookupError("Location not found")
    if name is not None and name != l.name:
        new = _clean_name(name, "Location")
        if db.query(LocationKeyword).filter(func.lower(LocationKeyword.name) == new.lower(), LocationKeyword.id != l.id).first():
            raise ValueError(f"'{new}' already exists")
        l.name = new
    if active is not None:
        l.is_active = bool(active)
    db.commit()
    db.refresh(l)
    return l


def delete_location(db: Session, lid: UUID) -> None:
    l = db.query(LocationKeyword).filter(LocationKeyword.id == lid).first()
    if not l:
        raise LookupError("Location not found")
    db.delete(l)
    db.commit()
