import uuid

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import Float
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import func

from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class RefundArchiveEntry(Base):
    """The admin Refunds sub-page: an admin pastes the M-Pesa confirmation
    message a buyer sent in when asking for a refund. We pull the payer's
    name (and code/amount/phone, where present) out of that message and
    file it here with a timestamp, so any admin can later search by
    username/name and see whether — and exactly when — that person's
    refund message was logged."""

    __tablename__ = "refund_archive_entries"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # The raw text the admin pasted in, kept verbatim for reference.
    raw_message = Column(Text, nullable=False)

    # Parsed out of the M-Pesa message (best-effort regex — see
    # refund_service.parse_mpesa_message).
    payer_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    mpesa_code = Column(String, nullable=True)
    amount = Column(Float, nullable=True)

    # If the admin also tagged this entry with the BASH username making
    # the refund request, so the search bar can match on it directly even
    # when the M-Pesa message's sender name doesn't match their BASH name.
    matched_username = Column(String, nullable=True)

    admin_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=True,
    )