from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_auth_requests
from app.core.database import get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.core.limiter import limiter
from app.schemas.user import UserRegister, UserLogin, TokenResponse, GoogleAuthRequest, VerifyEmailRequest, ResendVerificationRequest
from app.services import email_verification, mail_service
from app.services.auth_service import (
    create_user,
    get_user_by_email,
    get_user_by_username,
    authenticate_user,
    authenticate_or_create_google_user,
    confirm_email,
)

# Remove the prefix here since it will be added in __init__.py
router = APIRouter(tags=["Authentication"])

@router.post("/register")
@limiter.limit("10/minute")
def register(
    request: Request,
    user: UserRegister,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # A verification link can only reach a real inbox. Placeholder
    # "@keja.local" addresses (old phone-only signups) can't be verified, so
    # new accounts must use a real email.
    if str(user.email).lower().endswith("@keja.local"):
        raise HTTPException(status_code=400, detail="Please sign up with a real email address — we'll send you a verification link.")

    existing = get_user_by_email(db, user.email)
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Email already exists"
        )

    # Usernames are permanent once created (host_dashboard/profile don't
    # allow changing them later), so this is the one and only gate —
    # reject a duplicate here with a clean message instead of letting the
    # DB's unique constraint blow up into a raw 500 IntegrityError.
    if get_user_by_username(db, user.username):
        raise HTTPException(
            status_code=400,
            detail="Username already taken — pick another one"
        )

    try:
        # If email sending isn't configured yet, verification is off and the
        # account works immediately (nobody gets locked out by a missing key).
        needs_verification = mail_service.is_configured()
        new_user = create_user(db, user, pending_verification=needs_verification)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Username or email already taken"
        )
    
    if needs_verification:
        background_tasks.add_task(
            email_verification.send_verification_email, new_user.id, new_user.email, new_user.full_name
        )

    return {
        "message": "Account created — check your email for a verification link."
        if needs_verification else "User registered successfully",
        "user_id": str(new_user.id),
        "verification_required": bool(needs_verification),
    }


@router.post("/verify-email")
@limiter.limit("20/minute")
def verify_email(request: Request, body: VerifyEmailRequest, db: Session = Depends(get_db)):
    payload = email_verification.read_token(body.token)
    if not payload:
        raise HTTPException(status_code=400, detail="This verification link is invalid or has expired. Request a new one from the login screen.")
    from uuid import UUID
    try:
        uid = UUID(payload["sub"])
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid verification link")
    from app.models.user import User
    user = db.query(User).filter(User.id == uid).first()
    # The token is bound to the email it was issued for, so an old link can't
    # verify an account whose address has since changed.
    if not user or (user.email or "").lower() != str(payload.get("email", "")).lower():
        raise HTTPException(status_code=400, detail="This verification link is invalid or has expired.")
    confirm_email(db, user)
    return {"message": "Email verified — you can now log in."}


@router.post("/resend-verification")
@limiter.limit("3/minute")
def resend_verification(
    request: Request,
    body: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # Same answer whether or not the address exists / is pending, so this
    # can't be used to find out who has an account.
    user = get_user_by_email(db, body.email)
    if user and getattr(user, "email_pending_verification", False) and mail_service.is_configured():
        background_tasks.add_task(
            email_verification.send_verification_email, user.id, user.email, user.full_name
        )
    return {"message": "If that address has an unverified account, a new link is on its way."}

@router.post("/login", response_model=TokenResponse)
@limiter.limit("8/minute")
def login(
    request: Request,
    credentials: UserLogin,
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, credentials.email, credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    if getattr(user, "email_pending_verification", False):
        raise HTTPException(
            status_code=403,
            detail="Please verify your email first — we sent you a link (check spam too)."
        )
    
    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "is_host": user.is_host,
        "is_admin": user.is_admin,
        "token_version": user.token_version or 0
    })
    
    return {
        "access_token": token,
        "token_type": "bearer"
    }


@router.post("/auth/google", response_model=TokenResponse)
@limiter.limit("10/minute")
def google_login(
    request: Request,
    body: GoogleAuthRequest,
    db: Session = Depends(get_db)
):
    """Real Google Sign-In verification — replaces the old frontend code
    that decoded the Google token client-side and trusted it outright
    with no signature check (meaning anyone could forge a fake login by
    handing the browser a hand-crafted JWT-shaped string). This endpoint
    verifies the token is genuinely signed by Google, genuinely intended
    for this app (matches GOOGLE_CLIENT_ID), and not expired, before
    trusting anything in it.
    """
    try:
        # verify_oauth2_token checks the cryptographic signature against
        # Google's public keys, the token's expiry, AND that its
        # "audience" matches our Client ID — a token issued for some
        # other website can't be replayed against this endpoint.
        payload = google_id_token.verify_oauth2_token(
            body.id_token,
            google_auth_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=401,
            detail="Invalid Google token"
        )

    if not payload.get("email_verified", False):
        raise HTTPException(
            status_code=401,
            detail="Google account email is not verified"
        )

    email = payload["email"]
    name = payload.get("name") or ""
    picture = payload.get("picture") or ""

    user, was_created = authenticate_or_create_google_user(db, email, name, picture, ref_code=body.ref)

    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "is_host": user.is_host,
        "is_admin": user.is_admin,
        "token_version": user.token_version or 0
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }