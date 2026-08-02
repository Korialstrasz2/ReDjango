import { getData } from "./api";

export type MediaCacheEntry = {
  url: string;
  revision: string;
  size: number;
  kind: "image" | "thumbnail" | "audio" | "video" | "map_tile";
  label: string;
};

export type MediaCacheManifest = {
  scope: string;
  campaign: { id: number; name: string } | null;
  entries: MediaCacheEntry[];
  totalBytes: number;
};

export type MediaCacheProgress = {
  completed: number;
  total: number;
  completedBytes: number;
  totalBytes: number;
  currentLabel: string;
  downloaded: number;
  skipped: number;
  failed: number;
};

export type MediaCacheDownloadResult = Omit<MediaCacheProgress, "currentLabel">;

export type MediaStorageStatus = {
  supported: boolean;
  secure: boolean;
  usage: number | null;
  quota: number | null;
  persisted: boolean | null;
};

let registrationPromise: Promise<ServiceWorkerRegistration> | null = null;

export function mediaCacheSupported(): boolean {
  return typeof window !== "undefined"
    && window.isSecureContext
    && "serviceWorker" in navigator
    && "caches" in window;
}

async function registration(): Promise<ServiceWorkerRegistration> {
  if (!mediaCacheSupported()) throw new Error("La cache persistente richiede HTTPS o localhost e un browser compatibile.");
  registrationPromise ||= navigator.serviceWorker.register("/service-worker.js", { scope: "/" })
    .then(async (value) => {
      await navigator.serviceWorker.ready;
      return value;
    })
    .catch((error) => {
      registrationPromise = null;
      throw error;
    });
  return registrationPromise;
}

async function activeWorker(): Promise<ServiceWorker> {
  const current = await registration();
  const worker = current.active || current.waiting || current.installing;
  if (!worker) throw new Error("Il servizio cache non è ancora pronto.");
  if (worker.state === "activated") return worker;
  await new Promise<void>((resolve, reject) => {
    const timeout = window.setTimeout(() => reject(new Error("Avvio della cache scaduto.")), 10_000);
    worker.addEventListener("statechange", () => {
      if (worker.state === "activated") {
        window.clearTimeout(timeout);
        resolve();
      }
    });
  });
  return worker;
}

function sendMessage<T>(
  message: Record<string, unknown>,
  onProgress?: (progress: MediaCacheProgress) => void,
): Promise<T> {
  return activeWorker().then((worker) => new Promise<T>((resolve, reject) => {
    const channel = new MessageChannel();
    channel.port1.onmessage = (event: MessageEvent<Record<string, unknown>>) => {
      const payload = event.data || {};
      if (payload.type === "progress") {
        onProgress?.(payload as unknown as MediaCacheProgress);
        return;
      }
      channel.port1.close();
      if (payload.type === "error") reject(new Error(String(payload.message || "Errore cache media.")));
      else resolve(payload as T);
    };
    worker.postMessage(message, [channel.port2]);
  }));
}

export function getMediaCacheManifest(): Promise<MediaCacheManifest> {
  return getData<MediaCacheManifest>("/api/media/cache-manifest/");
}

export async function activateMediaCache(userId: number, campaignId: number | null): Promise<string> {
  const scope = `user-${userId}-campaign-${campaignId || 0}`;
  await sendMessage({ type: "activate", scope });
  return scope;
}

export async function deactivateMediaCache(): Promise<void> {
  if (!mediaCacheSupported()) return;
  const existing = await navigator.serviceWorker.getRegistration("/");
  const worker = existing?.active || existing?.waiting;
  if (!worker) return;
  await new Promise<void>((resolve) => {
    const channel = new MessageChannel();
    const timeout = window.setTimeout(resolve, 1_500);
    channel.port1.onmessage = () => {
      window.clearTimeout(timeout);
      channel.port1.close();
      resolve();
    };
    worker.postMessage({ type: "deactivate" }, [channel.port2]);
  });
}

export async function downloadMediaCache(
  manifest: MediaCacheManifest,
  onProgress: (progress: MediaCacheProgress) => void,
): Promise<MediaCacheDownloadResult> {
  return sendMessage<MediaCacheDownloadResult>(
    { type: "download", scope: manifest.scope, entries: manifest.entries },
    onProgress,
  );
}

export async function clearMediaCache(scope: string): Promise<void> {
  await sendMessage({ type: "clear", scope });
}

export async function mediaStorageStatus(): Promise<MediaStorageStatus> {
  const supported = mediaCacheSupported();
  if (!supported || !navigator.storage) {
    return { supported, secure: window.isSecureContext, usage: null, quota: null, persisted: null };
  }
  const [estimate, persisted] = await Promise.all([
    navigator.storage.estimate(),
    navigator.storage.persisted ? navigator.storage.persisted() : Promise.resolve(null),
  ]);
  return {
    supported,
    secure: window.isSecureContext,
    usage: typeof estimate.usage === "number" ? estimate.usage : null,
    quota: typeof estimate.quota === "number" ? estimate.quota : null,
    persisted,
  };
}

export async function requestPersistentMediaStorage(): Promise<boolean> {
  if (!mediaCacheSupported() || !navigator.storage?.persist) return false;
  return navigator.storage.persist();
}
