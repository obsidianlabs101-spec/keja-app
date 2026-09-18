# app/schemas/property.py
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PropertyImageRead(BaseModel):
    id: UUID
    url: str
    is_main: bool
    sort_order: int

    class Config:
        from_attributes = True


class PropertyCreate(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    property_type: str
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    county: str
    area: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    proximity_note: Optional[str] = None


class PropertyUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    property_type: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    county: Optional[str] = None
    area: Optional[str] = None
    proximity_note: Optional[str] = None
    is_available: Optional[bool] = None
    is_booked: Optional[bool] = None


class LandlordSummary(BaseModel):
    id: UUID
    full_name: str
    username: Optional[str] = None

    class Config:
        from_attributes = True


class PropertyRead(BaseModel):
    id: UUID
    landlord_id: UUID
    title: str
    description: Optional[str] = None
    price: float
    property_type: str
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    county: str
    area: Optional[str] = None
    proximity_note: Optional[str] = None
    main_image_url: Optional[str] = None
    is_available: bool
    is_booked: bool
    view_count: int
    created_at: Optional[datetime] = None
    images: List[PropertyImageRead] = Field(default_factory=list)

    class Config:
        from_attributes = True


class PropertyFilters(BaseModel):
    county: Optional[str] = None
    area: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    bedrooms: Optional[int] = None
    property_type: Optional[str] = None
    q: Optional[str] = None  # free-text search across title/area/county/proximity_note
