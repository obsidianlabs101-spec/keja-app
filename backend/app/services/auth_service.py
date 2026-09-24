from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserRegister

from app.core.security import hash_password
from app.core.security import verify_password


def get_user_by_email(
    db: Session,
    email: str
):

    return (
        db.query(User)
        .filter(User.email == email)
        .first()
    )


def get_user_by_username(
    db: Session,
    username: str
):
    """Username match, tolerant of the leading '@' either being present
    or absent on either side (signup form, host application form, and
    the DB itself have all stored it both ways at different points)."""
    if not username:
        return None
    clean = username.strip()
    bare = clean.lstrip("@").lower()
    return (
        db.query(User)
        .filter(func.lower(User.username).in_([bare, f"@{bare}"]))
        .first()
    )


def _generate_referral_code(db: Session, username: str) -> str:
    """Short, human-shareable code derived from the username, with a
    random suffix to disambiguate + guarantee uniqueness."""
    import re
    import secrets
    base = re.sub(r"[^a-z0-9]", "", (username or "user").lower().lstrip("@"))[:12] or "user"
    for _ in range(10):
        code = f"{base}{secrets.token_hex(2)}"
        if not db.query(User).filter(User.referral_code == code).first():
            return code
    return f"{base}{secrets.token_hex(4)}"


def _generate_unique_username_from_name(db: Session, name: str) -> str:
    """Turns a Google display name into a valid, unique @handle — mirrors
    the sanitization the frontend was already doing client-side (see the
    old handleGoogleCredentialResponse in index.html), but now actually
    checks uniqueness against the DB (case-insensitively — see
    get_user_by_username) instead of just trusting it'll be unique."""
    import re
    import secrets
    base = re.sub(r"[^a-zA-Z0-9_]", "_", (name or "user").strip())[:20] or "user"
    candidate = f"@{base}"
    if not get_user_by_username(db, candidate):
        return candidate
    for _ in range(10):
        candidate = f"@{base}_{secrets.token_hex(2)}"
        if not get_user_by_username(db, candidate):
            return candidate
    return f"@{base}_{secrets.token_hex(6)}"


def authenticate_or_create_google_user(
    db: Session,
    email: str,
    name: str,
    picture: str,
    ref_code: str | None = None,
):
    """Find-or-create for Google Sign-In. Called only after the ID token
    has already been cryptographically verified (see api/v1/auth.py's
    /auth/google endpoint) — this function trusts that email/name/picture
    genuinely came from Google.

    An existing password-based account with a matching email signs in
    via Google seamlessly (same account, just a second way in) — this is
    standard behavior and matches how most apps handle "sign in with
    Google" for an email that already has a password. ref_code is
    intentionally ignored in that branch: crediting a referral for
    someone who already has an account (just logging in a new way)
    would let the same person be "referred" repeatedly.
    """
    import secrets

    existing = get_user_by_email(db, email)
    if existing:
        return existing, False

    username = _generate_unique_username_from_name(db, name or email.split("@")[0])

    # Random password nobody knows or needs — this account only ever
    # signs in via Google, but password_hash is a required (NOT NULL)
    # column, so it still needs *something* stored. secrets.token_urlsafe
    # is cryptographically random, so this is safe even though it's
    # technically "guessable-in-theory" the same way any unused password
    # would be — nobody will ever try, since there's no reason to.
    random_password_hash = hash_password(secrets.token_urlsafe(32))

    db_user = User(
        username=username,
        full_name=name or username.lstrip("@"),
        email=email,
        phone=None,  # Google doesn't provide this — column is nullable
        password_hash=random_password_hash,
        profile_picture=picture or None,
    )
    db_user.referral_code = _generate_referral_code(db, username)

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # This was the actual gap: a Google signup previously never credited
    # whoever's referral link it came through, even when one was present
    # in the URL — see _credit_referrer_if_any's docstring for what this
    # does. Same shared helper the password-signup path uses, so the two
    # can never silently drift apart from each other again.
    _credit_referrer_if_any(db, ref_code, db_user)
    db.commit()

    return db_user, True


