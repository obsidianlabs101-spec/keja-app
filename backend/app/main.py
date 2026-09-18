from fastapi import FastAPI

from app.api.v1.auth import router as auth_router
from app.api.v1.admin import router as admin_router
from app.api.v1.admin_extra import router as admin_extra_router

from app.api.v1.users import router as user_router
from app.api.v1.properties import router as property_router
from app.api.v1.contact_unlock import router as contact_unlock_router

from app.core.config import settings
from app.core.database import Base
from app.core.database import engine
from app.core.database import ensure_schema_upgrades

from app.models.notification import Notification

# Ensure all models are imported so Base.metadata.create_all creates their tables.
# NOTE (Keja rebrand): Bash's events/social models (cheki, tickets, bookings,
# messages, streaming, etc.) are intentionally NOT imported here anymore —
# their tables simply stop being created/migrated going forward. The model
# files themselves are left on disk (unused) rather than deleted, in case
# any of that logic is worth mining later; see AUDIT_AND_PLAN.md.
from app.models.user_session import UserSession  # noqa: F401
from app.models.user_block import UserBlock  # noqa: F401
from app.models.admin_activity_log import AdminActivityLog  # noqa: F401
from app.models.platform_settings import PlatformSettings  # noqa: F401
from app.models.taxonomy_entry import TaxonomyEntry  # noqa: F401

from app.models.property import Property  # noqa: F401
from app.models.property_image import PropertyImage  # noqa: F401
from app.models.interested_property import InterestedProperty, PropertySwipe  # noqa: F401
from app.models.contact_unlock import ContactUnlock, ContactUnlockPoolEntry  # noqa: F401

from fastapi import Response

import traceback as _boot_traceback

# Create each table individually — checkfirst=True (the default) skips
# ones that already exist — instead of one Base.metadata.create_all()
# call. A single call means one bad table/index definition anywhere
# raises an exception that aborts the ENTIRE batch. See app/core/database.py.
for _table in Base.metadata.sorted_tables:
    try:
        _table.create(bind=engine, checkfirst=True)
    except Exception as e:
        print(f"⚠️ Database setup notice: failed to create table '{_table.name}': {e}")
        print(_boot_traceback.format_exc())

try:
    ensure_schema_upgrades(engine)
except Exception as e:
    print(f"⚠️ Schema upgrade notice: {e}")
    print(_boot_traceback.format_exc())


from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import os

from app.api.v1.media import router as media_router

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.limiter import limiter

app = FastAPI(
    title="Keja API"
)

# RATE LIMITING — see app/core/limiter.py.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


import traceback
from fastapi.responses import JSONResponse

@app.middleware("http")
async def security_headers(request, call_next):
    """Baseline security headers — response-only, never break functionality."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if not settings.DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.middleware("http")
async def log_requests(request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    print(f"--- INCOMING REQUEST: {request.method} {request.url.path} ---")
    try:
        response = await call_next(request)
        print(f"--- RESPONSE STATUS: {response.status_code} ---")
        return response
    except Exception as e:
        print("\n❌ !!! CRITICAL BACKEND CRASH !!! ❌")
        traceback.print_exc()
        print("------------------------------------\n")
        detail = str(e) if settings.DEBUG else "Internal Server Error"
        return JSONResponse(
            status_code=500,
            content={"detail": detail},
        )

# SECURITY: CORSMiddleware must be added last so it's genuinely outermost
# — see the long comment this originally shipped with in Bash's main.py
# for exactly why middleware order matters here (Starlette adds each new
# middleware to the FRONT of the stack).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure local disk storage directories exist
os.makedirs("static/avatars", exist_ok=True)
os.makedirs("static/properties", exist_ok=True)
os.makedirs("static/documents", exist_ok=True)

# Serve media directly from disk
app.mount("/static", StaticFiles(directory="static"), name="static")
if os.path.isdir("frontend"):
    app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(admin_extra_router)
app.include_router(user_router)
app.include_router(property_router)
app.include_router(contact_unlock_router)
app.include_router(media_router)


@app.get("/")
def home():
    return {
        "message": "Keja API running"
    }
