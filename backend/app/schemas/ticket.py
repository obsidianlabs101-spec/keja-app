from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class TicketCheckInRequest(BaseModel):
    event_id: UUID
    qr_payload: str

