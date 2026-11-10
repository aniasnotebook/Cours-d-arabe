// Works offline once opened: the page is fetched fresh when there is a connection, the copy is used otherwise.
const CACHE = "cours-arabe-v158";
const CORE = ["./", "index.html", "manifest.webmanifest", "logo-192.png", "logo-512.png", "logo-touch.png",
  "fonts/Amiri-400-arabic.woff2", "fonts/Amiri-400-latin.woff2", "fonts/Amiri-700-arabic.woff2", "fonts/Amiri-700-latin.woff2", "fonts/NotoNaskhArabic-500-arabic.woff2", "fonts/NotoNaskhArabic-500-latin.woff2", "fonts/NotoNaskhArabic-600-arabic.woff2", "fonts/NotoNaskhArabic-600-latin.woff2"];   // the fonts ship with the app: nothing is asked from Google

self.addEventListener("install", e => {
  // The cells' pictures are saved too, one by one, so lesson 2 also works offline (a missing one never blocks the install).
  const BOOK = [0, 1, 3, 5, 7, 9, 10, 11, 12, 14, 16, 17, 18, 19, 20, 21, 22, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 126].map(i => `book/n/k${i}.png`);
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE).then(() => Promise.all(BOOK.map(u => c.add(u).catch(() => {}))))).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  // Fonts never change: keep the first copy.
  if (url.hostname.endsWith("gstatic.com") || url.hostname.endsWith("googleapis.com")) {
    e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
      if (res.ok || res.type === "opaque") { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
      return res;
    })));
    return;
  }
  if (url.origin !== location.origin) return;
  // The book's pictures never change either: keep the first copy (each one is fetched the first time it shows).
  if (url.pathname.includes("/book/") || url.pathname.includes("/fonts/")) {
    e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
      return res;
    })));
    return;
  }
  // The game itself: newest version when online, saved copy when offline.
  // On a weak connection, the saved copy is used after 4 seconds instead of waiting.
  const net = fetch(req, { cache: "no-cache" }).then(res => {
    if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
    return res;
  });
  const saved = () => caches.match(req).then(hit => hit || caches.match("./"));
  const slow = new Promise(r => setTimeout(r, 4000)).then(() => saved()).then(hit => hit || net);
  e.respondWith(Promise.race([net, slow]).catch(saved));
});
