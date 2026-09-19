/**
 * BASH — api-config.js
 * The ONE place that knows where the backend lives. Every page loads this
 * before anything else (<script src="api-config.js">, first in <head>),
 * so by the time any page's own script runs, window.BASH_API_BASE_URL is
 * already set and it can just read it directly — no per-page fallback
 * URL to remember to update.
 *
 * To point the whole app at a different backend (new LAN IP, ngrok tunnel,
 * staging server, production domain, etc.), change ONLY the line below.
 */
window.BASH_API_BASE_URL = "https://keja-backend-uqzk.onrender.com";

/**
 * Heartbeat — tells the backend "a logged-in user is actively using the
 * app right now". Powers the admin "User Growth" analytics subpage (active
 * users + time spent). Fires once shortly after load, then every 60s, and
 * only while the tab is visible and a login token exists — so logged-out
 * visitors and backgrounded tabs don't inflate the numbers. Lives here
 * (not in any one page's JS) because api-config.js is the one script every
 * page already loads first, so this covers the whole app automatically.
 */
(function () {
    function pingHeartbeat() {
        if (document.visibilityState !== "visible") return;
        var token = (localStorage.getItem("bashToken") || "").trim();
        if (!token) return;
        fetch(window.BASH_API_BASE_URL + "/users/heartbeat", {
            method: "POST",
            headers: { "Authorization": "Bearer " + token, "Content-Type": "application/json" },
        }).catch(function () { /* best-effort — offline/backend-down shouldn't break the page */ });
    }

    setTimeout(pingHeartbeat, 3000);
    setInterval(pingHeartbeat, 60000);
    document.addEventListener("visibilitychange", function () {
        if (document.visibilityState === "visible") pingHeartbeat();
    });
})();

/**
 * Push notifications — registers this device to receive real phone/OS
 * notification-tray alerts (starting with the T-2h "still going?"
 * reminder) instead of ones only visible by opening the app. Lives here
 * (like the heartbeat above) so every page picks it up automatically.
 *
 * Only runs for a logged-in user, only asks for permission once (never
 * re-prompts if the person dismissed/denied it), and re-syncs the
 * subscription with the backend at most once a day so a renewed/rotated
 * browser subscription doesn't silently go stale.
 */
window.BASH_VAPID_PUBLIC_KEY = "BH4r2OEp-S9iKVU6g24OoiXQrE0KhFbj9dCYclg04bYfvxvwZA4dlCw-muNfi78sAyvR1vZScWOGwW1mPIwO3EY";

(function () {
    function urlBase64ToUint8Array(base64String) {
        const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
        const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        for (let i = 0; i < rawData.length; i++) outputArray[i] = rawData.charCodeAt(i);
        return outputArray;
    }

    async function registerForPush() {
        var token = (localStorage.getItem("bashToken") || "").trim();
        if (!token) return; // only for logged-in users
        if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;
        if (Notification.permission === "denied") return; // respect a past "no"

        var lastSync = Number(localStorage.getItem("bashPushSyncedAt") || 0);
        var alreadyAskedButNotSubscribed = Notification.permission === "default";
        if (!alreadyAskedButNotSubscribed && Date.now() - lastSync < 24 * 60 * 60 * 1000) return; // synced recently

        try {
            const reg = await navigator.serviceWorker.ready;
            let permission = Notification.permission;
            if (permission === "default") {
                permission = await Notification.requestPermission();
            }
            if (permission !== "granted") return;

            let sub = await reg.pushManager.getSubscription();
            if (!sub) {
                sub = await reg.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: urlBase64ToUint8Array(window.BASH_VAPID_PUBLIC_KEY),
                });
            }

            const json = sub.toJSON();
            await fetch(window.BASH_API_BASE_URL + "/users/push-subscription", {
                method: "POST",
                headers: { "Authorization": "Bearer " + token, "Content-Type": "application/json" },
                body: JSON.stringify({ endpoint: json.endpoint, keys: json.keys }),
            });
            localStorage.setItem("bashPushSyncedAt", String(Date.now()));
        } catch (err) {
            // Best-effort — a denied prompt, unsupported browser, or a
            // flaky network shouldn't break the page around it.
            console.warn("[BASH] push registration skipped:", err && err.message);
        }
    }

    setTimeout(registerForPush, 4000);
})();

/**
 * Keeps the cached bashCurrentUser in sync with the backend — mainly so
 * free_events_unlocked (the "padlock" on free events) and referral_code
 * update promptly once someone's referral goes through, without needing
 * to log out/in. Runs once per page load for a logged-in user; cheap
 * enough not to bother throttling further.
 */
(function () {
    async function refreshCurrentUser() {
        var token = (localStorage.getItem("bashToken") || "").trim();
        if (!token) return;
        try {
            const res = await fetch(window.BASH_API_BASE_URL + "/users/me", {
                headers: { "Authorization": "Bearer " + token },
            });
            if (!res.ok) return;
            const fresh = await res.json();
            const raw = localStorage.getItem("bashCurrentUser");
            const cached = raw ? JSON.parse(raw) : {};
            const merged = Object.assign({}, cached, {
                username: fresh.username || cached.username,
                bio: fresh.bio,
                location: fresh.location,
                county: fresh.county,
                town: fresh.town,
                referral_code: fresh.referral_code,
                free_events_unlocked: !!fresh.free_events_unlocked,
            });
            localStorage.setItem("bashCurrentUser", JSON.stringify(merged));
            window.dispatchEvent(new CustomEvent("bash-profile-updated", { detail: merged }));
        } catch (err) {
            console.warn("[BASH] profile refresh skipped:", err && err.message);
        }
    }
    setTimeout(refreshCurrentUser, 1500);
})();

/**
 * Compact number formatting for counters (likes, comments, followers,
 * following, post counts) — 1000 -> "1k", 1000000 -> "1m", 1000000000
 * -> "1b". Lives here so every page's script can just call
 * window.formatCount(n) instead of each re-implementing its own version.
 * Anything under 1000 is shown as-is (no rounding/decimals needed there).
 * One decimal place below 10 of a unit (e.g. "1.2k") for a bit more
 * precision right after crossing a threshold; drops the decimal once
 * it's not needed (e.g. "12k", not "12.0k").
 */
window.formatCount = function (n) {
    n = Number(n) || 0;
    const sign = n < 0 ? "-" : "";
    n = Math.abs(n);
    const units = [
        { value: 1e9, suffix: "b" },
        { value: 1e6, suffix: "m" },
        { value: 1e3, suffix: "k" },
    ];
    for (const u of units) {
        if (n >= u.value) {
            const scaled = n / u.value;
            const rounded = scaled < 10 ? Math.round(scaled * 10) / 10 : Math.round(scaled);
            return sign + rounded + u.suffix;
        }
    }
    return sign + String(n);
};