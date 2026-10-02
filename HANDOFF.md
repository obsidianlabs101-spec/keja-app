# Keja — Handoff (updated 2026-10-02)

This file is for a **new Claude chat session** picking up this project cold. Read
this whole file before touching anything. It replaces any earlier HANDOFF.md.

## What Keja is

A property rental platform for Kenya: website + Android app + FastAPI backend.
Renters browse/swipe listings, pay a small KES fee via M-Pesa to unlock a
landlord's contact, and landlords manage their own listings. There's an admin
back office for moderation. Originally rebuilt from an older project called
"Bash" (a ticketing app) — some unrelated dead code/routes from that still
exist in the backend (see "Known issues" below).

## Access

- **GitHub repo:** `obsidianlabs101-spec/keja-app` — https://github.com/obsidianlabs101-spec/keja-app
- **GitHub PAT (repo + workflow scopes), expires 2026-10-20:** deliberately
  **not stored in this file** — GitHub's push protection blocks any commit
  containing a recognizable token, for good reason (git history is
  permanent). The user has the real token from the chat where this file was
  written, as a separate file outside the repo. Ask them for it directly if
  you don't have it. After it expires, generate a new one at
  https://github.com/settings/tokens (repo + workflow scopes) and have the
  user share it the same way — never commit it. Use it for git push/pull
  (`https://<TOKEN>@github.com/obsidianlabs101-spec/keja-app.git`) and all
  `api.github.com` calls (Actions dispatch, releases, ci-logs).
- **Render workspace:** "Samson's workspace", id `tea-damevjtbedkc73bgqpfg`.
  Use the `mcp__Render__*` tools (list_services, list_deploys, list_logs) to
  check real deploy status — **do not trust "pushed to GitHub" as proof the
  backend is live**; it has silently failed to deploy before (see below).
  - Backend service: `keja-backend`, id `srv-damkdvn40ujc73b9fcc0`,
    https://keja-backend-uqzk.onrender.com
  - Frontend static site: `keja-frontend`, https://keja-frontend.onrender.com
- **Supabase project:** id `mepnzrjhmaotilbqnvsy`. Used for Postgres DB and
  image storage (buckets: `property-images`, `ad-images`).
- **Admin login (website/app):** email `sam@gmail.com` — the user changed the
  password at some point in this project; ask them for the current one if an
  admin session is needed, don't assume `string123` (that was the original
  leaked default, already rotated once).

## Architecture

- **Backend:** `backend/` — FastAPI + SQLAlchemy + Postgres (via Supabase).
  Tables are created/altered automatically at boot by
  `core/database.py`'s schema-upgrade helper — **new model → just import it
  in `main.py`** (see the block of `from app.models.X import Y # noqa: F401`
  lines) and it gets its table/columns added on the next deploy. No manual
  migrations needed.
- **Website:** `frontend/` — a single-page vanilla-JS app (`app.js`, `index.html`,
  `style.css`), no build step. Served as a static site by Render.
  `sw.js` is a service worker with a cache version string
  (`keja-cache-vNN`) — **bump it on every frontend change** or users won't
  see updates (currently v11).
