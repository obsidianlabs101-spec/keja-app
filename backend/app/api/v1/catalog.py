from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.services import catalog_service as svc

# Public read-only lists the website/app use for pickers and chips.
public_router = APIRouter(prefix="/properties", tags=["catalog"])
# Admin management (same require_admin as the rest of the back office).
admin_router = APIRouter(prefix="/admin/catalog", tags=["admin-catalog"])


class CategoryIn(BaseModel):
    name: str
    group: str


class CategoryPatch(BaseModel):
    name: Optional[str] = None
    group: Optional[str] = None
    active: Optional[bool] = None


class LocationIn(BaseModel):
    name: str


class LocationPatch(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None


def _guard(fn, *a, **k):
    try:
        return fn(*a, **k)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------- public
@public_router.get("/categories")
def public_categories(db: Session = Depends(get_db)):
    """All categories incl. hidden ones (flagged active=false) so clients can
    still group old listings; pickers show only active ones."""
    return [svc.serialize_category(c) for c in svc.list_categories(db)]


@public_router.get("/locations")
def public_locations(db: Session = Depends(get_db)):
    return [l.name for l in svc.list_locations(db, include_inactive=False)]


# ---------------------------------------------------------------- admin
@admin_router.get("")
def admin_catalog(db: Session = Depends(get_db), admin=Depends(require_admin)):
    use = svc.usage_counts(db)
    return {
        "groups": list(svc.GROUPS),
        "categories": [svc.serialize_category(c, use.get(c.name, 0)) for c in svc.list_categories(db)],
        "locations": [svc.serialize_location(l) for l in svc.list_locations(db)],
    }


@admin_router.post("/categories")
def admin_add_category(body: CategoryIn, db: Session = Depends(get_db), admin=Depends(require_admin)):
    return svc.serialize_category(_guard(svc.add_category, db, body.name, body.group), 0)


@admin_router.patch("/categories/{cid}")
def admin_update_category(cid: UUID, body: CategoryPatch, db: Session = Depends(get_db), admin=Depends(require_admin)):
    return svc.serialize_category(_guard(svc.update_category, db, cid, body.name, body.group, body.active))


@admin_router.delete("/categories/{cid}")
def admin_delete_category(cid: UUID, db: Session = Depends(get_db), admin=Depends(require_admin)):
    _guard(svc.delete_category, db, cid)
    return {"ok": True}


@admin_router.post("/locations")
def admin_add_location(body: LocationIn, db: Session = Depends(get_db), admin=Depends(require_admin)):
    return svc.serialize_location(_guard(svc.add_location, db, body.name))


@admin_router.patch("/locations/{lid}")
def admin_update_location(lid: UUID, body: LocationPatch, db: Session = Depends(get_db), admin=Depends(require_admin)):
    return svc.serialize_location(_guard(svc.update_location, db, lid, body.name, body.active))


@admin_router.delete("/locations/{lid}")
def admin_delete_location(lid: UUID, db: Session = Depends(get_db), admin=Depends(require_admin)):
    _guard(svc.delete_location, db, lid)
    return {"ok": True}
