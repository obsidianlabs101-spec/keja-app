const CACHE_NAME = "keja-cache-v12";

// This is a single-page app — index.html, style.css and app.js ARE the
// entire site. Each asset is fetched and cached individually rather than
// via cache.addAll() so one missing/renamed file can't fail the whole
// install silently.
const ASSETS = [
  "./",
  "index.html",
  "style.css",
  "app.js",
  "kenya-locations.js",
  "manifest.json",
  "assets/icon-192.png",
  "assets/icon-512.png",
  "assets/icon-maskable-192.png",
  "assets/icon-maskable-512.png",
  "assets/apple-touch-icon.png",
  "assets/keja-logo.svg",
  "assets/keja-logo-white.svg",
  "assets/favicon.svg",
];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      Promise.all(
        ASSETS.map((url) =>
          fetch(url)
            .then((res) => { if (res.ok) return cache.put(url, res); })
            .catch(() => {})
        )
      )
    )
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  const sameOrigin = url.origin === self.location.origin;
  const isImage = event.request.destination === "image";

  // Cache same-origin app-shell assets AND any image response — property
  // photos live on other origins entirely (the backend, Supabase
  // Storage), and a same-origin-only rule was silently never caching
  // them at all. Everything else cross-origin (API calls) still always
  // goes straight to the network.
  if (!sameOrigin && !isImage) return;

  // App shell (html/js/css/etc.): network-first, so a new deploy shows up on
  // the very next load instead of one visit later. Falls back to the cache
  // only when offline. Images stay cache-first (they never change per URL).
  if (!isImage) {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          if (res.ok) {
            const clone = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return res;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      const network = fetch(event.request)
        .then((res) => {
          if (res.ok) {
            const clone = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return res;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