- **Android:** `android/` — Kotlin + Jetpack Compose, single module
  (`app`). No local build toolchain in this sandbox (no Android SDK, no
  network access to Google's Maven) — **all Android changes are verified by
  pushing and checking GitHub Actions**, never compiled locally beyond a
  brace/paren balance check (see "How to work in this sandbox" below).

## How to work in this sandbox (read this before editing)

1. **No local build tools.** You can write/edit files and do a naive
   brace/paren balance check in Python, but that does NOT catch real Kotlin
   compile errors (missing imports, wrong types, etc.) — it only catches
   gross mismatches. Always push and check CI.
2. **Triggering a build:** after pushing to `main`,
   `POST /repos/obsidianlabs101-spec/keja-app/actions/workflows/android-build.yml/dispatches`
   with `{"ref":"main"}` (needs the PAT). Pushing to `main` alone also
   triggers it automatically (`on: push`), but dispatching immediately avoids
   waiting on a stale queued run.
3. **Checking the result:**
   `GET /repos/obsidianlabs101-spec/keja-app/actions/runs?per_page=1` for
   status. Builds take **3–6 minutes**; poll, don't assume done after 30s.
4. **If it fails:** GitHub's raw log download redirects to
   `*.blob.core.windows.net`, which is **not in this sandbox's network
   allowlist** — `curl`/`web_fetch` on it will fail. The workflow has a
   built-in fallback for exactly this: on failure it pushes the real Gradle/
   Kotlin error log to a branch called `ci-logs` (see
   `.github/workflows/android-build.yml`). Fetch it with:
   ```
   git fetch <token-url> ci-logs:refs/remotes/origin/ci-logs --force
   git show origin/ci-logs:last-build.log | grep -n "^e: "
   ```
   This has been reliable; trust it over guessing. (A `kotlinc` problem
   matcher / annotations approach was tried first and didn't work — the
   regex didn't match this Kotlin version's error format — so the log-to-
   branch fallback is the real mechanism now.)
5. **Signing:** there is a **permanent release keystore** stored as GitHub
   secrets (`KEJA_KEYSTORE_B64`, `KEJA_KEYSTORE_PASSWORD`) so every CI build
   is signed identically. This was added specifically because every build
   used to need an uninstall/reinstall on the test phone (Android refuses to
   install over an app signed with a different key, and every CI build used
   to get a fresh random debug key). **Never regenerate this keystore** —
   doing so would break updates for anyone who already has the app
   installed, back to needing uninstall/reinstall again.
6. **The Android APK is distributed via a GitHub Release**, tag
   `android-latest`, always re-published to the same tag so the download
   link never changes:
   `https://github.com/obsidianlabs101-spec/keja-app/releases/download/android-latest/app-debug.apk`.
   A companion `keja-version.json` (`{"build": N}`) is published alongside
   it, where N is `${{ github.run_number }}` — this is how the in-app
   updater (Profile → App update) knows a newer build exists. Both are only
   published `if: steps.build.outcome == 'success'`.
7. **Backend deploys are NOT verified by pushing alone.** Render
   auto-deploys on push to `main`, but it has **silently failed on every
   deploy for an extended period before** (see Known Issues) while still
   serving the old build — pushing + "looks fine" is not proof. Always
   confirm with `mcp__Render__list_deploys` → look for `"status": "live"` on
   the newest deploy, or check `mcp__Render__list_logs` for a clean recent
   request. `list_workspaces` → `list_services` if you ever lose the
   workspace/service IDs above.

## What's built (functionally complete, deployed and verified working)

- **Core rental flow:** property listings (apartments, Airbnb, commercial/
  shop — landlord picks a Category + sub-type, not free text), rent vs sale
  (`listing_type`), optional agent fee, photo galleries with a full-screen
  swipeable viewer (Back/Get contact), amenities as icon cards, Home/
  Discover/Interested pages with For rent/For sale pills and Apartments/
  Airbnb/Shops category filters.
- **Contact unlock:** KES 50 M-Pesa payment (manual confirmation message
  paste → admin reviews → "Show" sends the landlord's number to the renter's
  Alerts), or a free unlock via referral (share a link; when the referred
  friend actually signs up, the number is sent automatically). Till name is
  "Obsidian Labs".
- **Alerts (the bell):** in-app notification center for both landlords and
  renters — landlord number ready, application approved/rejected, listing
  approved/rejected, property booked, etc. On Android these also surface as
  **real system-tray notifications** (WorkManager background check every 15
  min + on app open, de-duplicated, styled with the brand bell + gradient),
  since there's no Firebase/push server set up — this is polling, not true
  push.
- **Property alerts (new):** a renter can ask "let me know about new
  properties matching X" (location / price range / landlord name) from an
  exit-intent dialog (see below). Saved via `/properties/alerts/me`; a
  newly created property is checked against every saved alert and matching
  renters get notified.
- **Exit-intent dialog (Android, Home screen, back button):** first
  back-press shows a styled dialog nudging toward setting up a property
  alert instead of leaving, with a "don't ask again" option; a second
  back-press (or tapping Exit) shows a short goodbye message and actually
  closes the app.
- **Host comments ("What renters say"):** a real comment thread on a
  landlord's public profile. One comment per renter per landlord (posting
  again edits it in place), visible to everyone, delete-your-own. Built on
  both website and Android.
- **Landlord features:** dashboard (gradient hero, stats, listings with
  Delete + Amenities + Mark booked, agent fee badge), landlord ID photo
  required before admin approval, public landlord profile page.
- **Admin back office:** separate pages (not just one dashboard) for
  Overview, New listings (approve/reject), Landlord applications
  (approve/reject + view ID photo), Payment messages (review pasted M-Pesa
  SMS, Show/Reject), All listings (force-booked, reject), Ads. Mirrored on
  web and Android.
- **Ads:** admin-managed banner ads on Home and Interested (not Discover —
  moved per request), with size guidance (4:1, 1200×300) and live preview.
- **Branding:** real logo/icon/favicon/loader from a supplied brand kit
  (outlined the wordmark in the actual Bricolage Grotesque font since the
  supplied SVGs silently fell back to a system font), applied to web + app
  (app icon, in-app logo, notification icon, login screen banner).
