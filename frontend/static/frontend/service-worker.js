const CACHE_VERSION = "v1";
const MEDIA_CACHE_PREFIX = `redjango-media-${CACHE_VERSION}-`;
const META_CACHE_PREFIX = `redjango-media-meta-${CACHE_VERSION}-`;
const CLIENT_SCOPE_CACHE = `redjango-media-client-scopes-${CACHE_VERSION}`;
const META_REQUEST_PATH = "/__redjango_media_cache__/manifest";
const ACTIVE_CACHE_REQUEST_PATH = "/__redjango_media_cache__/active-package";
const clientScopes = new Map();

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

function validScope(value) {
  return typeof value === "string" && /^user-\d+-campaign-\d+$/.test(value);
}

function cacheName(scope) {
  return `${MEDIA_CACHE_PREFIX}${scope}`;
}

function metaCacheName(scope) {
  return `${META_CACHE_PREFIX}${scope}`;
}

function clientScopeRequest(clientId) {
  return new Request(new URL(`/__redjango_media_cache__/clients/${encodeURIComponent(clientId)}`, self.location.origin));
}

async function saveClientScope(clientId, scope) {
  const cache = await caches.open(CLIENT_SCOPE_CACHE);
  await cache.put(clientScopeRequest(clientId), new Response(scope));
  clientScopes.set(clientId, scope);
}

async function removeClientScope(clientId) {
  clientScopes.delete(clientId);
  const cache = await caches.open(CLIENT_SCOPE_CACHE);
  await cache.delete(clientScopeRequest(clientId));
}

async function scopeForClient(clientId) {
  if (!clientId) return null;
  const inMemory = clientScopes.get(clientId);
  if (validScope(inMemory)) return inMemory;
  const cache = await caches.open(CLIENT_SCOPE_CACHE);
  const response = await cache.match(clientScopeRequest(clientId));
  if (!response) return null;
  const persisted = await response.text();
  if (!validScope(persisted)) {
    await cache.delete(clientScopeRequest(clientId));
    return null;
  }
  clientScopes.set(clientId, persisted);
  return persisted;
}

function isStaticMediaPath(pathname) {
  return [
    "/static/frontend/images/",
    "/static/frontend/audio/",
    "/static/frontend/video/",
    "/static/frontend/fonts/",
  ].some((prefix) => pathname.startsWith(prefix));
}

function isCacheableAssetUrl(value) {
  const url = new URL(value, self.location.origin);
  return url.origin === self.location.origin
    && (url.pathname.startsWith("/media/") || isStaticMediaPath(url.pathname));
}

function isCacheableAssetRequest(request) {
  if (request.method !== "GET") return false;
  return isCacheableAssetUrl(request.url);
}

function requestedByteRange(header, size) {
  const match = /^bytes=(\d*)-(\d*)$/.exec(header || "");
  if (!match) return null;
  const [, rawStart, rawEnd] = match;
  let start;
  let end;
  if (rawStart) {
    start = Number(rawStart);
    end = rawEnd ? Math.min(Number(rawEnd), size - 1) : size - 1;
  } else if (rawEnd) {
    start = Math.max(size - Number(rawEnd), 0);
    end = size - 1;
  } else return null;
  return Number.isInteger(start) && Number.isInteger(end) && start >= 0 && start <= end && start < size
    ? { start, end }
    : null;
}

async function cachedRange(request, scope) {
  const cache = await caches.open(await activeCacheName(scope));
  const cached = await cache.match(request.url, { ignoreVary: true });
  if (!cached) return fetch(request);
  const buffer = await cached.arrayBuffer();
  const range = requestedByteRange(request.headers.get("Range"), buffer.byteLength);
  if (!range) {
    return new Response(null, {
      status: 416,
      headers: { "Content-Range": `bytes */${buffer.byteLength}` },
    });
  }
  const headers = new Headers(cached.headers);
  headers.set("Accept-Ranges", "bytes");
  headers.set("Content-Range", `bytes ${range.start}-${range.end}/${buffer.byteLength}`);
  headers.set("Content-Length", String(range.end - range.start + 1));
  return new Response(buffer.slice(range.start, range.end + 1), { status: 206, headers });
}

