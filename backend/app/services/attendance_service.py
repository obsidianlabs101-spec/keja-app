"""
The "are you going?" pipeline described by the product spec:

  T-2h  -> every paid buyer gets a notification asking Yes/No.
  Yes   -> confirmation_status='confirmed'; funds stay locked in for payout.
  No    -> refunded immediately, minus a 12% processing fee; ticket freed
           back into circulation for someone else to buy.
  T-1h  -> anyone who never answered is treated as a YES — their ticket is
           auto-confirmed and no refund is issued (silence defaults to
           "still going"). Whatever's left (confirmation_status='confirmed')
           is frozen as the event's final list and AUTOMATICALLY verified
           and pushed to the host's Live Gate — no admin action, ever
           (see freeze_and_open_gate_for_event below). Admins just get a
           read-only heads-up notification of what was sent.

Driven by a periodic APScheduler job (see main.py). Every function here is
safe to call repeatedly/concurrently: each step is gated by a status or
timestamp check, so re-running the sweep never double-charges, double-
refunds, or double-notifies.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import SessionLocal
from app.models.booking import Booking
from app.models.event import Event
from app.models.payment import Payment
from app.models.ticket import Ticket
from app.models.notification import Notification
from app.models.user import User
from app.models.ticket_waitlist import TicketWaitlist
from app.services.push_service import send_web_push

REFUND_FEE_RATE = 0.12  # 12% cut on decline / no-response refunds
REMINDER_WINDOW = timedelta(hours=2)
FINAL_LIST_WINDOW = timedelta(hours=1)


def _wants_still_going_check(user) -> bool:
    """Reads User.notification_preferences directly (same pattern as
    booking_service._wants_ticket_confirmation) — default is True, matching
    _NOTIF_PREF_DEFAULTS in app/api/v1/users.py, so someone who's never
    opened the preferences panel still gets asked. This only gates the
    notification/push itself — the confirmation_status/deadline bookkeeping
    in send_t2_reminders always runs regardless, so the T-1h auto-confirm
    silence-means-still-going rule keeps working the same for everyone."""
    import json as _json
    raw = getattr(user, "notification_preferences", None)
    if not raw:
        return True
    try:
        prefs = _json.loads(raw)
        if isinstance(prefs, dict) and "still_going_check" in prefs:
            return bool(prefs["still_going_check"])
    except (ValueError, TypeError):
        pass
    return True

# Ticket sales genuinely close 2 hours before the event starts — same
# moment the T-2 "are you going?" reminder fires. This used to be tied to
# the host-set `ticket_deadline` field and an admin's manual "Close Ticket
# Sales" button, which nobody could keep straight against the T-1 final
# list — and worse, nothing ever actually enforced it, so buyers could
# purchase right up until the event regardless. `ticket_deadline` is now
# purely informational (fires a heads-up notification, see
# send_ticket_deadline_notice below) and doesn't gate anything; this
# window is what bookings.py actually checks before allowing a purchase.
SALES_CLOSE_WINDOW = timedelta(hours=2)


def verify_and_unlock_gate(db: Session, event: Event) -> dict:
    """Cross-checks every paid ticket for this event really belongs to it
    (and to a real payment), tallies the verified total, opens the
    host's Live Gate, and returns the tally. Called only by
    freeze_and_open_gate_for_event (below) — there is no admin action
    anywhere in this flow; the T-1hr sweep and the on-demand safety-net
    check are the only two triggers, and both share this exact same
    verification logic. Safe to call more than once — re-verifies and
    re-tallies rather than assuming the first pass was final."""
    rows = (
        db.query(Ticket, Booking, Payment)
        .join(Booking, Booking.id == Ticket.booking_id)
        .outerjoin(Payment, Payment.booking_id == Booking.id)
        .filter(Booking.event_id == event.id, Booking.status == "booked")
        .all()
    )

    verified_ticket_ids = []
    mismatched_ticket_ids = []
    seen_booking_ids = set()
    tally_amount = 0.0

    for ticket, booking, payment in rows:
        if str(booking.event_id) != str(event.id):
            mismatched_ticket_ids.append(str(ticket.id))
            continue
        if payment is not None and str(payment.booking_id) != str(booking.id):
            mismatched_ticket_ids.append(str(ticket.id))
            continue

        verified_ticket_ids.append(str(ticket.id))
        if booking.id not in seen_booking_ids:
            seen_booking_ids.add(booking.id)
            tally_amount += float(booking.total_amount or 0)

    tally_count = len(verified_ticket_ids)

    event.gate_unlocked = True
    event.tickets_sent_at = datetime.utcnow()
    event.final_tally_amount = tally_amount
    event.final_ticket_tally = tally_count
    db.add(event)

    return {
        "tickets_verified": tally_count,
        "amount_tallied": tally_amount,
        "mismatched_flagged": len(mismatched_ticket_ids),
    }


def _events_starting_within(db: Session, window_start, window_end):
    return (
        db.query(Event)
        .filter(
            Event.status == "published",
            Event.start_date.isnot(None),
            Event.start_date > window_start,
            Event.start_date <= window_end,
        )
        .all()
    )


def _events_due_for_final_list(db: Session, upper_bound):
    """Like _events_starting_within, but WITHOUT the `start_date > now`
    lower bound — used only for the T-1hr final-list/gate-unlock step.

    Bug this fixes: _events_starting_within requires start_date to still
    be in the future relative to whenever the sweep happens to run. The
    scheduler only fires every 5 minutes, so any event whose T-1hr window
    was missed — created with less than an hour of lead time before its
    start, a scheduler restart/deploy landing mid-window, a slow sweep,
    etc. — has start_date <= now by the time it's next checked, fails
    that `>` comparison, and is excluded FOREVER. The event goes "live"
    on the host dashboard with gate_unlocked stuck False permanently —
    there is no admin action that can free it, since none exists in this
    flow, so this was a genuine dead end for the host until this
    lower-bound removal fixed it.
    final_list_locked_at IS NULL is what actually guards against
    reprocessing an event twice; it's a safe, idempotent condition to
    catch up on regardless of how overdue the event now is.
    """
    return (
        db.query(Event)
        .filter(
            Event.status == "published",
            Event.start_date.isnot(None),
            Event.start_date <= upper_bound,
            Event.final_list_locked_at.is_(None),
        )
        .all()
    )


def send_ticket_deadline_notice(db: Session, now=None) -> int:
    """Ticket deadline is informational only — it doesn't close sales or
    do anything to the event. Once it passes, the host (and admins) get a
    one-time heads-up notification so they can see how sales are tracking
    against it. Real sales closing happens automatically at T-2
    (is_sales_closed, above) regardless of this date."""
    now = now or datetime.utcnow()
    events = (
        db.query(Event)
        .filter(
            Event.status == "published",
            Event.ticket_deadline.isnot(None),
            Event.ticket_deadline <= now,
        )
        .all()
    )
    notified = 0
    for event in events:
        if getattr(event, "ticket_deadline_notified_at", None):
            continue  # already notified once for this event

        sold = (
            db.query(func.coalesce(func.sum(Booking.quantity), 0))
            .filter(Booking.event_id == event.id, Booking.status == "booked")
            .scalar()
        ) or 0

        event.ticket_deadline_notified_at = now
        db.add(event)

        db.add(Notification(
            user_id=event.host_id,
            type="ticket_deadline_notice",
            title=f"Ticket deadline reached — {event.title}",
            body=(
                f"Your ticket deadline for \"{event.title}\" has passed — {int(sold)} tickets sold so "
                f"far. This is just a heads-up; sales stay open until 2 hours before the event starts."
            ),
            data={"event_id": str(event.id), "tickets_sold": int(sold)},
            context="host",
        ))
        notified += 1
    if notified:
        db.commit()
    return notified


def send_t2_reminders(db: Session, now=None):
    """For events starting in the next 2h, ping every paid buyer who
    hasn't been asked yet."""
    now = now or datetime.utcnow()
    events = _events_starting_within(db, now, now + REMINDER_WINDOW)
    sent = 0
    for event in events:
        bookings = (
            db.query(Booking)
            .filter(
                Booking.event_id == event.id,
                Booking.status == "booked",
                Booking.confirmation_status == "not_due",
            )
            .all()
        )
        for booking in bookings:
            deadline = event.start_date - FINAL_LIST_WINDOW
            booking.confirmation_status = "awaiting_response"
            booking.reminder_sent_at = now
            booking.confirmation_deadline = deadline
            db.add(booking)
            t2_title = f"Still going to {event.title}?"
            t2_body = (
                f"{event.title} starts in about 2 hours. Confirm you're going to lock in your "
                f"ticket, or let us know if you can't make it for an automatic refund (a 12% "
                f"processing fee applies). No response by {deadline.strftime('%H:%M')} will be "
                f"treated as a Yes — your ticket stays confirmed automatically and no refund is "
                f"issued."
            )
            # confirmation_status/deadline are set above unconditionally —
            # the T-1h sweep still needs those to auto-confirm on silence
            # either way. Only the notification/push itself is gated by
            # the user's preference.
            if _wants_still_going_check(booking.user):
                db.add(Notification(
                    user_id=booking.user_id,
                    type="attendance_check",
                    title=t2_title,
                    body=t2_body,
                    data={
                        "event_id": str(event.id),
                        "booking_id": str(booking.id),
                        "deadline": deadline.isoformat(),
                    },
                    context="user",
                ))
                # Real phone/OS notification-tray alert — this is the one that
                # needs to reach people even if the app isn't open. The two
                # actions let someone answer straight from the notification
                # instead of having to open the app first — sw.js's
                # notificationclick handler turns a tap on either into a
                # quickResponse=going/not_going deep link, and cheki.js's
                # handleQuickAttendanceResponse() submits it automatically the
                # instant the app opens.
                send_web_push(
                    db, booking.user, title=t2_title, body=t2_body,
                    data={"event_id": str(event.id), "booking_id": str(booking.id), "type": "attendance_check"},
                    image=event.poster_url,
                    tag=f"attendance-{booking.id}",
                    actions=[
                        {"action": "going", "title": "✅ I'm going"},
                        {"action": "not_going", "title": "❌ Can't make it"},
                    ],
                )
            sent += 1
    if sent:
        db.commit()
    return sent


def is_sales_closed(event: Event, now=None) -> bool:
    """True once we're within 2 hours of the event starting. Kept for
    anything that just wants a simple yes/no; bookings.py itself uses the
    more nuanced can_purchase() below, which allows reclaimed capacity
    through in the T-2..T-1 window."""
    now = now or datetime.utcnow()
    if not event.start_date:
        return False
    return now >= event.start_date - SALES_CLOSE_WINDOW


def purchase_window_phase(event: Event, now=None) -> str:
    """'open' (normal sales), 'reclaim' (T-2..T-1 — closed to the general
    public, but reclaimed_capacity from refunds can be bought by waitlist
    subscribers), or 'closed' (past T-1, no purchases at all)."""
    now = now or datetime.utcnow()
    if not event.start_date:
        return "open"
    close_at = event.start_date - SALES_CLOSE_WINDOW
    hard_close_at = event.start_date - FINAL_LIST_WINDOW
    if now >= hard_close_at:
        return "closed"
    if now >= close_at:
        return "reclaim"
    return "open"


def can_purchase(db: Session, event: Event, quantity: int, now=None) -> tuple[bool, str]:
    """The actual gate bookings.py checks before letting a purchase
    through. Returns (allowed, reason_if_not)."""
    now = now or datetime.utcnow()
    phase = purchase_window_phase(event, now)

    if phase == "closed":
        return False, "Ticket sales for this event have closed (1 hour before start)."

    if phase == "reclaim":
        available = int(getattr(event, "reclaimed_capacity", 0) or 0)
        if available < quantity:
            return False, (
                "General sales closed 2 hours before this event. "
                "Tap Notify Me and we'll ping you if a spot opens up."
            )
        # Claim it now so two buyers can't both grab the same reclaimed seat.
        event.reclaimed_capacity = available - quantity
        db.add(event)
        return True, ""

    return True, ""


def notify_waitlist_of_reopening(db: Session, event: Event, reclaimed_qty: int, now=None):
    """A decline/no-show refund just freed up `reclaimed_qty` ticket(s)
    during the T-2..T-1 window — ping everyone on this event's waitlist
    immediately so they can grab it before it's gone again."""
    now = now or datetime.utcnow()
    subscribers = db.query(TicketWaitlist).filter(TicketWaitlist.event_id == event.id).all()
    for sub in subscribers:
        db.add(Notification(
            user_id=sub.user_id,
            type="waitlist_ticket_available",
            title=f"A ticket just opened up — {event.title}",
            body=(
                f"{reclaimed_qty} ticket(s) just came back into circulation for \"{event.title}\". "
                f"Grab it now before someone else does — first come, first served."
            ),
            data={"event_id": str(event.id), "reclaimed": reclaimed_qty},
            context="user",
        ))
        sub.last_notified_at = now
        db.add(sub)


def _refund_booking(db: Session, booking: Booking, now, reason: str):
    """Shared refund path for an explicit No and an auto-refund on silence.
    Refunds (total - 12% fee) and frees the ticket back into circulation."""
    payment = (
        db.query(Payment)
        .filter(Payment.booking_id == booking.id, Payment.status == "paid")
        .order_by(Payment.created_at.desc())
        .first()
    )
    # Refund off what the buyer actually paid (payment.amount, or
    # buyer_total_amount if the payment row is missing for some reason) —
    # NOT booking.total_amount, which is the host's raw pre-markup value
    # and would refund 12% too little. See the column comments on Booking.
    gross = float(
        (payment.amount if payment else None)
        or booking.buyer_total_amount
        or (float(booking.total_amount or 0) * 1.12)
    )
    fee = round(gross * REFUND_FEE_RATE, 2)
    refund_amount = round(gross - fee, 2)

    booking.status = "refunded"
    booking.confirmation_status = "refunded"
    booking.refunded_at = now
    booking.refund_fee_amount = fee
    booking.refund_amount = refund_amount
    booking.refund_payout_status = "requested"
    booking.updated_at = now
    db.add(booking)

    if payment:
        payment.refunded_amount = refund_amount
        payment.refund_fee_amount = fee
        payment.refunded_at = now
        db.add(payment)

    # Freeing the booking from "paid" already makes the capacity check in
    # bookings.py treat this seat as available again. Marking the physical
    # ticket "refunded" additionally guarantees it can never be scanned in
    # at the gate even if someone still has the QR code saved.
    ticket = db.query(Ticket).filter(Ticket.booking_id == booking.id).first()
    if ticket:
        ticket.status = "refunded"
        ticket.updated_at = now
        db.add(ticket)

    # If this refund lands in the T-2..T-1 window, the freed quantity goes
    # back into circulation as reclaimed_capacity — purchasable only by
    # waitlist subscribers until T-1, when it's wiped for good.
    event = db.query(Event).filter(Event.id == booking.event_id).first()
    if event and purchase_window_phase(event, now) == "reclaim":
        qty = int(booking.quantity or 1)
        event.reclaimed_capacity = int(getattr(event, "reclaimed_capacity", 0) or 0) + qty
        db.add(event)
        notify_waitlist_of_reopening(db, event, qty, now)

    db.add(Notification(
        user_id=booking.user_id,
        type="refund_processed",
        title="Ticket refunded",
        body=(
            f"Your ticket was refunded ({reason}). KES {refund_amount:,.2f} is on its way back to "
            f"you (KES {fee:,.2f} processing fee applied). The ticket has been released back for sale."
        ),
        data={"booking_id": str(booking.id), "refund_amount": refund_amount, "fee": fee},
        context="user",
    ))


def respond_attendance(db: Session, booking: Booking, going: bool, now=None) -> Booking:
    """Called by the buyer-facing endpoint when they answer Yes/No."""
    now = now or datetime.utcnow()
    if booking.confirmation_status not in ("awaiting_response", "not_due"):
        return booking  # already resolved (e.g. already refunded) — no-op

    if going:
        booking.confirmation_status = "confirmed"
        booking.confirmed_at = now
        booking.updated_at = now
        db.add(booking)
        db.add(Notification(
            user_id=booking.user_id,
            type="attendance_confirmed",
            title="You're locked in",
            body="Thanks for confirming — your ticket and funds are secured for the event.",
            data={"booking_id": str(booking.id)},
            context="user",
        ))
    else:
        _refund_booking(db, booking, now, reason="you said you weren't going")

    db.commit()
    db.refresh(booking)
    return booking


def auto_confirm_unconfirmed(db: Session, now=None) -> int:
    """T-1hr sweep: anyone who never answered the T-2hr prompt defaults to
    a YES — their booking is auto-confirmed and no refund is issued. This
    is the intentional default (silence = still going); only an explicit
    "No" response ever triggers a refund (see respond_attendance)."""
    now = now or datetime.utcnow()
    overdue = (
        db.query(Booking)
        .filter(
            Booking.confirmation_status == "awaiting_response",
            Booking.confirmation_deadline.isnot(None),
            Booking.confirmation_deadline <= now,
        )
        .all()
    )
    for booking in overdue:
        booking.confirmation_status = "confirmed"
        booking.confirmed_at = now
        booking.updated_at = now
        db.add(booking)
        ac_title = "You're locked in"
        ac_body = (
            "You didn't respond to our 'still going?' check, so by default your ticket stays "
            "confirmed and no refund was issued. Your funds are secured for the event."
        )
        db.add(Notification(
            user_id=booking.user_id,
            type="attendance_auto_confirmed",
            title=ac_title,
            body=ac_body,
            data={"booking_id": str(booking.id)},
            context="user",
        ))
        send_web_push(
            db, booking.user, title=ac_title, body=ac_body,
            data={"booking_id": str(booking.id), "type": "attendance_auto_confirmed"},
        )
    if overdue:
        db.commit()
    return len(overdue)


