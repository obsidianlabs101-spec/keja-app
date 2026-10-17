"""Keeps the hottest public responses ready in memory.

Runs inside the server process. Every WARM_EVERY seconds it asks Keja's own
API (in-process, no network) for the URLs people hit first. Those requests go
through the normal response cache with a "refresh" marker, so the cache is
refilled BEFORE it goes stale. It also keeps a database connection warm.
Safe by design: a failure here is only logged and never affects users.
"""
import asyncio

WARM_EVERY = 25  # seconds (cache TTL for these is 30s)

# Exactly the URLs the website and the Android app request (the cache key is
# the path + sorted query string, so these must match what clients send).
HOT_URLS = [
    "/properties/?limit=48",
    "/properties/?limit=48&listing_type=rent",
    "/properties/?limit=48&listing_type=sale",
    "/properties/?limit=24",
    "/properties/category-counts",
    "/properties/category-counts?listing_type=rent",
    "/properties/category-counts?listing_type=sale",
    "/properties/categories",
    "/properties/locations",
    "/ads/home",
]

_refreshing: set = set()


async def refresh_url(app, url: str) -> None:
    """Fetch `url` through the app so the cache middleware stores a fresh copy."""
    if url in _refreshing:
        return
    _refreshing.add(url)
    try:
        import httpx
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://keja.internal", timeout=20) as client:
            await client.get(url, headers={"x-cache-refresh": "1"})
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Cache refresh skipped for {url}: {e}")
    finally:
        _refreshing.discard(url)


async def warm_forever(app) -> None:
    await asyncio.sleep(2)  # let startup finish
    while True:
        for url in HOT_URLS:
            await refresh_url(app, url)
        await asyncio.sleep(WARM_EVERY)
