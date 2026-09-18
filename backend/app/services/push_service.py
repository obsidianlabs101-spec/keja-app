"""
Web Push — sends a real notification that shows up in the user's phone/OS
notification tray via their browser's push service (FCM for Chrome/Android,
APNs-backed for Safari/iOS 16.4+, etc.), instead of something only visible
by opening the app.

Requires the `pywebpush` package (`pip install pywebpush`).

Usage:
    from app.services.push_service import send_web_push
    send_web_push(db, user, title="Still going?", body="...", data={...})

    # Optional extras — all are just richer fields in the same payload:
    send_web_push(
        db, user, title="...", body="...",
        image=event.poster_url,           # relative OR absolute path, see below
        tag=f"nearby-{event.id}",         # groups/replaces instead of stacking
        actions=[{"action": "going", "title": "✅ I'm going"}],
    )

Safe to call even if the user never enabled push (push_subscription is
None) — it's just a no-op then, so every call site can call this
unconditionally after creating an in-app Notification row.
"""
import json

from sqlalchemy.orm import Session

from app.core.config import settings

try:
    from pywebpush import webpush, WebPushException
    _PUSH_AVAILABLE = True
except ImportError:  # pywebpush not installed yet — degrade gracefully
    _PUSH_AVAILABLE = False


def _absolute_media_url(path):
    """Turns a relative static path (e.g. "static/posters/xxx.jpg") into a
    full URL the browser/OS can actually fetch for a push notification's
    image. Returns the input unchanged if it's already absolute, and None
    if there's nothing to show or nothing configured to build one from —
    better to send a notification with no image than one with a broken
    relative URL the OS silently fails to load."""
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not settings.PUBLIC_MEDIA_BASE_URL:
        return None
    return f"{settings.PUBLIC_MEDIA_BASE_URL}/{path.lstrip('/')}"


def send_web_push(
    db: Session,
    user,
    title: str,
    body: str,
    data: dict | None = None,
    image: str | None = None,
    tag: str | None = None,
    actions: list | None = None,
) -> bool:
    """Sends a push notification to `user`'s subscribed device(s). Returns
    True if a push was actually sent, False otherwise (no subscription,
    library missing, or the push failed). Never raises — a push failure
    should never break the request/sweep that triggered it.

    image: banner photo shown below the notification text (event poster,
        sender's avatar, etc). Chrome/Android only — Safari/iOS silently
        ignores it, which is fine, it just falls back to icon-only.
    tag: notifications sharing a tag replace each other in the tray
        instead of stacking (e.g. one entry per sender, not one per
        message). Omit for a reminder that should always stand on its own.
    actions: up to 2 dicts like {"action": "going", "title": "✅ I'm going"}
        — rendered as quick-action buttons. sw.js's notificationclick
        handler reads e.action to know which one was tapped.
    """
    if not _PUSH_AVAILABLE:
        print("⚠️  pywebpush not installed — skipping push notification (in-app notification still saved).")
        return False

    raw = getattr(user, "push_subscription", None)
    if not raw:
        return False

    try:
        subscription_info = json.loads(raw)
    except Exception:
        return False

    payload_dict = {
        "title": title,
        "body": body,
        "data": data or {},
    }
    abs_image = _absolute_media_url(image)
    if abs_image:
        payload_dict["image"] = abs_image
    if tag:
        payload_dict["tag"] = tag
    if actions:
        payload_dict["actions"] = actions

    payload = json.dumps(payload_dict)

    try:
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_CLAIM_EMAIL},
        )
        return True
    except WebPushException as e:
        status_code = getattr(e.response, "status_code", None)
        if status_code in (404, 410):
            # Subscription expired or was revoked by the browser — clear it
            # so we stop trying (and the frontend knows to re-subscribe).
            user.push_subscription = None
            db.add(user)
            db.commit()
        else:
            print(f"⚠️  Push notification failed for user {user.id}: {e}")
        return False
    except Exception as e:
        print(f"⚠️  Push notification error for user {user.id}: {e}")
        return False