"""Tiny free transactional-email sender (HTTPS only).

Render's free tier blocks outbound SMTP, so plain Gmail SMTP can't be used.
Two free HTTPS routes are supported, picked by which env vars are set:

  1. Gmail API (sends from your own Gmail, lands in the inbox)
       GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN, GMAIL_SENDER
  2. Brevo (300/day free)
       BREVO_API_KEY, BREVO_SENDER_EMAIL

`is_configured()` is False when neither is set; callers use that to switch
email verification off instead of locking people out.
"""
import base64
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from app.core.config import settings

_token_cache = {"value": None, "exp": 0.0}


def _gmail_ready() -> bool:
    return all([settings.GMAIL_CLIENT_ID, settings.GMAIL_CLIENT_SECRET, settings.GMAIL_REFRESH_TOKEN, settings.GMAIL_SENDER])


def _brevo_ready() -> bool:
    return bool(settings.BREVO_API_KEY and settings.BREVO_SENDER_EMAIL)


def is_configured() -> bool:
    return _gmail_ready() or _brevo_ready()


def _gmail_access_token() -> str:
    if _token_cache["value"] and time.time() < _token_cache["exp"] - 60:
        return _token_cache["value"]
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": settings.GMAIL_CLIENT_ID,
            "client_secret": settings.GMAIL_CLIENT_SECRET,
            "refresh_token": settings.GMAIL_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    _token_cache["value"] = data["access_token"]
    _token_cache["exp"] = time.time() + int(data.get("expires_in", 3000))
    return _token_cache["value"]


def send_email(to: str, subject: str, html: str, text: str) -> bool:
    """Returns True on success. Never raises (callers run this in the
    background; a mail hiccup must not break signup)."""
    try:
        if _gmail_ready():
            msg = MIMEMultipart("alternative")
            msg["To"] = to
            msg["From"] = f"Keja <{settings.GMAIL_SENDER}>"
            msg["Subject"] = subject
            msg.attach(MIMEText(text, "plain", "utf-8"))
            msg.attach(MIMEText(html, "html", "utf-8"))
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            r = requests.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers={"Authorization": f"Bearer {_gmail_access_token()}"},
                json={"raw": raw},
                timeout=15,
            )
            r.raise_for_status()
            return True
        if _brevo_ready():
            r = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": settings.BREVO_API_KEY, "accept": "application/json"},
                json={
                    "sender": {"name": "Keja", "email": settings.BREVO_SENDER_EMAIL},
                    "to": [{"email": to}],
                    "subject": subject,
                    "htmlContent": html,
                    "textContent": text,
                },
                timeout=15,
            )
            r.raise_for_status()
            return True
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Email send failed: {e}")
    return False
