"""Small in-process TTL cache for public, non-personal GET responses.

Why: Home/Discover/category chips ask the same question over and over (every
page change, every visitor). Answering from memory for a few seconds spares
the database; any successful write to listings/admin clears it at once, so
people never wait more than the TTL to see new data - usually not at all.

One Render instance = one cache. If Keja is ever scaled to several
instances, each keeps its own (still correct, just less effective).
"""
import threading
import time
from typing import Optional, Tuple

_MAX_ENTRIES = 300
_lock = threading.Lock()
_store: dict = {}  # key -> (expires_at, status, headers, body, media_type)


def get(key: str) -> Optional[Tuple[int, dict, bytes, Optional[str]]]:
    now = time.monotonic()
    with _lock:
        item = _store.get(key)
        if not item:
            return None
        if item[0] < now:
            _store.pop(key, None)
            return None
        return item[1], item[2], item[3], item[4]


def put(key: str, ttl: float, status: int, headers: dict, body: bytes, media_type: Optional[str]) -> None:
    with _lock:
        if len(_store) >= _MAX_ENTRIES:
            # drop the soonest-to-expire entry
            oldest = min(_store, key=lambda k: _store[k][0])
            _store.pop(oldest, None)
        _store[key] = (time.monotonic() + ttl, status, headers, body, media_type)


def clear() -> None:
    with _lock:
        _store.clear()
