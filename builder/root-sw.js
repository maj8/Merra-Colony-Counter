// colony.merra.org/sw.js: retires the offline copy installed by v1.0-v1.1, when the counter
// lived at the site root. The counter now lives at /counter/ with its own service worker.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (/^merra-colony-counter-v1\.[01]\./.test(k)) await caches.delete(k);
    await self.registration.unregister();
  })());
});
