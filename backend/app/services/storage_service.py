"""Uploads to Supabase Storage — clips, posters, and avatars all go
through this module now (see config.py's Supabase Storage section for
why: Render's disk is ephemeral and gets wiped on every redeploy/restart,
which was silently destroying uploaded media over time. Documents stay
on local disk for now — they're rarely re-fetched after initial admin
review, so the ephemeral-disk risk is lower there).

This intentionally uses the `requests` library (already a dependency,
used elsewhere for the M-Pesa/Daraja API) rather than the official
`supabase-py` SDK, to avoid adding a new dependency for what is just two
HTTP calls (PUT to upload, and a predictable public URL — no need to
call the API to construct it).
"""
import mimetypes

import requests

from app.core.config import settings

_UPLOAD_TIMEOUT_SECONDS = 60


def is_configured() -> bool:
    return bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY)


def upload_file(local_path: str, storage_filename: str, bucket: str) -> str:
    """Uploads a local file to the given Supabase Storage bucket and
    returns its public URL.

    Raises on any failure (network error, non-2xx response, misconfiguration)
    — callers are expected to catch this and decide whether to fall back to
    serving the local copy, matching the "best-effort" pattern already used
    for watermarking elsewhere in media.py.
    """
    if not is_configured():
        raise RuntimeError(
            "Supabase Storage isn't configured — set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY in the environment."
        )

    content_type = mimetypes.guess_type(storage_filename)[0] or "application/octet-stream"

    upload_url = f"{settings.SUPABASE_URL}/storage/v1/object/{bucket}/{storage_filename}"

    with open(local_path, "rb") as f:
        resp = requests.put(
            upload_url,
            data=f,
            headers={
                # IMPORTANT: apikey ONLY, no Authorization header.
                #
                # Supabase's docs are explicit that the new sb_secret_...
                # key format goes on apikey "instead" of Authorization,
                # not in addition to it. A previous version of this code
                # sent the same key on both — which happens to pass
                # Kong's gateway check (it allows Authorization to match
                # apikey), but then Storage itself receives that
                # Authorization header, tries to parse it as a JWT (the
                # traditional format), and rejects it with 401 since the
                # new key format isn't a JWT at all. apikey alone avoids
                # this entirely.
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Content-Type": content_type,
                # Overwrite semantics: our filenames are uuid4-based, so a
                # collision should never happen in practice, but "true"
                # here means a retried upload after a network blip
                # doesn't 409 instead of just succeeding.
                "x-upsert": "true",
            },
            timeout=_UPLOAD_TIMEOUT_SECONDS,
        )
    resp.raise_for_status()

    return f"{settings.SUPABASE_URL}/storage/v1/object/public/{bucket}/{storage_filename}"


def upload_clip(local_path: str, storage_filename: str) -> str:
    return upload_file(local_path, storage_filename, settings.SUPABASE_CLIPS_BUCKET)


def upload_poster(local_path: str, storage_filename: str) -> str:
    return upload_file(local_path, storage_filename, settings.SUPABASE_POSTERS_BUCKET)


def upload_avatar(local_path: str, storage_filename: str) -> str:
    return upload_file(local_path, storage_filename, settings.SUPABASE_AVATARS_BUCKET)