function isImmutableResponse(response) {
  return response.status === 200
    && !response.headers.has("Content-Range")
    && response.headers.get("X-ReDjango-Cacheability") === "immutable";
}

function isStorableResponse(response, url) {
  if (response.status !== 200 || response.headers.has("Content-Range")) return false;
  const pathname = new URL(url, self.location.origin).pathname;
  return isStaticMediaPath(pathname) || isImmutableResponse(response);
}

async function cacheFirst(request, scope) {
  const cache = await caches.open(await activeCacheName(scope));
  const cached = await cache.match(request, { ignoreVary: true });
  if (cached) return cached;
  const response = await fetch(request);
  if (isStorableResponse(response, request.url)) await cache.put(request, response.clone());
  return response;
}

self.addEventListener("fetch", (event) => {
  if (!isCacheableAssetRequest(event.request)) return;
  event.respondWith((async () => {
    const scope = await scopeForClient(event.clientId);
    if (!validScope(scope)) return fetch(event.request);
    return event.request.headers.has("Range")
      ? cachedRange(event.request, scope)
      : cacheFirst(event.request, scope);
  })());
});

async function loadRevisions(scope) {
  const cache = await caches.open(metaCacheName(scope));
  const response = await cache.match(META_REQUEST_PATH);
  if (!response) return {};
  try {
    const value = await response.json();
    return value && typeof value === "object" ? value : {};
  } catch {
    return {};
  }
}

async function saveRevisions(scope, revisions) {
  const cache = await caches.open(metaCacheName(scope));
  await cache.put(META_REQUEST_PATH, new Response(JSON.stringify(revisions), {
    headers: { "Content-Type": "application/json" },
  }));
}

function validActiveCacheName(scope, name) {
  return name === cacheName(scope) || name.startsWith(`${cacheName(scope)}-package-`);
}

async function activeCacheName(scope) {
  const cache = await caches.open(metaCacheName(scope));
  const response = await cache.match(ACTIVE_CACHE_REQUEST_PATH);
  const candidate = response ? await response.text() : "";
  return validActiveCacheName(scope, candidate) ? candidate : cacheName(scope);
}

async function saveActiveCacheName(scope, name) {
  if (!validActiveCacheName(scope, name)) throw new Error("Nome cache pacchetto non valido");
  const cache = await caches.open(metaCacheName(scope));
  await cache.put(ACTIVE_CACHE_REQUEST_PATH, new Response(name));
}

function packageCacheName(scope, token) {
  if (!/^[a-z0-9]{16,64}$/.test(token || "")) throw new Error("Identificatore importazione non valido");
  return `${cacheName(scope)}-package-${token}`;
}

async function deleteScopeCaches(scope) {
  const names = await caches.keys();
  const mediaPrefix = `${cacheName(scope)}-package-`;
  await Promise.all(names
    .filter((name) => name === cacheName(scope) || name === metaCacheName(scope) || name.startsWith(mediaPrefix))
    .map((name) => caches.delete(name)));
}

function post(port, payload) {
  if (port) port.postMessage(payload);
}

async function downloadEntries(scope, entries, port) {
  const cache = await caches.open(await activeCacheName(scope));
  const revisions = await loadRevisions(scope);
  const nextRevisions = { ...revisions };
  const totalBytes = entries.reduce((total, entry) => total + Math.max(0, Number(entry.size) || 0), 0);
  let completed = 0;
  let completedBytes = 0;
  let downloaded = 0;
  let skipped = 0;
  let failed = 0;

  for (const entry of entries) {
    const url = new URL(String(entry.url || ""), self.location.origin);
    const valid = isCacheableAssetUrl(url.href);
    const request = valid ? new Request(url.href, { credentials: "same-origin" }) : null;
    const cached = request ? await cache.match(request, { ignoreVary: true }) : null;
    const unchanged = cached && revisions[url.pathname + url.search] === String(entry.revision || "");
    try {
      if (!valid || !request) throw new Error("URL media non valido");
      if (unchanged) {
        skipped += 1;
      } else {
        const response = await fetch(request, { cache: "reload" });
        if (!isStorableResponse(response, url.href)) throw new Error(`Risposta non memorizzabile (${response.status})`);
        await cache.put(request, response.clone());
        nextRevisions[url.pathname + url.search] = String(entry.revision || "");
        downloaded += 1;
      }
    } catch (error) {
      failed += 1;
      delete nextRevisions[url.pathname + url.search];
    }
    completed += 1;
    completedBytes += Math.max(0, Number(entry.size) || 0);
    post(port, {
      type: "progress",
      completed,
      total: entries.length,
      completedBytes,
      totalBytes,
      currentLabel: String(entry.label || entry.url || "Media"),
      downloaded,
      skipped,
      failed,
    });
  }
  await saveRevisions(scope, nextRevisions);
  return { completed, total: entries.length, completedBytes, totalBytes, downloaded, skipped, failed };
}

self.addEventListener("message", (event) => {
  const message = event.data && typeof event.data === "object" ? event.data : {};
  const port = event.ports && event.ports[0];
  const sourceId = event.source && event.source.id;
  event.waitUntil((async () => {
    try {
      if (message.type === "activate") {
        if (!sourceId || !validScope(message.scope)) throw new Error("Scope cache non valido");
        await saveClientScope(sourceId, message.scope);
        post(port, { type: "done", scope: message.scope });
        return;
      }
      if (message.type === "deactivate") {
        if (sourceId) await removeClientScope(sourceId);
        post(port, { type: "done" });
        return;
      }
      const activeScope = await scopeForClient(sourceId);
      const scope = validScope(message.scope) ? message.scope : activeScope;
      if (!validScope(scope)) throw new Error("Cache media non attiva per questo client");
      if (scope !== activeScope) throw new Error("La cache richiesta non appartiene alla sessione attiva");
      if (message.type === "clear") {
        await deleteScopeCaches(scope);
        post(port, { type: "done", cleared: true });
        return;
      }
      if (message.type === "download") {
        const entries = Array.isArray(message.entries) ? message.entries : [];
        const result = await downloadEntries(scope, entries, port);
        post(port, { type: "done", ...result });
        return;
      }
      if (message.type === "importBegin") {
        const stagingName = packageCacheName(scope, String(message.token || ""));
        await caches.delete(stagingName);
        await caches.open(stagingName);
        post(port, { type: "done" });
        return;
      }
      if (message.type === "importEntry") {
        const stagingName = packageCacheName(scope, String(message.token || ""));
        if (!isCacheableAssetUrl(String(message.url || "")) || !(message.blob instanceof Blob)) {
          throw new Error("Voce importata non valida");
        }
        const url = new URL(String(message.url), self.location.origin);
        const cache = await caches.open(stagingName);
        await cache.put(new Request(url.href, { credentials: "same-origin" }), new Response(message.blob, {
          status: 200,
          headers: {
            "Content-Type": String(message.contentType || "application/octet-stream"),
            "Content-Length": String(message.blob.size),
            "Cache-Control": "private, max-age=31536000, immutable",
            "X-ReDjango-Cacheability": "immutable",
          },
        }));
        post(port, { type: "done" });
        return;
      }
      if (message.type === "importAbort") {
        await caches.delete(packageCacheName(scope, String(message.token || "")));
        post(port, { type: "done" });
        return;
      }
      if (message.type === "importCommit") {
        const stagingName = packageCacheName(scope, String(message.token || ""));
        const staging = await caches.open(stagingName);
        const keys = await staging.keys();
        const expectedCount = Number(message.expectedCount);
        const revisions = message.revisions && typeof message.revisions === "object" ? message.revisions : null;
        if (!Number.isInteger(expectedCount) || expectedCount < 0 || keys.length !== expectedCount || !revisions) {
          throw new Error("Pacchetto incompleto: la cache attiva non è stata modificata");
        }
        const previousName = await activeCacheName(scope);
        await saveRevisions(scope, revisions);
        await saveActiveCacheName(scope, stagingName);
        const names = await caches.keys();
        await Promise.all(names
          .filter((name) => validActiveCacheName(scope, name) && name !== stagingName)
          .map((name) => caches.delete(name)));
        if (previousName !== stagingName) await caches.delete(previousName);
        post(port, { type: "done", imported: keys.length });
        return;
      }
      throw new Error("Comando cache sconosciuto");
    } catch (error) {
      post(port, { type: "error", message: error instanceof Error ? error.message : "Errore cache media" });
    }
  })());
});
