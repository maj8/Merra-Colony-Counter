// Offline support. App files: network first (so updates arrive), cached copy when offline.
// Survey images: cached on install and served from the cache.
const VERSION = 'v1.2.0';   // the app's version: change it for every release (installed copies update when it changes)
const SHELL = ['./', 'index.html', 'styles.css', 'app.js', 'manifest.json', 'about.html',
  'icons/merra-192.png', 'icons/merra-512.png', 'icons/merra-maskable-192.png', 'icons/merra-maskable-512.png',
  'icons/merra-favicon-64.png', 'icons/merra-apple-touch-180.png'];

const CACHE = 'merra-colony-counter-' + VERSION;

try { importScripts('survey/survey.js'); } catch (e) { /* no survey: own-images mode */ }

self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const c = await caches.open(CACHE);
    await c.addAll(SHELL);
    await c.add('survey/survey.js').catch(() => {});
    const imgs = (self.SURVEY && self.SURVEY.images) || [];
    // cache survey images one by one so a single failure doesn't block the rest
    for (const it of imgs) await c.add('survey/images/' + encodeURIComponent(it.file)).catch(() => {});
    await self.skipWaiting();
  })());
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  if (url.origin !== location.origin) return;
  const isImage = url.pathname.includes('/survey/images/') || /\.(png|jpe?g)$/i.test(url.pathname);
  if (isImage) {
    e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request).then((r) => {
      if (r.ok) { const copy = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); }
      return r;
    })));
  } else {
    e.respondWith(fetch(e.request).then((r) => {
      if (r.ok) { const copy = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); }
      return r;
    }).catch(() => caches.match(e.request, { ignoreSearch: true })));
  }
});
