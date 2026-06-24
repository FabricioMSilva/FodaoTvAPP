const CACHE_NAME = 'fodao-player-v7';
const APP_SHELL = [
  '/index.html',
  '/player.html',
  '/style.css',
  '/app.js',
  '/player.js',
  '/register-sw.js',
  '/manifest.webmanifest',
  '/version.json',
  '/Logo.png',
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys
    .filter(key => key !== CACHE_NAME)
    .map(key => caches.delete(key)))));
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request)));
});
