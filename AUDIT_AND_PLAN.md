# Keja — Audit & Modification Plan
_(Bash → Keja rebuild, Phases 1–7 of the modification spec)_

This documents what was reused, changed, removed, and added — and, just
as important, what was deliberately **not** done in this pass so nothing
is quietly missing.

## KEEP (untouched, still doing real work)
- Auth: JWT login/register/Google sign-in (`api/v1/auth.py`, `services/auth_service.py`)
- `core/config.py`, `core/database.py` (including `ensure_schema_upgrades` —
  no Alembic, same bootstrap-migration approach as Bash), `core/security.py`,
  `core/limiter.py`
- Rate limiting (slowapi), security headers middleware, CORS setup
- Media storage (`services/storage_service.py`, `api/v1/media.py`) — reused
  directly for avatars; property images use the same disk-write pattern
- `kenya-locations.js` — reused as the county picker on Discover/Landlord
- Legal pages (terms/privacy/cookies) — left as-is content-wise

## MODIFY
- `core/dependencies.py` — added `require_landlord`, a same-column alias
  of `require_host` (no DB migration: "landlord" and "host" are the same
  `users.is_host` flag)
- `models/user.py` — removed the `events`/`sent_messages`/`received_messages`
  relationships (they referenced models no longer imported anywhere,
  which broke SQLAlchemy mapper configuration); added `free_contact_credits`
  and `referral_bonus_granted` for the new referral bonus (see below)
- `models/event.py` — `Event.host` relationship's `back_populates` removed
  to match (Event is still imported transitively by the admin panel, so
  the file stays, just decoupled from User's side)
- `services/auth_service.py` — `_credit_referrer_if_any` extended to also
  grant a **one-time** free contact-unlock credit on a user's first
  successful referral (existing free-events referral logic untouched)
- `schemas/user.py` / `api/v1/users.py` — `/users/me` now also returns
  `free_contact_credits` and `referral_bonus_granted`
- `main.py` — rewritten: only imports/registers the routers and models
  Keja actually uses (auth, admin, admin_extra, users, properties,
  contact-unlock, media); app title/APP_NAME → "Keja"
- Frontend `index.html`, `home.html`, `profile.html` — rebuilt from
  scratch with new content, same filenames (they were already the
  landing/home/profile pages)
- `manifest.json`, `sw.js`, `robots.txt`, `sitemap.xml`, `wrangler.jsonc`,
  `package.json` — rebranded to Keja; service worker cache list points at
  the real current page set
- App icons — regenerated as a simple purple house mark (`assets/*.png`);
  the old event-branded photos/splash screens were deleted

## REMOVE (from active use — files kept on disk, not deleted)
Bash's event/social feature set is unrelated to a rental platform and was
dropped from routing: bookings, tickets, live streaming, in-app messaging,
Cheki (vibe posts feed), Saka (roulette), the T-1/T-2 attendance scheduler,
waitlists, withdrawals, referral-for-free-events UI. The **model and
route files were not deleted** (e.g. `models/event.py`, `models/booking.py`,
`api/v1/bookings.py`) in case anything in them is worth mining later —
they're just no longer imported by `main.py`. Frontend pages actually
deleted: `cheki.*`, `saka.*`, `messages.*`, `host.html`, `host-agreement.html`,
`host_dashboard.*`, `saved-events.*`, `tutorial.html`, `video-trim.js`,
`countdown-badge.js`, `vibe-theme.js`, `profile-view.html`.

## ADD (new, real code — tested end-to-end, not just scaffolded)
**Backend**
- `models/property.py`, `models/property_image.py`,
  `models/interested_property.py` (`PropertySwipe` + `InterestedProperty`),
  `models/contact_unlock.py` (`ContactUnlock` + `ContactUnlockPoolEntry`)
- `schemas/property.py`, `schemas/contact_unlock.py`
- `services/property_service.py` — CRUD, search/filter, the Discover
  swipe queue (excludes already-swiped + your own listings), Interested list
- `services/contact_unlock_service.py` — the KES 50 manual M-Pesa
  matching flow, built directly on Bash's existing `parse_mpesa_message`
  parser (same two-sided match: buyer claim + admin-pasted statement).
  **STK Push is intentionally NOT implemented**, matching the spec's
  acceptance checklist.
- `api/v1/properties.py`, `api/v1/contact_unlock.py`
- **Referral bonus**: refer one friend who signs up → earn exactly one
  free contact-unlock credit, ever. The "Refer a friend" card on the
  profile page disappears permanently once that first referral lands
  (`referral_bonus_granted`), whether or not the credit's been spent.
  Every unlock after that (including once the free credit runs out)
  goes through the normal KES 50 flow.

**Frontend** (`frontend/`, same root as before — this IS the redesigned site)
- `keja.css` — full design system using the spec's exact color tokens
  (`#6C4DFF` primary / `#22C55E` green / `#F59E0B` orange, light + dark)
- `keja-app.js` — shared auth/session/theme/nav/service-worker-registration helpers
- `index.html` — login/signup, reads `?ref=CODE` from a referral link
- `home.html` / `home.js` — search bar, Recommended / Near Popular /
  Recently Added, one ad slot
- `discover.html` / `discover.js` — the actual swipe deck: drag with
  pointer events, right = interested, left = skip, swipe up or tap =
  full profile; filter sheet (county/area/price/type)
- `property.html` / `property.js` — gallery, price/status, proximity
  note, details grid, "Get Contact" → free-credit shortcut if available,
  else KES 50 till-payment modal with code paste → WhatsApp reveal once unlocked
- `interested.html` / `interested.js`
- `landlord.html` / `landlord.js` — "Become a landlord" request flow
  (reuses Bash's existing host-verification endpoints), listing
  create/edit, multi-photo upload, mark booked/available, remove
- `profile.html` / `profile.js` — theme toggle, referral card, credit
  count, links to My Listings / Interested

## Deliberately NOT done in this pass (be aware before you launch)
- **Admin panel** (`admin.html`/`admin.js`) — left untouched. It still
  works for user/event moderation but has no property-moderation UI yet.
  The backend admin contact-unlock endpoints
  (`GET/POST /contact-unlock/admin/...`) exist and work, just with no
  frontend for them yet — you'd call them directly or from API docs (`/docs`)
  for now.
- **Real till number** — `keja-app.js`'s `KEJA_MPESA_TILL.till` is a
  placeholder (`"000000"`). Swap it for your real Buy Goods/Paybill number
  before taking real payments.
- **Kotlin/Android app** — out of scope for this environment (no Android
  SDK/Gradle here); a separate task if/when you want it.
- **Legal page text** — terms/privacy/cookies still contain Bash's
  events-specific language; only navigation links were fixed. Worth a
  real rewrite pass before launch.
- Ads are a single static placeholder slot (`Keja.renderAd`) — no real ad
  network wired in.

## What was actually verified (not just written)
Ran a full request cycle against a live SQLite instance: register →
login → landlord creates listing → renter discovers it → swipes right →
appears in Interested → requests contact → free-credit path AND KES 50
manual-claim path both tested → referral signup grants exactly one
one-time credit → property image upload. All passed.
