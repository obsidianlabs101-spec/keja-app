# app/schemas/contact_unlock.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ContactUnlockStatus(BaseModel):
    property_id: UUID
    status: str  # pending | awaiting_admin_match | unlocked
    amount: float
    phone: Optional[str] = None       # only populated once status == "unlocked"
    whatsapp: Optional[str] = None    # only populated once status == "unlocked"
    unlocked_at: Optional[datetime] = None
    free_credits_available: int = 0

    class Config:
        from_attributes = True


class BuyerClaimRequest(BaseModel):
    # Either the bare M-Pesa code (e.g. "QGH7XXXXX") or the full
    # confirmation SMS pasted as-is — extract_code() in
    # contact_unlock_service handles both, same as Bash's booking flow.
    raw_text: str


class AdminBatchMatchRequest(BaseModel):
    raw_text: str
