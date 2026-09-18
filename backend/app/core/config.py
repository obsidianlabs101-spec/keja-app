# app/core/config.py
import secrets as _secrets
from dotenv import load_dotenv
import os

load_dotenv()


def _require_secret(env_name: str, min_len: int = 16) -> str:
    """Reads a secret from the environment and refuses to boot with an
    obviously-unsafe value (missing, empty, or a known placeholder). This
    used to silently accept short/placeholder strings, which is how a
    literal "Change_Admin" secret ended up shipping toward production."""
    value = os.getenv(env_name)
    placeholders = {
        "changeme", "change_me", "change-me", "placeholder", "secret",
        "eventmanagementsupersecretkey2026",
    }
    if not value or len(value) < min_len or value.strip().lower() in placeholders:
        raise RuntimeError(
            f"Refusing to start: {env_name} is missing or looks like a "
            f"placeholder/default value. Set a real random secret "
            f"(e.g. `python -c \"import secrets; print(secrets.token_hex(32))\"`) "
            f"in your .env before running the app."
        )
    return value


class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL")

    # --- Core auth secret -------------------------------------------------
    SECRET_KEY = _require_secret("SECRET_KEY")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    # 30 minutes (the old default) is far too short for a "close the app,
    ACCESS_TOKEN_EXPIRE_MINUTES = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24 * 30)
    )

    # --- Dedicated QR-signing secret ---------------------------------------
    # Previously derived from SECRET_KEY via simple string concatenation
    # (f"{SECRET_KEY}::qr-encryption"), which means anyone who ever saw
    # SECRET_KEY could also forge ticket QR codes. Kept fully independent
    # now so a leak of one secret doesn't compromise the other.
    QR_SECRET_KEY = os.getenv("QR_SECRET_KEY")
    if not QR_SECRET_KEY:
        # Don't hard-fail existing dev setups that haven't added this var
        # yet, but make it impossible to miss and never silently reuse
        # SECRET_KEY.
        QR_SECRET_KEY = _secrets.token_hex(32)
        print(
            "⚠️  QR_SECRET_KEY is not set in .env — generated a random one "
            "for this process only. Every restart will invalidate all "
            "previously-issued ticket QR codes. Set a permanent "
            "QR_SECRET_KEY (`python -c \"import secrets; print(secrets.token_hex(32))\"`) "
            "in .env before deploying."
        )

    # Optional: Add these if needed
    APP_NAME = os.getenv("APP_NAME", "Keja")
    APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    ADMIN_CREATION_SECRET = _require_secret("ADMIN_CREATION_SECRET")

    # Extra password gate on the admin Financials page (on top of normal
    # admin auth). Deliberately does NOT fall back to ADMIN_CREATION_SECRET
    # anymore — reusing one secret for two different privilege gates means
    # leaking either one compromises both.
    FINANCE_ACCESS_PASSWORD = _require_secret("FINANCE_ACCESS_PASSWORD")

    # --- CORS ---------------------------------------------------------------
    # Comma-separated list of exact origins allowed to call this API with
    # credentials, e.g. "https://app.example.com,https://admin.example.com".
    # No wildcard support on purpose: allow_origins=["*"] + allow_credentials
    # =True is both spec-invalid and, where it does leak through, means any
    # website on the internet can make authenticated requests as your users.
    _origins_raw = os.getenv("ALLOWED_ORIGINS", "")
    ALLOWED_ORIGINS = [o.strip() for o in _origins_raw.split(",") if o.strip()]
    if not ALLOWED_ORIGINS:
        # Safe localhost-only default so a forgotten env var fails closed
        # (blocks unknown origins) instead of failing open (allows every
        # origin). Production deploys MUST set ALLOWED_ORIGINS explicitly.
        ALLOWED_ORIGINS = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5500",
            "http://127.0.0.1:5500",
            "http://192.168.100.210:8000"
        ]
        print(
            "⚠️  ALLOWED_ORIGINS is not set in .env — defaulting to "
            "localhost-only CORS origins. Set ALLOWED_ORIGINS to your real "
            "frontend domain(s) before deploying."
        )

    # --- Valkey (cache + shared rate-limit storage) -------------------------
    # Redis-protocol-compatible. On Render, create a Key Value instance
    # (dashboard.render.com/new/redis) — it runs Valkey by default now —
    # and set this to its Internal Key Value URL so traffic never leaves
    # Render's private network. Left unset, the app runs exactly as before:
    # no caching, and the rate limiter falls back to a single-process
    # in-memory store (see limiter.py).
    VALKEY_URL = os.getenv("VALKEY_URL", "")

    # M-Pesa (for later)
    MPESA_CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY")
    MPESA_CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET")
    MPESA_PASSKEY = os.getenv("MPESA_PASSKEY")
    MPESA_SHORTCODE = os.getenv("MPESA_SHORTCODE")
    MPESA_ENVIRONMENT = os.getenv("MPESA_ENVIRONMENT", "sandbox")
    # Must be a PUBLIC https URL Safaricom's servers can reach (e.g. an ngrok
    MPESA_CALLBACK_URL = os.getenv("MPESA_CALLBACK_URL")
    # Optional comma-separated IP allowlist for /payments/mpesa/callback.
    # Left empty by default (see payments.py for why); set to Safaricom's
    # published Daraja IPs in production once your proxy's client-IP
    # forwarding is confirmed correct.
    _mpesa_ips_raw = os.getenv("MPESA_ALLOWED_IPS", "")
    MPESA_ALLOWED_IPS = [ip.strip() for ip in _mpesa_ips_raw.split(",") if ip.strip()]

    # --- Web Push (VAPID) ---------------------------------------------------
    # Powers real phone/OS-level notification-tray alerts (e.g. the T-2h
    # "still going?" reminder) instead of ones only visible inside the app.
    # A working keypair ships as the default so push works out of the box;
    # override with your own in .env for production (generate via
    # `vapid --gen` from the py-vapid package, or reuse this pair — it's
    # fine to keep, VAPID keys don't need to be secret-rotated like an API
    # key, they just identify this server to push services).
    VAPID_PUBLIC_KEY = os.getenv(
        "VAPID_PUBLIC_KEY",
        "BH4r2OEp-S9iKVU6g24OoiXQrE0KhFbj9dCYclg04bYfvxvwZA4dlCw-muNfi78sAyvR1vZScWOGwW1mPIwO3EY",
    )
    VAPID_PRIVATE_KEY = os.getenv(
        "VAPID_PRIVATE_KEY",
        "zgYZlwleI3XcyugTSMfotBoagvUJff5L7DrV8zZiBjQ",
    )
    VAPID_CLAIM_EMAIL = os.getenv("VAPID_CLAIM_EMAIL", "mailto:support@bashke.com")

    # A push notification's image/icon is fetched directly by the browser/OS
    # push service, not by the frontend's own JS — so unlike everywhere else
    # in the app (see resolveMediaUrl() in the frontend), a relative path
    # like "static/posters/xxx.jpg" can't be resolved against api-config.js's
    # API_BASE at send time, because there's no "current page" origin for
    # the OS to resolve it against. This is this backend's own public
    # domain (wherever FastAPI/uvicorn is actually reachable from), used
    # only to build a full https://.../static/... URL for push images.
    # Leave unset and push notifications simply omit the image rather than
    # send a broken relative URL.
    PUBLIC_MEDIA_BASE_URL = os.getenv("PUBLIC_MEDIA_BASE_URL", "").rstrip("/")

    # --- Supabase Storage (video clips) -------------------------------
    # Video clips are uploaded to Supabase Storage instead of local disk:
    # Render's free-tier filesystem is ephemeral (wiped on every redeploy/
    # restart), and a single 0.1-CPU instance streaming raw video to every
    # visitor is far too slow anyway. Images/avatars/posters/documents
    # stay on local disk for now — only clips are migrated in this pass.
    #
    # SUPABASE_SERVICE_ROLE_KEY (not the anon/publishable key) is required
    # specifically because RLS is now enabled with no policies on every
    # table/bucket — the service_role key is the one credential that
    # legitimately bypasses RLS, which is exactly what a trusted backend
    # upload needs. Never expose this key to the frontend.
    SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
    # Defensive: if someone pastes the REST API's base URL (which Supabase's
    # dashboard shows in some places, e.g. "...supabase.co/rest/v1") instead
    # of the bare project URL, strip that suffix back off. Storage's own API
    # lives at /storage/v1/... directly off the project URL, not nested
    # under /rest/v1 — concatenating onto an un-stripped value here produced
    # a broken .../rest/v1/storage/v1/... URL and a confusing 404.
    for _suffix in ("/rest/v1", "/storage/v1", "/auth/v1"):
        if SUPABASE_URL.endswith(_suffix):
            SUPABASE_URL = SUPABASE_URL[: -len(_suffix)]
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_CLIPS_BUCKET = os.getenv("SUPABASE_CLIPS_BUCKET", "clips")
    SUPABASE_POSTERS_BUCKET = os.getenv("SUPABASE_POSTERS_BUCKET", "posters")
    SUPABASE_AVATARS_BUCKET = os.getenv("SUPABASE_AVATARS_BUCKET", "avatars")

    # --- Google Sign-In ------------------------------------------------
    # Not a secret — this is the same Client ID already embedded in
    # index.html's frontend JS (OAuth Client IDs are meant to be public).
    # Used server-side purely to verify an incoming Google token's
    # "audience" actually matches this app, so a token issued for some
    # other website can't be replayed here.
    GOOGLE_CLIENT_ID = os.getenv(
        "GOOGLE_CLIENT_ID",
        "823168004855-f0uen8dsp37nek6hi0rft6dr6d1rrc8a.apps.googleusercontent.com",
    )


settings = Settings()