// EX20v Ağ Kontrol Merkezi — service worker (çevrimdışı açılış)
const CACHE = 'ex20v-v1.0.0';
const CORE = ['./', 'index.html', 'manifest.json', 'icons/icon-192.png', 'icons/icon-512.png', 'icons/apple-touch-icon.png'];
const CDN = ['cdn.tailwindcss.com', 'cdn.jsdelivr.net', 'unpkg.com'];

self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  // Ölçüm ve ajan istekleri asla önbelleğe alınmaz
  if (u.hostname === 'speed.cloudflare.com' || u.pathname.startsWith('/api/')) return;
  if (CDN.includes(u.hostname)) {
    // CDN: önbellekten ver, arka planda güncelle
    e.respondWith(caches.open(CACHE).then(async c => {
      const hit = await c.match(e.request);
      const net = fetch(e.request).then(r => { if (r.ok || r.type === 'opaque') c.put(e.request, r.clone()); return r; }).catch(() => hit);
      return hit || net;
    }));
    return;
  }
  if (u.origin === location.origin) {
    // Uygulama dosyaları: önce ağ (yeni sürüm hemen gelsin), yoksa önbellek
    e.respondWith(fetch(e.request).then(r => {
      if (r.ok) { const cl = r.clone(); caches.open(CACHE).then(c => c.put(e.request, cl)); }
      return r;
    }).catch(() => caches.match(e.request).then(r => r || caches.match('index.html'))));
  }
});
