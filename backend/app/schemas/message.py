from datetime import datetime
from pydantic import BaseModel

class MessageSendRequest(BaseModel):
    to_username: str
    text: str
    # "user" (sent from the personal profile inbox) or "host" (sent from the
    # host dashboard). Defaults to "user" so older clients keep working.
    context: str = "user"

class MessageResponse(BaseModel):
    id: str
    sender_username: str
    receiver_username: str
    text: str
    created_at: datetime
    read: bool = False
    context: str = "user"

class ThreadSummary(BaseModel):
    username: str
    last_message: str
    last_time: datetime
    unread: int
    context: str = "user"

class UnreadCountResponse(BaseModel):
    unread: int