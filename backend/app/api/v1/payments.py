from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.config import settings
from app.models.booking import Booking
from app.services.mpesa_service import initiate_stk_push, record_successful_payment, query_stk_status, mpesa_configured
from app.schemas.payment import (
    MpesaCallbackRequest,
    MpesaSTKPushRequest,
    MpesaSTKPushResponse,
    DarajaCallbackEnvelope,
    MpesaPaymentStatusResponse,
    ManualPaymentClaimRequest,
)
from app.services.booking_service import finalize_paid_booking
from app.models.payment import Payment
from app.models.platform_settings import get_or_create_platform_settings
from app.services.manual_payment_service import submit_buyer_claim
import uuid as _uuid
from datetime import datetime as _datetime

from app.core.limiter import limiter

router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
)


@router.post("/mpesa/stk-push", response_model=MpesaSTKPushResponse)
@limiter.limit("6/minute")
def mpesa_stk_push(
    request: Request,
    data: MpesaSTKPushRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    booking = db.query(Booking).filter(Booking.id == data.booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your booking")

    if booking.status == "booked":
        raise HTTPException(status_code=400, detail="This booking has already been paid for")

    # SECURITY: never trust a client-supplied payment amount. The old code
    # took `data.amount` straight from the request body and charged
    # whatever the caller sent — e.g. KES 1 on a booking that actually
    # costs KES 5,000 — then marked the *full* booking paid once that
    # smaller amount cleared M-Pesa. The amount charged is now always
    # derived from the booking record itself, which the client cannot
    # influence. `data.amount` is accepted for backward compatibility with
    # older frontend builds but is intentionally ignored.
    #
    # IMPORTANT: this must be buyer_total_amount (host price + 12% checkout
    # markup), NOT total_amount (the host's raw pre-markup value used for
    # payouts). Charging total_amount here was the bug that let buyers pay
    # exactly the host's listed price with the 12% platform/mpesa fee never
    # actually collected, even though every checkout screen displayed and
    # promised the marked-up total. The total_amount*1.12 fallback only
    # covers bookings created before buyer_total_amount existed.
    server_amount = float(booking.buyer_total_amount or (float(booking.total_amount or 0) * 1.12))
    if server_amount <= 0:
        raise HTTPException(status_code=400, detail="This booking has no amount owing")

    settings_row = get_or_create_platform_settings(db)
    account_reference = booking.booking_reference or "BASH"

    # Manual mode is triggered either by the admin's platform-wide toggle,
    # or automatically per-booking if Daraja isn't configured at all — in
    # both of those cases there's no point even attempting a real STK push.
    use_manual = bool(settings_row.manual_payment_mode) or not mpesa_configured()

    if not use_manual:
        try:
            payment = initiate_stk_push(
                db,
                booking_id=booking.id,
                phone_number=data.phone_number,
                amount=server_amount,
                currency=data.currency,
                account_reference=account_reference,
                mpesa_checkout_request_id=None,
            )
            # initiate_stk_push degrades to a local "initiated" stub on a
            # Daraja error rather than raising — that stub would just poll
            # forever with nothing ever prompting the buyer's phone, so
            # fall through to manual mode whenever a real push didn't
            # actually go out.
            if getattr(payment, "sent_real_push", False):
                return {
                    "booking_id": str(payment.booking_id),
                    "payment_id": str(payment.id),
                    "checkout_request_id": str(payment.mpesa_checkout_request_id),
                    "status": payment.status,
                    "mode": "stk",
                }
            payment.status = "abandoned"
            db.add(payment)
            db.commit()
            use_manual = True
        except Exception as e:
            print(f"WARNING: STK push raised, falling back to manual payment mode: {e}")
            use_manual = True

    # Manual mode: no real STK push, just a Payment row parked in
    # "awaiting_manual_payment" until the buyer pastes their code (see
    # POST /payments/mpesa/manual-claim) and it's matched against what
    # the admin pastes in from the real paybill statement.
    payment = Payment(
        booking_id=booking.id,
        provider="mpesa_manual",
        status="awaiting_manual_payment",
        amount=server_amount,
        currency=data.currency,
        mpesa_checkout_request_id=str(_uuid.uuid4()),
        created_at=_datetime.utcnow(),
        updated_at=_datetime.utcnow(),
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    return {
        "booking_id": str(payment.booking_id),
        "payment_id": str(payment.id),
        "checkout_request_id": str(payment.mpesa_checkout_request_id),
        "status": payment.status,
        "mode": "manual",
        "paybill_number": settings.MPESA_SHORTCODE,
        "account_reference": account_reference,
    }


@router.post("/mpesa/manual-claim")
@limiter.limit("10/minute")
def mpesa_manual_claim(
    request: Request,
    data: ManualPaymentClaimRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """The buyer has paid the paybill by hand and is telling us their code
    (or pasting the whole confirmation SMS). This alone never marks a
    booking paid — it's only one half of the match; see
    manual_payment_service.submit_buyer_claim for the other half (what an
    admin pastes in from the real statement)."""
    payment = (
        db.query(Payment)
        .filter(Payment.mpesa_checkout_request_id == data.checkout_request_id, Payment.provider == "mpesa_manual")
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    booking = db.query(Booking).filter(Booking.id == payment.booking_id).first()
    if not booking or str(booking.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not your payment")

    if payment.status == "paid":
        return {"booking_id": str(payment.booking_id), "payment_id": str(payment.id), "status": "paid"}

    if not (data.message or "").strip():
        raise HTTPException(status_code=400, detail="Paste your M-Pesa code or confirmation message")

    payment = submit_buyer_claim(db, payment, data.message)

    return {
        "booking_id": str(payment.booking_id),
        "payment_id": str(payment.id),
        "status": payment.status,
        "code_recognized": bool(payment.buyer_claimed_code),
    }


def _client_ip(request: Request) -> str:
    """Best-effort real client IP behind a reverse proxy/load balancer.
    Trusts X-Forwarded-For only because MPESA_ALLOWED_IPS is opt-in and
    the deployer is expected to configure their proxy to set this header
    correctly (and to not let it be spoofed from outside)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


@router.post("/mpesa/callback")
def mpesa_callback(
    data: DarajaCallbackEnvelope,
    request: Request,
    db: Session = Depends(get_db),
):
    """This is the URL Safaricom's Daraja servers POST to once the customer
    completes (or cancels/times out) the STK push prompt on their phone. Must
    be publicly reachable (see MPESA_CALLBACK_URL) — Safaricom cannot reach a
    LAN address.

    SECURITY: Safaricom doesn't sign callbacks by default, so this endpoint
    is unauthenticated by necessity. As a mitigation, if MPESA_ALLOWED_IPS
    is set in .env (comma-separated), only requests from those source IPs
    are accepted — set it to Safaricom's published Daraja IP ranges for
    production. Left unset by default so this doesn't break deployments
    behind proxies/tunnels (e.g. ngrok in sandbox) until you've confirmed
    your real client-IP header setup.
    """
    if settings.MPESA_ALLOWED_IPS:
        client_ip = _client_ip(request)
        if client_ip not in settings.MPESA_ALLOWED_IPS:
            print(f"⚠️  Rejected M-Pesa callback from disallowed IP: {client_ip}")
            raise HTTPException(status_code=403, detail="Forbidden")

    cb = data.Body.stkCallback
    receipt_number = None
    if cb.CallbackMetadata:
        for item in cb.CallbackMetadata.Item:
            if item.Name == "MpesaReceiptNumber":
                receipt_number = str(item.Value) if item.Value is not None else None

    # SECURITY FIX: this endpoint is necessarily unauthenticated (see the
    # docstring above) and MPESA_ALLOWED_IPS is opt-in, off by default —
    # meaning, without this check, ANYONE could POST a fake "ResultCode: 0"
    # here for a CheckoutRequestID they obtained by starting (but never
    # completing) a real payment on their own account, and get a free
    # ticket with no money ever moving. Before trusting a success claim,
    # independently ask Safaricom's own servers — using this app's own
    # Daraja credentials, which an attacker doesn't have — whether the
    # transaction genuinely completed. This can't be spoofed the way the
    # callback body itself can, because it isn't the attacker supplying
    # the answer anymore, Safaricom is.
    #
    # A failure claim (cb.ResultCode != 0, e.g. the customer cancelled or
    # the prompt timed out) doesn't need this extra check — there's
    # nothing to gain by forging a FAILURE, so only the success path is
    # gated.
    if cb.ResultCode == 0:
        verification = query_stk_status(cb.CheckoutRequestID)
        verified_result_code = None
        if verification is not None:
            try:
                verified_result_code = int(verification.get("ResultCode"))
            except (TypeError, ValueError):
                verified_result_code = None
        if verified_result_code != 0:
            # Callback claims success but Safaricom's own record doesn't
            # confirm it (or couldn't be reached right now) — refuse to
            # finalize rather than trust the callback body alone. Logged
            # loudly since a mismatch here is either a forged callback
            # attempt or a real Daraja outage, and either one is worth
            # someone's attention.
            print(
                f"⚠️  M-Pesa callback claimed success for "
                f"CheckoutRequestID={cb.CheckoutRequestID} but independent "
                f"Daraja verification did not confirm it "
                f"(got: {verification!r}). Refusing to finalize this payment."
            )
            raise HTTPException(
                status_code=400,
                detail="Payment could not be independently verified.",
            )

    try:
        payment = record_successful_payment(
            db,
            checkout_request_id=cb.CheckoutRequestID,
            receipt_number=receipt_number,
            result_code=cb.ResultCode,
            mpesa_receipt_number=receipt_number,
            raw_payload=data.model_dump_json(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if payment.status == "paid":
        finalize_paid_booking(db, payment)

    return {"payment_id": str(payment.id), "booking_id": str(payment.booking_id), "status": payment.status}


@router.post("/mpesa/dev-simulate-callback")
def mpesa_dev_simulate_callback(
    data: MpesaCallbackRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """DEV/DEMO ONLY. Real Safaricom callbacks require a publicly reachable
    HTTPS URL (see MPESA_CALLBACK_URL); on a local machine/LAN that's usually
    not available. This endpoint lets the frontend simulate the callback so
    the flow can still be demoed end-to-end. It refuses to run unless DEBUG
    is on, specifically so it can't be used as a way to forge "booked" status
    in production."""
    if not settings.DEBUG:
        raise HTTPException(status_code=403, detail="Dev-only endpoint is disabled (DEBUG is off)")

    # SECURITY: even though this route is already gated behind DEBUG, add a
    # second independent control — require the caller to be authenticated
    # and to actually own the booking behind this checkout_request_id.
    # DEBUG is an env var that can be left on by accident (as shipped
    # .env did); ownership checks don't depend on remembering to flip a
    # flag, so a misconfigured deploy still can't let a stranger fake
    # someone else's payment.
    existing_payment = (
        db.query(Payment)
        .filter(Payment.mpesa_checkout_request_id == data.checkout_request_id)
        .first()
    )
    if not existing_payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    owning_booking = db.query(Booking).filter(Booking.id == existing_payment.booking_id).first()
    if not owning_booking or str(owning_booking.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not your payment")

    try:
        payment = record_successful_payment(
            db,
            checkout_request_id=data.checkout_request_id,
            receipt_number=data.receipt_number,
            result_code=data.result_code,
            mpesa_receipt_number=data.receipt_number,
            raw_payload=data.model_dump_json(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if payment.status == "paid":
        finalize_paid_booking(db, payment)

    return {"payment_id": str(payment.id), "booking_id": str(payment.booking_id), "status": payment.status}


@router.get("/mpesa/status/{checkout_request_id}", response_model=MpesaPaymentStatusResponse)
def mpesa_payment_status(
    checkout_request_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Lets the frontend poll for a result instead of needing the callback to
    have already landed. If Daraja credentials are configured we also ask
    Safaricom directly (works in sandbox even without a public callback URL,
    though the query API doesn't carry the M-Pesa receipt number — only the
    callback does)."""
    payment = db.query(Payment).filter(Payment.mpesa_checkout_request_id == checkout_request_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    booking = db.query(Booking).filter(Booking.id == payment.booking_id).first()
    if not booking or str(booking.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not your payment")

    if payment.status == "initiated":
        result = query_stk_status(checkout_request_id)
        if result is not None:
            try:
                result_code = int(result.get("ResultCode"))
            except (TypeError, ValueError):
                result_code = None
            # SECURITY/CORRECTNESS: only ever let this active query confirm a
            # SUCCESS (ResultCode 0). A non-zero code here does NOT finalize
            # the payment as failed — Safaricom's STK Query API can return
            # codes like 1032 ("request cancelled by user") or 1037 ("DS
            # timeout, user cannot be reached") simply because the phone's
            # own prompt window expired, which is not the same thing as the
            # buyer actually declining, and can happen even when the buyer
            # did enter their PIN just outside that window. The real,
            # authoritative outcome — success OR failure — arrives via
            # Safaricom's asynchronous callback (mpesa_callback above); this
            # endpoint only ever needs to notice success a little early.
            # Leaving the status as "initiated" here means a genuinely late
            # callback can still land and correctly mark it paid, instead of
            # this query permanently locking it into "failed" first.
            if result_code == 0:
                payment = record_successful_payment(
                    db,
                    checkout_request_id=checkout_request_id,
                    receipt_number=None,
                    result_code=result_code,
                    mpesa_receipt_number=None,
                    raw_payload=str(result),
                )
                if payment.status == "paid":
                    finalize_paid_booking(db, payment)

    return MpesaPaymentStatusResponse(
        booking_id=payment.booking_id,
        payment_id=payment.id,
        status=payment.status,
        provider=payment.provider,
        mpesa_receipt_number=payment.mpesa_receipt_number,
    )

# NOTE: the old /withdrawals/request and /withdrawals/me endpoints that
# used to live here have been removed — they called
# create_withdrawal()/list_withdrawals_for_host(), functions that no
# longer exist in app.services.withdrawal_service now that payouts are
# event-scoped. That pipeline now lives at:
#   POST /users/payout/request   (app/api/v1/users.py)
#   GET  /users/payout/mine      (app/api/v1/users.py)
# which is what host_dashboard.js actually calls.