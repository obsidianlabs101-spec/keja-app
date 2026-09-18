import base64
import uuid
from datetime import datetime

import requests
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.payment import Payment

DARAJA_HOSTS = {
    "sandbox": "https://sandbox.safaricom.co.ke",
    "production": "https://api.safaricom.co.ke",
}

# In-process cache for the Daraja OAuth token. Safaricom issues these with a
# ~3600s validity and expects callers to reuse them — hitting /oauth/v1/generate
# on every single request (as this module used to) gets rate-limited with a
# 403, which is indistinguishable from a real credentials problem in the logs
# unless you know to look for it.
_token_cache = {"token": None, "expires_at": 0.0}


def _daraja_host() -> str:
    return DARAJA_HOSTS.get((settings.MPESA_ENVIRONMENT or "sandbox").lower(), DARAJA_HOSTS["sandbox"])


def mpesa_configured() -> bool:
    """True only once real credentials are present. Lets the rest of the app
    fall back to a safe local stub instead of crashing when they're not."""
    return bool(settings.MPESA_CONSUMER_KEY and settings.MPESA_CONSUMER_SECRET
                and settings.MPESA_PASSKEY and settings.MPESA_SHORTCODE)


def get_access_token(force_refresh: bool = False) -> str:
    """OAuth2 client-credentials grant against Daraja. Consumer key/secret are
    sent as HTTP Basic auth, exactly as Safaricom's docs specify.

    Cached in-process and reused until shortly before it expires — set
    force_refresh=True to bypass the cache (e.g. after the token was
    rejected as invalid) and pull a fresh one.
    """
    import time
    now = time.time()
    if not force_refresh and _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]

    url = f"{_daraja_host()}/oauth/v1/generate?grant_type=client_credentials"
    resp = requests.get(
        url,
        auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET),
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data["access_token"]
    # Refresh a minute early rather than cutting it exactly at expiry.
    expires_in = int(data.get("expires_in", 3599) or 3599)
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + max(expires_in - 60, 60)
    return token


def _password_and_timestamp():
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    raw = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}"
    password = base64.b64encode(raw.encode()).decode()
    return password, timestamp


def initiate_stk_push(
    db: Session,
    *,
    booking_id,
    phone_number: str,
    amount,
    currency: str,
    account_reference: str = "BASH",
    transaction_desc: str = "BASH Event Ticket",
    mpesa_checkout_request_id: str | None = None,
):
    """Creates the local Payment record either way. If real Daraja credentials
    are configured, also fires the actual STK push to the customer's phone;
    otherwise falls back to the old MVP stub (status stays 'initiated' until
    something calls the dev-simulate endpoint)."""
    checkout_id = mpesa_checkout_request_id
    sent_real_push = False

    if mpesa_configured():
        try:
            token = get_access_token()
            password, timestamp = _password_and_timestamp()
            payload = {
                "BusinessShortCode": settings.MPESA_SHORTCODE,
                "Password": password,
                "Timestamp": timestamp,
                # CustomerBuyGoodsOnline, not CustomerPayBillOnline: this
                # business number is a Till (Buy Goods), not a Paybill —
                # Safaricom's Daraja API treats these as genuinely
                # different transaction types, not just a label. Sending
                # PayBillOnline against a till number gets REJECTED by
                # Daraja (or in some cases silently misroutes the funds),
                # it's not just cosmetically wrong.
                "TransactionType": "CustomerBuyGoodsOnline",
                "Amount": int(round(float(amount))),
                "PartyA": phone_number,
                "PartyB": settings.MPESA_SHORTCODE,
                "PhoneNumber": phone_number,
                "CallBackURL": settings.MPESA_CALLBACK_URL or "https://example.com/payments/mpesa/callback",
                "AccountReference": account_reference,
                "TransactionDesc": transaction_desc,
            }
            resp = requests.post(
                f"{_daraja_host()}/mpesa/stkpush/v1/processrequest",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            checkout_id = data.get("CheckoutRequestID")
            sent_real_push = bool(checkout_id)
        except requests.RequestException as e:
            # Daraja unreachable / bad creds / phone rejected — don't crash the
            # request, degrade to the local stub so the rest of the flow (and
            # any dev-simulate fallback) still works.
            print(f"WARNING: M-Pesa STK push failed, falling back to stub: {e}")

    payment = Payment(
        booking_id=booking_id,
        provider="mpesa",
        status="initiated",
        amount=float(amount),
        currency=currency,
        mpesa_checkout_request_id=checkout_id or str(uuid.uuid4()),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        raw_payload=None,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    # In-memory only signal (not a DB column) for callers like
    # /payments/mpesa/stk-push that need to know whether a real push
    # actually reached the buyer's phone, vs. quietly degraded to the
    # local stub, so they can fall back to manual-payment mode.
    payment.sent_real_push = sent_real_push
    return payment


def query_stk_status(checkout_request_id: str):
    """Actively asks Daraja for the current state of an STK push (works in
    sandbox without needing a reachable callback URL, though it won't carry
    the M-Pesa receipt number - that only arrives via the callback)."""
    if not mpesa_configured():
        return None
    for attempt in range(2):
        try:
            token = get_access_token(force_refresh=(attempt == 1))
            password, timestamp = _password_and_timestamp()
            payload = {
                "BusinessShortCode": settings.MPESA_SHORTCODE,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id,
            }
            resp = requests.post(
                f"{_daraja_host()}/mpesa/stkpushquery/v1/query",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=20,
            )
            if resp.status_code in (401, 403) and attempt == 0:
                # Cached token was rejected — refresh it and try once more
                # instead of surfacing a spurious failure for the whole poll.
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print(f"WARNING: M-Pesa STK query failed: {e}")
            return None
    return None


def record_successful_payment(
    db: Session,
    *,
    checkout_request_id: str,
    receipt_number: str | None,
    result_code: int,
    mpesa_receipt_number: str | None,
    raw_payload: str | None = None,
):
    payment = (
        db.query(Payment)
        .filter(Payment.mpesa_checkout_request_id == checkout_request_id)
        .first()
    )
    if payment is None:
        raise ValueError("Payment not found for checkout_request_id")

    if int(result_code) == 0:
        payment.status = "paid"
        payment.mpesa_result_code = str(result_code)
        payment.mpesa_receipt_number = mpesa_receipt_number or receipt_number
    else:
        payment.status = "failed"
        payment.mpesa_result_code = str(result_code)

    payment.raw_payload = raw_payload
    payment.updated_at = datetime.utcnow()
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment