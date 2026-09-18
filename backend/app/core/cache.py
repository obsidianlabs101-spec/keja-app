# app/core/cache.py
#
# Thin wrapper around a Valkey (Redis-protocol-compatible) connection,
# used for two things:
#   1. Cache-aside reads for hot, public, read-heavy endpoints (event
#      list/detail) — see get_json/set_json/delete below.
#   2. A shared storage_uri for slowapi's rate limiter, so limits are
#      enforced across ALL Render instances/workers instead of each
#      process keeping its own in-memory counter (see limiter.py).
#
# Deliberately fails "open" everywhere except the rate limiter: if
# VALKEY_URL isn't set, or the cache is briefly unreachable, every
# cached endpoint just falls back to hitting Postgres directly like it
# always did. A cache outage should degrade performance, never take the
# site down or serve an error.
import json
import logging
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger("bash.cache")

_client = None
_client_init_attempted = False


def get_client():
    """Returns a shared Valkey client, or None if caching isn't configured
    or the import/connection failed. Lazily initialized so the app can
    still boot with zero Valkey-related setup (local dev, VALKEY_URL
    unset, etc.)."""
    global _client, _client_init_attempted

    if _client is not None:
        return _client
    if _client_init_attempted:
        return None
    _client_init_attempted = True

    if not settings.VALKEY_URL:
        logger.info("VALKEY_URL not set — caching disabled, reads go straight to Postgres.")
        return None

    try:
        # redis-py (pinned in requirements.txt) talks to Valkey natively —
        # they share the same wire protocol, Valkey being a protocol-
        # compatible fork of Redis. It's also what slowapi/limits'
        # storage_uri backend requires by import name (see limiter.py),
        # so using it here too avoids needing two separate client
        # packages. If valkey-py happens to be installed instead, prefer
        # it — same API, just the more literally-named option.
        try:
            from valkey import Redis as _Client
        except ImportError:
            from redis import Redis as _Client

        client = _Client.from_url(
            settings.VALKEY_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        _client = client
        logger.info("Connected to Valkey cache.")
        return _client
    except Exception as e:
        logger.warning(f"⚠️  Could not connect to Valkey at VALKEY_URL ({e}) — caching disabled, falling back to Postgres for every read.")
        return None


def get_json(key: str) -> Optional[Any]:
    """Returns the deserialized value for `key`, or None on a miss OR any
    cache error. Callers should treat None as \"go fetch it yourself\" —
    never distinguish a real cache miss from an outage."""
    client = get_client()
    if client is None:
        return None
    try:
        raw = client.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as e:
        logger.warning(f"Cache read failed for key={key}: {e}")
        return None


def set_json(key: str, value: Any, ttl_seconds: int) -> None:
    """Best-effort write-through. Never raises — a failed cache write
    should never fail the request that computed the value."""
    client = get_client()
    if client is None:
        return
    try:
        client.set(key, json.dumps(value, default=str), ex=ttl_seconds)
    except Exception as e:
        logger.warning(f"Cache write failed for key={key}: {e}")


def delete(*keys: str) -> None:
    """Best-effort invalidation. Call this from every code path that
    mutates something a cached response depends on."""
    if not keys:
        return
    client = get_client()
    if client is None:
        return
    try:
        client.delete(*keys)
    except Exception as e:
        logger.warning(f"Cache invalidation failed for keys={keys}: {e}")


def delete_by_prefix(prefix: str) -> None:
    """Deletes every key starting with `prefix`. Used for the public event
    list cache, which is keyed per (search, category) combo — a single
    event changing needs to invalidate all of them, not just one, since
    we don't know in advance which filter combos it appeared under.
    Uses SCAN (not KEYS) so it doesn't block Valkey on a large keyspace."""
    client = get_client()
    if client is None:
        return
    try:
        matched = list(client.scan_iter(match=f"{prefix}*", count=200))
        if matched:
            client.delete(*matched)
    except Exception as e:
        logger.warning(f"Cache prefix invalidation failed for prefix={prefix}: {e}")