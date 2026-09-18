# app/services/contact_unlock_service.py
"""
Manual M-Pesa matching for the KES 50 "unlock landlord contact" flow.
Deliberately modeled on app/services/manual_payment_service.py rather than
re-derived — same two-sided match (buyer claim + admin-pasted statement),
same extract_code() shape, same "whichever side arrives second triggers
it" ordering. STK Push is NOT implemented per the spec's acceptance
checklist; this is the whole payment path for now.
"""
import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.contact_unlock import ContactUnlock, ContactUnlockPoolEntry, CONTACT_UNLOCK_FEE_KES
from app.services.refund_service import parse_mpesa_message

_BARE_CODE_RE = re.compile(r"^[A-Z0-9]{8,12}$")


def extract_code(raw_text: str) -> Optional[str]:
    text = (raw_text or "").strip()
    if not text:
        return None
    parsed = parse_mpesa_message(text)
    if parsed["mpesa_code"]:
        return parsed["mpesa_code"]
    candidate = text.upper().replace(" ", "")
    if _BARE_CODE_RE.match(candidate):
        return candidate
    return None


def _amounts_match(a: Optional[float], b: Optional[float]) -> bool:
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) < 0.01


def get_or_create_unlock(db: Session, user_id: UUID, property_id: UUID) -> ContactUnlock:
    unlock = (
        db.query(ContactUnlock)
        .filter(ContactUnlock.user_id == user_id, ContactUnlock.property_id == property_id)
        .first()
    )
    if unlock:
        return unlock
    unlock = ContactUnlock(user_id=user_id, property_id=property_id, amount=CONTACT_UNLOCK_FEE_KES)
    db.add(unlock)
    db.commit()
    db.refresh(unlock)
    return unlock


def _finalize_unlock(db: Session, unlock: ContactUnlock, code: str) -> None:
    unlock.status = "unlocked"
    unlock.matched_code = code
    unlock.unlocked_at = datetime.utcnow()
    db.add(unlock)
    db.commit()
    db.refresh(unlock)


def use_free_credit(db: Session, unlock: ContactUnlock, user) -> ContactUnlock:
    """Spends one of the user's one-time referral-earned free contact
    credits (see User.free_contact_credits / referral_bonus_granted in
    app/models/user.py) to unlock this property's contact instantly,
    bypassing the M-Pesa manual-match flow entirely."""
    if unlock.status == "unlocked":
        return unlock
    if (user.free_contact_credits or 0) <= 0:
        raise ValueError("No free contact credits available")

    user.free_contact_credits = user.free_contact_credits - 1
    db.add(user)
    _finalize_unlock(db, unlock, "FREE_REFERRAL_CREDIT")
    return unlock


def submit_buyer_claim(db: Session, unlock: ContactUnlock, raw_text: str) -> ContactUnlock:
    code = extract_code(raw_text)

    unlock.buyer_claimed_code = code
    unlock.buyer_claimed_raw_message = raw_text
    unlock.buyer_claimed_at = datetime.utcnow()
    unlock.status = "awaiting_admin_match"
    db.add(unlock)
    db.commit()
    db.refresh(unlock)

    if code:
        pending_pool = (
            db.query(ContactUnlockPoolEntry)
            .filter(ContactUnlockPoolEntry.code == code, ContactUnlockPoolEntry.matched == "false")
            .order_by(ContactUnlockPoolEntry.created_at.asc())
            .all()
        )
        for entry in pending_pool:
            if _amounts_match(entry.amount, unlock.amount):
                entry.matched = "true"
                entry.matched_unlock_id = unlock.id
                db.add(entry)
                _finalize_unlock(db, unlock, code)
                break

    return unlock


def batch_match_admin_codes(db: Session, raw_text: str, admin_id) -> dict:
    chunks = [c.strip() for c in re.split(r"\n\s*\n|\r\n\r\n", raw_text or "") if c.strip()]
    if len(chunks) <= 1:
        chunks = [c.strip() for c in (raw_text or "").splitlines() if c.strip()]

    matched_unlocks = []
    pooled_entries = []

    for chunk in chunks:
        parsed = parse_mpesa_message(chunk)
        code = parsed["mpesa_code"] or extract_code(chunk)
        amount = parsed["amount"]
        if not code:
            continue

        unlock = (
            db.query(ContactUnlock)
            .filter(
                ContactUnlock.status == "awaiting_admin_match",
                ContactUnlock.buyer_claimed_code == code,
            )
            .first()
        )
        if unlock is not None and _amounts_match(amount, unlock.amount):
            _finalize_unlock(db, unlock, code)
            matched_unlocks.append(unlock)
            continue

        entry = ContactUnlockPoolEntry(code=code, amount=amount, raw_message=chunk, admin_id=admin_id)
        db.add(entry)
        db.commit()
        db.refresh(entry)
        pooled_entries.append(entry)

    return {"matched": matched_unlocks, "pooled": pooled_entries}
