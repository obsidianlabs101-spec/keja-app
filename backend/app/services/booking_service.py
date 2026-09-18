import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.event import Event
from app.models.ticket import Ticket
from app.models.user import User
from app.models.platform_settings import get_or_create_platform_settings


def _new_reference() -> str:
    return f"EVR-{uuid.uuid4().hex[:12].upper()}"


def _new_ticket_code() -> str:
    # Short enough for a staff member to type at the gate, long enough to
    # not collide in practice; uniqueness is still enforced at the DB level.
    return uuid.uuid4().hex[:8].upper()


def create_booking(db: Session, user_id, event_id, quantity: int = 1, note=None, unit_price: float = 0.0, ticket_tier: str | None = None, buyer_total_amount: float | None = None) -> Booking:
    total_amount = float(quantity) * float(unit_price)
    # buyer_total_amount is the actual M-Pesa charge — and per the
    # booking-fee-only model, that is ONLY Bash's 12% booking fee, never
    # the ticket price itself. Bash never collects, holds, or refunds the
    # ticket price; that's paid directly to the Host at the venue. This
    # field is still named buyer_total_amount for now (matches the DB
    # column) even though it no longer represents "the buyer's total for
    # the event" — just the fee. Renaming the column/field itself is a
    # separate follow-up, not bundled into this fix.
    #
    # Falling back to total_amount*0.12 here is a safety net for any
    # future caller that forgets to pass it explicitly — it must never
    # silently collapse to total_amount (charging the full ticket price
    # instead of just the fee), which is the exact bug this fallback
    # exists to prevent a regression back into.
    if buyer_total_amount is None:
        buyer_total_amount = round(total_amount * 0.12, 2)
    booking = Booking(
        user_id=user_id,
        event_id=event_id,
        ticket_tier=ticket_tier,
        quantity=quantity,
        unit_price=unit_price,
        total_amount=total_amount,
        buyer_total_amount=buyer_total_amount,
        note=note,
        booking_reference=_new_reference(),
        status="pending",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    # For MVP: create 1 ticket immediately (even before payment), but keep it as "pending" via status.
    # We'll mark the ticket as issued only once payment is recorded.
    ticket = Ticket(
        booking_id=booking.id,
        qr_payload="",  # filled later when payment is confirmed
        status="pending",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(ticket)
    db.commit()
    return booking


class SoldOutError(Exception):
    """Raised by create_free_booking_fcfs when a free event's capacity is
    already spoken for. A distinct exception (rather than a generic
    ValueError) so callers can tell "sold out" apart from any other
    failure and show the buyer a "first come, first served" message
    instead of a generic error."""


class InsufficientCreditsError(Exception):
    """Raised by create_free_booking_fcfs when the user doesn't have a
    referral credit to spend. Booking a free event costs one credit,
    earned by getting one new signup through your referral link — see
    the referral_credits column comment on User for the full mechanic."""


def create_free_booking_fcfs(db: Session, user_id, event_id, quantity: int = 1, note=None, ticket_tier: str | None = None) -> Booking:
    """The FREE-EVENT-ONLY booking path. Enforces strict first-come,
    first-served ordering by doing the capacity check and the booking
    creation inside ONE locked transaction, instead of the normal
    pending -> (separate) claim-free two-step. That two-step is
    fine for paid events (M-Pesa naturally throttles how fast someone can
    actually claim a ticket), but for free events it left a window where
    two buyers could both pass the capacity check before either was
    actually marked paid, over-selling the event.

    Also spends one referral_credits credit from the user in the SAME
    locked transaction, but only while PlatformSettings.referral_gate_enabled
    is on (see the toggle at the top of this function) — free events cost
    a referral credit instead of cash ONLY in that mode. There's no
    separate check for the one-time free_events_unlocked browsing flag
    here: since credits can only ever be earned via the same referral
    event that sets that flag, having any credits at all already implies
    it's set.

    SELECT ... FOR UPDATE on the event row serializes concurrent bookings
    for the SAME event — a second request has to wait for the first
    request's transaction to commit (or roll back) before it can even read
    the row, so the "sold" count it sees always reflects every booking
    that has already won the race. Whichever request's transaction commits
    first genuinely was first, which is what "first come, first served"
    actually means at the database level.
    """
    event = (
        db.query(Event)
        .filter(Event.id == event_id)
        .with_for_update()
        .first()
    )
    if event is None:
        raise ValueError("Event not found")

    if event.capacity is not None:
        sold = (
            db.query(func.coalesce(func.sum(Booking.quantity), 0))
            .filter(Booking.event_id == event_id, Booking.status == "booked")
            .scalar()
        ) or 0
        if int(sold) + int(quantity) > int(event.capacity):
            db.rollback()  # releases the row lock without touching anything
            raise SoldOutError("This free event is fully booked — it's first come, first served.")

    # Booking a free event costs one referral credit, not cash — but only
    # while an admin has the Referral Gate switched ON (PlatformSettings.
    # referral_gate_enabled, OFF by default). With the gate off, free
    # events are simply bookable, same as a $0 paid event would be, no
    # credit involved at all — skip locking/checking/spending the user
    # row entirely rather than doing the work and ignoring the result.
    settings_row = get_or_create_platform_settings(db)
    if bool(settings_row.referral_gate_enabled):
        # Locking the user row here (with_for_update) for the same reason
        # the event row is locked above: without it, two concurrent
        # booking attempts by the same user (e.g. a double-tap, or two
        # open tabs) could both read "I have 1 credit" before either
        # commits, spending the same single credit twice.
        user = (
            db.query(User)
            .filter(User.id == user_id)
            .with_for_update()
            .first()
        )
        if user is None:
            db.rollback()
            raise ValueError("User not found")
        if (user.referral_credits or 0) < 1:
            db.rollback()  # releases both row locks without touching anything
            raise InsufficientCreditsError(
                "You need a referral credit to book a free event — refer a friend to earn one."
            )
        user.referral_credits = user.referral_credits - 1
        db.add(user)

    now = datetime.utcnow()
    booking = Booking(
        user_id=user_id,
        event_id=event_id,
        ticket_tier=ticket_tier,
        quantity=quantity,
        unit_price=0.0,
        total_amount=0.0,
        buyer_total_amount=0.0,
        note=note,
        booking_reference=_new_reference(),
        # Marked paid immediately (in the SAME transaction as the capacity
        # check above) — this is what makes the capacity check above
        # actually airtight instead of just a courtesy check with a race
        # window after it.
        status="booked",
        created_at=now,
        updated_at=now,
    )
    db.add(booking)
    db.flush()  # get booking.id without releasing the row lock (no commit yet)

    ticket = Ticket(
        booking_id=booking.id,
        qr_payload="",  # filled in later, once /issue-qr is called
        status="pending",
        created_at=now,
        updated_at=now,
    )
    db.add(ticket)

    db.commit()  # lock is released here, now that everything is durable
    db.refresh(booking)
    return booking


def issue_qr_ticket(db: Session, booking: Booking, qr_payload: str, ticket_id=None) -> Ticket:
    # SECURITY: this is the single choke point every code path (the
    # /bookings/{id}/issue-qr endpoint AND the payment-callback finalize
    # flow) goes through to turn a ticket "issued". Enforcing the paid
    # check here too means neither caller can accidentally issue a valid,
    # scannable ticket for an unpaid booking.
    if booking.status != "booked":
        raise ValueError(f"Refusing to issue a QR ticket for booking {booking.id}: booking is not paid (status={booking.status})")

    q = db.query(Ticket).filter(Ticket.booking_id == booking.id)
    ticket = q.first()
    if ticket is None:
        raise ValueError("Ticket not found for booking")

    ticket.qr_payload = qr_payload
    if not ticket.ticket_code:
        ticket.ticket_code = _new_ticket_code()
    ticket.status = "issued"
    ticket.updated_at = datetime.utcnow()
    if ticket_id is not None:
        # optional: validate
        if str(ticket.id) != str(ticket_id):
            raise ValueError("Ticket id mismatch")

    booking.updated_at = datetime.utcnow()
    db.add(ticket)
    db.add(booking)
    db.commit()
    db.refresh(ticket)
    return ticket


def record_payment_and_set_status(db: Session, booking: Booking, payment_id, amount: str = None) -> None:
    """SECURITY: defense-in-depth check — even though the amount charged is
    now always derived server-side (see /payments/mpesa/stk-push), refuse
    to mark a booking as paid if the recorded payment amount doesn't match
    what the booking actually owes. This protects against any future code
    path that creates a Payment with a client- or otherwise-influenced
    amount; a mismatch here means something upstream regressed, not that
    the booking should silently be treated as settled.
    A small epsilon accounts for float rounding, not for real underpayment.
    """
    booking_payment = (
        db.query(type(booking).payments.property.mapper.class_)
        .filter_by(id=payment_id)
        .first()
    )

    # Buyers are charged buyer_total_amount (host price + 12% markup), NOT
    # total_amount (the host's raw pre-markup value) — see the column
    # comments on Booking. Falls back to total_amount for any legacy row
    # created before buyer_total_amount existed.
    expected = float(booking.buyer_total_amount or booking.total_amount or 0)
    paid_amount = float(amount) if amount is not None else (
        float(booking_payment.amount) if booking_payment is not None else expected
    )
    if expected > 0 and paid_amount < expected - 0.01:
        raise ValueError(
            f"Refusing to mark booking {booking.id} paid: recorded payment "
            f"amount ({paid_amount}) is less than the amount owed ({expected})."
        )

    booking.status = "booked"
    booking.updated_at = datetime.utcnow()
    db.add(booking)

    if booking_payment is not None:
        if amount is not None:
            booking_payment.amount = amount
        booking_payment.status = "paid"
        booking_payment.updated_at = datetime.utcnow()

    db.commit()

def finalize_paid_booking(db: Session, payment) -> None:
    """Shared by every path that can mark a Payment "paid" — the real
    Daraja callback, the dev-simulate endpoint, and both directions of
    the manual-payment code match (buyer claim landing after an admin
    already pasted the code, or vice versa). Marks the booking paid and
    issues its QR ticket.

    A failure to mark the booking paid stops ticket issuance too, and the
    failure is logged instead of silently disappearing — see the comment
    history on this function's previous home (app/api/v1/payments.py) for
    why that matters.
    """
    from app.models.ticket import Ticket as _Ticket  # local import: avoids a
    from app.models.payment import Payment as _Payment  # circular import at module load
    from app.services.qr_service import generate_encrypted_qr

    booking = db.query(Booking).filter(Booking.id == payment.booking_id).first()
    if not booking:
        return

    try:
        record_payment_and_set_status(db, booking, payment.id, amount=payment.amount)
    except Exception as e:
        print(f"⚠️  Refusing to finalize booking {booking.id} as paid: {e}")
        return

    db.refresh(booking)
    if booking.status != "booked":
        print(f"⚠️  Booking {booking.id} did not end up in 'paid' status after payment finalize — not issuing a ticket.")
        return

    ticket_record = db.query(_Ticket).filter(_Ticket.booking_id == booking.id).first()
    if ticket_record:
        qr_payload_data = {
            "ticket_id": str(ticket_record.id),
            "booking_id": str(booking.id),
            "booking_ref": booking.booking_reference,
            "event_id": str(booking.event_id),
            "user_id": str(booking.user_id),
            "tier": booking.ticket_tier or "Standard",
        }
        qr_payload = generate_encrypted_qr(qr_payload_data)
        try:
            issue_qr_ticket(db, booking, qr_payload)
            _notify_ticket_confirmed(db, booking)
        except Exception as e:
            print(f"⚠️  Failed to issue QR ticket for booking {booking.id}: {e}")


def _wants_ticket_confirmation(user) -> bool:
    """Reads User.notification_preferences directly rather than importing
    from app.api.v1.users (would be a service-importing-a-router layering
    inversion) — default is True, matching _NOTIF_PREF_DEFAULTS there, so
    someone who's never opened the preferences panel still gets notified."""
    import json as _json
    raw = getattr(user, "notification_preferences", None)
    if not raw:
        return True
    try:
        prefs = _json.loads(raw)
        if isinstance(prefs, dict) and "ticket_confirmation" in prefs:
            return bool(prefs["ticket_confirmation"])
    except (ValueError, TypeError):
        pass
    return True


def _notify_ticket_confirmed(db: Session, booking) -> None:
    from app.models.notification import Notification
    from app.models.user import User as _User
    from app.models.event import Event as _Event
    from app.services.push_service import send_web_push

    user = db.query(_User).filter(_User.id == booking.user_id).first()
    if not user or not _wants_ticket_confirmation(user):
        return

    event = db.query(_Event).filter(_Event.id == booking.event_id).first()
    event_title = event.title if event else "your event"
    title = "Ticket confirmed 🎟️"
    body = f"You're in for {event_title} — {booking.booking_reference}. Your QR ticket is ready in the app."

    db.add(Notification(
        user_id=user.id,
        type="ticket_confirmation",
        title=title,
        body=body,
        data={"booking_id": str(booking.id)},
        context="user",
    ))
    db.commit()
    send_web_push(
        db, user, title=title, body=body,
        data={"booking_id": str(booking.id), "type": "ticket_confirmation"},
        tag=f"ticket-{booking.id}",
    )