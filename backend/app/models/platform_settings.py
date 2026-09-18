from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class PlatformSettings(Base):
    """Single-row table (id is always 1) holding platform-wide toggles that
    admins flip from the Admin panel. Kept as one row rather than a generic
    key/value table on purpose — there are only a handful of these switches
    and a dedicated boolean column per switch is simpler to reason about
    and query than parsing a JSON blob every request.

    free_events_only: the "Technical Difficulties" kill-switch. When True,
    POST /events/create rejects any event with a price (or any ticket tier
    amount) above 0 — see events.py's create_new_event — so hosts can only
    post free events until an admin flips this back off. GET
    /events/platform-status is the public (no-auth) endpoint the host
    dashboard polls to know whether to hide its price/ticket-tier calculator
    and show the technical-difficulties banner.
    """

    __tablename__ = "platform_settings"

    id = Column(Integer, primary_key=True, default=1)

    free_events_only = Column(Boolean, nullable=False, default=False, server_default="false")

    free_events_only_updated_at = Column(DateTime, nullable=True)
    # NOTE: points at users.id, not admins.id. get_current_admin/require_admin
    # (app/core/dependencies.py) authenticates via User.is_admin and returns a
    # User row — the `admins` table is unused legacy auth, same trap
    # database.py's ensure_schema_upgrades comment describes for the old
    # withdrawals.admin_id FK. Pointing this at "admins" instead of "users"
    # would reject every real admin id with a ForeignKeyViolation.
    free_events_only_updated_by_admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # manual_payment_mode: the M-Pesa manual-payment switch. When True,
    # POST /payments/mpesa/stk-push (payments.py) skips the real Daraja STK
    # push entirely and instead hands the buyer the paybill number to pay
    # into by hand — see the "Manual Payments" admin subpage. When False,
    # STK is attempted as normal; note the app ALSO falls back to manual
    # mode automatically, per-booking, any time a real STK attempt raises
    # (Daraja unreachable/misconfigured) regardless of this flag — this
    # column only controls the deliberate, platform-wide default.
    manual_payment_mode = Column(Boolean, nullable=False, default=False, server_default="false")
    manual_payment_mode_updated_at = Column(DateTime, nullable=True)
    manual_payment_mode_updated_by_admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # referral_gate_enabled: whether booking a FREE event requires a
    # referral credit at all. OFF by default — free events are simply
    # bookable, no referral required. When an admin flips this ON, the
    # exact original mechanic comes back: User.free_events_unlocked /
    # referral_credits (see the columns' own comments on User) gate
    # browsing/booking again, same as before this switch existed. See
    # booking_service.create_free_booking_fcfs (the enforcement) and
    # GET /events/platform-status (the public no-auth read the frontend's
    # referral.js polls to decide whether to show padlocks at all).
    referral_gate_enabled = Column(Boolean, nullable=False, default=False, server_default="false")
    referral_gate_enabled_updated_at = Column(DateTime, nullable=True)
    referral_gate_enabled_updated_by_admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


def get_or_create_platform_settings(db) -> "PlatformSettings":
    """Every call site should go through this instead of querying the model
    directly — it guarantees the single settings row exists (row id=1)
    instead of every caller having to handle the "table exists but is
    empty" first-boot case itself."""
    row = db.query(PlatformSettings).filter(PlatformSettings.id == 1).first()
    if row is None:
        row = PlatformSettings(id=1, free_events_only=False)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row