"use strict";
// Cache ONLY this public offline page and public icons. Never store app HTML,
// API responses, credentials, journal/mood/chat records, or submitted requests.
const PUBLIC_CACHE = "enwen-public-offline-v1";
const OFFLINE_PAGE = "/static/offline.html";
const PUBLIC_ASSETS = [OFFLINE_PAGE, "/static/icons/enwen-192.png", "/static/icons/enwen-512.png", "/static/icons/enwen-180.png"];
self.addEventListener("install", event => {
  event.waitUntil(caches.open(PUBLIC_CACHE).then(cache => cache.addAll(PUBLIC_ASSETS)));
  // Do not force a waiting update into a page with an unsaved draft.
});
self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    for (const name of await caches.keys()) {
      if (name.startsWith("enwen-public-offline-") && name !== PUBLIC_CACHE) await caches.delete(name);
    }
    await self.clients.claim();
  })());
});
const offlineResponse = () => caches.open(PUBLIC_CACHE).then(cache => cache.match(OFFLINE_PAGE));
self.addEventListener("fetch", event => {
  const request = event.request, url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(async () => (await offlineResponse()) || new Response(
      "ENWEN cannot be reached. No action or notification was sent. Please reconnect or restart the local server.",
      {status:503, headers:{"Content-Type":"text/plain; charset=utf-8"}}
    )));
  } else if (!url.search && PUBLIC_ASSETS.includes(url.pathname)) {
    event.respondWith(fetch(request).catch(() => caches.open(PUBLIC_CACHE).then(cache => cache.match(request))));
  }
});
