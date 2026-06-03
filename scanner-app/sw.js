// Service Worker for offline support (PWA shell caching).
// Bump CACHE_VERSION whenever the cached assets change to force an update.
const CACHE_VERSION = 'scanner-cache-v4';

// Only the static app shell. Note: paths are relative so this works whether the
// app is served from the domain root or a sub-path. API calls are never cached.
const APP_SHELL = [
    './',
    './index.html',
    './style.css',
    './app.js',
    './manifest.json',
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_VERSION).then((cache) => cache.addAll(APP_SHELL))
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    // Drop old cache versions.
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    const { request } = event;

    // Never intercept non-GET or cross-origin (API / CDN) requests — let them hit
    // the network so scans, logins and pushes always reach the backend.
    if (request.method !== 'GET' || new URL(request.url).origin !== self.location.origin) {
        return;
    }

    event.respondWith(
        caches.match(request).then((cached) => cached || fetch(request))
    );
});
