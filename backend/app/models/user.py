# app/models/user.py
import uuid

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import func
from sqlalchemy.orm import relationship  # Add this import
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

from app.core.database import Base


class User(Base):

    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # When this account was created. Added after the table already had
    # rows in production — existing rows will land with created_at=NULL
    # since the schema-upgrade ALTER TABLE has no way to know their real
    # signup date; the growth-analytics query excludes NULLs from the
    # weekly signup buckets rather than crashing on them. Every new
    # signup from here on gets it set automatically by the DB.
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=True,
    )

    email = Column(
        String,
        unique=True,
        nullable=False
    )

    username = Column(
        String,
        unique=True,
        nullable=False
    )

    full_name = Column(
        String,
        nullable=False
    )

    phone = Column(
        String,
        unique=True,
        nullable=True
    )

    profile_picture = Column(
        String,
        nullable=True
    )

    bio = Column(
        String,
        nullable=True
    )

    location = Column(
        String,
        nullable=True
    )

    # Structured county/town, set via the county/town pickers in the
    # profile-picture edit modal (frontend/profile.html). Distinct from
    # the free-text `location` field above — this is what powers the
    # "Near Me" card on the home page by matching against Event.county,
    # instead of GPS geolocation.
    county = Column(String, nullable=True)
    town = Column(String, nullable=True)

    # --- Referral / "free events" padlock -----------------------------
    # Every user gets a referral_code the first time it's needed (see
    # get_or_create_referral_code in auth_service.py). Sharing their link
    # (index.html?ref=<code>) and getting one new signup through it lifts
    # free_events_unlocked for good, so free events are no longer blurred
    # for them — that part is a one-time, permanent unlock.
    #
    # Actually BOOKING a given free event is separate and repeatable:
    # each successful referral also deposits one referral_credits credit,
    # and booking any one free event spends exactly one credit. So the
    # first referral does double duty (permanent unlock + first spendable
    # credit); every referral after that only adds more credits. There is
    # deliberately no per-event tracking of "which referral paid for
    # which event" — credits are a simple fungible balance.
    referral_code = Column(String, unique=True, nullable=True, index=True)
    referred_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    free_events_unlocked = Column(Boolean, nullable=False, default=False, server_default="false")
    referral_credits = Column(Integer, nullable=False, default=0, server_default="0")

    # Keja: one-time "refer a friend to earn a free contact unlock"
    # bonus. Deliberately separate from the free_events_unlocked/
    # referral_credits pair above (Bash's old events-referral system,
    # left untouched) so the two schemes can't interfere with each
    # other. referral_bonus_granted flips to True the first time
    # _credit_referrer_if_any() successfully credits this user as a
    # referrer, and never again — that's what makes the "refer a
    # friend" button on the profile page disappear for good once it's
    # been earned, whether or not the credit has been spent yet.
    free_contact_credits = Column(Integer, nullable=False, default=0, server_default="0")
    referral_bonus_granted = Column(Boolean, nullable=False, default=False, server_default="false")

    # --- Saka discoverability status -----------------------------------
    # One of: "friends", "dating", "available", "casual", "invisible", or
    # NULL (never set / opted out). Drives which Saka browse tab this
    # user's card shows up under (see stream.py's sakaStatus on the reel
    # response + frontend/saka.js's visiblePeople filter). "invisible"
    # deliberately means "opted out of browsing" rather than a 5th browse
    # tab — an invisible user never appears in any Saka tab, and can only
    # be found by someone searching their exact @username.
    # saka_status_expires_at is optional: statuses set with a duration
    # (e.g. "available for 6 hours") auto-expire — once past this
    # timestamp the status is treated as unset everywhere it's read,
    # without needing a background job to clear it. NULL here means "no
    # expiry" (stays until the person changes or clears it themselves).
    saka_status = Column(String, nullable=True)
    saka_status_expires_at = Column(DateTime(timezone=True), nullable=True)

    # --- Duplicate Guard -------------------------------------------------
    # A face photo, submitted once and admin-approved, used for two things:
    # (1) required to appear in Saka's roulette/swipe deck (not the grid —
    #     the grid keeps using their latest post), and (2) shown to a host
    #     at the Live Gate when a ticket gets scanned twice, so they can
    #     compare the person in front of them against who actually paid.
    # Never shown anywhere else — this is deliberately not the public
    # avatar. duplicate_guard_status: "not_submitted" | "pending" |
    # "approved" | "rejected".
    duplicate_guard_photo_url = Column(String, nullable=True)
    duplicate_guard_status = Column(String, nullable=False, default="not_submitted", server_default="not_submitted")
    duplicate_guard_submitted_at = Column(DateTime(timezone=True), nullable=True)
    duplicate_guard_reviewed_at = Column(DateTime(timezone=True), nullable=True)
    duplicate_guard_rejection_reason = Column(String, nullable=True)

    # Host-level toggle (one setting covers every event this host runs —
    # not per-event) — self-service, no admin approval needed for this
    # part; only the photo itself gets admin-reviewed. See
    # POST /events/{id}/checkin's duplicate-scan branch.
    duplicate_guard_enabled = Column(Boolean, nullable=False, default=False, server_default="false")

    social_links = Column(
        String,
        nullable=True
    )

    notification_preferences = Column(
        String,
        nullable=True
    )

    phone_verified = Column(
        Boolean,
        default=False
    )

    password_hash = Column(
        String,
        nullable=False
    )

    is_host = Column(
        Boolean,
        default=False
    )

    host_verification_status = Column(
        String,
        default="unverified"
    )

    # --- Gold Host Organiser badge -----------------------------------------
    # Recomputed (rating_service.recompute_host_gold_status) every time a
    # rating is submitted for one of this host's events. True once they
    # have at least 5 rated events and the average of their most recent 5
    # events' average ratings is >= 4.5. Swaps the host's feed badge from
    # the standard red "ORGANISER" pill to a gold one — see cheki.html.
    gold_organiser = Column(
        Boolean,
        default=False,
        server_default="false",
    )

    government_id = Column(
        String,
        nullable=True
    )

    government_id_image_url = Column(
        String,
        nullable=True
    )

    business_registration = Column(
        String,
        nullable=True
    )

    business_registration_image_url = Column(
        String,
        nullable=True
    )

    bank_name = Column(
        String,
        nullable=True
    )

    account_number = Column(
        String,
        nullable=True
    )

    account_name = Column(
        String,
        nullable=True
    )

    bank_business_number = Column(
        String,
        nullable=True
    )

    bank_branch = Column(
        String,
        nullable=True
    )

    swift_code = Column(
        String,
        nullable=True
    )

    mpesa_paybill = Column(
        String,
        nullable=True
    )

    kra_pin = Column(
        String,
        nullable=True
    )
    host_pin = Column(
        String,
        nullable=True,
        default="1234"
    )
    verification_requested_at = Column(
        DateTime,
        nullable=True
    )

    verification_approved_at = Column(
        DateTime,
        nullable=True
    )

    verification_admin_note = Column(
        String,
        nullable=True
    )

    is_admin = Column(
        Boolean,
        default=False
    )

    # Separate, narrower gate on top of is_admin — only admins with this
    # set can see the Financials page (payout ledger + platform revenue),
    # even if they're a fully-privileged admin otherwise. Granted via
    # POST /admin/financials/grant-access using ADMIN_CREATION_SECRET, or
    # set directly in the DB for the first finance-cleared admin.
    is_finance_verified = Column(
        Boolean,
        default=False,
        server_default="false",
    )

    # Every distinct financial-page session (unlock -> eventually leaves
    # the page or logs out) — the "Cuto" activity log on the Financials
    # page. Track separately from Notification so it never gets swept up
    # in a user-facing notifications list.
    last_financial_access_at = Column(
        DateTime,
        nullable=True,
    )

    is_active = Column(
        Boolean,
        default=True
    )

    # Bumped by /users/me/logout-all-sessions (and anywhere else that should
    # kill existing sessions, e.g. a future password-change endpoint). Every
    # JWT embeds the token_version it was issued with; get_current_user
    # rejects a token whose version doesn't match the current value here —
    # so revoking access no longer waits for a token to naturally expire,
    # which matters a lot more now that tokens can live for 30 days.
    token_version = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0"
    )

    # Browser PushSubscription (endpoint + keys), stored as a JSON string.
    # Set via POST /users/push-subscription once the app registers for
    # notifications; cleared automatically if the push service reports the
    # subscription as expired/invalid. Lets us fire real notification-tray
    # alerts (e.g. the T-2h "still going?" reminder) even when the app
    # isn't open, instead of only showing up inside the in-app panel.
    push_subscription = Column(
        String,
        nullable=True,
    )

    # Keja rebrand: the old `events`/`sent_messages`/`received_messages`
    # relationships (Bash's Event/Message models) were removed here since
    # those models are no longer imported anywhere (see app/main.py) —
    # a string-based relationship() to an unregistered class breaks
    # EVERY query against User at mapper-configuration time, not just
    # the unused relationship itself. Property.landlord is a plain
    # foreign_keys=[...] relationship on the Property side (see
    # app/models/property.py) and doesn't need a matching back_populates
    # here.