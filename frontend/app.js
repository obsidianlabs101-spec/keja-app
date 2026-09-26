/* ============================================================
 * Keja app.js — same UI/markup/CSS as provided, wired to the real
 * FastAPI backend instead of the fake in-memory `properties` array.
 * No visual/design changes were made here — only behavior.
 * ============================================================ */

const API_BASE = "https://keja-backend-uqzk.onrender.com";
const MPESA_TILL = { till: "4396353", name: "Obsidian Labs", amount: 50 };

const app = document.getElementById("app");
const modalBackdrop = document.getElementById("modalBackdrop");
const modal = document.getElementById("modal");

let currentView = localStorage.getItem("kejaView") || "home";
let viewParams = {}; // extra data for views that need it (e.g. landlordProfile -> {landlordId})
let dark = localStorage.getItem("kejaDark") === "1";
let theme = localStorage.getItem("kejaTheme") || "pro";
const THEMES = { pro: "Professional", rangi: "Rangi" };

let token = localStorage.getItem("kejaToken") || "";
let currentUser = null;
try { currentUser = JSON.parse(localStorage.getItem("kejaUser") || "null"); } catch (e) { currentUser = null; }

let properties = [];          // whatever the current page (home/category/search) is showing
let discoverQueue = [];       // this user's Discover feed
let interestedList = [];      // fetched Interested properties
let interestedIds = new Set();
let discoverUIHidden = false;

if (dark) document.body.classList.add("dark");
document.body.classList.toggle("rangi", theme === "rangi");
function setTheme(t) { theme = t; localStorage.setItem("kejaTheme", t); document.body.classList.toggle("rangi", t === "rangi"); render(); toast(THEMES[t] + " look applied"); }

function money(n) { return "KES " + Math.round(Number(n) || 0).toLocaleString(); }

function mediaUrl(url) {
  if (!url) return "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1000&q=80";
  if (url.startsWith("http")) return url;
  return API_BASE + "/" + url.replace(/^\/+/, "");
}

const ICON_EYE = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z"/><circle cx="12" cy="12" r="3"/></svg>`;
const ICON_EYE_OFF = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.94 10.94 0 0 1 12 19c-7 0-11-7-11-7a20.3 20.3 0 0 1 5.06-5.94M9.9 4.24A10.94 10.94 0 0 1 12 4c7 0 11 7 11 7a20.3 20.3 0 0 1-2.16 3.19M14.12 14.12a3 3 0 1 1-4.24-4.24"/><path d="M1 1l22 22"/></svg>`;

/* ---------------- API helper ---------------- */
async function api(path, options) {
  options = options || {};
  const headers = Object.assign({}, options.headers || {});
  if (token) headers["Authorization"] = "Bearer " + token;
  if (options.body && !(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const res = await fetch(API_BASE + path, Object.assign({}, options, { headers }));
  if (res.status === 401) {
    logout(true);
  }
  let data = null;
  try { data = await res.json(); } catch (e) { data = null; }
  if (!res.ok) {
    const msg = (data && (data.detail || data.message)) || "Something went wrong";
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

function setSession(newToken, user) {
  token = newToken;
  currentUser = user;
  localStorage.setItem("kejaToken", token);
  localStorage.setItem("kejaUser", JSON.stringify(user));
  updateAvatar();
}

function isLoggedIn() { return !!token; }

async function refreshCurrentUser() {
  if (!isLoggedIn()) return null;
  try {
    const fresh = await api("/users/me");
    currentUser = fresh;
    localStorage.setItem("kejaUser", JSON.stringify(fresh));
    updateAvatar();
    return fresh;
  } catch (e) {
    return currentUser;
  }
}

function navItemsFor(u) {
  if (u && u.is_admin) return [["admin", "⌂", "Overview"], ["adminNew", "✦", "New"], ["adminLandlords", "☺", "Landlords"], ["adminPayments", "✓", "Payments"], ["adminListings", "▤", "Listings"], ["adminAds", "◎", "Ads"], ["profile", "◉", "Profile"]];
    return [["home", "⌂", "Home"], ["discover", "⌕", "Discover"], ["interested", "♡", "Interested"], ["profile", "◉", "Profile"]];
}
function buildNav() {
  const nav = document.querySelector(".bottom-nav"); if (!nav) return;
  const items = navItemsFor(isLoggedIn() ? currentUser : null);
  nav.classList.toggle("scroll", items.length > 5);
  nav.style.gridTemplateColumns = items.length > 5 ? "" : `repeat(${items.length},1fr)`;
  nav.innerHTML = items.map(([v, i, l]) => `<button data-view="${v}" class="nav-item ${v === currentView ? "active" : ""}"><span>${i}</span><small>${l}</small><b class="nav-badge" id="nb-${v}" hidden></b></button>`).join("");
  nav.querySelectorAll(".nav-item").forEach(x => x.onclick = () => goto(x.dataset.view));
  if (isLoggedIn() && currentUser && currentUser.is_admin) refreshAdminBadges();
}
function refreshAdminBadges() {
  api("/admin/keja/overview").then(o => {
    [["adminNew", o.unreviewed_properties], ["adminLandlords", o.pending_landlords], ["adminPayments", o.pending_payments]].forEach(([v, n]) => {
      const el = document.getElementById("nb-" + v); if (!el) return;
      el.textContent = n > 99 ? "99+" : n; el.hidden = !n;
    });
  }).catch(() => {});
}
// The bell (alerts) — logged-in renters and landlords only.
let unreadAlerts = 0;
function updateBell() {
  const btn = document.getElementById("bellBtn"); if (!btn) return;
  const show = isLoggedIn() && currentUser && !currentUser.is_admin;
  btn.hidden = !show;
  if (!show) return;
  api("/users/notifications?context=user").then(list => {
    unreadAlerts = list.filter(n => !n.read).length;
    const b = document.getElementById("bellBadge");
    b.textContent = unreadAlerts > 9 ? "9+" : unreadAlerts; b.hidden = !unreadAlerts;
  }).catch(() => {});
}
setInterval(() => { if (!document.hidden) { updateBell(); if (currentUser && currentUser.is_admin) refreshAdminBadges(); } }, 60000);

function updateAvatar() {
  buildNav(); updateBell();
  const el = document.querySelector(".avatar");
  if (!el) return;
  if (currentUser && (currentUser.name || currentUser.username)) {
    el.textContent = (currentUser.name || currentUser.username).trim().slice(0, 2).toUpperCase();
  } else {
    el.textContent = "SM";
  }
}

/* ---------------- Render dispatch ---------------- */
const ADMIN_VIEWS = ["admin", "adminNew", "adminLandlords", "adminPayments", "adminListings", "adminAds", "profile", "alerts"];
function render() {
  // Role-based pages: admins only see admin pages; landlords get "My listings" instead of Interested.
  if (isLoggedIn() && currentUser) {
    if (currentUser.is_admin && !ADMIN_VIEWS.includes(currentView)) currentView = "admin";
  }
  document.querySelectorAll(".nav-item").forEach(x => x.classList.toggle("active", x.dataset.view === currentView));
  if (currentView === "home") home();
  if (currentView === "discover") discover();
  if (currentView === "interested") interestedPage();
  if (currentView === "profile") profile();
  if (currentView === "landlord") landlord();
  if (currentView === "admin") admin();
  if (currentView === "adminNew") adminNew();
  if (currentView === "adminLandlords") adminLandlords();
  if (currentView === "adminPayments") adminPayments();
  if (currentView === "adminListings") adminListings();
  if (currentView === "adminAds") adminAds();
  if (currentView === "alerts") alertsPage();
  if (currentView === "landlordProfile") landlordProfile();
  localStorage.setItem("kejaView", currentView);
}

function goto(view, params) {
  currentView = view;
  viewParams = params || {};
  render();
  window.scrollTo(0, 0);
}

/* ---------------- Shared property card ---------------- */
function propertyCard(p) {
  return `<article class="property" data-property="${p.id}">
 <img src="${mediaUrl(p.main_image_url)}" alt="${p.property_type} in ${p.area || p.county}">
 <div class="property-body"><div class="price">${money(p.price)}<span class="muted" style="font-size:12px;font-weight:500"> / month</span></div>
 <div class="meta">${p.property_type} · ${p.area || p.county}</div>${p.proximity_note ? `<div class="tag">${p.proximity_note}</div>` : ""}${p.is_booked ? `<div class="tag" style="background:#FFF0F0;color:#C92D2D;margin-left:6px">Booked</div>` : ""}</div></article>`;
}
function bindCards() {
  document.querySelectorAll("[data-property]").forEach(el => el.onclick = () => openProperty(el.dataset.property));
}

/* ---------------- Home ---------------- */
function home() {
  app.innerHTML = `<section class="hero"><div class="eyebrow">WELCOME BACK 👋</div><h1>Find a place<br>you'll love.</h1><p>Discover apartments, Airbnb stays and shops/commercial spaces in one place.</p>
 <div class="search"><span style="padding:12px">⌕</span><input id="searchInput" placeholder="Search location, type or landmark"><button id="searchBtn">Search</button></div></section>
 <div class="category-grid">
   <button class="category-card" data-cat="apartments"><span class="cat-icon">⌂</span><strong>Apartments</strong><small>Long-term homes</small></button>
   <button class="category-card" data-cat="airbnb"><span class="cat-icon">✦</span><strong>Airbnb</strong><small>Short stays</small></button>
   <button class="category-card" data-cat="commercial"><span class="cat-icon">▦</span><strong>Shops / Commercial</strong><small>Business spaces</small></button>
 </div>
 <div class="ad" data-ad-slot="home">ADVERTISEMENT</div>
 <div class="section-head"><h2>Popular around Nairobi</h2></div><div class="chips"><button class="chip" data-area="Kilimani">Kilimani</button><button class="chip" data-area="Westlands">Westlands</button><button class="chip" data-area="Roysambu">Roysambu</button><button class="chip" data-area="Kasarani">Kasarani</button><button class="chip" data-area="Kahawa">Kahawa</button></div>
 <div class="section-head"><h2>Recommended for you</h2><button class="chip" id="discoverBtn">See all</button></div><div class="grid" id="homeGrid"><div class="empty" style="grid-column:1/-1">${loaderHtml()}</div></div>`;
  hydrateAds();

  document.getElementById("discoverBtn").onclick = () => goto("discover");
  document.getElementById("searchBtn").onclick = () => search();
  document.getElementById("searchInput").onkeydown = e => { if (e.key === "Enter") search(); };
  document.querySelectorAll(".category-card").forEach(b => b.onclick = () => categoryPage(b.dataset.cat));
  document.querySelectorAll(".chips .chip").forEach(b => b.onclick = () => { document.getElementById("searchInput").value = b.dataset.area; search(); });

  api("/properties/?limit=12").then(list => {
    properties = list;
    const grid = document.getElementById("homeGrid");
    if (!grid) return; // user navigated away already
    grid.innerHTML = list.length ? list.slice(0, 6).map(propertyCard).join("") : `<div class="empty" style="grid-column:1/-1"><h3>No listings yet</h3><p class="muted">Be the first to list a property.</p></div>`;
    bindCards();
  }).catch(() => {
    const grid = document.getElementById("homeGrid");
    if (grid) grid.innerHTML = `<div class="empty" style="grid-column:1/-1"><h3>Couldn't load listings</h3></div>`;
  });
}

function categoryPage(cat) {
  const labels = { apartments: "Apartments", airbnb: "Airbnb", commercial: "Shops / Commercial" };
  app.innerHTML = `<div class="section-head"><div><div class="eyebrow">KEJA CATEGORIES</div><h2>${labels[cat]}</h2></div><button class="chip" id="backHome">Back</button></div>
 <div class="grid" id="catGrid"><div class="empty" style="grid-column:1/-1">${loaderHtml()}</div></div>`;
  document.getElementById("backHome").onclick = () => goto("home");

  if (cat === "commercial") {
    document.getElementById("catGrid").outerHTML = `<div class="empty"><div class="emoji">▦</div><h3>Commercial spaces</h3><p class="muted">Shops, offices and other business spaces will appear here as landlords publish them.</p><button class="primary" id="browseAll">Browse all properties</button></div>`;
    document.getElementById("browseAll").onclick = () => goto("discover");
    return;
  }

  api("/properties/?limit=50").then(list => {
    const filtered = list.filter(p => cat === "airbnb" ? p.property_type === "Airbnb" : p.property_type !== "Airbnb");
    const grid = document.getElementById("catGrid");
    if (!grid) return;
    grid.innerHTML = filtered.length ? filtered.map(propertyCard).join("") : `<div class="empty" style="grid-column:1/-1"><h3>No listings yet</h3></div>`;
    bindCards();
  });
}

function search() {
  const q = document.getElementById("searchInput").value.trim();
  if (!q) return;
  app.innerHTML = `<div class="section-head"><h2>Search results</h2><button class="chip" id="backHome">Back</button></div>
 <div class="grid" id="searchGrid"><div class="empty" style="grid-column:1/-1">Searching…</div></div>`;
  document.getElementById("backHome").onclick = () => goto("home");
  api("/properties/?limit=50&q=" + encodeURIComponent(q)).then(found => {
    const grid = document.getElementById("searchGrid");
    if (!grid) return;
    grid.innerHTML = found.length ? found.map(propertyCard).join("") : `<div class="empty" style="grid-column:1/-1"><div class="emoji">⌕</div><h3>No places found</h3><p class="muted">Try a different location, property type or landmark.</p></div>`;
    bindCards();
  }).catch(() => toast("Search failed — try again"));
}

/* ---------------- Discover (vertical feed) ---------------- */
function discover() {
  if (!isLoggedIn()) {
    app.innerHTML = `<div class="empty locked"><div class="emoji">⌕</div><h3>Log in to discover places</h3><p class="muted">Create a free account to swipe through listings and save the ones you like.</p><button class="primary" id="discLogin" style="margin-top:14px">Log in</button></div>`;
    document.getElementById("discLogin").onclick = () => openLogin();
    return;
  }

  app.innerHTML = `<section class="discover-page ${discoverUIHidden ? "ui-hidden" : ""}" id="discoverPage"><div class="section-head"><div><div class="eyebrow">DISCOVER</div><h2 style="margin-top:5px">Find your next keja</h2></div></div>
 <div class="discover-scroll vertical" id="discoverScroll"><div class="empty" style="width:100%">${loaderHtml()}</div></div>
 <div class="swipe-hint">Scroll up or down to browse the next property</div></section>`;

  api("/properties/discover?limit=30").then(list => {
    discoverQueue = list;
    const scroller = document.getElementById("discoverScroll");
    if (!scroller) return;
    if (!list.length) {
      scroller.outerHTML = `<div class="empty" style="width:100%"><div class="emoji">🏠</div><h3>You've seen everything for now</h3><p class="muted">Check back later for new listings.</p></div>`;
      return;
    }
    scroller.innerHTML = list.map(x => {
      const imgs = (x.images && x.images.length) ? x.images.slice().sort((a, b) => a.sort_order - b.sort_order).map(i => i.url) : [x.main_image_url];
      return `<article class="swipe-card" data-id="${x.id}" data-landlord="${x.landlord_id}">
   <div class="swipe-gallery">${imgs.map(u => `<img src="${mediaUrl(u)}" alt="${x.property_type} in ${x.area || x.county}">`).join("")}</div>
   <div class="gradient"></div>
   ${imgs.length > 1 ? `<div class="gallery-dots">${imgs.map((_, i) => `<span class="dot${i === 0 ? " active" : ""}"></span>`).join("")}</div>` : ""}
   <div class="swipe-info"><div class="price">${money(x.price)}</div><div class="meta">${x.property_type} · ${x.area || x.county}</div>${x.proximity_note ? `<div style="margin-top:9px">${x.proximity_note}</div>` : ""}</div>
   <div class="discover-fab-stack">
     <button class="discover-fab landlord-fab" title="View landlord's properties" data-action="landlord">⌂</button>
     <button class="discover-fab interested-fab ${interestedIds.has(x.id) ? "active" : ""}" title="Save to Interested" data-action="interested">♡</button>
     <button class="discover-fab hide-fab" title="Hide buttons">${discoverUIHidden ? ICON_EYE_OFF : ICON_EYE}</button>
   </div>
 </article>`;
    }).join("");
    bindDiscoverCards();
  }).catch(() => {
    const scroller = document.getElementById("discoverScroll");
    if (scroller) scroller.outerHTML = `<div class="empty" style="width:100%"><h3>Couldn't load Discover</h3></div>`;
  });
}

function bindDiscoverCards() {
  document.querySelectorAll("#discoverScroll .swipe-card").forEach(card => {
    const id = card.dataset.id;
    const landlordId = card.dataset.landlord;

    card.querySelector('[data-action="landlord"]').onclick = (e) => { e.stopPropagation(); goto("landlordProfile", { landlordId }); };

    const heartBtn = card.querySelector('[data-action="interested"]');
    heartBtn.onclick = async (e) => {
      e.stopPropagation();
      try {
        await api(`/properties/${id}/swipe?direction=right`, { method: "POST" });
        interestedIds.add(id);
        heartBtn.classList.add("active");
        toast("Saved to Interested");
      } catch (err) { toast(err.message || "Couldn't save"); }
    };

    card.querySelector(".hide-fab").onclick = (e) => {
      e.stopPropagation();
      discoverUIHidden = !discoverUIHidden;
      const page = document.getElementById("discoverPage");
      if (page) page.classList.toggle("ui-hidden", discoverUIHidden);
      document.querySelectorAll("#discoverScroll .hide-fab").forEach(btn => {
        btn.innerHTML = discoverUIHidden ? ICON_EYE_OFF : ICON_EYE;
      });
    };

    const gallery = card.querySelector(".swipe-gallery");
    const dots = card.querySelectorAll(".gallery-dots .dot");
    if (gallery && dots.length) {
      gallery.addEventListener("scroll", () => {
        const idx = Math.round(gallery.scrollLeft / gallery.clientWidth);
        dots.forEach((d, i) => d.classList.toggle("active", i === idx));
      }, { passive: true });
    }

    card.onclick = () => openProperty(id);
  });
}

/* ---------------- Interested ---------------- */
function interestedPage() {
  if (!isLoggedIn()) {
    app.innerHTML = `<div class="empty locked"><div class="emoji">♡</div><h3>Log in to see your saved places</h3><button class="primary" id="intLogin" style="margin-top:14px">Log in</button></div>`;
    document.getElementById("intLogin").onclick = () => openLogin();
    return;
  }
  app.innerHTML = `<section class="hero"><div class="eyebrow">YOUR SAVED PLACES</div><h1>Interested</h1><p>Properties you've saved.</p></section><div class="ad" data-ad-slot="interested">ADVERTISEMENT</div><div id="interestedBody"><div class="empty">${loaderHtml()}</div></div>`;
  hydrateAds();
  api("/properties/interested").then(list => {
    interestedList = list;
    interestedIds = new Set(list.map(p => p.id));
    const body = document.getElementById("interestedBody");
    if (!body) return;
    body.innerHTML = list.length ? `<div class="grid">${list.map(propertyCard).join("")}</div>` : `<div class="empty"><div class="emoji">♡</div><h3>Nothing saved yet</h3><p class="muted">Save a place you like in Discover and it'll appear here.</p><button class="primary" id="goDiscover">Discover places</button></div>`;
    bindCards();
    const b = document.getElementById("goDiscover"); if (b) b.onclick = () => goto("discover");
  });
}

/* ---------------- Landlord public profile (new) ---------------- */
function landlordProfile() {
  const landlordId = viewParams.landlordId;
  app.innerHTML = `<div class="section-head"><div><div class="eyebrow">LANDLORD</div><h2 id="landlordName">Loading…</h2></div><button class="chip" id="backBtn">Back</button></div>
 <div id="landlordMeta"></div>
 <div class="grid" id="landlordGrid"><div class="empty" style="grid-column:1/-1">${loaderHtml()}</div></div>`;
  document.getElementById("backBtn").onclick = () => goto("discover");
  if (!landlordId) return;
  api(`/properties/landlord/${landlordId}`).then(data => {
    const nameEl = document.getElementById("landlordName");
    if (nameEl) nameEl.textContent = data.landlord.full_name || data.landlord.username || "Landlord";
    const meta = document.getElementById("landlordMeta");
    if (meta) meta.innerHTML = `<div class="lp-head">${avatarHtml(data.landlord.profile_picture, data.landlord.full_name, 84)}${data.landlord.bio ? `<p class="muted">${escHtml(data.landlord.bio)}</p>` : ""}<div class="lp-stats"><div><strong>${data.property_count}</strong><small>Properties uploaded</small></div><div><strong>${data.properties.length}</strong><small>Available now</small></div></div></div>`;
    const grid = document.getElementById("landlordGrid");
    if (!grid) return;
    grid.innerHTML = data.properties.length ? data.properties.map(propertyCard).join("") : `<div class="empty" style="grid-column:1/-1"><h3>No other listings from this landlord yet</h3></div>`;
    bindCards();
  }).catch(() => toast("Couldn't load this landlord's properties"));
}

/* ---------------- Profile ---------------- */
function profile() {
  const signedIn = isLoggedIn() && currentUser;
  const initials = signedIn ? (currentUser.name || currentUser.username || "SM").trim().slice(0, 2).toUpperCase() : "SM";
  const roleLabel = signedIn ? (currentUser.is_admin ? "Admin" : currentUser.is_host ? "Landlord" : "Renter") : "Guest";
  app.innerHTML = `<section class="profile-head"><div class="big-avatar">${initials}</div><div><h2 style="margin:0">${signedIn ? (currentUser.name || currentUser.username) : "Your profile"}</h2><p class="muted" style="margin:6px 0"><span class="role-badge">${roleLabel}</span></p></div></section>
 <div class="panel"><strong id="profInterestedCount">${interestedIds.size || "…"}</strong><div class="muted">Interested properties</div></div>
 ${signedIn && (currentUser.is_host || currentUser.is_admin) ? `<div class="section-head"><h2>Your workspace</h2></div><div class="settings-list"><div class="setting"><div><strong>${currentUser.is_admin ? "Admin dashboard" : "Landlord dashboard"}</strong><div class="muted">${currentUser.is_admin ? "Platform management" : "Manage listings and activity"}</div></div><button class="chip" id="dashBtn">Open</button></div></div>` : ""}
 ${signedIn && !currentUser.is_host && !currentUser.is_admin ? `<div class="section-head"><h2>Your workspace</h2></div><div class="settings-list"><div class="setting"><div><strong>Become a landlord</strong><div class="muted">List your own properties on Keja</div></div><button class="chip" id="landlordDashBtn">Get started</button></div></div>` : ""}
 <div class="section-head"><h2>Appearance</h2></div>
 <div class="theme-picker">
  <button class="theme-card ${theme === "pro" ? "active" : ""}" data-theme="pro"><span class="swatch pro"><i></i><i></i><i></i></span><b>Professional</b><small>Calm, clean and business-like</small></button>
  <button class="theme-card ${theme === "rangi" ? "active" : ""}" data-theme="rangi"><span class="swatch rangi"><i></i><i></i><i></i></span><b>Rangi</b><small>Bold, colourful and playful</small></button>
 </div>
 <div class="settings-list" style="margin-top:12px">
 <div class="setting"><div><strong>Dark mode</strong><div class="muted">Same layout, easier on the eyes at night</div></div><button class="switch ${dark ? "on" : ""}" id="darkSwitch"><span></span></button></div>
 <div class="setting"><div><strong>Account</strong><div class="muted">${signedIn ? "Signed in as " + (currentUser.email || currentUser.username) : "Log in or create your Keja account"}</div></div><button class="chip" id="loginBtn">${signedIn ? "Log out" : "Log in"}</button></div>
 ${signedIn ? `<div class="setting" style="margin-top:10px"><div><strong>Switch account</strong><div class="muted">Log in as someone else without losing this session first</div></div><button class="chip" id="switchAccountBtn">Switch</button></div>` : ""}
 </div>`;
  document.getElementById("darkSwitch").onclick = toggleDark;
  document.querySelectorAll(".theme-card").forEach(b => b.onclick = () => setTheme(b.dataset.theme));
  const dash = document.getElementById("dashBtn"); if (dash) dash.onclick = () => goto(currentUser.is_admin ? "admin" : "landlord");
  const ldash = document.getElementById("landlordDashBtn"); if (ldash) ldash.onclick = () => goto("landlord");
  document.getElementById("loginBtn").onclick = () => { signedIn ? logout() : openLogin(); };
  const switchBtn = document.getElementById("switchAccountBtn");
  if (switchBtn) switchBtn.onclick = () => openLogin();

  if (signedIn) {
    api("/properties/interested").then(list => {
      interestedIds = new Set(list.map(p => p.id));
      const el = document.getElementById("profInterestedCount");
      if (el) el.textContent = list.length;
    }).catch(() => {});
  }
}

function logout(silent) {
  token = ""; currentUser = null;
  localStorage.removeItem("kejaToken");
  localStorage.removeItem("kejaUser");
  updateAvatar();
  currentView = "profile";
  render();
  if (!silent) toast("Logged out");
}

function requireCapability(check, label, neededRoleForLogin) {
  if (check) return true;
  const notLandlordYet = label === "Landlord" && isLoggedIn();
  app.innerHTML = `<div class="empty locked"><div class="emoji">🔒</div><h3>${label} access only</h3><p class="muted">${notLandlordYet ? "Your account isn't a landlord yet — request access from your profile." : isLoggedIn() ? "Your account doesn't have access to this dashboard yet." : `Log in with your ${neededRoleForLogin} account to open this dashboard.`}</p><button class="primary" id="lockLogin" style="margin-top:14px">${notLandlordYet ? "Go to profile" : isLoggedIn() ? "Back to profile" : "Log in"}</button></div>`;
  document.getElementById("lockLogin").onclick = () => isLoggedIn() ? goto("profile") : openLogin();
  return false;
}

/* ---------------- Landlord dashboard ---------------- */
function landlord() {
  if (!isLoggedIn()) { requireCapability(false, "Landlord", "landlord"); return; }

  if (!currentUser.is_host) {
    // Real host-verification status, not a fake locked screen
    api("/users/host-verification/me").then(v => {
      const status = v.host_verification_status || "none";
      if (status === "pending") {
        app.innerHTML = `<div class="empty locked"><div class="emoji">⏳</div><h3>Verification pending</h3><p class="muted">We're reviewing your landlord application. This usually takes a short while.</p></div>`;
      } else {
        renderBecomeLandlord();
      }
    }).catch(() => renderBecomeLandlord());
    return;
  }

  app.innerHTML = `<section class="dashboard"><div class="dash-top"><div><div class="eyebrow">LANDLORD</div><h1>Dashboard</h1></div><button class="primary" id="addProperty">＋ Add property</button></div>
 <div class="profile-strip"><label class="avatar-upload" title="Change photo">${avatarHtml(currentUser.profile_pic_url, currentUser.name, 60)}<input type="file" id="avatarFile" accept="image/*" hidden></label><div style="flex:1;min-width:0"><strong>${escHtml(currentUser.name || "Your profile")}</strong><div class="muted" style="font-size:12px" id="avatarMsg">Click your photo to change it</div></div><button class="chip" id="viewPublicProfile">View profile</button></div>
 <div class="stats" id="landlordStats"><div class="stat">Active listings<strong>…</strong></div><div class="stat">Property views<strong>…</strong></div><div class="stat">Interested<strong>…</strong></div><div class="stat">Contact unlocks<strong>…</strong></div></div>
 <div class="section-head"><h2>Your listings</h2><span class="muted" id="listingCount"></span></div>
 <div class="table-card"><table class="table"><thead><tr><th>Property</th><th>Price</th><th>Views</th><th>Status</th><th></th></tr></thead><tbody id="listingsBody"><tr><td colspan="5">Loading…</td></tr></tbody></table></div>
 </section>`;
  document.getElementById("addProperty").onclick = openAdd;
  document.getElementById("avatarFile").onchange = async (ev) => {
    const f = ev.target.files[0]; if (!f) return;
    const msg = document.getElementById("avatarMsg"); msg.textContent = "Uploading photo…";
    try {
      const fd = new FormData(); fd.append("file", f);
      const r = await api("/users/me/avatar", { method: "POST", body: fd });
      currentUser.profile_pic_url = r.profile_pic_url;
      toast("Profile photo updated"); landlord();
    } catch (e) { msg.textContent = e.message || "Upload failed"; }
  };
  document.getElementById("viewPublicProfile").onclick = () => {
    api(`/properties/landlord/${currentUser.id}`).then(d => openLandlordModal(d, null)).catch(() => toast("Couldn't load your profile"));
  };

  api("/properties/mine/stats").then(s => {
    const el = document.getElementById("landlordStats");
    if (!el) return;
    el.innerHTML = `<div class="stat">Active listings<strong>${s.active_listings}</strong></div><div class="stat">Property views<strong>${s.total_views}</strong></div><div class="stat">Interested<strong>${s.interested_count}</strong></div><div class="stat">Contact unlocks<strong>${s.contact_unlocks}</strong><small class="muted">${money(s.contact_unlocks_revenue)} received</small></div>`;
  }).catch(() => {});

  loadLandlordListings();
}

function renderBecomeLandlord() {
  app.innerHTML = `<div class="empty locked"><div class="emoji">⌂</div><h3>Become a landlord</h3><p class="muted">List your property on Keja. Verification helps keep the platform trustworthy for renters.</p><button class="primary" id="becomeBtn" style="margin-top:14px">Get started</button></div>`;
  document.getElementById("becomeBtn").onclick = openBecomeLandlordModal;
}

function openAmenitiesEditor(p) {
  if (!p) return;
  modal.innerHTML = `<div class="modal-head"><h2 style="margin:0">What does it have?</h2><button class="close" id="close">×</button></div>
 <p class="muted" style="font-size:13px">${escHtml(p.property_type)} · ${escHtml(p.area || p.county)}</p>${amenityPickerHtml(p.amenities)}
 <button class="primary" id="saveAmenities" style="width:100%;margin-top:16px">Save</button>`;
  showModal();
  document.getElementById("close").onclick = hideModal;
  document.getElementById("saveAmenities").onclick = async () => {
    try { await api(`/properties/${p.id}`, { method: "PATCH", body: JSON.stringify({ amenities: pickedAmenities(modal) }) }); hideModal(); toast("Amenities saved"); loadLandlordListings(); }
    catch (e) { toast(e.message || "Couldn't save"); }
  };
}

function loadLandlordListings() {
  api("/properties/mine").then(list => {
    const body = document.getElementById("listingsBody");
    const count = document.getElementById("listingCount");
    if (!body) return;
    if (count) count.textContent = list.length + " active";
    body.innerHTML = list.length ? list.map(p => `<tr data-id="${p.id}"><td><img class="mini-img" src="${mediaUrl(p.main_image_url)}">${p.property_type}<br><span class="muted">${p.area || p.county}${p.proximity_note ? " · " + escHtml(p.proximity_note) : ""}</span>${p.review_status === "rejected" ? `<br><span class="muted" style="color:#ef4444">Rejected${p.review_note ? ": " + escHtml(p.review_note) : ""}</span>` : ""}</td><td>${money(p.price)}</td><td>👁 ${p.view_count}<br><span class="muted">✦ ${(p.amenities || []).length} amenities</span></td><td><span class="status ${p.is_booked ? "booked" : "available"}">${p.is_booked ? "Booked" : "Available"}</span></td><td><button class="chip toggleBookedBtn">${p.is_booked ? "Mark available" : "Mark booked"}</button> <button class="chip amenBtn">Amenities</button> <button class="chip danger delBtn">Delete</button></td></tr>`).join("") : `<tr><td colspan="5">No listings yet — add your first property.</td></tr>`;
    body.querySelectorAll("tr[data-id]").forEach(row => {
      const id = row.dataset.id;
      const amenBtn = row.querySelector(".amenBtn");
      if (amenBtn) amenBtn.onclick = () => openAmenitiesEditor(list.find(x => x.id === id));
      const btn = row.querySelector(".toggleBookedBtn");
      if (btn) btn.onclick = async () => {
        const wantBooked = btn.textContent.trim() === "Mark booked";
        try { await api(`/properties/${id}`, { method: "PATCH", body: JSON.stringify({ is_booked: wantBooked }) }); loadLandlordListings(); }
        catch (e) { toast(e.message || "Couldn't update"); }
      };
      const delBtn = row.querySelector(".delBtn");
      if (delBtn) delBtn.onclick = () => confirmBox("Delete this listing?", "It will be removed from Keja and renters won't see it any more.", "Delete", () =>
        api(`/properties/${id}`, { method: "DELETE" }).then(() => { toast("Listing deleted"); loadLandlordListings(); }).catch(e => toast(e.message || "Couldn't delete")));
    });
  }).catch(() => {
    const body = document.getElementById("listingsBody");
    if (body) body.innerHTML = `<tr><td colspan="5">Couldn't load your listings.</td></tr>`;
  });
}

/* ---------------- Admin: separate page per function ---------------- */
function adminGuard() {
  if (!isLoggedIn() || !currentUser || !currentUser.is_admin) { requireCapability(false, "Admin", "admin"); return false; }
  return true;
}
function timeAgo(iso) {
  if (!iso) return "";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return Math.floor(s / 60) + " min ago";
  if (s < 86400) return Math.floor(s / 3600) + " h ago";
  return Math.floor(s / 86400) + " d ago";
}
function adminHead(eyebrow, title, sub) {
  return `<section class="dashboard"><div class="dash-top"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1></div><span class="tag">ADMIN</span></div><p class="muted" style="margin:6px 0 16px">${sub}</p>`;
}
function askText(title, placeholder, confirmLabel, cb, required) {
  modal.innerHTML = `<div class="modal-head"><h2 style="margin:0">${escHtml(title)}</h2><button class="close" id="close">×</button></div>
 <label class="field" style="margin-top:12px"><textarea id="askInput" rows="3" placeholder="${escHtml(placeholder)}"></textarea></label>
 <p class="muted" id="askErr" style="font-size:12px;min-height:14px;color:#ef4444"></p>
 <button class="primary" style="width:100%" id="askOk">${escHtml(confirmLabel)}</button>`;
  showModal();
  document.getElementById("close").onclick = hideModal;
  document.getElementById("askOk").onclick = () => {
    const v = document.getElementById("askInput").value.trim();
    if (required && !v) { document.getElementById("askErr").textContent = "Please add a short reason."; return; }
    hideModal(); cb(v);
  };
}
function confirmBox(title, text, confirmLabel, cb) {
  modal.innerHTML = `<div class="modal-head"><h2 style="margin:0">${escHtml(title)}</h2><button class="close" id="close">×</button></div>
 <p class="muted" style="margin:10px 0 16px">${escHtml(text)}</p>
 <div style="display:flex;gap:10px"><button class="chip" style="flex:1" id="cbNo">Cancel</button><button class="primary danger" style="flex:1" id="cbYes">${escHtml(confirmLabel)}</button></div>`;
  showModal();
  document.getElementById("close").onclick = hideModal;
  document.getElementById("cbNo").onclick = hideModal;
  document.getElementById("cbYes").onclick = () => { hideModal(); cb(); };
}

function admin() {
  if (!adminGuard()) return;
  const tiles = [
    ["adminNew", "New listings", "unreviewed_properties", "Review newly posted properties"],
    ["adminLandlords", "Landlord applications", "pending_landlords", "Approve landlords and check their ID"],
    ["adminPayments", "Payment messages", "pending_payments", "Review pasted M-Pesa messages"],
    ["adminListings", "All listings", "total_properties", "Reject, or mark as booked"],
  ];
  app.innerHTML = adminHead("KEJA ADMIN", "Overview", "What needs your attention right now.") +
    `<div class="stats" id="adminStats">${tiles.map(([v, t]) => `<button class="stat admin-tile" data-go="${v}">${t}<strong>…</strong></button>`).join("")}<div class="stat">Total users<strong id="tileUsers">…</strong></div></div></section>`;
  document.querySelectorAll(".admin-tile").forEach(b => b.onclick = () => goto(b.dataset.go));
  api("/admin/keja/overview").then(o => {
    document.getElementById("adminStats").innerHTML = tiles.map(([v, t, k, sub]) => `<button class="stat admin-tile" data-go="${v}">${t}<strong>${o[k]}</strong><small class="muted">${sub}</small></button>`).join("") + `<div class="stat">Total users<strong>${o.total_users}</strong></div>`;
    document.querySelectorAll(".admin-tile").forEach(b => b.onclick = () => goto(b.dataset.go));
  }).catch(() => {});
}

function adminPropCard(p, opts) {
  const badge = p.review_status === "rejected" ? `<span class="pill red">Rejected</span>` : p.is_booked ? `<span class="pill amber">Booked</span>` : p.review_status === "approved" ? `<span class="pill green">Approved</span>` : `<span class="pill">New</span>`;
  return `<div class="acard" data-id="${p.id}"><img class="acard-img" src="${mediaUrl(p.main_image_url)}" alt="">
 <div class="acard-body"><div class="acard-top"><strong>${escHtml(p.property_type)} · ${money(p.price)}</strong>${badge}</div>
 <div class="muted" style="font-size:12px">${escHtml(p.area || p.county || "")} · ${p.image_count} photo${p.image_count === 1 ? "" : "s"} · ${timeAgo(p.created_at)}</div>
 <div class="muted" style="font-size:12px">Landlord: ${escHtml(p.landlord_name || "—")}${p.landlord_phone ? " · " + escHtml(p.landlord_phone) : ""}</div>
 ${p.review_note ? `<div class="muted" style="font-size:12px;color:#ef4444">Reason: ${escHtml(p.review_note)}</div>` : ""}
 <div class="acard-actions">${opts}</div></div></div>`;
}
function adminReview(id, action, note, reload) {
  api(`/admin/keja/properties/${id}/review`, { method: "POST", body: JSON.stringify({ action, note }) })
    .then(() => { toast(action === "approve" ? "Approved" : "Rejected — landlord notified"); reload(); refreshAdminBadges(); })
    .catch(e => toast(e.message || "Couldn't update"));
}

function adminNew() {
  if (!adminGuard()) return;
  app.innerHTML = adminHead("NEW LISTINGS", "New properties", "Newly posted listings that haven't been reviewed yet. They are live until you reject them.") + `<div id="adminBody">${loaderHtml()}</div></section>`;
  const load = () => api("/admin/keja/properties?review=unreviewed").then(list => {
    const body = document.getElementById("adminBody"); if (!body) return;
    body.innerHTML = list.length ? list.map(p => adminPropCard(p, `<button class="primary" data-act="approve">Approve</button><button class="chip danger" data-act="reject">Reject</button>`)).join("") : `<div class="empty">Nothing new to review 🎉</div>`;
    body.querySelectorAll(".acard").forEach(card => {
      const id = card.dataset.id;
      card.querySelector('[data-act="approve"]').onclick = () => adminReview(id, "approve", null, load);
      card.querySelector('[data-act="reject"]').onclick = () => askText("Reject this listing", "Reason for the landlord (e.g. photos unclear)", "Reject listing", note => adminReview(id, "reject", note, load), true);
    });
  }).catch(e => { const b = document.getElementById("adminBody"); if (b) b.innerHTML = `<div class="empty">${escHtml(e.message || "Couldn't load")}</div>`; });
  load();
}

function adminLandlords() {
  if (!adminGuard()) return;
  app.innerHTML = adminHead("LANDLORDS", "Landlord applications", "Check the ID photo, then approve or reject.") + `<div id="adminBody">${loaderHtml()}</div></section>`;
  const load = () => api("/admin/hosts/pending").then(list => {
    const body = document.getElementById("adminBody"); if (!body) return;
    body.innerHTML = list.length ? list.map(u => `<div class="acard col" data-id="${u.id}"><div class="acard-body">
 <div class="acard-top"><strong>${escHtml(u.full_name || u.email)}</strong><span class="pill">${timeAgo(u.verification_requested_at)}</span></div>
 <div class="muted" style="font-size:12px">${escHtml(u.email || "")}${u.phone ? " · " + escHtml(u.phone) : ""}</div>
 <div class="muted" style="font-size:12px">ID number: ${escHtml(u.government_id || "—")}</div>
 <div class="acard-actions">${u.government_id_image_url ? `<button class="chip" data-act="id">View ID photo</button>` : `<span class="pill red">No ID photo</span>`}<button class="primary" data-act="approve">Approve</button><button class="chip danger" data-act="reject">Reject</button></div></div></div>`).join("") : `<div class="empty">No applications waiting</div>`;
    body.querySelectorAll(".acard").forEach(card => {
      const id = card.dataset.id;
      const idBtn = card.querySelector('[data-act="id"]');
      if (idBtn) idBtn.onclick = () => viewLandlordId(id);
      const decide = (approve, note) => api(`/admin/hosts/${id}/verify`, { method: "POST", body: JSON.stringify({ approve, note }) })
        .then(() => { toast(approve ? "Landlord approved" : "Application rejected"); load(); refreshAdminBadges(); })
        .catch(e => toast(e.message || "Couldn't update"));
      card.querySelector('[data-act="approve"]').onclick = () => decide(true, null);
      card.querySelector('[data-act="reject"]').onclick = () => askText("Reject application", "Reason (shown to the applicant)", "Reject", note => decide(false, note), true);
    });
  }).catch(e => { const b = document.getElementById("adminBody"); if (b) b.innerHTML = `<div class="empty">${escHtml(e.message || "Couldn't load")}</div>`; });
  load();
}
function viewLandlordId(userId) {
  modal.innerHTML = `<div class="modal-head"><h2 style="margin:0">ID photo</h2><button class="close" id="close">×</button></div><div id="idBody">${loaderHtml()}</div>`;
  showModal(); document.getElementById("close").onclick = hideModal;
  api(`/admin/keja/landlords/${userId}/id-image`).then(r => {
    document.getElementById("idBody").innerHTML = `<img src="data:${r.content_type};base64,${r.data_base64}" alt="ID photo" style="width:100%;border-radius:12px;margin-top:10px">`;
  }).catch(e => { document.getElementById("idBody").innerHTML = `<p class="muted">${escHtml(e.message || "No ID photo on file")}</p>`; });
}

function adminPayments() {
  if (!adminGuard()) return;
  app.innerHTML = adminHead("PAYMENTS", "Payment messages", "Renters paste their M-Pesa message here. Check it against your till, then tap Show number to send the landlord's number to their Alerts.") + `<div id="adminBody">${loaderHtml()}</div></section>`;
  const load = () => api("/contact-unlock/admin/pending").then(list => {
    const body = document.getElementById("adminBody"); if (!body) return;
    body.innerHTML = list.length ? list.map(r => `<div class="acard col" data-id="${r.id}"><div class="acard-body">
 <div class="acard-top"><strong>${escHtml(r.buyer_name || "Renter")}</strong><span class="pill">${timeAgo(r.buyer_claimed_at)}</span></div>
 <div class="muted" style="font-size:12px">${r.buyer_phone ? escHtml(r.buyer_phone) + " · " : ""}for ${escHtml(r.property_title || "a property")} · expected ${money(r.amount)}</div>
 <div class="sms-box">${escHtml(r.buyer_claimed_raw_message || r.buyer_claimed_code || "(empty)")}</div>
 <div class="muted" style="font-size:12px">Will send: ${escHtml(r.landlord_name || "landlord")} ${r.landlord_phone ? "· " + escHtml(r.landlord_phone) : "(no phone on file!)"}</div>
 <div class="acard-actions"><button class="primary" data-act="show">Show number</button><button class="chip danger" data-act="reject">Reject</button></div></div></div>`).join("") : `<div class="empty">No payment messages waiting</div>`;
    body.querySelectorAll(".acard").forEach(card => {
      const id = card.dataset.id;
      card.querySelector('[data-act="show"]').onclick = () => api(`/contact-unlock/admin/${id}/show`, { method: "POST" })
        .then(() => { toast("Number sent to the user's Alerts"); load(); refreshAdminBadges(); }).catch(e => toast(e.message || "Couldn't send"));
      card.querySelector('[data-act="reject"]').onclick = () => askText("Reject payment message", "Reason for the renter (optional)", "Reject", note =>
        api(`/contact-unlock/admin/${id}/reject`, { method: "POST", body: JSON.stringify({ reason: note }) }).then(() => { toast("Rejected — user notified"); load(); refreshAdminBadges(); }).catch(e => toast(e.message || "Couldn't reject")), false);
    });
  }).catch(e => { const b = document.getElementById("adminBody"); if (b) b.innerHTML = `<div class="empty">${escHtml(e.message || "Couldn't load")}</div>`; });
  load();
}

function adminListings() {
  if (!adminGuard()) return;
  let filter = viewParams.filter || "all";
  app.innerHTML = adminHead("LISTINGS", "All properties", "Reject a listing, or mark it as booked when you know it's taken.") +
    `<div class="chips" id="adminFilters">${[["all", "All"], ["live", "Live"], ["booked", "Booked"], ["rejected", "Rejected"]].map(([k, l]) => `<button class="chip" data-f="${k}">${l}</button>`).join("")}</div><div id="adminBody" style="margin-top:12px">${loaderHtml()}</div></section>`;
  let all = [];
  const draw = () => {
    document.querySelectorAll("#adminFilters .chip").forEach(c => c.classList.toggle("active", c.dataset.f === filter));
    const list = all.filter(p => filter === "all" || (filter === "booked" && p.is_booked) || (filter === "rejected" && p.review_status === "rejected") || (filter === "live" && p.is_available));
    const body = document.getElementById("adminBody"); if (!body) return;
    body.innerHTML = list.length ? list.map(p => adminPropCard(p,
      `<button class="chip" data-act="book">${p.is_booked ? "Reopen" : "Mark booked"}</button>` +
      (p.review_status === "rejected" ? `<button class="primary" data-act="approve">Approve</button>` : `<button class="chip danger" data-act="reject">Reject</button>`))).join("") : `<div class="empty">Nothing here</div>`;
    body.querySelectorAll(".acard").forEach(card => {
      const id = card.dataset.id, p = all.find(x => x.id === id);
      card.querySelector('[data-act="book"]').onclick = () => confirmBox(p.is_booked ? "Reopen listing?" : "Mark as booked?", p.is_booked ? "It will show to renters again." : "It will disappear from renters' feeds and the landlord will be told.", p.is_booked ? "Reopen" : "Mark booked", () =>
        api(`/admin/keja/properties/${id}/force-booked`, { method: "POST", body: JSON.stringify({ booked: !p.is_booked }) }).then(() => { toast("Updated"); load(); }).catch(e => toast(e.message || "Couldn't update")));
      const rj = card.querySelector('[data-act="reject"]'); if (rj) rj.onclick = () => askText("Reject this listing", "Reason for the landlord", "Reject listing", note => adminReview(id, "reject", note, load), true);
      const ap = card.querySelector('[data-act="approve"]'); if (ap) ap.onclick = () => adminReview(id, "approve", null, load);
    });
  };
  const load = () => api("/admin/keja/properties?review=all").then(list => { all = list; draw(); }).catch(e => { const b = document.getElementById("adminBody"); if (b) b.innerHTML = `<div class="empty">${escHtml(e.message || "Couldn't load")}</div>`; });
  document.querySelectorAll("#adminFilters .chip").forEach(c => c.onclick = () => { filter = c.dataset.f; draw(); });
  load();
}

function adminAds() {
  if (!adminGuard()) return;
  app.innerHTML = adminHead("ADS", "Ad placement", "The banners shown on Home and on the Interested page.") +
    `<div class="panel" id="adPanel"><div class="ad-placement-row"><div><strong>Home feed</strong><small>Promotional slot under the categories</small></div><span class="status" id="adStatusHome">…</span></div><div class="ad-placement-row"><div><strong>Interested page</strong><small>Top of the Interested page</small></div><span class="status" id="adStatusInterested">…</span></div></div>
 <button class="primary" id="adPlacementBtn" style="margin-top:14px;width:100%">Manage ads</button></section>`;
  document.getElementById("adPlacementBtn").onclick = () => openAdPlacement();
  api("/admin/ads").then(r => {
    [["home", "adStatusHome"], ["interested", "adStatusInterested"]].forEach(([k, id]) => {
      const el = document.getElementById(id); if (!el) return;
      const live = (r.ads || []).some(a => a.placement === k && a.is_active);
      el.textContent = live ? "Live" : "No ad"; el.className = "status " + (live ? "available" : "");
    });
  }).catch(() => {});
}

/* ---------------- Alerts (the bell) ---------------- */
function alertsPage() {
  if (!isLoggedIn()) { app.innerHTML = `<div class="empty locked"><div class="emoji">🔔</div><h3>Log in to see your alerts</h3><button class="primary" id="alLogin" style="margin-top:14px">Log in</button></div>`; document.getElementById("alLogin").onclick = () => openLogin(); return; }
  app.innerHTML = `<section class="hero"><div class="eyebrow">MESSAGES FROM KEJA</div><h1>Alerts</h1><p>Landlord numbers and updates about the properties you asked about.</p></section><div id="alertsBody">${loaderHtml()}</div>`;
  api("/users/notifications?context=user").then(list => {
    const body = document.getElementById("alertsBody"); if (!body) return;
    body.innerHTML = list.length ? list.map(n => {
      const d = n.data || {};
      const wa = String(d.phone || "").replace(/\D/g, ""), waFmt = wa.startsWith("0") ? "254" + wa.slice(1) : wa;
      return `<div class="alert-card ${n.read ? "" : "unread"}"><div class="acard-top"><strong>${escHtml(n.title)}</strong><span class="muted" style="font-size:11px">${timeAgo(n.created_at)}</span></div>
 ${n.body ? `<div style="margin-top:4px;font-size:14px">${escHtml(n.body)}</div>` : ""}
 <div class="acard-actions">${d.phone ? `<a class="primary" href="tel:${escHtml(d.phone)}">Call</a><a class="chip" href="https://wa.me/${waFmt}" target="_blank" rel="noopener">WhatsApp</a>` : ""}${d.property_id ? `<button class="chip" data-prop="${escHtml(d.property_id)}">View property</button>` : ""}</div></div>`;
    }).join("") : `<div class="empty"><div class="emoji">🔔</div>No alerts yet. When a landlord's number is ready, it shows up here.</div>`;
    body.querySelectorAll("[data-prop]").forEach(b => b.onclick = () => openProperty(b.dataset.prop));
    if (list.some(n => !n.read)) api("/users/notifications/read-all", { method: "POST" }).then(updateBell).catch(() => {});
  }).catch(e => { const b = document.getElementById("alertsBody"); if (b) b.innerHTML = `<div class="empty">${escHtml(e.message || "Couldn't load alerts")}</div>`; });
}

/* ---------------- Property modal (view + Get Contact) ---------------- */
// All photos of a property, main/first-sorted, falling back to the main image.
function photoList(p) {
  const list = (p.images && p.images.length)
    ? p.images.slice().sort((a, b) => a.sort_order - b.sort_order).map(i => i.url)
    : [p.main_image_url];
  return list.filter(Boolean);
}

// Full-screen swipeable photo viewer. Back (left) returns to the property
// dialog underneath; Contact (right) closes the viewer and runs the same
// get-contact flow as the dialog's own button.
function openPhotoViewer(p) {
  const photos = photoList(p);
  const v = document.createElement("div");
  v.className = "photo-viewer";
  v.innerHTML = `<div class="pv-count" id="pvCount">1 / ${photos.length}</div>
 <div class="pv-track" id="pvTrack">${photos.map(u => `<div class="pv-slide"><img src="${escHtml(mediaUrl(u))}" alt=""></div>`).join("")}</div>
 ${photos.length > 1 ? `<button class="pv-nav pv-prev" id="pvPrev" aria-label="Previous photo">‹</button><button class="pv-nav pv-next" id="pvNext" aria-label="Next photo">›</button>` : ""}
 <div class="pv-bar"><button class="pv-back" id="pvBack" type="button">← Back</button><button class="pv-contact" id="pvContact" type="button"${p.is_booked ? " disabled" : ""}>${p.is_booked ? "Booked" : "Get contact"}</button></div>`;
  document.body.appendChild(v);

  const track = v.querySelector("#pvTrack");
  const count = v.querySelector("#pvCount");
  const index = () => Math.round(track.scrollLeft / track.clientWidth);
  const go = i => track.scrollTo({ left: Math.max(0, Math.min(photos.length - 1, i)) * track.clientWidth, behavior: "smooth" });
  track.addEventListener("scroll", () => { count.textContent = (index() + 1) + " / " + photos.length; });
  if (photos.length > 1) {
    v.querySelector("#pvPrev").onclick = () => go(index() - 1);
    v.querySelector("#pvNext").onclick = () => go(index() + 1);
  }
  const close = () => { document.removeEventListener("keydown", onKey); v.remove(); };
  function onKey(e) {
    if (e.key === "Escape") close();
    else if (e.key === "ArrowLeft") go(index() - 1);
    else if (e.key === "ArrowRight") go(index() + 1);
  }
  document.addEventListener("keydown", onKey);
  v.querySelector("#pvBack").onclick = close;
  v.querySelector("#pvContact").onclick = () => {
    close();
    handleGetContact(p.id);
    const area = document.getElementById("contactArea");
    if (area) area.scrollIntoView({ block: "center", behavior: "smooth" });
  };
}

function openProperty(id) {
  modal.innerHTML = `<div class="modal-head"><h2 style="margin:0">Loading…</h2><button class="close" id="close">×</button></div>`;
  showModal();
  document.getElementById("close").onclick = hideModal;

  api(`/properties/${id}`).then(p => {
    modal.innerHTML = `<div class="modal-head"><h2 style="margin:0">${p.property_type}</h2><button class="close" id="close">×</button></div>
 <div class="hero-wrap"><img src="${mediaUrl(p.main_image_url)}" alt=""><button class="view-photos" id="viewPhotosBtn" type="button">⤢ Photos${photoList(p).length > 1 ? " (" + photoList(p).length + ")" : ""}</button><div class="hero-overlay"><div class="landlord-chip" id="landlordChip"><div class="avatar-img fallback" style="width:38px;height:38px;max-height:none;border-radius:50%;font-size:16px">K</div><div><b>Landlord</b><small>View profile</small></div></div>${(p.amenities && p.amenities.length) ? `<div class="amenity-row">${amenityCards(p.amenities)}</div>` : ""}</div></div><div style="padding-top:15px"><div class="price">${money(p.price)} <span class="muted" style="font-size:12px">/ month</span></div><p><strong>${p.area || p.county}</strong>${p.proximity_note ? " · " + p.proximity_note : ""}</p><p class="muted">${p.description || ""}</p>
 <div id="contactArea"><button class="primary" style="width:100%;margin-top:8px" id="contactBtn">${p.is_booked ? "This property is booked" : "Get contact"}</button><p class="muted" style="font-size:11px;text-align:center">A KES 50 payment is matched first. The landlord's WhatsApp number is revealed after successful confirmation.</p></div></div>`;
    document.getElementById("close").onclick = hideModal;
    const contactBtn = document.getElementById("contactBtn");
    document.getElementById("viewPhotosBtn").onclick = () => openPhotoViewer(p);
    api(`/properties/landlord/${p.landlord_id}`).then(d => {
      const chip = document.getElementById("landlordChip"); if (!chip) return;
      const n = d.property_count || 0;
      chip.innerHTML = `${avatarHtml(d.landlord.profile_picture, d.landlord.full_name, 38)}<div><b>${escHtml(d.landlord.full_name)}</b><small>${n ? n + " propert" + (n === 1 ? "y" : "ies") + " · " : ""}View profile</small></div>`;
      chip.onclick = () => openLandlordModal(d, p.id);
    }).catch(() => {});
    if (p.is_booked) { contactBtn.disabled = true; return; }
    contactBtn.onclick = () => handleGetContact(p.id);
  }).catch(() => {
    modal.innerHTML = `<div class="modal-head"><h2 style="margin:0">Not found</h2><button class="close" id="close">×</button></div><p class="muted">This listing may have been removed.</p>`;
    document.getElementById("close").onclick = hideModal;
  });
}

async function handleGetContact(propertyId) {
  if (!isLoggedIn()) { hideModal(); openLogin(); toast("Log in to contact a landlord"); return; }
  const area = document.getElementById("contactArea");
  area.innerHTML = `<p class="muted" style="text-align:center">Checking…</p>`;
  try {
    const status = await api(`/contact-unlock/${propertyId}`);
    renderContactArea(propertyId, status);
  } catch (e) {
    area.innerHTML = `<p class="muted" style="text-align:center">Couldn't check contact status.</p>`;
  }
}

function renderContactArea(propertyId, status) {
  const area = document.getElementById("contactArea");
  if (!area) return;
  if (status.status === "unlocked") {
    const wa = (status.whatsapp || "").replace(/\D/g, "");
    const waFmt = wa.startsWith("0") ? "254" + wa.slice(1) : wa;
    area.innerHTML = `<div class="setting" style="margin-top:8px"><div><strong>Contact unlocked</strong><br><a href="tel:${status.phone}" style="color:var(--primary)">${status.phone}</a></div></div>
 <a class="primary" style="width:100%;display:block;text-align:center;text-decoration:none;margin-top:10px" href="https://wa.me/${waFmt}" target="_blank">Message on WhatsApp</a>`;
    return;
  }
  if (status.status === "awaiting_admin_match") {
    area.innerHTML = `<p class="muted" style="text-align:center">We've sent your M-Pesa message to our team. The landlord's number will arrive in your <b>Alerts</b> (the 🔔 at the top) as soon as it's verified.</p><button class="chip" id="resendBtn" style="width:100%">Resend payment code</button>`;
    document.getElementById("resendBtn").onclick = () => renderContactClaimForm(propertyId, status);
    return;
  }
  if (status.free_credits_available > 0) {
    area.innerHTML = `<button class="primary" style="width:100%" id="useFreeCreditBtn">Get contact — Free credit available 🎁</button>`;
    document.getElementById("useFreeCreditBtn").onclick = async () => {
      try {
        const updated = await api(`/contact-unlock/${propertyId}/use-free-credit`, { method: "POST" });
        toast("Free contact credit used 🎉");
        renderContactArea(propertyId, updated);
      } catch (e) { toast(e.message || "Couldn't unlock"); }
    };
    return;
  }
  renderContactChoice(propertyId, status);
}

function openReferralInstructions(propertyId, status) {
  modal.innerHTML = `<div class="modal-head"><h2 style="margin:0">Get this number free</h2><button class="close" id="close">×</button></div>
 <ol class="pay-steps" style="margin-top:14px">
  <li><i>1</i><div><b>Share your link</b><span>Tap the button below and send your personal link to a friend who doesn't have a Keja account yet.</span></div></li>
  <li><i>2</i><div><b>Your friend signs up</b><span>They must open your link and create an account. Logging in to an existing account doesn't count.</span></div></li>
  <li><i>3</i><div><b>The number arrives automatically</b><span>The moment they sign up, the landlord's number is sent to your <b>Alerts</b> (the 🔔 at the top of Home).</span></div></li>
  <li><i>4</i><div><b>Good to know</b><span>This free unlock works once. Don't want to wait? You can pay KES ${MPESA_TILL.amount} instead.</span></div></li>
 </ol>
 <button class="primary" style="width:100%;margin-top:14px" id="startRefBtn">Start &amp; share my link</button>
 <button class="chip" style="width:100%;margin-top:8px" id="refPayBtn">Pay KES ${MPESA_TILL.amount} instead</button>`;
  showModal();
  document.getElementById("close").onclick = hideModal;
  document.getElementById("refPayBtn").onclick = () => { hideModal(); renderContactClaimForm(propertyId, status); };
  document.getElementById("startRefBtn").onclick = async () => {
    try { await api(`/contact-unlock/${propertyId}/request-referral`, { method: "POST" }); } catch (e) { toast(e.message || "Couldn't start"); return; }
    hideModal(); shareReferralLink(); toast("Waiting for your friend — we'll alert you");
  };
}

function shareReferralLink() {
  const code = currentUser && currentUser.referral_code;
  if (!code) { toast("Log in to get your referral link"); return; }
  const link = location.origin + location.pathname.split("?")[0] + "?ref=" + code;
  if (navigator.share) {
    navigator.share({ title: "Keja", text: "Check out Keja — find your next home in Kenya!", url: link }).catch(() => {});
  } else if (navigator.clipboard) {
    navigator.clipboard.writeText(link).then(
      () => toast("Link copied — send it to a friend to unlock a free contact!"),
      () => toast("Couldn't copy the link")
    );
  } else {
    toast(link);
  }
}

function renderContactChoice(propertyId, status) {
  const area = document.getElementById("contactArea");
  if (!area) return;
  const canEarnFree = isLoggedIn() && currentUser && !currentUser.referral_bonus_granted;
  area.innerHTML = `<div style="display:flex;gap:10px">
 ${canEarnFree ? `<button class="chip" id="shareBtn" style="flex:1">Share &amp; unlock free</button>` : ""}
 <button class="primary" id="payBtn" style="flex:1">Pay KES ${MPESA_TILL.amount}</button>
 </div>
 <p class="muted" style="font-size:11px;text-align:center;margin-top:8px">${canEarnFree ? "Refer a friend who signs up to earn 1 free contact unlock, or pay now." : "A KES " + MPESA_TILL.amount + " payment is matched, then the landlord's WhatsApp is revealed."}</p>`;
  if (canEarnFree) document.getElementById("shareBtn").onclick = () => openReferralInstructions(propertyId, status);
  document.getElementById("payBtn").onclick = () => renderContactClaimForm(propertyId, status);
}

function renderContactClaimForm(propertyId, status) {
  const area = document.getElementById("contactArea");
  if (!area) return;
  const canGoBack = isLoggedIn() && currentUser && !currentUser.referral_bonus_granted;
  area.innerHTML = `${canGoBack ? `<button class="chip" id="backToChoiceBtn" style="margin-bottom:10px">← Back</button>` : ""}
 <div class="pay-card"><h3>Pay KES ${MPESA_TILL.amount} via M-Pesa</h3><p class="muted" style="margin:2px 0 14px;font-size:12px">One-time payment to unlock this landlord's contact.</p>
 <ol class="pay-steps">
  <li><i>1</i><div><b>Open M-Pesa</b><span>Go to Lipa na M-Pesa → Buy Goods and Services.</span></div></li>
  <li><i>2</i><div><b>Enter the Till number</b><div class="till-box"><div><strong>${MPESA_TILL.till}</strong><small>Business name: ${MPESA_TILL.name}</small></div><button class="chip" id="copyTillBtn" type="button">Copy</button></div></div></li>
  <li><i>3</i><div><b>Enter the amount</b><span>KES ${MPESA_TILL.amount} — the exact amount, so we can match it.</span></div></li>
  <li><i>4</i><div><b>Confirm and pay</b><span>Check the name reads ${MPESA_TILL.name}, then enter your M-Pesa PIN.</span></div></li>
  <li><i>5</i><div><b>Paste your confirmation</b><span>Copy the M-Pesa SMS (it starts with a code like QGH7XXXXX) and paste it below.</span></div></li>
 </ol>
 <label class="field" style="margin-top:12px"><span>M-Pesa confirmation message</span><textarea id="claimText" rows="3" placeholder="e.g. QGH7XXXXX Confirmed. Ksh50.00 paid to Obsidian Labs…"></textarea></label>
 <p class="muted" id="claimError" style="font-size:12px;min-height:14px;color:#ef4444"></p>
 <p class="muted" style="font-size:11px;margin:0 0 10px">We match your payment to your account, usually within a few minutes. Keep the SMS until your contact unlocks.</p>
 <button class="primary" style="width:100%" id="submitClaimBtn">I've paid — verify my code</button></div>`;
  document.getElementById("copyTillBtn").onclick = async (ev) => {
    const btn = ev.currentTarget;
    try { await navigator.clipboard.writeText(MPESA_TILL.till); } catch (e) {
      const t = document.createElement("textarea"); t.value = MPESA_TILL.till; document.body.appendChild(t); t.select(); try { document.execCommand("copy"); } catch (e2) {} t.remove();
    }
    btn.textContent = "Copied ✓";
  };
  if (canGoBack) document.getElementById("backToChoiceBtn").onclick = () => renderContactChoice(propertyId, status);
  document.getElementById("submitClaimBtn").onclick = async () => {
    const raw = document.getElementById("claimText").value.trim();
    const errEl = document.getElementById("claimError");
    if (!raw) { errEl.textContent = "Paste your M-Pesa code or message first."; return; }
    try {
      const updated = await api(`/contact-unlock/${propertyId}/claim`, { method: "POST", body: JSON.stringify({ raw_text: raw }) });
      renderContactArea(propertyId, updated);
      toast(updated.status === "unlocked" ? "Contact unlocked!" : "Submitted — verifying your payment");
    } catch (e) { errEl.textContent = e.message || "Couldn't submit — try again"; }
  };
}

/* ---------------- Add property modal ---------------- */
function openAdd() {
  modal.innerHTML = `<div class="modal-head"><h2 style="margin:0">Add property</h2><button class="close" id="close">×</button></div>
 <div class="form-grid" style="margin-top:18px"><label class="field"><span>Property type</span><select id="addType"><option>Bedsitter</option><option>1 Bedroom</option><option>2 Bedroom</option><option>Airbnb</option></select></label>
 <label class="field"><span>Price (KES)</span><input id="addPrice" type="number" placeholder="15000"></label><label class="field"><span>Location</span><input id="addLocation" placeholder="Kilimani"></label><label class="field"><span>Nearby landmark</span><input id="addLandmark" placeholder="10 min from Yaya"></label><label class="field full"><span>Description</span><textarea id="addDesc" rows="4" placeholder="Tell renters about the property"></textarea></label><div class="field full"><span>What does it have?</span><small class="muted">Tick everything that applies — renters see these as icons on your listing.</small>${amenityPickerHtml()}</div><label class="field full"><span>Property images</span><input id="addImages" type="file" multiple accept="image/*"></label>
 <p class="muted field full" id="addError" style="font-size:12px;min-height:14px"></p>
 <button class="primary field full" id="publish">Publish listing</button></div>`;
  showModal();
  document.getElementById("close").onclick = hideModal;
  document.getElementById("publish").onclick = async () => {
    const btn = document.getElementById("publish");
    const errEl = document.getElementById("addError");
    const type = document.getElementById("addType").value;
    const price = Number(document.getElementById("addPrice").value);
    const location = document.getElementById("addLocation").value.trim();
    const landmark = document.getElementById("addLandmark").value.trim();
    const desc = document.getElementById("addDesc").value.trim();
    const files = document.getElementById("addImages").files;
    if (!price || !location) { errEl.textContent = "Price and location are required."; return; }
    btn.disabled = true; btn.textContent = "Publishing…";
    try {
      const prop = await api("/properties/create", {
        method: "POST",
        body: JSON.stringify({
          title: `${type} in ${location}`,
          price, property_type: type, county: location, area: location,
          proximity_note: landmark || null, description: desc || null,
          amenities: pickedAmenities(modal),
        }),
      });
      for (let i = 0; i < files.length; i++) {
        const fd = new FormData();
        fd.append("file", files[i]);
        await api(`/properties/${prop.id}/images?is_main=${i === 0}`, { method: "POST", body: fd });
      }
      hideModal();
      toast("Listing published 🎉");
      if (currentView === "landlord") loadLandlordListings();
    } catch (e) {
      errEl.textContent = e.message || "Couldn't publish listing";
      btn.disabled = false; btn.textContent = "Publish listing";
    }
  };
}

/* ---------------- Become-a-landlord modal ---------------- */
function openBecomeLandlordModal() {
  modal.innerHTML = `<div class="modal-head"><h2 style="margin:0">Become a landlord</h2><button class="close" id="close">×</button></div>
 <p class="muted">Verification is reviewed by our team to keep Keja trustworthy for renters.</p>
 <label class="field"><span>Government ID number</span><input id="govId"></label>
 <label class="field" style="margin-top:10px"><span>Phone for renter contact</span><input id="landlordPhone" value="${(currentUser && currentUser.phone) || ""}"></label>
 <label class="field" style="margin-top:10px"><span>Photo of your ID (required)</span><input id="idPhoto" type="file" accept="image/*"></label>
 <p class="muted" style="font-size:11px;margin:4px 0 0">Only our admins can see this. It isn't shown to renters.</p>
 <p class="muted" id="becomeError" style="font-size:12px;min-height:14px"></p>
 <button class="primary" style="width:100%" id="becomeSubmit">Submit for review</button>`;
  showModal();
  document.getElementById("close").onclick = hideModal;
  document.getElementById("becomeSubmit").onclick = async () => {
    const btn = document.getElementById("becomeSubmit");
    const idFile = document.getElementById("idPhoto").files[0];
    if (!idFile) { document.getElementById("becomeError").textContent = "Please add a clear photo of your ID."; return; }
    btn.disabled = true; btn.textContent = "Submitting…";
    try {
      const fd = new FormData(); fd.append("file", idFile);
      await api("/users/me/id-image", { method: "POST", body: fd });
      await api("/users/host-verification/request", {
        method: "POST",
        body: JSON.stringify({
          government_id: document.getElementById("govId").value.trim(),
          phone: document.getElementById("landlordPhone").value.trim(),
        }),
      });
      hideModal();
      toast("Submitted — we'll review shortly");
      if (currentView === "landlord") landlord();
    } catch (e) {
      document.getElementById("becomeError").textContent = e.message || "Couldn't submit";
      btn.disabled = false; btn.textContent = "Submit for review";
    }
  };
}

/* ---------------- Login / signup ---------------- */
function openLogin() {
  let mode = "login";

  const submit = async () => {
    const id = (document.getElementById("authId").value || "").trim();
    const pass = (document.getElementById("authPass").value || "").trim();
    const nameEl = document.getElementById("authName");
    const errEl = document.getElementById("authError");
    if (!id || !pass) { if (errEl) errEl.textContent = "Enter your details to continue"; return; }
    const submitBtn = document.getElementById("loginSubmit");
    submitBtn.disabled = true; submitBtn.textContent = "Please wait…";
    try {
      const isEmail = id.includes("@");
      if (mode === "signup") {
        await api("/register", {
          method: "POST",
          body: JSON.stringify({
            full_name: (nameEl && nameEl.value.trim()) || id,
            username: id.split("@")[0].replace(/\s+/g, "").toLowerCase() + Math.floor(Math.random() * 1000),
            email: isEmail ? id : `${id.replace(/\D/g, "")}@keja.local`,
            phone: isEmail ? "" : id,
            password: pass,
          }),
        });
      }
      const loginRes = await api("/login", {
        method: "POST",
        body: JSON.stringify({ email: isEmail ? id : `${id.replace(/\D/g, "")}@keja.local`, password: pass }),
      });
      const me = await fetch(API_BASE + "/users/me", { headers: { Authorization: "Bearer " + loginRes.access_token } }).then(r => r.json());
      setSession(loginRes.access_token, me);
      hideModal();
      // Auto-detect: landlord/admin access comes from the account
      // itself (is_host / is_admin), never from a role picked at
      // login — there is no such picker anymore.
      goto(me.is_admin ? "admin" : me.is_host ? "landlord" : "home");
      toast(`Welcome${me.name ? ", " + me.name.split(" ")[0] : ""}!`);
    } catch (e) {
      if (errEl) errEl.textContent = e.message || "Something went wrong";
    } finally {
      submitBtn.disabled = false; submitBtn.textContent = mode === "login" ? "Log in" : "Create account";
    }
  };

  const draw = () => {
    modal.innerHTML = `<div class="auth-card"><div class="auth-brand"><img class="brand-logo brand-logo-light" src="assets/keja-logo.svg" alt="Keja"><img class="brand-logo brand-logo-dark" src="assets/keja-logo-white.svg" alt="" aria-hidden="true"></div><button class="close" id="close">×</button>
  <div class="auth-hero"><div class="auth-orb">♡</div><h2>${mode === "login" ? "Welcome back to Keja" : "Create your Keja account"}</h2><p>Find a place, save the ones you like and message landlords directly.</p></div>
  <div class="auth-tabs"><button class="${mode === "login" ? "active" : ""}" data-mode="login">Log in</button><button class="${mode === "signup" ? "active" : ""}" data-mode="signup">Sign up</button></div>
  ${mode === "signup" ? `<label class="field" style="margin-bottom:12px"><span>Full name</span><input id="authName" placeholder="e.g. Sarah Mwangi"></label>` : ""}
  <label class="field"><span>Email or phone</span><input id="authId" placeholder="e.g. 0712 345 678"></label>
  <label class="field" style="margin-top:12px"><span>Password</span><input id="authPass" type="password" placeholder="••••••••"></label>
  <p class="muted" id="authError" style="font-size:12px;min-height:14px;text-align:center"></p>
  <button class="primary" style="width:100%;margin-top:16px" id="loginSubmit">${mode === "login" ? "Log in" : "Create account"}</button>
  <a class="chip" href="https://github.com/obsidianlabs101-spec/keja-app/releases/download/android-latest/app-debug.apk" style="width:100%;display:flex;align-items:center;justify-content:center;gap:8px;margin-top:10px;text-decoration:none;box-sizing:border-box">⬇ Download Android app</a>
  <p class="auth-note">By continuing, you agree to Keja's terms and privacy policy. Landlords: request landlord access from your profile after signing up.</p></div>`;
    document.getElementById("close").onclick = hideModal;
    modal.querySelectorAll(".auth-tabs button").forEach(b => b.onclick = () => { mode = b.dataset.mode; draw(); });
    document.getElementById("loginSubmit").onclick = submit;
    ["authId", "authPass", "authName"].forEach(id => { const el = document.getElementById(id); if (el) el.onkeydown = e => { if (e.key === "Enter") submit(); }; });
  };
  draw(); showModal();
}

/* ---------------- Amenities + avatars (shared helpers) ---------------- */
// Keys must match ALLOWED_AMENITIES in backend/app/schemas/property.py.
const AMENITIES = [
  { key: "bathroom", label: "Own bathroom", icon: "🛁" }, { key: "balcony", label: "Balcony", icon: "🌇" },
  { key: "parking", label: "Parking", icon: "🅿️" }, { key: "wifi", label: "WiFi", icon: "📶" },
  { key: "water", label: "24/7 water", icon: "💧" }, { key: "security", label: "Security", icon: "🛡️" },
  { key: "cctv", label: "CCTV", icon: "📹" }, { key: "meter", label: "Own KPLC meter", icon: "⚡" },
  { key: "gated", label: "Gated compound", icon: "🏘️" }, { key: "furnished", label: "Furnished", icon: "🛋️" },
  { key: "pets", label: "Pets allowed", icon: "🐾" }, { key: "lift", label: "Lift", icon: "🛗" },
  { key: "generator", label: "Backup power", icon: "🔋" }, { key: "kitchen", label: "Fitted kitchen", icon: "🍳" },
  { key: "laundry", label: "Laundry area", icon: "🧺" }, { key: "garden", label: "Garden", icon: "🌳" },
];
function amenityCards(keys) {
  return (keys || []).map(k => AMENITIES.find(a => a.key === k)).filter(Boolean)
    .map(a => `<div class="amenity-card"><span>${a.icon}</span><small>${a.label}</small></div>`).join("");
}
function amenityPickerHtml(selected) {
  selected = selected || [];
  return `<div class="amenity-picker">${AMENITIES.map(a => `<label class="amenity-chip"><input type="checkbox" value="${a.key}" ${selected.includes(a.key) ? "checked" : ""}><span>${a.icon} ${a.label}</span></label>`).join("")}</div>`;
}
function pickedAmenities(root) {
  return [...root.querySelectorAll(".amenity-picker input:checked")].map(i => i.value);
}
function avatarHtml(url, name, size) {
  const style = `width:${size}px;height:${size}px;max-height:none;border-radius:50%;flex:none`;
  const src = safeHttpUrl(url);
  if (src) return `<img class="avatar-img" style="${style};object-fit:cover" src="${escHtml(src)}" alt="">`;
  const initial = escHtml(((name || "K").trim()[0] || "K").toUpperCase());
  return `<div class="avatar-img fallback" style="${style};font-size:${Math.round(size * 0.42)}px">${initial}</div>`;
}
function openLandlordModal(d, backId) {
  const L = d.landlord;
  modal.innerHTML = `<div class="modal-head"><button class="chip" id="lpBack">← Back</button><button class="close" id="close">×</button></div>
 <div class="lp-head">${avatarHtml(L.profile_picture, L.full_name, 92)}<h2 style="margin:10px 0 2px">${escHtml(L.full_name)}</h2>${L.username ? `<div class="muted">@${escHtml(L.username)}</div>` : ""}${L.bio ? `<p class="muted" style="margin:8px 0 0">${escHtml(L.bio)}</p>` : ""}
 <div class="lp-stats"><div><strong>${d.property_count}</strong><small>Properties uploaded</small></div><div><strong>${d.properties.length}</strong><small>Available now</small></div></div></div>
 <div class="lp-list">${d.properties.length ? d.properties.map(p => `<div class="lp-item" data-id="${p.id}"><img src="${escHtml(mediaUrl(p.main_image_url))}" alt=""><div><b>${money(p.price)}</b><span class="muted" style="display:block;font-size:12px">${escHtml(p.property_type)} · ${escHtml(p.area || p.county)}</span></div></div>`).join("") : `<p class="muted" style="text-align:center">No available listings right now.</p>`}</div>`;
  showModal();
  document.getElementById("close").onclick = hideModal;
  document.getElementById("lpBack").onclick = () => backId ? openProperty(backId) : hideModal();
  modal.querySelectorAll(".lp-item").forEach(el => el.onclick = () => openProperty(el.dataset.id));
}

/* ---------------- Ads (real, backed by /ads and /admin/ads) ---------------- */
// Brand loader (from the Keja brand kit): orbiting diamond + opening door.
function loaderHtml(label) {
  return `<div class="keja-loader" role="status" aria-live="polite"><svg width="56" height="56" viewBox="0 0 160 160" aria-hidden="true"><circle class="keja-loader__track" cx="80" cy="80" r="54"/><g class="keja-loader__orbit"><path d="M80 17 91 27 80 37 69 27Z"/></g><path class="keja-loader__home" d="M47 75 80 47 113 75V116H47Z"/><rect class="keja-loader__door" x="62" y="79" width="36" height="37" rx="4"/><circle class="keja-loader__knob" cx="91" cy="98" r="3"/></svg><span>${label || "Finding your space…"}</span></div>`;
}

function escHtml(v) {
  return String(v == null ? "" : v).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function safeHttpUrl(u) { return /^https?:\/\//i.test(u || "") ? u : ""; }

// Fills every <div data-ad-slot="home|interested"> on screen with the active ad
// for that placement. On any failure or when no ad exists, the dashed
// "ADVERTISEMENT" placeholder simply stays.
function hydrateAds() {
  document.querySelectorAll("[data-ad-slot]").forEach(el => {
    const placement = el.dataset.adSlot;
    fetch(API_BASE + "/ads/" + encodeURIComponent(placement)).then(r => r.ok ? r.json() : null).then(d => {
      if (!d || !d.ad || !document.body.contains(el)) return;
      const img = `<img src="${escHtml(safeHttpUrl(d.ad.image_url))}" alt="Advertisement" loading="lazy">`;
      const link = safeHttpUrl(d.ad.link_url);
      el.classList.add("has-ad");
      el.innerHTML = link ? `<a href="${escHtml(link)}" target="_blank" rel="noopener noreferrer sponsored">${img}</a>` : img;
    }).catch(() => {});
  });
}

async function openAdPlacement() {
  const placements = [["home", "Home feed", "Promotional slot under the category buttons"], ["interested", "Interested page", "Slot at the top of the Interested page"]];
  modal.innerHTML = `<div class="modal-head"><h2 style="margin:0">Ad placement</h2><button class="close" id="close">×</button></div>
 <p class="muted">Upload an image for a placement. Uploading makes it the live ad and replaces the previous one. JPG, PNG or WEBP, 5MB max.</p>
 <div class="ad-spec"><strong>Ad size (same for Home and Interested)</strong><br>Ratio <b>4:1</b> (wide banner). Best: <b>1200 × 300 px</b>; minimum 800 × 200. Keep logos and text inside the centre 80% — the edges can be trimmed on narrow screens.</div><div id="adBody"><div class="empty">${loaderHtml()}</div></div>`;
  showModal(); document.getElementById("close").onclick = hideModal;

  async function draw() {
    let ads = [];
    try { ads = (await api("/admin/ads")).ads || []; } catch (e) { toast(e.message); }
    document.getElementById("adBody").innerHTML = placements.map(([key, label, hint]) => {
      const cur = ads.find(a => a.placement === key && a.is_active);
      return `<div class="ad-editor" data-p="${key}"><strong>${label}</strong><small class="muted" style="display:block;margin:2px 0 8px">${hint}</small>
 ${cur ? `<img class="ad-preview" src="${escHtml(safeHttpUrl(cur.image_url))}" alt="Current ${label} ad"><div class="muted" style="font-size:12px;margin:6px 0">Live now${cur.link_url ? " · links to " + escHtml(cur.link_url) : " · no link"}</div>` : `<div class="muted" style="font-size:12px;margin-bottom:6px">No live ad — the placeholder is shown.</div>`}
 <input type="file" accept="image/png,image/jpeg,image/webp" class="ad-file" autocomplete="off"><div class="ad-note muted" style="font-size:12px;margin-top:4px"></div>
 <input type="text" inputmode="url" autocapitalize="none" autocomplete="off" data-lpignore="true" data-form-type="other" name="ad-link-${key}" class="ad-link" placeholder="Website (optional, e.g. bash.co.ke)" value="${cur && cur.link_url ? escHtml(cur.link_url) : ""}" style="width:100%;margin-top:8px">
 <div style="display:flex;gap:8px;margin-top:8px"><button type="button" class="primary ad-upload" style="flex:1">${cur ? "Replace ad" : "Upload ad"}</button>${cur ? `<button type="button" class="chip ad-save-link">Save link</button><button type="button" class="chip ad-off">Turn off</button>` : ""}</div>
 <p class="ad-error" style="font-size:12px;color:#ef4444;margin-top:6px;min-height:14px"></p></div>`;
    }).join("");

    document.querySelectorAll(".ad-editor").forEach(box => {
      const key = box.dataset.p;
      const cur = ads.find(a => a.placement === key && a.is_active);
      const linkVal = () => box.querySelector(".ad-link").value.trim();
      box.querySelector(".ad-file").onchange = (ev) => {
        const f = ev.target.files[0], note = box.querySelector(".ad-note");
        note.textContent = ""; if (!f) return;
        const url = URL.createObjectURL(f), im = new Image();
        im.onload = () => {
          const r = im.width / im.height; URL.revokeObjectURL(url);
          note.textContent = Math.abs(r - 4) / 4 > 0.15
            ? `This image is ${im.width}×${im.height} (${r.toFixed(1)}:1). It will be cropped to fit 4:1 — use 1200×300 for a clean fit.`
            : `${im.width}×${im.height} — good fit ✓`;
        };
        im.src = url;
      };
      box.querySelector(".ad-upload").onclick = async (ev) => {
        const errEl = box.querySelector(".ad-error");
        errEl.textContent = "";
        const f = box.querySelector(".ad-file").files[0];
        if (!f) { errEl.textContent = "Choose an image first — tap \"Choose file\" above, then Upload ad."; return; }
        const fd = new FormData(); fd.append("placement", key); fd.append("file", f); if (linkVal()) fd.append("link_url", linkVal());
        const label = ev.target.textContent;
        ev.target.disabled = true; ev.target.textContent = "Uploading…";
        try {
          await api("/admin/ads", { method: "POST", body: fd });
          toast(`${label === "Replace ad" ? "Replaced" : "Uploaded"} — ${key === "home" ? "Home" : "Interested"} ad is live`);
        } catch (e) {
          errEl.textContent = e.message || "Upload failed — please try again.";
        } finally {
          ev.target.disabled = false; ev.target.textContent = label;
        }
        draw();
      };
      const off = box.querySelector(".ad-off");
      if (off) off.onclick = async () => { try { await api("/admin/ads/" + cur.id, { method: "PATCH", body: JSON.stringify({ is_active: false }) }); toast("Ad turned off"); } catch (e) { toast(e.message); } draw(); };
      const sv = box.querySelector(".ad-save-link");
      if (sv) sv.onclick = async () => { try { await api("/admin/ads/" + cur.id, { method: "PATCH", body: JSON.stringify({ link_url: linkVal() || null }) }); toast("Link saved"); } catch (e) { toast(e.message); } draw(); };
    });
  }
  draw();
}

/* ---------------- Modal / toast / theme plumbing (unchanged) ---------------- */
function showModal() { modalBackdrop.classList.remove("hidden"); document.body.style.overflow = "hidden"; }
function hideModal() { modalBackdrop.classList.add("hidden"); document.body.style.overflow = ""; }
let toastTimer;
function toast(msg) { const el = document.getElementById("toast"); if (!el) { alert(msg); return; } el.textContent = msg; el.classList.add("show"); clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove("show"), 2200); }
function toggleDark() { dark = !dark; document.body.classList.toggle("dark", dark); localStorage.setItem("kejaDark", dark ? "1" : "0"); render(); }

document.getElementById("bellBtn").onclick = () => goto("alerts");
document.querySelector(".avatar").onclick = () => isLoggedIn() ? goto("profile") : openLogin();
modalBackdrop.onclick = e => { if (e.target === modalBackdrop) hideModal(); };
document.addEventListener("keydown", e => { if (e.key === "Escape") hideModal(); });

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  });
}

/* ---------------- Keyboard handling ---------------- */
// Keep the focused field visible when the on-screen keyboard opens, and hide
// the bottom nav while it's up so it can't cover the form.
document.addEventListener("focusin", e => {
  if (e.target.matches && e.target.matches("input,textarea,select")) {
    setTimeout(() => { try { e.target.scrollIntoView({ block: "center", behavior: "smooth" }); } catch (x) {} }, 300);
  }
});
if (window.visualViewport) {
  const vv = window.visualViewport;
  const onVV = () => document.body.classList.toggle("kb-open", vv.height < window.innerHeight * 0.75);
  vv.addEventListener("resize", onVV);
}

/* ---------------- Boot ---------------- */
updateAvatar();
render();
if (isLoggedIn()) refreshCurrentUser().then(() => { if (currentView === "profile" || currentView === "landlord" || currentView === "admin") render(); });
