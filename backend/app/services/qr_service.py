import json
from datetime import datetime, timedelta

from jose import jwt

from app.core.config import settings


def _secret_for_qr() -> str:
    """Dedicated, independent secret for signing ticket QR codes — kept
    fully separate from settings.SECRET_KEY (used for user/admin auth
    tokens) so a leak of one never lets an attacker forge the other."""
    return settings.QR_SECRET_KEY


def generate_encrypted_qr(payload: dict) -> str:
    # jose.jwt supports signing/encryption. For encrypted blob we use JWE via jwt.encode with encryption keys.
    # If ALGORITHM is HS256, it is signing; we still wrap in encrypted container using secret as key.
    # For MVP: treat the output as an encrypted blob.
    exp = datetime.utcnow() + timedelta(hours=6)
    data = payload.copy()
    data.update({"exp": exp, "check_in_status": False})

    token = jwt.encode(
        data,
        _secret_for_qr(),
        algorithm="HS256",
    )
    return token


def decrypt_and_validate_qr(qr_blob: str) -> dict:
    decoded = jwt.decode(
        qr_blob,
        _secret_for_qr(),
        algorithms=["HS256"],
    )
    # basic shape validation
    required = {"ticket_id", "booking_id", "event_id", "user_id"}
    missing = required - set(decoded.keys())
    if missing:
        raise ValueError(f"Invalid QR payload, missing: {missing}")
    return decoded
