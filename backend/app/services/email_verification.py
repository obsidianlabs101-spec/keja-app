"""Signed, expiring email-verification links."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

from app.core.config import settings
from app.services import mail_service

_PURPOSE = "verify_email"
_LIFETIME_HOURS = 48


def make_token(user_id, email: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=_LIFETIME_HOURS)
    return jwt.encode(
        {"sub": str(user_id), "email": email, "purpose": _PURPOSE, "exp": exp},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def read_token(token: str) -> Optional[dict]:
    """Returns the payload if the token is genuine, unexpired and meant for
    email verification (a normal login token can never be used here)."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
    if payload.get("purpose") != _PURPOSE or not payload.get("sub"):
        return None
    return payload


def send_verification_email(user_id, email: str, name: str) -> bool:
    link = f"{settings.FRONTEND_URL}/?verify={make_token(user_id, email)}"
    first = (name or "there").split(" ")[0]
    subject = "Verify your Keja email"
    text = (
        f"Hi {first},\n\nWelcome to Keja! Confirm your email to finish creating your account:\n\n{link}\n\n"
        f"The link works for {_LIFETIME_HOURS} hours. If you didn't sign up, you can ignore this email."
    )
    html = (
        f'<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:24px;color:#1a1530">'
        f'<h2 style="margin:0 0 12px">Welcome to Keja, {first}!</h2>'
        f'<p>Confirm your email to finish creating your account.</p>'
        f'<p style="margin:24px 0"><a href="{link}" style="background:#6C4DFF;color:#fff;text-decoration:none;'
        f'padding:12px 22px;border-radius:999px;font-weight:bold;display:inline-block">Verify my email</a></p>'
        f'<p style="font-size:12px;color:#666">Or paste this link into your browser:<br>{link}</p>'
        f'<p style="font-size:12px;color:#666">The link works for {_LIFETIME_HOURS} hours. '
        f"If you didn't sign up, you can ignore this email.</p></div>"
    )
    return mail_service.send_email(email, subject, html, text)
