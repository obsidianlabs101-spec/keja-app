# app/models/landlord_id_document.py
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class LandlordIdDocument(Base):
    """A landlord applicant's ID photo.

    Deliberately stored in the database and only ever served through an
    admin-authenticated endpoint — NOT in a public Supabase bucket, because
    a public URL to someone's government ID is a serious privacy leak.
    """

    __tablename__ = "landlord_id_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    content_type = Column(String, nullable=False)
    data = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
