"""Manual M-Pesa payment matching.

Flow: when manual mode is on (or STK failed), a buyer pays the paybill by
hand and pastes back either the bare code (e.g. "QGH7XXXXX") or the full
M-Pesa confirmation SMS. Separately, an admin pastes in a batch of the real
confirmation messages/codes copied from the actual paybill statement.
A booking is only finalized as paid once BOTH sides agree on the same
code AND the same amount — the buyer's own claim is never trusted alone.

Matching is order-independent (see ManualPaymentPoolEntry) — whichever
side arrives second is the one that triggers the finalize.
"""
import re
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.manual_payment_pool import ManualPaymentPoolEntry
from app.services.refund_service import parse_mpesa_message
from app.services.booking_service import finalize_paid_booking

# A bare code pasted with no surrounding message — e.g. the buyer just
# copied "QGH7XXXXX" instead of the whole SMS. Real Safaricom codes are
# uppercase alphanumeric, 10 characters. Kept slightly looser (8-12) to
# match parse_mpesa_message's own tolerance rather than reject a valid
# code the SMS-shaped regex was never meant to gate.
_BARE_CODE_RE = re.compile(r"^[A-Z0-9]{8,12}$")


def extract_code(raw_text: str) -> Optional[str]:
    """Best-effort code extraction that works whether the person pasted a
    full M-Pesa SMS or just the bare code by itself."""
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


def submit_buyer_claim(db: Session, payment: Payment, raw_text: str) -> Payment:
    """Buyer says "I've paid" and pastes their code/message. Tries an
    immediate match against anything an admin already pasted in; if
    nothing matches yet, the claim just sits on the Payment row waiting
    for the admin's next batch."""
    code = extract_code(raw_text)

    payment.buyer_claimed_code = code
    payment.buyer_claimed_raw_message = raw_text
    payment.buyer_claimed_at = datetime.utcnow()
    payment.status = "awaiting_admin_match"
    db.add(payment)
    db.commit()
    db.refresh(payment)

    if code:
        pool_entry = (
            db.query(ManualPaymentPoolEntry)
            .filter(
                ManualPaymentPoolEntry.code == code,
                ManualPaymentPoolEntry.matched == False,  # noqa: E712
            )
            .order_by(ManualPaymentPoolEntry.created_at.asc())
            .all()
        )
        for entry in pool_entry:
            if _amounts_match(entry.amount, payment.amount):
                entry.matched = True
                entry.matched_payment_id = payment.id
                entry.matched_at = datetime.utcnow()
                db.add(entry)
                payment.status = "paid"
                payment.mpesa_receipt_number = code
                db.add(payment)
                db.commit()
                db.refresh(payment)
                finalize_paid_booking(db, payment)
                break

    return payment


def batch_match_admin_codes(db: Session, raw_text: str, admin_id) -> dict:
    """Admin pastes one or more confirmation messages/codes (blank-line or
    single-line separated) copied from the real paybill statement. Each
    is parsed, matched against pending buyer claims immediately, and
    whatever doesn't match is parked in the pool for a later buyer claim
    to catch."""
    chunks = [c.strip() for c in re.split(r"\n\s*\n|\r\n\r\n", raw_text or "") if c.strip()]
    if len(chunks) <= 1:
        # No blank-line separation supplied — fall back to one entry per
        # non-empty line, which covers admins just pasting a bare list of
        # codes (one per line) rather than full SMS blocks.
        chunks = [c.strip() for c in (raw_text or "").splitlines() if c.strip()]

    matched_payments = []
    pooled_entries = []

    for chunk in chunks:
        parsed = parse_mpesa_message(chunk)
        code = parsed["mpesa_code"] or extract_code(chunk)
        amount = parsed["amount"]
        if not code:
            continue

        payment = (
            db.query(Payment)
            .filter(
                Payment.provider == "mpesa_manual",
                Payment.status == "awaiting_admin_match",
                Payment.buyer_claimed_code == code,
            )
            .first()
        )
        if payment is not None and _amounts_match(amount, payment.amount):
            payment.status = "paid"
            payment.mpesa_receipt_number = code
            payment.raw_payload = chunk
            db.add(payment)
            db.commit()
            db.refresh(payment)
            finalize_paid_booking(db, payment)
            matched_payments.append(payment)
            continue

        entry = ManualPaymentPoolEntry(
            code=code,
            amount=amount,
            raw_message=chunk,
            admin_id=admin_id,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        pooled_entries.append(entry)

    return {
        "matched_payment_ids": [str(p.id) for p in matched_payments],
        "matched_booking_ids": [str(p.booking_id) for p in matched_payments],
        "pooled_count": len(pooled_entries),
        "matched_count": len(matched_payments),
    }


def force_match_payment(db: Session, payment: Payment, admin_id, admin_note: Optional[str] = None) -> Payment:
    """Escape hatch for the admin panel: the buyer's claimed code visibly
    is in the real statement but didn't auto-match — usually a rounding/
    fee-deduction difference in the amount, or the buyer mistyped a
    character. An admin who has manually eyeballed both sides can force
    the booking through instead of leaving a genuinely-paid buyer stuck."""
    payment.status = "paid"
    if not payment.mpesa_receipt_number:
        payment.mpesa_receipt_number = payment.buyer_claimed_code
    if admin_note:
        payment.raw_payload = f"[force-matched by admin] {admin_note}"
    db.add(payment)
    db.commit()
    db.refresh(payment)
    finalize_paid_booking(db, payment)
    return payment