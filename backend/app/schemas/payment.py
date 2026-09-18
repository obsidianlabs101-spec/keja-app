from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class MpesaSTKPushRequest(BaseModel):
    booking_id: UUID
    phone_number: str  # e.g. 2547XXXXXXXX
    amount: float
    currency: str = "KES"


class MpesaSTKPushResponse(BaseModel):
    booking_id: UUID
    payment_id: UUID
    checkout_request_id: str
    status: str
    # "stk" = a real Daraja push was sent to the buyer's phone.
    # "manual" = manual-payment mode (admin toggle, or STK failed) — the
    # frontend should show paybill_number/account_reference and collect
    # the buyer's code via POST /payments/mpesa/manual-claim instead of
    # polling for a phone-prompt result.
    mode: str = "stk"
    paybill_number: Optional[str] = None
    account_reference: Optional[str] = None


class ManualPaymentClaimRequest(BaseModel):
    checkout_request_id: str
    # Whatever the buyer pasted — either the bare M-Pesa code or the full
    # confirmation SMS. The code is extracted server-side either way; see
    # app.services.manual_payment_service.extract_code.
    message: str


class MpesaCallbackRequest(BaseModel):
    checkout_request_id: str
    merchant_request_id: Optional[str] = None
    result_code: int
    result_desc: Optional[str] = None
    receipt_number: Optional[str] = None


class DarajaCallbackItem(BaseModel):
    Name: str
    Value: Optional[object] = None


class DarajaCallbackMetadata(BaseModel):
    Item: list[DarajaCallbackItem] = []


class DarajaStkCallback(BaseModel):
    MerchantRequestID: Optional[str] = None
    CheckoutRequestID: str
    ResultCode: int
    ResultDesc: Optional[str] = None
    CallbackMetadata: Optional[DarajaCallbackMetadata] = None


class DarajaCallbackBody(BaseModel):
    stkCallback: DarajaStkCallback


class DarajaCallbackEnvelope(BaseModel):
    """The exact shape Safaricom's Daraja servers POST to CallBackURL."""
    Body: DarajaCallbackBody


class MpesaPaymentStatusResponse(BaseModel):
    booking_id: UUID
    payment_id: UUID
    status: str
    mpesa_receipt_number: Optional[str] = None
    provider: Optional[str] = None