/* ============================================================
 * Keja app.js — same UI/markup/CSS as provided, wired to the real
 * FastAPI backend instead of the fake in-memory `properties` array.
 * No visual/design changes were made here — only behavior.
 * ============================================================ */

const API_BASE = "https://keja-backend-uqzk.onrender.com";
const MPESA_TILL = { till: "4396353", name: "Keja Kenya", amount: 50 };

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

function updateAvatar() {
  const el = document.querySelector(".avatar");
  if (!el) return;
  if (currentUser && (currentUser.name || currentUser.username)) {
    el.textContent = (currentUser.name || currentUser.username).trim().slice(0, 2).toUpperCase();
  } else {
    el.textContent = "SM";
  }
}

/* ---------------- Render dispatch ---------------- */
function render() {
  document.querySelectorAll(".nav-item").forEach(x => x.classList.toggle("active", x.dataset.view === currentView));
  if (currentView === "home") home();
  if (currentView === "discover") discover();
  if (currentView === "interested") interestedPage();
  if (currentView === "profile") profile();
  if (currentView === "landlord") landlord();
  if (currentView === "admin") admin();
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
 <div class="ad">ADVERTISEMENT</div>
 <div class="section-head"><h2>Popular around Nairobi</h2></div><div class="chips"><button class="chip" data-area="Kilimani">Kilimani</button><button class="chip" data-area="Westlands">Westlands</button><button class="chip" data-area="Roysambu">Roysambu</button><button class="chip" data-area="Kasarani">Kasarani</button><button class="chip" data-area="Kahawa">Kahawa</button></div>
 <div class="section-head"><h2>Recommended for you</h2><button class="chip" id="discoverBtn">See all</button></div><div class="grid" id="homeGrid"><div class="empty" style="grid-column:1/-1">Loading…</div></div>`;

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
 <div class="grid" id="catGrid"><div class="empty" style="grid-column:1/-1">Loading…</div></div>`;
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
 <div class="discover-scroll vertical" id="discoverScroll"><div class="empty" style="width:100%">Loading…</div></div>
 <div class="swipe-hint">Scroll up or down to browse the next property</div><div class="ad">ADVERTISEMENT</div></section>`;

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
  app.innerHTML = `<section class="hero"><div class="eyebrow">YOUR SAVED PLACES</div><h1>Interested</h1><p>Properties you've saved.</p></section><div id="interestedBody"><div class="empty">Loading…</div></div>`;
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
 <div class="grid" id="landlordGrid"><div class="empty" style="grid-column:1/-1">Loading…</div></div>`;
  document.getElementById("backBtn").onclick = () => goto("discover");
  if (!landlordId) return;
  api(`/properties/landlord/${landlordId}`).then(data => {
    const nameEl = document.getElementById("landlordName");
    if (nameEl) nameEl.textContent = data.landlord.full_name || data.landlord.username || "Landlord";
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
 <div class="stats" id="landlordStats"><div class="stat">Active listings<strong>…</strong></div><div class="stat">Property views<strong>…</strong></div><div class="stat">Interested<strong>…</strong></div><div class="stat">Contact unlocks<strong>…</strong></div></div>
 <div class="section-head"><h2>Your listings</h2><span class="muted" id="listingCount"></span></div>
 <div class="table-card"><table class="table"><thead><tr><th>Property</th><th>Price</th><th>Proximity</th><th>Status</th><th></th></tr></thead><tbody id="listingsBody"><tr><td colspan="5">Loading…</td></tr></tbody></table></div>
 </section>`;
  document.getElementById("addProperty").onclick = openAdd;

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

function loadLandlordListings() {
  api("/properties/mine").then(list => {
    const body = document.getElementById("listingsBody");
    const count = document.getElementById("listingCount");
    if (!body) return;
    if (count) count.textContent = list.length + " active";
    body.innerHTML = list.length ? list.map(p => `<tr data-id="${p.id}"><td><img class="mini-img" src="${mediaUrl(p.main_image_url)}">${p.property_type}<br><span class="muted">${p.area || p.county}</span></td><td>${money(p.price)}</td><td>${p.proximity_note || "—"}</td><td><span class="status ${p.is_booked ? "booked" : "available"}">${p.is_booked ? "Booked" : "Available"}</span></td><td><button class="chip toggleBookedBtn">${p.is_booked ? "Mark available" : "Mark booked"}</button></td></tr>`).join("") : `<tr><td colspan="5">No listings yet — add your first property.</td></tr>`;
    body.querySelectorAll("tr[data-id]").forEach(row => {
      const id = row.dataset.id;
      const btn = row.querySelector(".toggleBookedBtn");
      if (btn) btn.onclick = async () => {
        const wantBooked = btn.textContent.trim() === "Mark booked";
        try { await api(`/properties/${id}`, { method: "PATCH", body: JSON.stringify({ is_booked: wantBooked }) }); loadLandlordListings(); }
        catch (e) { toast(e.message || "Couldn't update"); }
      };
    });
  }).catch(() => {
    const body = document.getElementById("listingsBody");
    if (body) body.innerHTML = `<tr><td colspan="5">Couldn't load your listings.</td></tr>`;
  });
}

/* ---------------- Admin dashboard ---------------- */
function admin() {
  if (!isLoggedIn() || !currentUser || !currentUser.is_admin) { requireCapability(false, "Admin", "admin"); return; }

  app.innerHTML = `<section class="dashboard"><div class="dash-top"><div><div class="eyebrow">KEJA ADMIN</div><h1>Admin dashboard</h1></div><span class="tag">ADMIN</span></div>
 <div class="stats" id="adminStats"><div class="stat">Total properties<strong>…</strong></div><div class="stat">Active landlords<strong>…</strong></div><div class="stat">Total users<strong>…</strong></div><div class="stat">Pending verifications<strong>…</strong></div></div>
 <div class="section-head"><h2>Ad placement</h2><button class="chip" id="adPlacementBtn">Manage ads</button></div>
 <div class="panel"><p class="muted">Create and manage ad slots shown across Home and Discover.</p><div class="ad-placement-row"><div><strong>Home feed</strong><small>Bottom promotional slot</small></div><span class="status available">Active</span></div><div class="ad-placement-row"><div><strong>Discover</strong><small>Between property cards</small></div><span class="status available">Active</span></div></div>
 <div class="section-head"><h2>Recent listings</h2></div><div class="table-card"><table class="table"><thead><tr><th>Property</th><th>Price</th><th>Location</th></tr></thead><tbody id="adminListingsBody"><tr><td colspan="3">Loading…</td></tr></tbody></table></div></section>`;

  document.getElementById("adPlacementBtn").onclick = openAdPlacement;

  api("/admin/platform-stats").then(s => {
    const el = document.getElementById("adminStats");
    if (!el) return;
    el.innerHTML = `<div class="stat">Total properties<strong>${s.total_properties}</strong></div><div class="stat">Active landlords<strong>${s.active_landlords}</strong></div><div class="stat">Total users<strong>${s.total_users}</strong></div><div class="stat">Pending verifications<strong>${s.pending_verifications}</strong></div>`;
  }).catch(() => {});

  api("/properties/?limit=20").then(list => {
    const body = document.getElementById("adminListingsBody");
    if (!body) return;
    body.innerHTML = list.length ? list.map(p => `<tr><td><img class="mini-img" src="${mediaUrl(p.main_image_url)}">${p.property_type}</td><td>${money(p.price)}</td><td>${p.area || p.county}</td></tr>`).join("") : `<tr><td colspan="3">No listings yet</td></tr>`;
  }).catch(() => {
    const body = document.getElementById("adminListingsBody");
    if (body) body.innerHTML = `<tr><td colspan="3">Couldn't load listings</td></tr>`;
  });
}

/* ---------------- Property modal (view + Get Contact) ---------------- */
function openProperty(id) {
  modal.innerHTML = `<div class="modal-head"><h2 style="margin:0">Loading…</h2><button class="close" id="close">×</button></div>`;
  showModal();
  document.getElementById("close").onclick = hideModal;

  api(`/properties/${id}`).then(p => {
    modal.innerHTML = `<div class="modal-head"><h2 style="margin:0">${p.property_type}</h2><button class="close" id="close">×</button></div>
 <img src="${mediaUrl(p.main_image_url)}" alt=""><div style="padding-top:15px"><div class="price">${money(p.price)} <span class="muted" style="font-size:12px">/ month</span></div><p><strong>${p.area || p.county}</strong>${p.proximity_note ? " · " + p.proximity_note : ""}</p><p class="muted">${p.description || ""}</p>
 <div id="contactArea"><button class="primary" style="width:100%;margin-top:8px" id="contactBtn">${p.is_booked ? "This property is booked" : "Get contact"}</button><p class="muted" style="font-size:11px;text-align:center">A KES 50 payment is matched first. The landlord's WhatsApp number is revealed after successful confirmation.</p></div></div>`;
    document.getElementById("close").onclick = hideModal;
    const contactBtn = document.getElementById("contactBtn");
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
    area.innerHTML = `<p class="muted" style="text-align:center">We're verifying your M-Pesa payment — check back shortly.</p><button class="chip" id="resendBtn" style="width:100%">Resend payment code</button>`;
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
  if (canEarnFree) document.getElementById("shareBtn").onclick = shareReferralLink;
  document.getElementById("payBtn").onclick = () => renderContactClaimForm(propertyId, status);
}

function renderContactClaimForm(propertyId, status) {
  const area = document.getElementById("contactArea");
  if (!area) return;
  const canGoBack = isLoggedIn() && currentUser && !currentUser.referral_bonus_granted;
  area.innerHTML = `${canGoBack ? `<button class="chip" id="backToChoiceBtn" style="margin-bottom:10px">← Back</button>` : ""}
 <div class="ad" style="text-align:left;padding:14px;font-size:12.5px">Go to M-Pesa → Lipa na M-Pesa → Buy Goods and Services<br>Till Number: <b>${MPESA_TILL.till}</b> (${MPESA_TILL.name})<br>Amount: <b>KES ${MPESA_TILL.amount}</b></div>
 <label class="field" style="margin-top:10px"><span>Paste the M-Pesa confirmation SMS (or just the code)</span><textarea id="claimText" rows="3" placeholder="e.g. QGH7XXXXX Confirmed. Ksh50.00 sent..."></textarea></label>
 <p class="muted" id="claimError" style="font-size:12px;min-height:14px"></p>
 <button class="primary" style="width:100%" id="submitClaimBtn">I've paid — verify my code</button>`;
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
 <label class="field"><span>Price (KES)</span><input id="addPrice" type="number" placeholder="15000"></label><label class="field"><span>Location</span><input id="addLocation" placeholder="Kilimani"></label><label class="field"><span>Nearby landmark</span><input id="addLandmark" placeholder="10 min from Yaya"></label><label class="field full"><span>Description</span><textarea id="addDesc" rows="4" placeholder="Tell renters about the property"></textarea></label><label class="field full"><span>Property images</span><input id="addImages" type="file" multiple accept="image/*"></label>
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
 <p class="muted" id="becomeError" style="font-size:12px;min-height:14px"></p>
 <button class="primary" style="width:100%" id="becomeSubmit">Submit for review</button>`;
  showModal();
  document.getElementById("close").onclick = hideModal;
  document.getElementById("becomeSubmit").onclick = async () => {
    const btn = document.getElementById("becomeSubmit");
    btn.disabled = true; btn.textContent = "Submitting…";
    try {
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
    modal.innerHTML = `<div class="auth-card"><div class="auth-brand">keja<span>.</span></div><button class="close" id="close">×</button>
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

/* ---------------- Ad placement (demo — no backend ad system yet) ---------------- */
function openAdPlacement() {
  modal.innerHTML = `<div class="modal-head"><h2 style="margin:0">Ad placement</h2><button class="close" id="close">×</button></div>
 <p class="muted">Control where advertisements appear and what type of placement is used.</p>
 <div class="ad-setting"><strong>Home feed</strong><label><input type="checkbox" checked> Enabled</label><select><option>Bottom of feed</option><option>After recommended</option></select></div>
 <div class="ad-setting"><strong>Discover feed</strong><label><input type="checkbox" checked> Enabled</label><select><option>Between cards</option><option>After 3 cards</option></select></div>
 <div class="ad-setting"><strong>Property profile</strong><label><input type="checkbox"> Enabled</label><select><option>Below property details</option></select></div>
 <button class="primary" style="width:100%;margin-top:14px" id="saveAds">Save placements</button>`;
  showModal(); document.getElementById("close").onclick = hideModal;
  document.getElementById("saveAds").onclick = () => { hideModal(); toast("Ad placement settings saved (demo — not yet backed by a real ad system)"); };
}

/* ---------------- Modal / toast / theme plumbing (unchanged) ---------------- */
function showModal() { modalBackdrop.classList.remove("hidden"); document.body.style.overflow = "hidden"; }
function hideModal() { modalBackdrop.classList.add("hidden"); document.body.style.overflow = ""; }
let toastTimer;
function toast(msg) { const el = document.getElementById("toast"); if (!el) { alert(msg); return; } el.textContent = msg; el.classList.add("show"); clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove("show"), 2200); }
function toggleDark() { dark = !dark; document.body.classList.toggle("dark", dark); localStorage.setItem("kejaDark", dark ? "1" : "0"); render(); }

document.querySelectorAll(".nav-item").forEach(x => x.onclick = () => goto(x.dataset.view));
document.querySelector(".avatar").onclick = () => isLoggedIn() ? goto("profile") : openLogin();
modalBackdrop.onclick = e => { if (e.target === modalBackdrop) hideModal(); };
document.addEventListener("keydown", e => { if (e.key === "Escape") hideModal(); });

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  });
}

/* ---------------- Boot ---------------- */
updateAvatar();
render();
if (isLoggedIn()) refreshCurrentUser().then(() => { if (currentView === "profile" || currentView === "landlord" || currentView === "admin") render(); });
