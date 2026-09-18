import uuid
from datetime import datetime

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class TaxonomyEntry(Base):
    """Backs the admin Adder page (GET/POST /admin/taxonomy, DELETE
    /admin/taxonomy/{id}) and the public pickers that read admin-added
    options (GET /admin/taxonomy/public, read by cheki.js's
    loadAdderCategoryPills). Was frontend-only until now — the Adder page
    existed and called these routes, but nothing on the backend answered
    them, hence every request 404ing ("Not Found" in the admin screenshot
    that prompted this table).

    entry_type is one of "category" | "town" | "location" — kept as a
    plain string rather than a DB enum so adding a fourth type later is a
    one-line frontend change, no migration.

    parent_town is only ever set for entry_type="location" (a named spot
    that isn't itself an official town/constituency — e.g. a specific
    venue) and records which town it falls under, for display/filtering.
    Always NULL for "category" and "town" rows.
    """

    __tablename__ = "taxonomy_entries"
    __table_args__ = (
        # Case-sensitive at the DB level; submitAdderEntry's "already
        # existed" check in admin.js does its own case-INsensitive
        # comparison against the loaded list before ever hitting this
        # constraint, so in practice duplicates are caught earlier with a
        # friendlier message — this is the backstop for a race between two
        # admins adding the same value at once.
        UniqueConstraint("entry_type", "value", name="uq_taxonomy_type_value"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    entry_type = Column(
        String,
        nullable=False,
        index=True,
    )

    value = Column(
        String,
        nullable=False,
    )

    parent_town = Column(
        String,
        nullable=True,
    )

    created_by_admin_id = Column(
        UUID(as_uuid=True),
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )