from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.booking import Booking
from app.models.event import Event
from app.schemas.booking import BookingCreate, BookingResponse, BookingQRResponse, BookingQuoteResponse, AttendanceResponseRequest
from app.services.booking_service import create_booking, issue_qr_ticket, create_free_booking_fcfs, SoldOutError, InsufficientCreditsError
from app.services.qr_service import generate_encrypted_qr
from app.services.attendance_service import respond_attendance, can_purchase, purchase_window_phase
from app.models.ticket import Ticket
from app.models.payment import Payment
from app.models.user import User
from sqlalchemy import func

router = APIRouter(
    prefix="/bookings",
    tags=["Bookings"],
)


def _to_booking_response(db: Session, booking: Booking) -> BookingResponse:
    """Builds the full BookingResponse, joining in the event/host/payment/QR
    details the frontend tickets page (saved-events.js) needs so it can
    treat this endpoint as the source of truth instead of localStorage —
    a booking made on one device now shows up correctly on any other."""
    event = db.query(Event).filter(Event.id == booking.event_id).first()
    host = None
    if event is not None:
        host = db.query(User).filter(User.id == event.host_id).first()
    payment = (
        db.query(Payment)
        .filter(Payment.booking_id == booking.id, Payment.status == "paid")
        .order_by(Payment.id.desc())
        .first()
    )
    ticket = (
        db.query(Ticket)
        .filter(Ticket.booking_id == booking.id)
        .order_by(Ticket.id.desc())
        .first()
    )
    return BookingResponse(
        booking_id=booking.id,
        booking_reference=booking.booking_reference,
        event_id=booking.event_id,
        user_id=booking.user_id,
        ticket_tier=booking.ticket_tier,
        quantity=booking.quantity,
        unit_price=booking.unit_price,
        total_amount=booking.total_amount,
        buyer_total_amount=booking.buyer_total_amount,
        status=booking.status,
        event_title=getattr(event, "title", None),
        event_venue=getattr(event, "venue_name", None),
        event_date=getattr(event, "start_date", None),
        event_description=getattr(event, "description", None),
        host_username=getattr(host, "username", None),
        mpesa_receipt_number=getattr(payment, "mpesa_receipt_number", None),
        qr_payload=getattr(ticket, "qr_payload", None),
        archived_at=booking.archived_at,
        # Door Notes are a paid-ticket perk — a "booked"/unpaid reservation
        # never sees them, even though the column lives on the event itself.
        door_notes=getattr(event, "door_notes", None) if booking.status == "booked" else None,
    )


def _resolve_tier_price(event: Event, ticket_tier) -> float:
    """Every booking used to be charged event.price flat, completely
    ignoring which tier (Early Bird / VIP / Gate, etc) the buyer actually
    picked — so a VIP buyer paid the same as an Early Bird buyer. Look up
    the chosen tier's real amount in Event.ticket_tiers; fall back to the
    flat price only if there are no tiers or the label didn't match one."""
    if not ticket_tier or not getattr(event, "ticket_tiers", None):
        return float(event.price or 0.0)
    try:
        import json
        tiers = json.loads(event.ticket_tiers)
    except Exception:
        return float(event.price or 0.0)
    for t in tiers or []:
        if str(t.get("label", "")).strip().lower() == str(ticket_tier).strip().lower():
            return float(t.get("amount") or 0.0)
    return float(event.price or 0.0)


@router.post("/create", response_model=BookingResponse)
def create_new_booking(
    data: BookingCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # MVP: any authenticated user can book.
    event = db.query(Event).filter(Event.id == data.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    quantity = int(data.quantity or 1)
    allowed, reason = can_purchase(db, event, quantity)
    if not allowed:
        raise HTTPException(status_code=400, detail=reason)

    price = _resolve_tier_price(event, data.ticket_tier)

    # FREE EVENTS: route through the atomic, row-locked FCFS path — see
    # create_free_booking_fcfs's docstring for why this can't reuse the
    # paid-event flow below. This also marks the booking "booked" directly
    # (skipping pending), so /bookings/{id}/claim-free — still
    # called by some frontend flows right after this — becomes a no-op
    # confirmation rather than the thing that actually flips the status.
    # Booking a free event spends one referral credit instead of cash —
    # see create_free_booking_fcfs's docstring for the full mechanic.
    if price <= 0:
        try:
            booking = create_free_booking_fcfs(
                db,
                user_id=current_user.id,
                event_id=data.event_id,
                quantity=quantity,
                note=data.note,
                ticket_tier=data.ticket_tier,
            )
        except SoldOutError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except InsufficientCreditsError as e:
            raise HTTPException(status_code=402, detail=str(e))
        return _to_booking_response(db, booking)

    subtotal = quantity * price
    # Booking-fee-only model: Bash charges ONLY its 12% booking fee, never
    # the ticket price itself (subtotal) — the ticket price is paid
    # directly to the Host at the venue, off-platform. `total` here is
    # the actual M-Pesa charge amount, so it must be the fee alone, not
    # subtotal + fee. platform_fee/mpesa_fee are kept as a sub-split of
    # that fee for accounting clarity (Safaricom's own transaction cost
    # still applies to whatever amount is actually charged via STK).
    platform_fee = subtotal * 0.10
    mpesa_fee = subtotal * 0.02
    total = platform_fee + mpesa_fee

    # optional: check capacity if set
    if event.capacity is not None:
        sold = db.query(Booking).filter(Booking.event_id == event.id, Booking.status == "booked").with_entities(func.coalesce(func.sum(Booking.quantity), 0)).scalar() or 0
        if sold + quantity > event.capacity:
            raise HTTPException(status_code=400, detail="Not enough tickets available")

    booking = create_booking(
        db,
        user_id=current_user.id,
        event_id=data.event_id,
        ticket_tier=data.ticket_tier,
        quantity=quantity,
        note=data.note,
        unit_price=price,
        buyer_total_amount=total,
    )

    return _to_booking_response(db, booking)


@router.get("/me", response_model=list[BookingResponse])
def get_my_bookings(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    bookings = db.query(Booking).filter(Booking.user_id == current_user.id).all()
    return [_to_booking_response(db, b) for b in bookings]


@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking_detail(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if str(booking.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not your booking")

    return _to_booking_response(db, booking)


@router.post("/{booking_id}/archive", response_model=BookingResponse)
def archive_booking(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Tickets-page 'drag onto history' action. Only ever stamps
    archived_at — never touches status or deletes the row, so a paid
    ticket can be hidden but can never actually disappear, and it stays
    hidden on every device the buyer logs into (not just the one they
    archived it from)."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if str(booking.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not your booking")
    if booking.status != "booked":
        raise HTTPException(status_code=400, detail="Only paid tickets can be archived")

    booking.archived_at = datetime.utcnow()
    db.commit()
    db.refresh(booking)
    return _to_booking_response(db, booking)


@router.post("/{booking_id}/unarchive", response_model=BookingResponse)
def unarchive_booking(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Restores an archived ticket back to the main 'Booked' list."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if str(booking.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not your booking")

    booking.archived_at = None
    db.commit()
    db.refresh(booking)
    return _to_booking_response(db, booking)


@router.post("/{booking_id}/claim-free", response_model=BookingResponse)
def claim_free_booking(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Free (KES 0) events skip M-Pesa entirely — this marks a pending
    booking as paid directly so the buyer can go straight to issue-qr.
    Refuses anything with a real amount attached, so this can never be
    used to dodge payment on a priced ticket."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if str(booking.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not your booking")
    if float(booking.total_amount or 0) > 0:
        raise HTTPException(status_code=400, detail="This booking isn't free — pay via M-Pesa instead")

    if booking.status != "booked":
        booking.status = "booked"
        booking.updated_at = datetime.utcnow()
        db.add(booking)
        db.commit()
        db.refresh(booking)
        from app.services.booking_service import _notify_ticket_confirmed
        _notify_ticket_confirmed(db, booking)

    return BookingResponse(
        booking_id=booking.id,
        booking_reference=booking.booking_reference,
        event_id=booking.event_id,
        user_id=booking.user_id,
        ticket_tier=booking.ticket_tier,
        quantity=booking.quantity,
        unit_price=booking.unit_price,
        total_amount=booking.total_amount,
        buyer_total_amount=booking.buyer_total_amount,
        status=booking.status,
    )


@router.post("/quote", response_model=BookingQuoteResponse)
def quote_booking(
    data: BookingCreate,
    db: Session = Depends(get_db),
):
    event = db.query(Event).filter(Event.id == data.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    phase = purchase_window_phase(event)
    if phase == "closed":
        raise HTTPException(status_code=400, detail="Ticket sales for this event have closed (1 hour before start).")

    quantity = int(data.quantity or 1)
    unit_price = _resolve_tier_price(event, data.ticket_tier)
    subtotal = quantity * unit_price
    # Booking-fee-only model — see the identical comment above in
    # create_booking_endpoint for the full explanation. This quote must
    # show the buyer the real amount they'll actually be charged.
    platform_fee = subtotal * 0.10
    mpesa_fee = subtotal * 0.02
    total = platform_fee + mpesa_fee

    return BookingQuoteResponse(
        event_id=data.event_id,
        ticket_tier=data.ticket_tier,
        quantity=quantity,
        unit_price=unit_price,
        subtotal=subtotal,
        platform_fee=platform_fee,
        mpesa_fee_estimate=mpesa_fee,
        total=total,
    )


@router.post("/{booking_id}/issue-qr", response_model=BookingQRResponse)
def issue_booking_qr(
    booking_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if str(booking.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not your booking")

    # SECURITY: a Ticket row exists from the moment a booking is created
    # (before any payment happens), so this check is the only thing
    # standing between "I created a booking" and "I have a scannable,
    # gate-valid ticket". Without it, anyone could skip payment entirely
    # by calling this endpoint straight after /bookings/create.
    if booking.status != "booked":
        raise HTTPException(
            status_code=400,
            detail="This booking hasn't been paid for yet — complete payment before a ticket can be issued.",
        )

    # Encrypted QR blob payload with full ticket details
    ticket = db.query(Ticket).filter(Ticket.booking_id == booking_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    payload = {
        "ticket_id": str(ticket.id),
        "booking_id": str(booking.id),
        "booking_ref": booking.booking_reference,
        "event_id": str(booking.event_id),
        "user_id": str(booking.user_id),
        "tier": booking.ticket_tier or "Standard",
        "issued_at": int(__import__("time").time()),
    }
    qr_blob = generate_encrypted_qr(payload)

    ticket_resp = issue_qr_ticket(db, booking, qr_blob)

    return BookingQRResponse(
        booking_id=booking.id,
        ticket_id=ticket_resp.id,
        qr_payload=ticket_resp.qr_payload,
        ticket_code=ticket_resp.ticket_code,
        status=ticket_resp.status,
    )


@router.post("/{booking_id}/attendance-response", response_model=BookingResponse)
def submit_attendance_response(
    booking_id: str,
    data: AttendanceResponseRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """The buyer's answer to the T-2hr 'are you still going?' prompt.
    Yes locks the ticket/funds in; No refunds immediately minus the 12%
    processing fee and frees the ticket back into circulation. Safe to
    call more than once — a booking that's already been resolved is
    simply returned as-is."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if str(booking.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not your booking")

    booking = respond_attendance(db, booking, going=data.going)

    return BookingResponse(
        booking_id=booking.id,
        booking_reference=booking.booking_reference,
        event_id=booking.event_id,
        user_id=booking.user_id,
        ticket_tier=booking.ticket_tier,
        quantity=booking.quantity,
        unit_price=booking.unit_price,
        total_amount=booking.total_amount,
        buyer_total_amount=booking.buyer_total_amount,
        status=booking.status,
    )