- **In-app updater (Android, Profile → App update):** checks
  `keja-version.json` against the installed build number, downloads and
  installs the new APK via `FileProvider` + the system installer. This is
  what the permanent signing key (above) makes possible without
  uninstalling.
- **Security pass completed:** property-image upload now validates actual
  image bytes (was trusting the client-supplied filename/extension — a
  renamed non-image file would've been stored and served with a spoofed
  Content-Type); rate limiting added to contact-unlock claim/free-credit/
  referral and host-verification/ID-photo upload (previously unlimited).
  Reviewed and confirmed clean: no SQL injection (ORM everywhere,
  parameterized; the only raw SQL is static DDL from model metadata at
  boot), no IDOR on property update/delete (ownership checked), CORS is an
  explicit allowlist (no wildcard+credentials), M-Pesa callback has IP
  allowlisting + a DEBUG-gated dev-simulate endpoint.
- **Theming:** two visual styles (Professional, Rangi) x light/dark, all
  driven by `LocalKejaPalette` — any new UI should read colors from there,
  never hardcode hex values, or it'll look broken in Rangi (this exact bug
  happened once already — a hardcoded purple heart in Discover — and was
  fixed).

## Known issues / things to watch

1. **Backend deploys can silently fail.** This happened for a long stretch:
   `DATABASE_URL` uses the `postgresql+psycopg` (v3) dialect but only
   `psycopg2-binary` was installed, so the server crashed on every boot —
   Render kept serving a stale old build the whole time while every deploy
   showed `update_failed`. Fixed by adding `psycopg[binary]` to
   `requirements.txt`, but **always verify new deploys show `"status":
   "live"`** via the Render MCP tools, never assume a push "worked" just
   because GitHub accepted it.
2. **Dead code from the old "Bash" app** (events, bookings, community
   posts, follows, etc.) is still mounted in the backend — unused by Keja,
   not wired to any current UI, but it's live attack surface nobody
   reviews. Worth removing as its own careful task (check nothing secretly
   depends on it first); explicitly deferred so far to avoid breaking
   something mid-task.
3. **Android token storage** uses plain DataStore Preferences, not
   encrypted. Acceptable (Android sandboxes per-app storage) but
   `androidx.security:security-crypto` / EncryptedSharedPreferences would
   be stronger. Not done — noted, not urgent.
4. **A stale-git-ref scare happened once** mid-project (a `git fetch` without
   an explicit refspec returned a cached/stale `origin/main` pointing at a
   totally different, older history, which looked like a destructive
   concurrent edit). It turned out to be a tooling artifact, not a real
   conflict — resolved by fetching with an explicit refspec
   (`git fetch <url> main:refs/remotes/origin/main`). If something like this
   happens again: don't panic-push, don't force-push, re-fetch explicitly
   and compare `git merge-base` before concluding history diverged.
5. **The CI "problem matcher" annotations don't work** (wrong regex for
   this Kotlin version's output) — rely on the `ci-logs` branch fallback
   described above, not GitHub's check-run annotations, when debugging a
   failed Android build.
6. The **till name is "Obsidian Labs"**, not "Keja Kenya" — this was
   changed partway through; if you see "Keja Kenya" anywhere in an M-Pesa
   context, it's stale and should be fixed.

## Suggested next steps (nothing urgent is currently broken)

- Ask the user if they want the dead "Bash" routes actually removed now
  (issue 2 above).
- Consider real push notifications (Firebase) instead of the 15-minute
  WorkManager poll, if instant alerts matter enough to justify setting up a
  Firebase project.
- Consider EncryptedSharedPreferences for the Android auth token (issue 3).
- The website hasn't had the same "visually stunning" redesign pass the
  Android screens got (Home, Profile, Discover, Interested, Landlord
  dashboard, Auth/login, exit-intent dialog) — the user may want parity
  there eventually; nothing has been promised.

## Working style notes for whoever picks this up

- The user dictates quickly/informally (voice-to-text typos are common —
  read intent, not literal text, but when genuinely ambiguous, it's fine to
  make a reasonable call and say what you assumed).
- They've caught real mistakes before (removing the wrong thing, missing
  the actual point of a request) — when a request is ambiguous, lean toward
  checking existing code/behavior first rather than guessing from scratch.
- They want both web and Android kept in parity for anything that's a real
  feature (not true for pure visual polish passes, which have been
  Android-only so far by request).
- Always trigger the Android build and wait for a real pass/fail after any
  Android change — several rounds of this project shipped silently-broken
  builds before this discipline was enforced. Same for backend: verify
  Render shows `live`, don't just push and assume.
