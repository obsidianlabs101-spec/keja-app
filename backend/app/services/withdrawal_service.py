"""
Host payout pipeline — one event at a time.

Flow (matches the product spec exactly):
  1. Once an event is 24h past its end and its final list was sent to the
     Live Gate (Event.gate_unlocked), it becomes payout-eligible. The host
     presses "Request Payout" on that specific event.
  2. That creates a Withdrawal(status="requested") and alerts admins with
     the gross revenue, our 12% cut, and the host's expected net payout.
  3. Admin presses "Message" -> Withdrawal moves to
     "awaiting_host_confirmation" and the host gets a notification showing
     the event name, expected payment, and the bank/M-Pesa details on file,
     with Confirm/Deny.
  4. Host Confirms -> "confirmed_by_host". Admin manually sends the money
     via their own M-Pesa and logs the resulting M-Pesa code, which marks
     the withdrawal "paid": that becomes the host-financials + bash-
     financials record, and the code is sent to the host's notifications
     as proof of payment.
     Host Denies -> "denied_by_host". The host edits their bank/M-Pesa
     details, then resubmits, which puts the request straight back to
     "requested" for another pass through the same pipeline.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.withdrawal import Withdrawal
from app.models.event import Event
from app.models.booking import Booking
from app.models.ticket import Ticket
from app.models.notification import Notification

PLATFORM_CUT_RATE = 0.12
PAYOUT_ELIGIBILITY_DELAY = timedelta(hours=24)

# Statuses that mean "this event already has an in-flight or settled
# withdrawal" — a host can't open a second request for the same event
# while one of these is active.
ACTIVE_WITHDRAWAL_STATUSES = (
    "requested",
    "awaiting_host_confirmation",
    "confirmed_by_host",
    "paid",
)


def _payout_clock_start(event: Event):
    """Payout eligibility clock starts 24h after the event STARTS (not
    ends) — matches how the door/gate flow actually plays out: an event
    can run late into the night or span multiple days, and hosts need
    their money the day after doors opened, not after some potentially
    much later end_date."""
    return event.start_date


def _supposed_and_came(db: Session, event: Event):
    """'Supposed to come' = the frozen T-1 final list count that was
    actually sent to the Live Gate (Event.final_ticket_tally). Falls back
    to a live count of paid bookings if tickets were never formally sent
    (e.g. a very old event from before this pipeline existed)."""
    supposed = event.final_ticket_tally
    if supposed is None:
        supposed = (
            db.query(func.coalesce(func.sum(Booking.quantity), 0))
            .filter(Booking.event_id == event.id, Booking.status == "paid")
            .scalar()
        ) or 0
    came = (
        db.query(func.count(Ticket.id))
        .join(Booking, Booking.id == Ticket.booking_id)
        .filter(Booking.event_id == event.id, Ticket.status == "checked_in")
        .scalar()
    ) or 0
    return int(supposed), int(came)


def _revenue_breakdown(event: Event):
    # final_tally_amount is the sum of Booking.total_amount across paid
    # bookings, and Booking.total_amount is quantity * event.price — the
    # host's own face-value ticket price, with NO platform markup baked
    # in (the markup is only ever applied on top at buyer checkout, see
    # bookings.py's `total = subtotal + platform_fee + mpesa_fee`, which
    # is charged via M-Pesa but never written into Booking.total_amount).
    # So this is already exactly what the host is owed — the platform's
    # cut is additive revenue collected from the buyer, not a slice taken
    # out of the host's side. host_amount must equal gross, never less.
    gross = float(event.final_tally_amount or 0.0)
    platform_cut = round(gross * PLATFORM_CUT_RATE, 2)  # informational only — never subtracted from the host
    host_amount = round(gross, 2)
    return gross, platform_cut, host_amount


def get_host_payout_events(db: Session, host_id):
    """Every event this host owns that has had its final list sent to the
    Live Gate, annotated with attendance tally, revenue breakdown, payout
    eligibility, and the status of any existing withdrawal for it."""
    now = datetime.utcnow()
    events = (
        db.query(Event)
        .filter(Event.host_id == host_id, Event.gate_unlocked.is_(True))
        .order_by(Event.start_date.desc())
        .all()
    )

    withdrawals = {
        w.event_id: w
        for w in db.query(Withdrawal).filter(Withdrawal.host_id == host_id).all()
    }

    rows = []
    for event in events:
        started_at = _payout_clock_start(event)
        eligible_at = (started_at + PAYOUT_ELIGIBILITY_DELAY) if started_at else None
        is_ended_24h = bool(eligible_at and now >= eligible_at)

        supposed, came = _supposed_and_came(db, event)
        gross, platform_cut, host_amount = _revenue_breakdown(event)

        w = withdrawals.get(event.id)
        withdrawal_status = w.status if w else None

        rows.append({
            "event_id": str(event.id),
            "title": event.title,
            "venue_date": event.start_date.isoformat() if event.start_date else None,
            "started_at": started_at.isoformat() if started_at else None,
            "eligible_at": eligible_at.isoformat() if eligible_at else None,
            "is_ended_24h": is_ended_24h,
            "supposed_count": supposed,
            "came_count": came,
            "gross_revenue": gross,
            "platform_cut": platform_cut,
            "host_payout_amount": host_amount,
            # "unpaid" = eligible, nothing requested yet -> Request Payout
            # button becomes active. Any other state mirrors the
            # withdrawal's own status. "settled" once paid.
            "payout_status": (
                "settled" if withdrawal_status == "paid" else
                withdrawal_status if withdrawal_status else
                ("unpaid" if is_ended_24h else "not_eligible_yet")
            ),
            "withdrawal_id": str(w.id) if w else None,
            "mpesa_code": w.mpesa_code if w else None,
            "paid_at": w.paid_at.isoformat() if (w and w.paid_at) else None,
            # BUG FIX: host_dashboard.js's "awaiting_host_confirmation" card
            # (what the host sees after admin presses Message) and the
            # "denied_by_host" edit-and-resubmit form both read
            # row.mpesa_paybill / bank_name / account_number / account_name
            # directly off this response — but this endpoint never actually
            # included them. The confirm/deny buttons still worked (they
            # only need withdrawal_id), but the host never saw what bank/
            # M-Pesa details were on file, and — worse — the edit form's
            # inputs always pre-filled blank, so a host who resubmitted
            # without manually retyping every field wiped out previously
            # correct details with empty strings instead of actually
            # updating them. Admin's payout list reads these same columns
            # straight off the Withdrawal row (see admin.py's
            # _serialize_withdrawal), so it was faithfully showing exactly
            # what got resubmitted — including the accidental blanks.
            "mpesa_paybill": w.mpesa_paybill if w else None,
            "bank_name": w.bank_name if w else None,
            "account_number": w.account_number if w else None,
            "account_name": w.account_name if w else None,
            "bank_business_number": w.bank_business_number if w else None,
        })
    return rows


def create_event_payout_request(db: Session, host, event_id):
    event = db.query(Event).filter(Event.id == event_id, Event.host_id == host.id).first()
    if event is None:
        raise ValueError("Event not found")
    if not event.gate_unlocked:
        raise ValueError("This event's final list hasn't been sent to the Live Gate yet")

    started_at = _payout_clock_start(event)
    if not started_at or datetime.utcnow() < started_at + PAYOUT_ELIGIBILITY_DELAY:
        raise ValueError("Payout unlocks 24 hours after the event starts")

    existing = (
        db.query(Withdrawal)
        .filter(Withdrawal.event_id == event.id, Withdrawal.status.in_(ACTIVE_WITHDRAWAL_STATUSES))
        .first()
    )
    if existing:
        raise ValueError("A payout request for this event is already in progress")

    gross, platform_cut, host_amount = _revenue_breakdown(event)
    if host_amount <= 0:
        raise ValueError("No payout available for this event yet")

    withdrawal = Withdrawal(
        host_id=host.id,
        event_id=event.id,
        amount=host_amount,
        gross_revenue=gross,
        platform_cut=platform_cut,
        host_payout_amount=host_amount,
        status="requested",
        bank_name=getattr(host, "bank_name", None),
        account_number=getattr(host, "account_number", None),
        account_name=getattr(host, "account_name", None),
        bank_business_number=getattr(host, "bank_business_number", None),
        mpesa_paybill=getattr(host, "mpesa_paybill", None),
        requested_at=datetime.utcnow(),
    )
    db.add(withdrawal)
    db.flush()  # assigns withdrawal.id without committing yet, so the
                # notifications below can reference the real id directly

    from app.models.user import User
    admins_module_users = db.query(User).filter(User.is_admin.is_(True)).all()
    for admin_user in admins_module_users:
        db.add(Notification(
            user_id=admin_user.id,
            type="payout_requested",
            title=f"Payout requested — {event.title}",
            body=(
                f"{getattr(host, 'username', None) or host.full_name} requested payout for "
                f"\"{event.title}\". Gross KES {gross:,.2f}, our 12% cut KES {platform_cut:,.2f}, "
                f"host expects KES {host_amount:,.2f}. Press Message to send them the bank "
                f"details for confirmation."
            ),
            data={
                "withdrawal_id": str(withdrawal.id),
                "event_id": str(event.id),
                "gross_revenue": gross,
                "platform_cut": platform_cut,
                "host_payout_amount": host_amount,
            },
            context="user",  # admin's own account, not the host inbox
        ))

    db.commit()
    db.refresh(withdrawal)
    return withdrawal


def message_host_for_payout(db: Session, withdrawal: Withdrawal, admin_id):
    if withdrawal.status != "requested":
        raise ValueError("This request isn't awaiting a message right now")

    withdrawal.status = "awaiting_host_confirmation"
    withdrawal.messaged_at = datetime.utcnow()
    withdrawal.admin_id = admin_id
    db.add(withdrawal)

    event = db.query(Event).filter(Event.id == withdrawal.event_id).first()
    event_title = event.title if event else "your event"

    bank_lines = []
    if withdrawal.mpesa_paybill:
        bank_lines.append(f"M-Pesa Paybill/Till: {withdrawal.mpesa_paybill}")
    if withdrawal.bank_name:
        bank_lines.append(f"Bank: {withdrawal.bank_name}")
    if withdrawal.account_number:
        bank_lines.append(f"Account No: {withdrawal.account_number}")
    if withdrawal.account_name:
        bank_lines.append(f"Account Name: {withdrawal.account_name}")
    if withdrawal.bank_business_number:
        bank_lines.append(f"Business No: {withdrawal.bank_business_number}")
    bank_summary = " · ".join(bank_lines) if bank_lines else "No bank/M-Pesa details on file"

    db.add(Notification(
        user_id=withdrawal.host_id,
        type="payout_confirmation_request",
        title=f"Confirm payout details — {event_title}",
        body=(
            f"Event: {event_title}\nExpected payment: KES {withdrawal.host_payout_amount:,.2f}\n"
            f"{bank_summary}\n\nConfirm these details are correct to proceed, or deny to edit "
            f"your bank/M-Pesa details first."
        ),
        data={
            "withdrawal_id": str(withdrawal.id),
            "event_id": str(withdrawal.event_id) if withdrawal.event_id else None,
            "event_title": event_title,
            "host_payout_amount": withdrawal.host_payout_amount,
            "bank_name": withdrawal.bank_name,
            "account_number": withdrawal.account_number,
            "account_name": withdrawal.account_name,
            "bank_business_number": withdrawal.bank_business_number,
            "mpesa_paybill": withdrawal.mpesa_paybill,
        },
        context="host",
    ))

    db.commit()
    db.refresh(withdrawal)
    return withdrawal


def respond_to_payout_message(db: Session, withdrawal: Withdrawal, confirm: bool):
    if withdrawal.status != "awaiting_host_confirmation":
        raise ValueError("This request isn't waiting on your confirmation")

    withdrawal.host_responded_at = datetime.utcnow()
    if confirm:
        withdrawal.status = "confirmed_by_host"
    else:
        withdrawal.status = "denied_by_host"
    db.add(withdrawal)

    if withdrawal.admin_id:
        db.add(Notification(
            user_id=withdrawal.admin_id,
            type="payout_host_response",
            title="Host responded to payout message",
            body=(
                f"Host {'confirmed' if confirm else 'denied'} the payout details for withdrawal "
                f"{withdrawal.id}."
                + ("" if confirm else " They'll edit their bank/M-Pesa details and resubmit.")
            ),
            data={"withdrawal_id": str(withdrawal.id), "confirmed": confirm},
            context="user",  # admin's own account, not the host inbox
        ))

    db.commit()
    db.refresh(withdrawal)
    return withdrawal


def resubmit_payout_request(db: Session, host, withdrawal: Withdrawal):
    if withdrawal.status != "denied_by_host":
        raise ValueError("Only a denied request can be resubmitted")

    # Only bank/M-Pesa details are refreshed on resubmit — everything else
    # about the original request (event, revenue breakdown) stays the same.
    withdrawal.bank_name = getattr(host, "bank_name", None)
    withdrawal.account_number = getattr(host, "account_number", None)
    withdrawal.account_name = getattr(host, "account_name", None)
    withdrawal.bank_business_number = getattr(host, "bank_business_number", None)
    withdrawal.mpesa_paybill = getattr(host, "mpesa_paybill", None)
    withdrawal.status = "requested"
    withdrawal.messaged_at = None
    withdrawal.host_responded_at = None
    withdrawal.requested_at = datetime.utcnow()
    db.add(withdrawal)

    from app.models.user import User
    for admin_user in db.query(User).filter(User.is_admin.is_(True)).all():
        db.add(Notification(
            user_id=admin_user.id,
            type="payout_requested",
            title="Payout re-requested (bank details updated)",
            body=(
                f"Host updated their bank/M-Pesa details and re-requested payout of "
                f"KES {withdrawal.host_payout_amount:,.2f}."
            ),
            data={"withdrawal_id": str(withdrawal.id), "event_id": str(withdrawal.event_id) if withdrawal.event_id else None},
            context="user",  # admin's own account, not the host inbox
        ))

    db.commit()
    db.refresh(withdrawal)
    return withdrawal


def mark_payout_paid(db: Session, withdrawal: Withdrawal, admin_id, mpesa_code: str):
    if withdrawal.status != "confirmed_by_host":
        raise ValueError("Host hasn't confirmed this payout yet")
    if not mpesa_code or not mpesa_code.strip():
        raise ValueError("An M-Pesa confirmation code is required")

    withdrawal.status = "paid"
    withdrawal.mpesa_code = mpesa_code.strip().upper()
    withdrawal.paid_at = datetime.utcnow()
    withdrawal.processed_at = withdrawal.paid_at
    withdrawal.admin_id = admin_id
    db.add(withdrawal)

    event = db.query(Event).filter(Event.id == withdrawal.event_id).first()
    event_title = event.title if event else "your event"

    db.add(Notification(
        user_id=withdrawal.host_id,
        type="payout_paid",
        title=f"Payout sent — {event_title}",
        body=(
            f"KES {withdrawal.host_payout_amount:,.2f} for \"{event_title}\" has been sent to your "
            f"M-Pesa/bank details. M-Pesa code: {withdrawal.mpesa_code} — keep this as your proof "
            f"of payment."
        ),
        data={
            "withdrawal_id": str(withdrawal.id),
            "mpesa_code": withdrawal.mpesa_code,
            "amount": withdrawal.host_payout_amount,
        },
        context="host",
    ))

    db.commit()
    db.refresh(withdrawal)
    return withdrawal


def list_pending_withdrawals(db: Session):
    """Everything still moving through the pipeline — used by the admin
    Payout Requests page."""
    return (
        db.query(Withdrawal)
        .filter(Withdrawal.status.in_(["requested", "awaiting_host_confirmation", "confirmed_by_host"]))
        .order_by(Withdrawal.requested_at.asc())
        .all()
    )


def list_paid_withdrawals(db: Session):
    """Settled payouts — the Host Financials / Bash Financials ledger."""
    return (
        db.query(Withdrawal)
        .filter(Withdrawal.status == "paid")
        .order_by(Withdrawal.paid_at.desc())
        .all()
    )