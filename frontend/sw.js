const CACHE_NAME = 'keja-cache-v1';

// Only list assets we are certain exist at the site root. Unlike
// cache.addAll(), which fails the ENTIRE install if a single URL 404s,
// we fetch each one individually and just skip whatever isn't
// available — a missing/renamed file can no longer silently break the
// whole service worker.
const ASSETS = [
  './',
  'index.html',
  'home.html',
  'discover.html',
  'property.html',
  'interested.html',
  'landlord.html',
  'profile.html',
  'manifest.json',
  'api-config.js',
  'keja-app.js',
  'keja.css',
  'kenya-locations.js',
  'home.js',
  'discover.js',
  'property.js',
  'interested.js',
  'landlord.js',
  'profile.js',
  'assets/icon-192.png',
  'assets/icon-512.png',
  'assets/icon-maskable-192.png',
  'assets/icon-maskable-512.png',
  'assets/apple-touch-icon.png',
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      Promise.all(
        ASSETS.map((url) =>
          fetch(url).then((res) => {
            if (res.ok) return cache.put(url, res);
          }).catch(() => {})
        )
      )
    )
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// Network-first for API calls and api-config.js (so a fresh backend URL
// is never stuck stale behind the cache); cache-first for everything
// else (fast repeat loads, works offline for pages already visited).
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  const isApiConfig = url.pathname.endsWith('api-config.js');

  if (isApiConfig || url.pathname.includes('/properties') || url.pathname.includes('/contact-unlock') || url.pathname.includes('/users') || url.pathname.includes('/login') || url.pathname.includes('/register')) {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(event.request))
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      return (
        cached ||
        fetch(event.request).then((res) => {
          if (res.ok && event.request.method === 'GET') {
            const clone = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return res;
        })
      );
    })
  );
});
