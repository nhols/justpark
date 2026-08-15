const CACHE_NAME = "lemon-linnet-shell-v1";
const SCOPE_URL = new URL(self.registration.scope);
const PRECACHE_URLS = [
  "./",
  "manifest.webmanifest",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "icons/apple-touch-icon.png",
  "icons/favicon-64.png",
].map((path) => new URL(path, SCOPE_URL).href);

function isDashboardData(url) {
  return url.pathname.startsWith(`${SCOPE_URL.pathname}api/`) || url.pathname.endsWith("/dashboard.json");
}

async function precacheAppShell() {
  const cache = await caches.open(CACHE_NAME);
  const rootUrl = new URL("./", SCOPE_URL);
  const urls = new Set(PRECACHE_URLS);

  try {
    const response = await fetch(rootUrl, { cache: "reload" });
    if (response.ok) {
      await cache.put(rootUrl, response.clone());
      const html = await response.text();
      for (const match of html.matchAll(/\b(?:href|src)="([^"]+)"/g)) {
        const assetUrl = new URL(match[1], rootUrl);
        if (
          assetUrl.origin === self.location.origin &&
          assetUrl.pathname.startsWith(SCOPE_URL.pathname) &&
          !isDashboardData(assetUrl)
        ) {
          urls.add(assetUrl.href);
        }
      }
    }
  } catch {
    // Individual resources below can still be cached when the root is unavailable.
  }

  await Promise.allSettled([...urls].map((url) => cache.add(url)));
}

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    await precacheAppShell();
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const cacheNames = await caches.keys();
    await Promise.all(cacheNames
      .filter((name) => name.startsWith("lemon-linnet-shell-") && name !== CACHE_NAME)
      .map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});

async function networkFirstNavigation(request) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put(request, response.clone());
    return response;
  } catch {
    return (await cache.match(request)) || cache.match(new URL("./", SCOPE_URL));
  }
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  const response = await fetch(request);
  if (response.ok && response.type === "basic") {
    const cache = await caches.open(CACHE_NAME);
    await cache.put(request, response.clone());
  }
  return response;
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin || isDashboardData(url)) return;

  if (request.mode === "navigate") {
    event.respondWith(networkFirstNavigation(request));
    return;
  }

  event.respondWith(cacheFirst(request));
});