def _credit_referrer_if_any(db: Session, ref_code: str | None, new_user: User) -> None:
    """Shared by both signup paths (password-based create_user, and
    Google-based authenticate_or_create_google_user) — sets referred_by
    on the new account, permanently unlocks free-events browsing for the
    referrer, deposits one referral_credits credit, and notifies them.
    Only ever called for a genuinely brand-new account (both callers
    return early for an existing account), so this can't be re-triggered.
    """
    ref_code = (ref_code or "").strip()
    if not ref_code:
        return
    referrer = db.query(User).filter(User.referral_code == ref_code).first()
    if not referrer:
        return

    new_user.referred_by_user_id = referrer.id

    from app.models.notification import Notification
    referrer.free_events_unlocked = True
    referrer.referral_credits = (referrer.referral_credits or 0) + 1

    # Keja one-time contact-unlock bonus — only the referrer's FIRST
    # successful referral ever grants this (see the column's docstring
    # in app/models/user.py). Every referral after that still runs the
    # old free_events_unlocked/referral_credits logic above unchanged,
    # it just doesn't grant a second free contact credit.
    earned_contact_bonus = False
    if not referrer.referral_bonus_granted:
        referrer.free_contact_credits = (referrer.free_contact_credits or 0) + 1
        referrer.referral_bonus_granted = True
        earned_contact_bonus = True

    db.add(referrer)
    notif_body = f"{new_user.username or new_user.full_name} signed up through your link — free events are unlocked, and you've got {referrer.referral_credits} credit(s) to book one."
    if earned_contact_bonus:
        notif_body += " You've also earned 1 free landlord-contact unlock on Keja."
    db.add(Notification(
        user_id=referrer.id,
        type="referral_unlocked",
        title="You earned a free event credit 🎟️",
        body=notif_body,
        data={
            "referred_username": new_user.username,
            "referral_credits": referrer.referral_credits,
            "earned_contact_bonus": earned_contact_bonus,
        },
        context="user",
    ))

    # If the referrer had asked for a specific landlord's number ("share &
    # unlock free"), this signup is the trigger: spend the credit and send
    # the number to their Alerts.
    if earned_contact_bonus:
        from app.models.contact_unlock import ContactUnlock
        from app.services.notify_service import notify_contact_ready
        waiting = (
            db.query(ContactUnlock)
            .filter(ContactUnlock.user_id == referrer.id, ContactUnlock.status == "awaiting_referral")
            .order_by(ContactUnlock.created_at.asc())
            .first()
        )
        if waiting is not None:
            from datetime import datetime as _dt
            referrer.free_contact_credits = max(0, (referrer.free_contact_credits or 0) - 1)
            waiting.status = "unlocked"
            waiting.matched_code = "FREE_REFERRAL_CREDIT"
            waiting.unlocked_at = _dt.utcnow()
            db.add(waiting)
            notify_contact_ready(db, waiting, commit=False)


def create_user(
    db: Session,
    user: UserRegister
):

    db_user = User(
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        password_hash=hash_password(
            user.password
        )
    )
    db_user.referral_code = _generate_referral_code(db, user.username)

    # Free-events padlock + referral credit: whoever's referral link this
    # signup came through gets it credited the moment this account is
    # created — see frontend's referral.js for the share-card UI that
    # generates the ?ref=<code> link, and index.html for where it's read
    # back out. ref_code has to be captured BEFORE the commit below,
    # since _credit_referrer_if_any needs db_user.id to already exist
    # (referred_by_user_id is a foreign key) — but the actual credit
    # application happens after, in one shared pass with the Google path.
    ref_code = getattr(user, "ref", None)

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    _credit_referrer_if_any(db, ref_code, db_user)
    db.commit()

    return db_user


def update_host_verification(
    db: Session,
    user: User,
    data
):

    for field in (
        "government_id",
        "government_id_image_url",
        "business_registration",
        "business_registration_image_url",
        "bank_name",
        "account_number",
        "account_name",
        "bank_business_number",
        "bank_branch",
        "swift_code",
        "mpesa_paybill",
        "kra_pin",
        "host_pin",
    ):
        value = getattr(data, field, None)
        if value is not None:
            setattr(user, field, value)

    user.host_verification_status = "pending"

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def approve_host_verification(
    db: Session,
    user_id: str
):

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    user.is_host = True
    user.host_verification_status = "approved"
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def authenticate_user(
    db: Session,
    email: str,
    password: str
):

    user = get_user_by_email(
        db,
        email
    )

    if not user:
        return None

    if not verify_password(
        password,
        user.password_hash
    ):
        return None

    return user

def get_user_by_id(
    db: Session,
    user_id: str
):
    return (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )


def update_user_profile(
    db: Session,
    user: User,
    data
):
    profile_fields = ["bio", "location", "county", "town", "social_links"]
    
    for field in profile_fields:
        value = getattr(data, field, None)
        if value is not None:
            setattr(user, field, value)
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


def request_host_verification(
    db: Session,
    user: User,
    data
):
    from datetime import datetime

    for field in (
        "government_id",
        "government_id_image_url",
        "business_registration",
        "business_registration_image_url",
        "bank_name",
        "account_number",
        "account_name",
        "bank_business_number",
        "bank_branch",
        "swift_code",
        "mpesa_paybill",
        "kra_pin",
        "host_pin",
    ):
        value = getattr(data, field, None)
        if value is not None:
            setattr(user, field, value)

    # phone wasn't in the loop above, so the phone number typed into the
    # host application form was silently discarded — never reaching the
    # database at all.
    phone_value = getattr(data, "phone", None)
    if phone_value:
        user.phone = phone_value.strip()

    # Usernames are permanent once set at signup — intentionally NOT
    # editable from the host application form (or anywhere else). A
    # `username` field may still arrive on this payload from older
    # frontend builds; it's ignored here on purpose.

    user.host_verification_status = "pending"
    user.verification_requested_at = datetime.utcnow()

    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Most likely cause: the phone number typed into this form
        # already belongs to a different account (phone has a unique
        # constraint) — this used to surface as a raw 500. Roll back
        # and turn it into a message the person can actually act on.
        db.rollback()
        raise ValueError(
            "That phone number is already registered to another Keja account. "
            "Use a different number, or leave it blank to keep the one on your account."
        )
    db.refresh(user)

    return user


def list_pending_host_verifications(db: Session):
    return (
        db.query(User)
        .filter(User.host_verification_status == "pending")
        .all()
    )


def approve_or_reject_host_verification(
    db: Session,
    user_id: str,
    approve: bool,
    note: str = None
):
    from datetime import datetime
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    
    if approve:
        user.is_host = True
        user.host_verification_status = "approved"
        user.verification_approved_at = datetime.utcnow()
    else:
        user.host_verification_status = "rejected"
    
    user.verification_admin_note = note
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user