// Service Worker for offline support and PWA
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open('scanner-cache').then(cache => {
            return cache.addAll([
                '/',
                '/index.html',
                '/style.css',
                '/script.js',
                '/manifest.json'
            ]);
        })
    );
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request).then(response => {
            return response || fetch(event.request);
        })
    );
});