def freeze_and_open_gate_for_event(db: Session, event: Event, now=None) -> bool:
    """Freezes the confirmed-going list and auto-opens the Live Gate for a
    SINGLE event, if it's due (published, within FINAL_LIST_WINDOW of
    starting or already started) and hasn't been processed yet. Returns
    True if it just unlocked the gate, False if there was nothing to do
    (not due yet, or already locked/unlocked).

    This is the shared body used by:
      1. send_t1_final_list's batch sweep (the scheduler, every 5 min), and
      2. an on-demand safety-net check wherever an event gets looked up
         (see events.py's live_gate_summary/gate_checkin and stream.py's
         _map_feed_item_to_reel) — so the gate opens the moment anyone
         views the event even if the scheduler missed its window or
         isn't running at all. Two independent triggers for the same
         idempotent action means there's no single point of failure for
         "why didn't my gate open automatically". There is no admin
         action anywhere in this path.

    The gate-unlock itself is committed on its own, before anything else
    is attempted — see the try/except below for why.
    """
    now = now or datetime.utcnow()
    if getattr(event, "final_list_locked_at", None):
        return False  # already frozen for this event
    if event.status != "published" or not event.start_date:
        return False
    if event.start_date > now + FINAL_LIST_WINDOW:
        return False  # not due yet — real T-1hr check, not "always unlock on view"

    confirmed = (
        db.query(Booking)
        .filter(Booking.event_id == event.id, Booking.confirmation_status == "confirmed")
        .all()
    )
    count = sum(b.quantity or 0 for b in confirmed)
    amount = sum(float(b.total_amount or 0) for b in confirmed)

    event.final_list_locked_at = now
    event.reclaimed_capacity = 0
    db.add(event)

    # Automatically verify + open the Live Gate. This IS the function's
    # one essential job, so it's committed here on its own — before the
    # notification code below gets anywhere near it. Notifications are
    # FYI only; a bug or bad row in them must never be able to roll back
    # a gate that's already been verified and opened, which is exactly
    # what would happen if this were all one commit at the end.
    tally = verify_and_unlock_gate(db, event)
    db.commit()

    # Best-effort only, from here down. If anything below raises, the
    # gate stays open (already committed above) — we just roll back the
    # unsent notifications and log it, instead of letting it silently
    # re-lock a host out with no visible error.
    try:
        admins = db.query(User).filter(User.is_admin.is_(True)).all()
        for admin in admins:
            db.add(Notification(
                user_id=admin.id,
                type="final_list_sent",
                title=f"Final list auto-sent — {event.title}",
                body=(
                    f"{event.title} starts within the hour. {tally['tickets_verified']} verified "
                    f"tickets (KES {tally['amount_tallied']:,.2f}) were automatically sent to the "
                    f"host's Live Gate."
                    + (f" {tally['mismatched_flagged']} mismatched ticket(s) were flagged and excluded." if tally['mismatched_flagged'] else "")
                ),
                data={
                    "event_id": str(event.id),
                    "confirmed_count": count,
                    "confirmed_amount": amount,
                    "tickets_verified": tally["tickets_verified"],
                    "amount_tallied": tally["amount_tallied"],
                },
                context="user",  # admin's own account, not a host inbox
            ))

        # Tell the host their gate is live, what they're owed, and when
        # they'll be able to request it (24h after the event STARTS).
        eligible_at = event.start_date + timedelta(hours=24) if event.start_date else None
        eligible_note = (
            f" You'll be able to request payout starting {eligible_at.strftime('%b %d, %Y at %H:%M')} UTC "
            f"(24 hours after doors open)."
            if eligible_at else ""
        )
        db.add(Notification(
            user_id=event.host_id,
            type="live_gate_ready",
            title=f"Live Gate is open — {event.title}",
            body=(
                f"{tally['tickets_verified']} tickets verified · KES {tally['amount_tallied']:,.2f} "
                f"confirmed. Your gate is now live and ready to check guests in. That's your expected "
                f"payout for this event.{eligible_note}"
            ),
            data={
                "event_id": str(event.id),
                "tickets_sent": tally["tickets_verified"],
                "amount": tally["amount_tallied"],
                "eligible_at": eligible_at.isoformat() if eligible_at else None,
            },
            context="host",
        ))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"⚠️ Live Gate opened for event {event.id}, but its notifications failed to send: {e}")

    return True


