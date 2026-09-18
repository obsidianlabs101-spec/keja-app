"""
app/api/v1/public_share.py

Public, no-auth-required share landing pages for events and posts.

Why this exists: WhatsApp, TikTok, iMessage, etc. build the little
preview card (image + title) you see under a pasted link by fetching the
URL themselves and reading its <meta property="og:..."> tags — they do
NOT run JavaScript. cheki.html is a client-rendered SPA, so a link like
".../cheki.html?reelId=xyz" has no way to show a per-post image/title in
that preview; every shared link would look identical and generic.

These two routes return plain server-rendered HTML with the right
og:title/og:image/og:video tags baked in for the *specific* event or post
being shared, so the link preview actually shows that flyer/clip. The
page body itself is a minimal "here's the media + an Open in BASH button"
landing page — so a non-user who taps the link lands on our site (not
straight into the app), sees the content, and gets a clear path to the
real site/app instead of a dead end.
"""
import html as html_lib
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.event import Event
from app.models.cheki_feed_item import ChekiFeedItem

router = APIRouter(tags=["Public Share"])

SITE_NAME = "BASH"


def _abs_media_url(request, media_url: str) -> str:
    """Media is stored as a relative path like /static/posters/x.jpg —
    social crawlers need an absolute URL to fetch the preview image."""
    if not media_url:
        return ""
    if media_url.startswith("http://") or media_url.startswith("https://"):
        return media_url
    base = str(request.base_url).rstrip("/")
    return f"{base}{media_url}"


def _is_video_url(url: str) -> bool:
    return bool(url) and url.lower().split("?")[0].endswith((".mp4", ".webm", ".mov", ".mkv"))


def _render_share_page(request, *, title: str, description: str, media_url: str, app_deeplink: str) -> str:
    esc = html_lib.escape
    is_video = _is_video_url(media_url)
    abs_media = _abs_media_url(request, media_url)
    page_url = str(request.url)

    og_media_tags = ""
    if abs_media and is_video:
        og_media_tags = f"""
    <meta property="og:video" content="{esc(abs_media)}" />
    <meta property="og:video:type" content="video/mp4" />
    <meta name="twitter:card" content="player" />
    <meta name="twitter:player:stream" content="{esc(abs_media)}" />"""
    elif abs_media:
        og_media_tags = f"""
    <meta property="og:image" content="{esc(abs_media)}" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:image" content="{esc(abs_media)}" />"""

    media_body = ""
    if abs_media and is_video:
        media_body = f'<video src="{esc(abs_media)}" controls autoplay muted playsinline loop style="width:100%;border-radius:16px;"></video>'
    elif abs_media:
        media_body = f'<img src="{esc(abs_media)}" alt="{esc(title)}" style="width:100%;border-radius:16px;display:block;" />'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{esc(title)} · {SITE_NAME}</title>
<meta property="og:site_name" content="{SITE_NAME}" />
<meta property="og:title" content="{esc(title)}" />
<meta property="og:description" content="{esc(description)}" />
<meta property="og:url" content="{esc(page_url)}" />
<meta property="og:type" content="website" />{og_media_tags}
<meta name="description" content="{esc(description)}" />
<style>
  body {{ margin:0; background:#0a0a0a; color:#fff; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }}
  .wrap {{ max-width:480px; margin:0 auto; padding:20px; }}
  .brand {{ display:flex; align-items:center; gap:8px; font-weight:800; letter-spacing:0.5px; margin-bottom:16px; color:#ff2d95; }}
  .media-box {{ position:relative; }}
  .watermark-badge {{
    position:absolute; bottom:14px; right:14px; background:rgba(0,0,0,0.55);
    color:#fff; font-weight:800; font-size:13px; letter-spacing:0.5px;
    padding:6px 12px; border-radius:999px; backdrop-filter:blur(4px);
    border:1px solid rgba(255,255,255,0.25); pointer-events:none;
  }}
  h1 {{ font-size:19px; margin:16px 0 6px; }}
  p.desc {{ font-size:14px; color:#bbb; line-height:1.5; margin:0 0 20px; }}
  a.cta {{
    display:block; text-align:center; padding:14px; border-radius:14px;
    background:#ff2d95; color:#fff; font-weight:800; text-decoration:none; font-size:15px;
  }}
  .foot {{ text-align:center; font-size:11px; color:#555; margin-top:18px; }}
</style>
</head>
<body>
  <div class="wrap">
    <div class="brand">🎉 {SITE_NAME}</div>
    <div class="media-box">
      {media_body}
      <div class="watermark-badge">{SITE_NAME}</div>
    </div>
    <h1>{esc(title)}</h1>
    <p class="desc">{esc(description)}</p>
    <a class="cta" href="{esc(app_deeplink)}">Open in {SITE_NAME}</a>
    <div class="foot">Shared from {SITE_NAME} — Kenya's live event marketplace</div>
  </div>
</body>
</html>"""


@router.get("/e/{event_id}", response_class=HTMLResponse)
def share_event_page(event_id: str, request: Request, db: Session = Depends(get_db)):
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
    except Exception:
        event = None

    deeplink = f"/frontend/cheki.html?reelId={event_id}"
    if event is None:
        return HTMLResponse(
            _render_share_page(
                request,
                title=f"Event not found · {SITE_NAME}",
                description="This event may have been removed or the link is incorrect.",
                media_url="",
                app_deeplink="/frontend/home.html",
            ),
            status_code=404,
        )

    when = ""
    try:
        when = event.start_date.strftime("%a %d %b, %I:%M %p") if event.start_date else ""
    except Exception:
        when = ""

    description = " · ".join(filter(None, [when, event.venue_name, (event.description or "")[:160]]))
    media_url = event.video_url or event.poster_url or ""

    return HTMLResponse(_render_share_page(
        request,
        title=event.title,
        description=description or f"Catch {event.title} on {SITE_NAME}.",
        media_url=media_url,
        app_deeplink=deeplink,
    ))


@router.get("/p/{reel_id}", response_class=HTMLResponse)
def share_post_page(reel_id: str, request: Request, db: Session = Depends(get_db)):
    item = db.query(ChekiFeedItem).filter(ChekiFeedItem.reel_id == reel_id).first()

    deeplink = f"/frontend/cheki.html?reelId={reel_id}"
    if item is None:
        return HTMLResponse(
            _render_share_page(
                request,
                title=f"Post not found · {SITE_NAME}",
                description="This post may have been removed or the link is incorrect.",
                media_url="",
                app_deeplink="/frontend/cheki.html",
            ),
            status_code=404,
        )

    title = item.event_name or (f"{item.username} on {SITE_NAME}" if item.username else f"A post on {SITE_NAME}")
    description = item.caption or item.vibe_text or f"See this on {SITE_NAME}."

    return HTMLResponse(_render_share_page(
        request,
        title=title,
        description=description,
        media_url=item.media_url or "",
        app_deeplink=deeplink,
    ))