from datetime import datetime
from pydantic import BaseModel
from uuid import UUID
from typing import Optional


class WithdrawalRequest(BaseModel):
    event_id: UUID


# users.py imports these two names specifically — aliasing instead of
# renaming so nothing else that already depends on WithdrawalRequest /
# PayoutRespondRequest needs to change.
PayoutRequestCreate = WithdrawalRequest


class WithdrawalResponse(BaseModel):
    id: UUID
    host_id: UUID
    event_id: Optional[UUID]
    amount: float
    currency: str
    status: str
    gross_revenue: Optional[float] = None
    platform_cut: Optional[float] = None
    host_payout_amount: Optional[float] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    account_name: Optional[str] = None
    mpesa_paybill: Optional[str] = None
    mpesa_code: Optional[str] = None
    requested_at: datetime
    messaged_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PayoutRespondRequest(BaseModel):
    confirm: bool


PayoutRespond = PayoutRespondRequest


class MarkPaidRequest(BaseModel):
    mpesa_code: str


# Kept for backwards compatibility with any older admin callers — no
# longer used by the new Message/Confirm/Deny/Mark-Paid pipeline.
class AdminWithdrawalAction(BaseModel):
    payout_reference: Optional[str] = None
    approve: bool = True
    note: Optional[str] = None