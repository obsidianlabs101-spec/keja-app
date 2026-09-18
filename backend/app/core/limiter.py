# app/core/limiter.py
#
# Central rate limiter (slowapi, backed by an in-process memory store —
# fine for a single-instance deploy; move to a Redis storage_uri if BASH
# ever runs multiple worker processes/replicas, since separate processes
# don't share this in-memory counter).
#
# Before this file existed, there was NO rate limiting anywhere on the
# API: /auth/login, /auth/register, and the M-Pesa STK-push trigger could
# all be hit as fast as a script could send requests — meaning unlimited
# password-guessing against login, unlimited fake-account creation, and
# unlimited STK push prompts spammed to a real phone number. This closes
# that gap.
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# Keyed by client IP. Behind a reverse proxy (nginx/Render/Railway), make
# sure X-Forwarded-For is trusted/forwarded correctly or every request
# will appear to come from the proxy's single IP, making the limit apply
# globally instead of per-visitor.
#
# storage_uri: when VALKEY_URL is set, counters live in Valkey so every
# Render instance/worker enforces the SAME limit against the same
# counter — without this, each process has its own in-memory count, so
# e.g. a "5/minute" login limit actually becomes "5/minute PER PROCESS"
# once you run more than one instance, which defeats the point. Falls
# back to the original in-memory store when VALKEY_URL isn't set, so
# local dev needs no extra setup.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"],
    storage_uri=settings.VALKEY_URL or None,
)