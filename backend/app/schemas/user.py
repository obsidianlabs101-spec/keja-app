from typing import Optional

from pydantic import BaseModel
from pydantic import EmailStr


class UserRegister(BaseModel):

    username: str
    full_name: str
    email: EmailStr
    phone: str
    password: str
    # Referral code from a shared link (index.html?ref=<code>) — if it
    # matches a real user, that user's free-events padlock lifts.
    ref: Optional[str] = None
    


class UserLogin(BaseModel):

    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    # The raw ID token from Google's Sign-In JS library (response.credential
    # in the browser callback) — verified server-side before being trusted,
    # never decoded/trusted client-side. See auth_service.py's
    # authenticate_or_create_google_user for the actual verification.
    id_token: str
    # Optional referral code, read from the same ?ref=<code> URL param the
    # password-signup form already uses (see index.html) — this was
    # previously never captured for the Google path at all, meaning
    # whoever referred a Google-signup user got no credit for it.
    ref: str | None = None


class UserProfile(BaseModel):
    id: str
    email: str
    name: str
    username: Optional[str] = None
    profile_pic_url: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    county: Optional[str] = None
    town: Optional[str] = None
    referral_code: Optional[str] = None
    free_events_unlocked: bool = False
    host_pin: Optional[str] = None
    is_host: bool
    is_admin: bool   # <-- add this
    host_verification_status: Optional[str] = None
    free_contact_credits: int = 0
    referral_bonus_granted: bool = False

    class Config:
        from_attributes = True


class HostProfileUpdate(BaseModel):

    bio: Optional[str] = None
    location: Optional[str] = None
    county: Optional[str] = None
    town: Optional[str] = None
    social_links: Optional[str] = None
    phone: Optional[str] = None
    username: Optional[str] = None
    government_id: Optional[str] = None
    government_id_image_url: Optional[str] = None
    business_registration: Optional[str] = None
    business_registration_image_url: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    account_name: Optional[str] = None
    bank_branch: Optional[str] = None
    swift_code: Optional[str] = None
    mpesa_paybill: Optional[str] = None
    kra_pin: Optional[str] = None
    host_pin: Optional[str] = None


class HostVerificationResponse(BaseModel):

    id: str
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    host_verification_status: str
    verification_requested_at: Optional[str] = None
    verification_approved_at: Optional[str] = None
    government_id: Optional[str] = None
    government_id_image_url: Optional[str] = None
    business_registration: Optional[str] = None
    business_registration_image_url: Optional[str] = None
    bank_name: Optional[str] = None
    mpesa_paybill: Optional[str] = None
    kra_pin: Optional[str] = None
    host_pin: Optional[str] = None

    class Config:
        from_attributes = True


class AdminHostVerificationAction(BaseModel):

    user_id: str
    approve: bool
    note: Optional[str] = None


class TokenResponse(BaseModel):

    access_token: str
    token_type: str


class SakaStatusUpdate(BaseModel):
    """Body for PUT /users/me/saka-status. `status` must be one of
    ALLOWED_SAKA_STATUSES in app/api/v1/users.py ("friends", "dating",
    "available", "casual", "invisible"). duration_unit/duration_value
    are only meaningful for non-"invisible" statuses: unit is "hours",
    "days", or "off" (never expires until manually changed), and value
    is how many of that unit from now. Both are optional/ignored when
    duration_unit is "off" or omitted, or when status is "invisible"
    (which never auto-expires)."""

    status: str
    duration_unit: Optional[str] = "off"
    duration_value: Optional[int] = None