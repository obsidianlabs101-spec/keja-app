/**
 * BASH — referral.js
 *
 * Free events: browsing is unrestricted — no blur, nothing hidden. The
 * padlock badge on a free event's card is just an indicator; tapping it
 * (or trying to actually claim a free ticket while unreferred) opens a
 * share card with your invite link + a copy button, which you paste to
 * someone yourself (no auto-send). Once that person signs up through the
 * link, the backend deposits a referral credit on your account (see
 * auth_service._credit_referrer_if_any) — one credit is spent per free
 * event actually claimed (see booking_service.create_free_booking_fcfs).
 * api-config.js's periodic /users/me refresh keeps the cached credit
 * count in sync within a page load or two.
 *
 * REFERRAL GATE SWITCH: all of the above only actually applies while an
 * admin has PlatformSettings.referral_gate_enabled turned ON (the
 * "Referral Gate" admin page) — OFF by default. gateEnabled below is
 * fetched once from the public GET /events/platform-status on script
 * load; isLocked() short-circuits to false whenever it's off, which is
 * what makes every padlock badge disappear everywhere this module is used
 * (cheki.js, home.js) without either of those files needing to know
 * anything about the switch themselves. Defaults to false (unlocked)
 * before the fetch resolves and if it fails — a network hiccup should
 * never wrongly lock someone out of a free event they'd otherwise be able
 * to book with zero friction.
 */
