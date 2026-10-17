"""In-process stale-while-revalidate cache for public, non-personal GET responses.

Why: Home/Discover/category chips ask the same questions over and over, and
the database (a different server, maybe a different country) answers slowly.
So:
  * fresh (within `ttl`)            -> answered from memory, instantly
  * stale (older, up to STALE_FOR)  -> still answered from memory instantly,
                                       and refreshed in the background
  * missing                         -> asked from the database (rare: only the
                                       very first request after a restart)
A background warmer (see app/core/warmer.py) keeps the hot URLs fresh, so in
practice new visitors almost never wait for the database at all.

Any successful write to listings/admin clears everything at once, so people
never see stale data after a change.

One Render instance = one cache. With several instances each keeps its own.
"""
import threading
import time
from typing import Optional, Tuple

STALE_FOR = 15 * 60          # serve stale copies for up to 15 minutes while refreshing
_MAX_ENTRIES = 300
_lock = threading.Lock()
_store: dict = {}  # key -> (fresh_until, stale_until, status, headers, body, media_type)


def get(key: str) -> Optional[Tuple[bool, int, dict, bytes, Optional[str]]]:
    """Returns (is_fresh, status, headers, body, media_type) or None."""
    now = time.monotonic()
    with _lock:
        item = _store.get(key)
        if not item:
            return None
        if item[1] < now:
            _store.pop(key, None)
            return None
        return item[0] >= now, item[2], item[3], item[4], item[5]


def put(key: str, ttl: float, status: int, headers: dict, body: bytes, media_type: Optional[str]) -> None:
    now = time.monotonic()
    with _lock:
        if len(_store) >= _MAX_ENTRIES:
            oldest = min(_store, key=lambda k: _store[k][1])
            _store.pop(oldest, None)
        _store[key] = (now + ttl, now + max(ttl, STALE_FOR), status, headers, body, media_type)


def clear() -> None:
    with _lock:
        _store.clear()
