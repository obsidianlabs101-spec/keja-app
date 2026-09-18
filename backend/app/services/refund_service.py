import re
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.refund_archive import RefundArchiveEntry
from app.models.user import User


# A typical Safaricom M-Pesa confirmation reads something like:
#   "QGH7XXXXX Confirmed. Ksh500.00 received from JOHN KAMAU 0712345678
#   on 17/7/26 at 2:30 PM. New M-PESA balance is Ksh1,200.00."
# This is a best-effort parser — it's fine if a field comes back empty;
# the admin can still archive the raw message and search on it.
_CODE_RE = re.compile(r"\b([A-Z0-9]{8,12})\b\s+Confirmed", re.IGNORECASE)
_AMOUNT_RE = re.compile(r"Ksh\s?([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE)
_PHONE_RE = re.compile(r"\b(07\d{8}|01\d{8}|2547\d{8}|2541\d{8})\b")
# Name sits between "from"/"to" and the phone number (or end of that clause).
_NAME_RE = re.compile(
    r"\b(?:from|to)\s+([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){0,3})\s*(?:0\d{9}|-|,|\.|$)",
)


def parse_mpesa_message(raw_message: str) -> dict:
    text = (raw_message or "").strip()

    code_match = _CODE_RE.search(text)
    amount_match = _AMOUNT_RE.search(text)
    phone_match = _PHONE_RE.search(text)
    name_match = _NAME_RE.search(text)

    amount = None
    if amount_match:
        try:
            amount = float(amount_match.group(1).replace(",", ""))
        except ValueError:
            amount = None

    return {
        "mpesa_code": code_match.group(1).upper() if code_match else None,
        "amount": amount,
        "phone": phone_match.group(1) if phone_match else None,
        "payer_name": name_match.group(1).strip() if name_match else None,
    }


def archive_refund_message(
    db: Session,
    raw_message: str,
    admin_id,
    matched_username: Optional[str] = None,
) -> RefundArchiveEntry:
    parsed = parse_mpesa_message(raw_message)
    entry = RefundArchiveEntry(
        raw_message=raw_message,
        payer_name=parsed["payer_name"],
        phone=parsed["phone"],
        mpesa_code=parsed["mpesa_code"],
        amount=parsed["amount"],
        matched_username=(matched_username or "").strip().lstrip("@") or None,
        admin_id=admin_id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def search_refund_archive(db: Session, query: str, limit: int = 50):
    q = (query or "").strip().lstrip("@")
    if not q:
        return (
            db.query(RefundArchiveEntry)
            .order_by(RefundArchiveEntry.created_at.desc())
            .limit(limit)
            .all()
        )
    like = f"%{q}%"
    return (
        db.query(RefundArchiveEntry)
        .filter(
            or_(
                RefundArchiveEntry.matched_username.ilike(like),
                RefundArchiveEntry.payer_name.ilike(like),
                RefundArchiveEntry.phone.ilike(like),
                RefundArchiveEntry.mpesa_code.ilike(like),
            )
        )
        .order_by(RefundArchiveEntry.created_at.desc())
        .limit(limit)
        .all()
    )