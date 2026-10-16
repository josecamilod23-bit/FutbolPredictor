
const CACHE = "futbolpredictor-v1";
self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE).then(cache => cache.add("/"))
  );
  self.skipWaiting();
});
self.addEventListener("activate", event => {
  event.waitUntil(self.clients.claim());
});
self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  event.respondWith(
    fetch(event.request).then(response => {
      if (response.ok && url.pathname === "/") {
        const copy = response.clone();
        caches.open(CACHE).then(cache => cache.put("/", copy));
      }
      return response;
    }).catch(() => caches.match(event.request))
  );
});
