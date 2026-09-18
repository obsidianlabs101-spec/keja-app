# app/core/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session
from uuid import UUID
from app.core.database import get_db
from app.models.user import User
from app.models.admin import Admin
from app.core.security import decode_token

security = HTTPBearer(
    bearerFormat="JWT",
    description="Provide the JWT access token using the Bearer scheme"
)


def _token_version_matches(payload: dict, user) -> bool:
    """
    Tokens embed the token_version they were issued with; this compares
    that against the user's current value so a bumped token_version (via
    /users/me/logout-all-sessions) invalidates every previously-issued
    token immediately, instead of waiting out however long that token's
    natural expiry is (which can now be up to 30 days). A token minted
    before this field existed won't carry the claim at all — treat that
    as version 0 so already-issued tokens keep working normally until
    someone actually triggers a logout-everywhere.
    """
    token_ver = payload.get("token_version", 0)
    user_ver = getattr(user, "token_version", 0) or 0
    try:
        return int(token_ver) == int(user_ver)
    except (TypeError, ValueError):
        return False


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials

    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        
        if user_id is None:
            raise credentials_exception
            
        # Convert string to UUID
        try:
            user_uuid = UUID(user_id)
        except ValueError:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_uuid).first()
    
    if user is None:
        raise credentials_exception

    if not _token_version_matches(payload, user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This session was logged out remotely — please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
):
    """Like get_current_user, but returns None instead of raising when no/invalid
    token is present — for endpoints that are public but personalize their
    response (e.g. "is_following") when the caller happens to be logged in."""
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
        user_id = payload.get("sub")
        if user_id is None:
            return None
        user_uuid = UUID(user_id)
    except Exception:
        return None

    user = db.query(User).filter(User.id == user_uuid).first()
    if user is None or not _token_version_matches(payload, user):
        return None
    return user


# NEW UPDATED CODE for backend/app/core/dependencies.py
def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        is_admin = payload.get("is_admin", False)

        if user_id is None:
            raise credentials_exception
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User token is missing/invalid is_admin claim"
            )

        try:
            user_uuid = UUID(user_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token sub is not a valid UUID"
            )

    except JWTError:
        raise credentials_exception

    #  FIX: Now querying the User table for your account with is_admin set to True
    user = db.query(User).filter(User.id == user_uuid, User.is_admin == True).first()
    if user is None:
        raise credentials_exception

    if not _token_version_matches(payload, user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This session was logged out remotely — please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

def require_host(
    current_user=Depends(get_current_user)
):
    if not current_user.is_host:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Host access required"
        )
    return current_user


# Keja rename: a "landlord" is exactly Bash's "host" concept (same
# users.is_host column — no migration needed, just a clearer name at the
# API layer for the rental platform).
def require_landlord(
    current_user=Depends(get_current_user)
):
    if not current_user.is_host:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Landlord access required — enable landlord mode on your profile first"
        )
    return current_user

def require_admin(
    current_admin=Depends(get_current_admin)
):
    return current_admin