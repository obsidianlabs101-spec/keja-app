from pydantic import BaseModel, field_validator
from datetime import datetime
from uuid import UUID
from typing import Optional, List


class TicketTier(BaseModel):
    label: str
    amount: float
    capacity: Optional[int] = None


class EventCreate(BaseModel):

    title: str

    description: str

    # Paid-ticket-holder-only instructions (parking, dress code, gate
    # password, etc). Deliberately NOT on EventRead — see the model
    # column's docstring in app/models/event.py for why.
    door_notes: Optional[str] = None

    category: str

    venue_name: str

    # Structured county — same County dropdown the host already fills in
    # for venue_name, sent separately so "Near Me" on the home page can
    # match it exactly against the buyer's own profile county.
    county: Optional[str] = None

    # Optional venue coordinates — kept for potential future map use, no
    # longer read by "Near Me" (that's county-based now, not GPS).
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    price: float

    capacity: Optional[int] = None

    start_date: datetime

    end_date: datetime

    poster_url: Optional[str] = None

    video_url: Optional[str] = None

    ticket_deadline: Optional[datetime] = None

    # Confirmed BASH usernames the host tagged as performers — see the
    artist_usernames: Optional[List[str]] = None

    # Custom ticket tiers (Early Bird, VIP, Gate, etc). When present,
    ticket_tiers: Optional[List[TicketTier]] = None



class EventRead(BaseModel):

    id: UUID
    host_id: UUID
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    venue_name: Optional[str] = None
    county: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    price: Optional[float] = None
    capacity: Optional[int] = None
    start_date: Optional[datetime] = None
    # Optional, not required: end_date is a plain nullable column at the DB
    end_date: Optional[datetime] = None
    status: str
    poster_url: Optional[str] = None
    video_url: Optional[str] = None
    ticket_deadline: Optional[datetime] = None
    artist_usernames: Optional[List[str]] = None
    ticket_tiers: Optional[List[TicketTier]] = None

    @field_validator("artist_usernames", mode="before")
    @classmethod
    def _parse_artist_usernames(cls, v):
        # The Event model stores this as a JSON-encoded string column
        if v is None or isinstance(v, list):
            return v
        if isinstance(v, str):
            import json
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else None
            except Exception:
                return None
        return None

    @field_validator("ticket_tiers", mode="before")
    @classmethod
    def _parse_ticket_tiers(cls, v):
        if v is None or isinstance(v, list):
            return v
        if isinstance(v, str):
            import json
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else None
            except Exception:
                return None
        return None

    class Config:
        from_attributes = True