def send_t1_final_list(db: Session, now=None) -> int:
    """T-1hr sweep: freeze the confirmed-going list for events starting
    within the next hour, then AUTOMATICALLY verify it and push it to
    the host's Live Gate — no admin action, ever. Admins still get a
    read-only notification with the full details (so they know exactly
    what was sent and to whom), and the host gets a heads-up with their
    expected payout and when they'll be able to request it. An admin can
    open the event in the panel and see the 'Live Gate unlocked' state,
    but there is nothing for them to click or approve.

    Thin wrapper around freeze_and_open_gate_for_event — see that
    function for the actual per-event logic, which is also used as an
    on-demand safety net independent of this scheduled sweep."""
    now = now or datetime.utcnow()
    events = _events_due_for_final_list(db, now + FINAL_LIST_WINDOW)
    locked = 0
    for event in events:
        if freeze_and_open_gate_for_event(db, event, now=now):
            locked += 1
    return locked


def run_attendance_sweep():
    """Entry point for the scheduler — owns its own DB session since it
    runs outside any request/response cycle.

    Each step below has its own try/except + rollback. Previously all
    four shared one try/except, so an exception in an EARLIER step (say,
    a malformed booking breaking the T-2hr reminder pass) silently
    skipped every LATER step too — including send_t1_final_list, the one
    that actually opens hosts' Live Gates — every 5 minutes, for as long
    as that one bad row existed, with nothing to show for it but a
    single generic log line. Isolating each step means a bug anywhere
    else can never take the Live-Gate step down with it."""
    db = SessionLocal()
    reminders = auto_confirms = final_lists = deadline_notices = rating_prompts = 0
    try:
        try:
            reminders = send_t2_reminders(db)
        except Exception as e:
            print(f"⚠️ Attendance sweep: T-2hr reminders step failed: {e}")
            db.rollback()

        try:
            auto_confirms = auto_confirm_unconfirmed(db)
        except Exception as e:
            print(f"⚠️ Attendance sweep: auto-confirm step failed: {e}")
            db.rollback()

        try:
            final_lists = send_t1_final_list(db)
        except Exception as e:
            print(f"⚠️ Attendance sweep: final-list/Live-Gate step failed: {e}")
            db.rollback()

        try:
            deadline_notices = send_ticket_deadline_notice(db)
        except Exception as e:
            print(f"⚠️ Attendance sweep: ticket-deadline-notice step failed: {e}")
            db.rollback()

        try:
            # Imported here, not at module top, to avoid a circular import —
            # rating_service imports Event/Booking/Notification same as
            # this module does, but doesn't need anything from here.
            from app.services.rating_service import send_rate_event_prompts
            rating_prompts = send_rate_event_prompts(db)
        except Exception as e:
            print(f"⚠️ Attendance sweep: rating-prompts step failed: {e}")
            db.rollback()

        if reminders or auto_confirms or final_lists or deadline_notices or rating_prompts:
            print(
                f"Attendance sweep: {reminders} reminders sent, "
                f"{auto_confirms} auto-confirmed (no refund), {final_lists} final lists locked, "
                f"{deadline_notices} deadline notices sent, {rating_prompts} rating prompts sent"
            )
        else:
            # Heartbeat only — deliberately quiet (no timestamp spam), but
            # present. Without this, "nothing to do this tick" and "the
            # scheduler isn't running at all" both look identical in the
            # logs, which is exactly the question that matters when a
            # host's Live Gate doesn't open on time.
            print("Attendance sweep: tick — nothing due")
    finally:
        db.close()