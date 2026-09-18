from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_auth_requests
from app.core.database import get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.core.limiter import limiter
from app.schemas.user import UserRegister, UserLogin, TokenResponse, GoogleAuthRequest
from app.services.auth_service import (
    create_user,
    get_user_by_email,
    get_user_by_username,
    authenticate_user,
    authenticate_or_create_google_user,
)

# Remove the prefix here since it will be added in __init__.py
router = APIRouter(tags=["Authentication"])

@router.post("/register")
@limiter.limit("10/minute")
def register(
    request: Request,
    user: UserRegister,
    db: Session = Depends(get_db)
):
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
        new_user = create_user(db, user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Username or email already taken"
        )
    
    return {
        "message": "User registered successfully",
        "user_id": str(new_user.id)
    }

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