# app/schemas/host_comment.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class HostCommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=500)


class HostCommentRead(BaseModel):
    id: UUID
    body: str
    created_at: Optional[datetime] = None
    author_name: str
    author_avatar: Optional[str] = None
    is_mine: bool = False

    class Config:
        from_attributes = True
