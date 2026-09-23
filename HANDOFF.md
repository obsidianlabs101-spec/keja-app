# Keja — Project Handoff

Read this whole document before doing anything. It contains everything
needed to keep working on this project without re-discovering things
the hard way (several items below cost real debugging time to figure
out the first time).

**Your first instruction, once you've read this: build a real ad-media
placement feature, restricted to admin users only.** Details in the
"Next task" section near the bottom.

---

## 1. What Keja is

A rental property platform for the Kenyan market (Nairobi-focused).
Renters browse/swipe listings, save ones they like, and pay a small fee
(or use a referral credit) to unlock a landlord's contact info.
Landlords list properties and manage them from a dashboard. There's a
website and a native Android app, both talking to the same backend.

It was rebuilt from an unrelated nightlife/events app called "Bash" —
you may see leftover code, model names, or comments referencing that;
it's not a bug, it's inherited scaffolding that was reused instead of
rebuilt from scratch where it still worked (auth, media upload
patterns, rate limiting, etc.).

## 2. Live URLs

| What | URL |
|---|---|
| Website | https://keja-frontend.onrender.com |
| Backend API | https://keja-backend-uqzk.onrender.com |
| GitHub repo | https://github.com/obsidianlabs101-spec/keja-app |
| Android APK (always the latest build, public, no login needed) | https://github.com/obsidianlabs101-spec/keja-app/releases/download/android-latest/app-debug.apk |

## 3. Architecture

- **Frontend** (`/frontend`): a single-page vanilla JS app — just
  `index.html`, `app.js`, `style.css`, no build step, no framework.
  Deployed as a **Render Static Site**, auto-deploys on push to `main`.
- **Backend** (`/backend`): FastAPI (Python), deployed as a **Render
  Web Service** on the free tier. Auto-deploys on push to `main`.
  Free tier means: (a) the disk is **ephemeral** — wiped on every
  deploy or restart, and (b) it **spins down after ~15 min idle**, so
  the first request after a gap takes a few seconds to wake up. Both
  are normal, not bugs.