(function () {
  let gateEnabled = false;
  (function fetchGateStatus() {
    const base = (window.BASH_API_BASE_URL || "").replace(/\/$/, "");
    if (!base) return;
    fetch(`${base}/events/platform-status`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) gateEnabled = !!data.referral_gate_enabled; })
      .catch(() => {}); // leave gateEnabled at its safe default (off)
  })();

  function getCachedUser() {
    try {
      const raw = localStorage.getItem("bashCurrentUser");
      return raw ? JSON.parse(raw) : null;
    } catch (_) { return null; }
  }

  function isLoggedIn() {
    return !!(localStorage.getItem("bashToken") || "").trim();
  }

  function isFreePrice(price) {
    const n = Number(price);
    return !Number.isNaN(n) && n <= 0;
  }

  // Exposed so pages showing referral-adjacent UI that isn't a padlock
  // (profile.html's Free Event Coins chip) can hide themselves the same
  // way padlocks do, without each duplicating the platform-status fetch
  // this module already does on load.
  function isGateEnabled() {
    return gateEnabled;
  }

  // True while the padlock should still be showing.
  function isLocked() {
    if (!gateEnabled) return false; // switch is off — free events are never locked
    if (!isLoggedIn()) return true; // no account yet = definitely locked
    const u = getCachedUser();
    return !(u && u.free_events_unlocked);
  }

  function referralLink() {
    const u = getCachedUser();
    const code = u && u.referral_code;
    // Build off the current page's own folder (not a hardcoded domain
    // root) so the link still resolves correctly whether the app is
    // deployed at the site root or nested under a subpath, e.g.
    // /frontend/. Mirrors the location.pathname approach cheki.js uses
    // for its own share links.
    const dir = window.location.pathname.replace(/[^/]*$/, "");
    const base = window.location.origin + dir + "index.html";
    return code ? `${base}?ref=${encodeURIComponent(code)}` : base;
  }

  // ---- Modal markup/CSS, injected once ----
  let modalEl = null;
  function ensureModal() {
    if (modalEl) return modalEl;
    const style = document.createElement("style");
    style.textContent = `
      .referral-modal-overlay{position:fixed;inset:0;z-index:20000;display:none;
        align-items:center;justify-content:center;padding:20px;
        background:rgba(2,3,8,.82);backdrop-filter:blur(6px);}
      .referral-modal-overlay.open{display:flex;}
      .referral-modal-card{width:100%;max-width:360px;background:linear-gradient(160deg,#1a1a1f,#101012);
        border:1px solid rgba(255,255,255,.1);border-radius:22px;padding:24px 22px;text-align:center;
        box-shadow:0 24px 70px rgba(0,0,0,.6);}
      .referral-modal-lock{font-size:2rem;margin-bottom:8px;}
      .referral-modal-card h3{margin:0 0 8px;font-size:1.05rem;color:#fff;font-family:inherit;}
      .referral-modal-card p{margin:0 0 16px;font-size:.82rem;line-height:1.45;color:rgba(255,255,255,.65);}
      .referral-modal-linkrow{display:flex;align-items:center;gap:8px;background:rgba(255,255,255,.06);
        border:1px solid rgba(255,255,255,.12);border-radius:14px;padding:10px 12px;margin-bottom:14px;}
      .referral-modal-linkrow input{flex:1;min-width:0;background:none;border:none;color:#fff;
        font-size:.76rem;outline:none;}
      .referral-modal-copy{flex-shrink:0;width:34px;height:34px;border-radius:10px;border:none;
        background:linear-gradient(135deg,#ff003c,#ff8a00);color:#fff;cursor:pointer;
        display:flex;align-items:center;justify-content:center;}
      .referral-modal-copy svg{width:16px;height:16px;}
      .referral-modal-whatsapp{flex-shrink:0;width:34px;height:34px;border-radius:10px;border:none;
        background:#25D366;color:#fff;cursor:pointer;
        display:flex;align-items:center;justify-content:center;}
      .referral-modal-whatsapp svg{width:18px;height:18px;}
      .referral-modal-hint{font-size:.7rem;color:rgba(255,255,255,.45);margin-bottom:16px;}
      .referral-modal-close{border:none;background:rgba(255,255,255,.08);color:#fff;
        border-radius:999px;padding:10px 20px;font-weight:700;font-size:.82rem;cursor:pointer;width:100%;}
    `;
    document.head.appendChild(style);

    modalEl = document.createElement("div");
    modalEl.className = "referral-modal-overlay";
    modalEl.innerHTML = `
      <div class="referral-modal-card">
        <div class="referral-modal-lock"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg></div>
        <h3>Free events are locked</h3>
        <p>Get one friend to sign up through your link and every free event on BASH unlocks for you — for good.</p>
        <div class="referral-modal-linkrow">
          <input type="text" readonly id="referralLinkInput" value="">
          <button type="button" class="referral-modal-copy" id="referralCopyBtn" aria-label="Copy link">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
          </button>
          <button type="button" class="referral-modal-whatsapp" id="referralWhatsAppBtn" aria-label="Send on WhatsApp">
            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.6 6.32A8.86 8.86 0 0 0 12.05 4c-4.87 0-8.83 3.94-8.83 8.8 0 1.55.41 3.06 1.19 4.4L3.2 21.6l4.55-1.19a8.9 8.9 0 0 0 4.28 1.09h.01c4.87 0 8.83-3.94 8.83-8.8a8.7 8.7 0 0 0-2.58-6.24l.31-.14zm-5.55 13.54h-.01a7.4 7.4 0 0 1-3.76-1.03l-.27-.16-2.79.73.75-2.71-.18-.28a7.3 7.3 0 0 1-1.13-3.9c0-4.04 3.3-7.32 7.4-7.32a7.36 7.36 0 0 1 7.38 7.32c0 4.04-3.3 7.35-7.39 7.35zm4.05-5.5c-.22-.11-1.31-.65-1.52-.72-.2-.08-.35-.11-.5.11-.15.22-.57.72-.7.87-.13.15-.26.16-.48.05-.22-.11-.94-.35-1.79-1.11-.66-.6-1.1-1.33-1.23-1.55-.13-.22-.01-.34.1-.45.1-.1.22-.26.33-.39.11-.13.15-.22.22-.37.07-.15.04-.28-.02-.39-.06-.11-.5-1.22-.69-1.67-.18-.44-.37-.38-.5-.38l-.43-.01c-.15 0-.39.06-.6.28-.2.22-.78.77-.78 1.87s.8 2.17.91 2.32c.11.15 1.58 2.46 3.87 3.35.54.22.96.36 1.29.46.54.17 1.03.15 1.42.09.43-.06 1.31-.53 1.5-1.05.19-.51.19-.95.13-1.05-.06-.1-.2-.15-.42-.26z"/></svg>
          </button>
        </div>
        <p class="referral-modal-hint" id="referralCopyHint">Paste it to a friend on WhatsApp, SMS, wherever.</p>
        <button type="button" class="referral-modal-close" id="referralModalClose">Got it</button>
      </div>
    `;
    document.body.appendChild(modalEl);

    modalEl.addEventListener("click", (e) => { if (e.target === modalEl) closeShareCard(); });
    modalEl.querySelector("#referralModalClose").addEventListener("click", closeShareCard);
    modalEl.querySelector("#referralCopyBtn").addEventListener("click", () => {
      const input = modalEl.querySelector("#referralLinkInput");
      const hint = modalEl.querySelector("#referralCopyHint");
      const doFallbackCopy = () => {
        input.removeAttribute("readonly");
        input.select();
        try { document.execCommand("copy"); } catch (_) {}
        input.setAttribute("readonly", "");
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(input.value).catch(doFallbackCopy);
      } else {
        doFallbackCopy();
      }
      hint.textContent = "Copied! Now paste it to a friend.";
      setTimeout(() => { hint.textContent = "Paste it to a friend on WhatsApp, SMS, wherever."; }, 2200);
    });
    modalEl.querySelector("#referralWhatsAppBtn").addEventListener("click", () => {
      const link = modalEl.querySelector("#referralLinkInput").value;
      const eventName = modalEl.dataset.eventName || "";
      // wa.me with a pre-filled ?text= opens WhatsApp with the message
      // already typed into the compose box, ready to send — it does NOT
      // auto-send anything or pick a recipient; the person still chooses
      // who to send it to and taps send themselves, same as pasting the
      // link manually would, just with the inviting wording already done
      // for them. No recipient number in the URL means WhatsApp opens its
      // own contact/chat picker instead of a specific chat.
      const message = eventName
        ? `Come through to ${eventName} with me 👀 book free on BASH: ${link}`
        : `Been finding free events on BASH — book one with me: ${link}`;
      window.open(`https://wa.me/?text=${encodeURIComponent(message)}`, "_blank");
    });
    return modalEl;
  }

  function closeShareCard() {
    if (modalEl) modalEl.classList.remove("open");
  }

  function openShareCard(eventName) {
    // Not signed in at all — there's no referral link to share yet, so
    // the only sensible next step is to get them signed up first.
    if (!isLoggedIn()) {
      window.location.href = "index.html";
      return;
    }
    const el = ensureModal();
    el.querySelector("#referralLinkInput").value = referralLink();
    el.dataset.eventName = eventName || "";
    el.classList.add("open");
  }

  // ---- Padlock badge builder ----
  // Returns a small absolutely-positioned button element; caller places
  // it inside a `position:relative` container over the free event's media.
  // eventName is optional — both call sites (cheki.js, home.js) have it
  // readily available on the post/event object they're already rendering
  // from, so it costs them nothing to pass through, and it's what lets
  // the WhatsApp message below say "come to X with me" instead of a
  // generic invite.
  function buildPadlockBadge(eventName) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "bash-padlock-badge";
    btn.setAttribute("aria-label", "Locked — invite a friend to unlock free events");
    btn.innerHTML = `
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>
      </svg>`;
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      openShareCard(eventName);
    });
    return btn;
  }

  if (!document.getElementById("bash-padlock-style")) {
    const s = document.createElement("style");
    s.id = "bash-padlock-style";
    s.textContent = `
      .bash-padlock-badge{position:absolute;z-index:5;top:10px;right:10px;width:34px;height:34px;
        border-radius:50%;border:1px solid rgba(255,255,255,.25);background:rgba(2,3,8,.62);
        backdrop-filter:blur(4px);color:#fff;display:flex;align-items:center;justify-content:center;
        cursor:pointer;}
    `;
    document.head.appendChild(s);
  }

  window.BashReferral = {
    isFreePrice,
    isLocked,
    isGateEnabled,
    referralLink,
    openShareCard,
    buildPadlockBadge,
  };
})();