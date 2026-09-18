/**
 * Keja — shared app shell.
 * Same "one place that knows where the backend lives" pattern as Bash's
 * api-config.js (kept, unmodified, one folder up) — this file layers
 * Keja-specific auth/theme/nav helpers on top of it. Every Keja page
 * loads api-config.js FIRST, then this file.
 */

window.KEJA_MPESA_TILL = {
    // Placeholder till number — replace with the real Buy Goods/Paybill
    // number before going live. Nothing else in the contact-unlock flow
    // needs to change when this is swapped for a real one.
    till: "000000",
    name: "Keja Kenya",
    amount: 50,
};

(function () {
    const TOKEN_KEY = "kejaToken";
    const USER_KEY = "kejaCurrentUser";
    const THEME_KEY = "kejaTheme";

    function apiBase() {
        return window.BASH_API_BASE_URL;
    }

    function getToken() {
        return (localStorage.getItem(TOKEN_KEY) || "").trim();
    }

    function setSession(token, user) {
        if (token) localStorage.setItem(TOKEN_KEY, token);
        if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
    }

    function getUser() {
        try {
            return JSON.parse(localStorage.getItem(USER_KEY) || "null");
        } catch (e) {
            return null;
        }
    }

    function clearSession() {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
    }

    function isLoggedIn() {
        return !!getToken();
    }

    async function api(path, options) {
        options = options || {};
        const headers = Object.assign({}, options.headers || {});
        const token = getToken();
        if (token) headers["Authorization"] = "Bearer " + token;
        if (options.body && !(options.body instanceof FormData)) {
            headers["Content-Type"] = "application/json";
        }
        const res = await fetch(apiBase() + path, Object.assign({}, options, { headers }));
        if (res.status === 401) {
            clearSession();
            if (!location.pathname.endsWith("/keja/index.html") && !location.pathname.endsWith("/keja/")) {
                location.href = "index.html";
            }
        }
        let data = null;
        try {
            data = await res.json();
        } catch (e) {
            data = null;
        }
        if (!res.ok) {
            const message = (data && (data.detail || data.message)) || "Something went wrong";
            throw new Error(typeof message === "string" ? message : JSON.stringify(message));
        }
        return data;
    }

    async function refreshCurrentUser() {
        if (!isLoggedIn()) return null;
        try {
            const fresh = await api("/users/me");
            setSession(null, fresh);
            return fresh;
        } catch (e) {
            return getUser();
        }
    }

    function requireAuth() {
        if (!isLoggedIn()) {
            location.href = "index.html";
        }
    }

    function fmtPrice(n) {
        n = Math.round(Number(n) || 0);
        return "KES " + n.toLocaleString("en-KE");
    }

    function initTheme() {
        const saved = localStorage.getItem(THEME_KEY);
        const preferred = saved || (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
        document.documentElement.setAttribute("data-theme", preferred);
    }

    function toggleTheme() {
        const current = document.documentElement.getAttribute("data-theme") || "light";
        const next = current === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", next);
        localStorage.setItem(THEME_KEY, next);
        return next;
    }

    const NAV_ITEMS = [
        { key: "home", label: "Home", href: "home.html", icon: "M3 11.5 12 4l9 7.5M5 10v9a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1v-9" },
        { key: "discover", label: "Discover", href: "discover.html", icon: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm3.5 5.5-2 5.5-5.5 2 2-5.5 5.5-2Z" },
        { key: "interested", label: "Interested", href: "interested.html", icon: "M12 20.5s-7.5-4.6-9.6-9A5.2 5.2 0 0 1 12 6.4 5.2 5.2 0 0 1 21.6 11.5c-2.1 4.4-9.6 9-9.6 9Z" },
        { key: "profile", label: "Profile", href: "profile.html", icon: "M12 12a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9Zm0 2c-4.4 0-8 2.2-8 5v1.5h16V19c0-2.8-3.6-5-8-5Z" },
    ];

    function renderNav(activeKey) {
        const nav = document.createElement("nav");
        nav.className = "keja-bottom-nav";
        nav.innerHTML = NAV_ITEMS.map(function (item) {
            const active = item.key === activeKey ? " active" : "";
            return (
                '<a class="keja-nav-item' + active + '" href="' + item.href + '">' +
                '<svg viewBox="0 0 24 24" width="22" height="22"><path d="' + item.icon + '" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
                '<span>' + item.label + '</span></a>'
            );
        }).join("");
        document.body.appendChild(nav);
    }

    function renderAd(containerId) {
        const el = document.getElementById(containerId);
        if (!el) return;
        el.innerHTML =
            '<div class="keja-ad">' +
            '<span class="keja-ad-label">ADVERTISEMENT</span>' +
            '<div class="keja-ad-body">Your ad could be here — reach renters across Nairobi.</div>' +
            '</div>';
    }

    window.Keja = {
        api,
        getToken,
        getUser,
        setSession,
        clearSession,
        isLoggedIn,
        refreshCurrentUser,
        requireAuth,
        fmtPrice,
        initTheme,
        toggleTheme,
        renderNav,
        renderAd,
    };

    initTheme();

    if ("serviceWorker" in navigator) {
        window.addEventListener("load", function () {
            navigator.serviceWorker.register("sw.js").catch(function () {});
        });
    }
})();