- **Database**: Supabase Postgres, project ref `mepnzrjhmaotilbqnvsy`,
  region eu-west-1. Connected via the **connection pooler**, not a
  direct connection (direct connections need IPv6, which Render's
  free tier doesn't have — this took a failed deploy to figure out).
- **Image storage**: Supabase Storage, bucket `property-images`
  (public read, open insert policy). Property photos are uploaded
  here, **never to local disk** on the backend — see gotcha #2 below
  for why that matters.
- **Android app** (`/android`): Kotlin + Jetpack Compose, native, not
  a webview wrapper. Same backend, same design tokens as the website
  (colors/type/shapes were extracted directly from `style.css`).
  Built via **GitHub Actions** (`.github/workflows/android-build.yml`)
  because there's no Android SDK in a Claude sandbox. The workflow
  publishes the built APK as a **public GitHub Release** under the
  tag `android-latest` (overwritten every build) — deliberately NOT
  as an Actions artifact, because artifacts require a GitHub login to
  download and a Release asset doesn't.

## 4. Credentials you'll need

**GitHub personal access token** (scopes: `repo` + `workflow`, both
required — see gotcha #4):

Not stored here — GitHub's push protection correctly blocks committing
a live token to the repo, and that protection shouldn't be
circumvented. **Ask the user for the current token** at the start of
your session; they've been generating these at
https://github.com/settings/tokens/new with `repo` + `workflow`
checked. Push like this once you have it (works from a plain bash
tool, no git credential setup needed):
```bash
git add -A && git commit -m "..."
git push https://<TOKEN>@github.com/obsidianlabs101-spec/keja-app.git main
```
This token may expire or already have — if a push gets a 403 or a
push-protection rejection, ask the user for a fresh one rather than
assuming the code is wrong.

**Supabase** — if you have Supabase MCP tools connected, you likely
already have project access without needing raw keys. If you need the
anon key directly (e.g. to hand it to backend code as an env var),
it's already set on Render as `SUPABASE_ANON_KEY` — no need to
re-fetch it unless you're rotating it.

**Test accounts already set up:**
- Landlord (real, approved `is_host=true`): phone `0757277507`,
  email `smuiruri360@gmail.com` — this is the actual user's own
  account.
- Admin: `sam@gmail.com` / password `string123` — a separate account
  created specifically for admin testing.
- Real M-Pesa till number wired into the contact-unlock flow:
  `4396353`.

## 5. Deploying changes

1. Edit files under `/frontend`, `/backend`, or `/android`.
2. Before writing any Kotlin, run the sanity checks below — they've
   caught real bugs before a single CI run was wasted:
   ```bash
   # brace/paren balance across all Kotlin files
   find android -name "*.kt" | while read f; do python3 -c "
   c = open('$f').read()
   if c.count('{')!=c.count('}') or c.count('(')!=c.count(')'):
       print('MISMATCH: $f')
   "; done
   # the exact anti-pattern that broke a build once (see gotcha #5)
   grep -rn "androidx\.compose\.[a-z.]*\.\(composed\|clickable\|remember\)\s*{" android --include="*.kt"
   ```
   For the website: `node --check app.js` and a brace-count check on
   `style.css`.
3. Commit and push (command above). Render auto-deploys frontend and
   backend on every push to `main` — no manual trigger needed. If
   Render MCP tools are connected, you can watch deploy status; if the
   deploy touches `DATABASE_URL`/`SUPABASE_ANON_KEY`/etc., those are
   env vars on the Render service, not in the repo.
4. If you touched `/android`, GitHub Actions builds it automatically
   (same push, filtered by the `paths:` rule in the workflow). Poll
   via the GitHub API:
   ```bash
   curl -s -H "Authorization: token <TOKEN>" -H "User-Agent: keja-deploy" \
     "https://api.github.com/repos/obsidianlabs101-spec/keja-app/actions/runs?per_page=1"
   ```
   Then check jobs/steps the same way (`.../actions/runs/<id>/jobs`).
5. **You very likely cannot fetch the raw build log yourself** — see
   gotcha #3. If a build fails, ask the user to paste the last ~40
   lines from the failed step in the GitHub Actions UI rather than
   trying repeatedly to fetch it through blocked network paths.
6. After a successful Android build, verify the release actually
   updated (don't just trust "success" — check the file changed):
   ```bash
   curl -s -o /dev/null -w "%{http_code} %{size_download}\n" -L \
     "https://github.com/obsidianlabs101-spec/keja-app/releases/download/android-latest/app-debug.apk"
   ```

## 6. Gotchas — read before you repeat these

1. **Supabase pooler cluster index isn't always `aws-0`.** Hostnames
   look like `aws-1-eu-west-1.pooler.supabase.com` — the number varies
   per project and isn't guessable from the region name. Get the exact
   string from the user's Supabase dashboard (Connect → Transaction
   pooler) rather than assuming `aws-0`. Guessing wrong doesn't error
   cleanly — it hangs (direct connection, no IPv6) or fails with
   "tenant not found" (wrong pooler shard).

2. **Render's free-tier disk is ephemeral.** Anything written to local
   disk on the backend (`open(path, "wb")` etc.) vanishes on the next
   deploy or restart. This caused a real bug where uploaded property
   photos worked once, then silently 404'd after the next unrelated
   deploy. Property images go to Supabase Storage
   (`upload_to_supabase_storage()` in `property_service.py`) — follow
   that pattern for any other file uploads.

3. **GitHub Actions log/artifact downloads redirect to Azure blob
   storage** (`productionresultssa1.blob.core.windows.net`), which may
   not be reachable from your sandbox's network egress. If a build
   fails and you can't fetch the log text, don't guess at fixes
   blindly — ask the user to copy-paste the error from the Actions UI.
   The Checks API annotations endpoint usually only gives you
   "Process completed with exit code 1", not the actual compiler
   error — not useful on its own.

4. **Pushing to `.github/workflows/*` needs the `workflow` scope**,
   not just `repo`. A token with only `repo` gets silently rejected
   for that specific path (everything else pushes fine). If you hit
   this, it's a token scope issue, not a git config issue.

5. **In Jetpack Compose, don't give every child of a `Box` a
   `matchParentSize()` modifier.** At least one child needs natural/
   intrinsic sizing, or the `Box` has nothing to measure against and
   the whole thing renders at zero size — no error, just invisible.
   This caused the entire Rangi theme to render nothing for a while.
   Also: don't call an extension function by fully-qualified name like
   `androidx.compose.ui.composed { }` — that's invalid Kotlin syntax
   for extension functions; import it and call it on the receiver.

6. **A shared CSS class's old rules can silently break new uses of
   it.** `.swipe-card{touch-action:none}` (from an old design concept)
   blocked touch-scrolling on the *new* vertical Discover feed, which
   reused the same class name. Fixed with a more specific selector
   override — but the lesson is: check the *whole* history of a class
   name before reusing it for something new.

7. **Don't size scrollable containers with a guessed
   `calc(100vh - Npx)`.** When the guess is even slightly off, content
   below the scroller gets pushed off-screen, and the outer page and
   inner scroll-snap container end up fighting over the same touch
   gesture. Use flexbox (`flex: 1; min-height: 0` on the scroller) so
   it's sized by what's actually left, not by arithmetic.

## 7. Known limitations (deliberate, not oversights)

- Android builds are **debug APKs**, not signed for the Play Store.
- M-Pesa integration is **manual-match only** (user pastes the
  confirmation SMS/code, an admin endpoint matches it) — no STK Push.
  This was an explicit spec requirement, not a shortcut.
- Supabase tables have **no Row Level Security policies** — flagged to
  the user already. Not a blocker since the app never exposes the
  Supabase anon/service key to any client; only the FastAPI backend
  talks to the DB. Worth fixing properly before a real public launch.
- The referral system grants exactly **one** free contact-unlock
  credit per user, ever, on their first successful referral — this is
  intentional, not a bug if a second referral doesn't grant another.

## 8. Next task (your first instruction)

**Build a real ad-media placement feature, admin-only.**

Right now, "ads" on Home and Discover (both website and Android) are a
static placeholder — just a dashed box with the word "ADVERTISEMENT".
There's also an admin "Ad placement" panel in the website's admin
dashboard, but it's a demo too (toggles/dropdowns that just show a
toast on save, no backend).

What to build:
- A backend model/table for ad slots (e.g. `AdSlot`: id, placement —
  `"home"` or `"discover"` — image_url, link_url (optional), is_active,
  created_at).
- An admin-only endpoint to upload an ad image (reuse
  `upload_to_supabase_storage()`, same pattern as property photos —
  maybe a separate bucket, e.g. `ad-images`, so it's not mixed with
  property photos) and set/update the active ad for a placement.
- Only admins (`is_admin=True`, same dependency pattern as
  `/admin/platform-stats`) can create/update/deactivate ads.
- Wire the real ad into Home and Discover on **both** the website and
  the Android app, replacing the static placeholder with the actual
  uploaded image when one exists for that placement (falling back to
  the current placeholder, or nothing, when there isn't one).
- Wire the website's existing admin "Ad placement" panel to this real
  backend instead of the demo toast.
- Add the equivalent management UI to the Android admin dashboard too
  (it currently doesn't have one at all).

Confirm scope with the user if anything above is ambiguous (e.g.
whether ads need a click-through link, whether non-admin landlords
should ever be able to buy/upload ad slots later) rather than guessing
silently — this was raised as an open question in the previous session
and the user hasn't answered it yet.
