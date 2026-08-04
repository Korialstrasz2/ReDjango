import { apiRequest, getData } from "./api";

export type MediaCacheEntry = {
  url: string;
  cacheKey: string;
  revision: string;
  size: number;
  kind: "image" | "thumbnail" | "audio" | "video" | "map_tile" | "static_media";
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

export type MediaPackageImportResult = {
  imported: number;
  totalBytes: number;
  campaignName: string;
};

type PortableMediaFile = MediaCacheEntry & {
  archivePath: string;
  sha256: string;
  contentType: string;
};

type PortableMediaPackage = {
  format: "redjango-media-package";
  version: 1;
  payload: {
    campaign: { id: number; name: string };
    createdAt: string;
    files: PortableMediaFile[];
    totalBytes: number;
  };
  signature: { algorithm: "hmac-sha256"; value: string };
};

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

const ZIP_LOCAL_FILE = 0x04034b50;
const ZIP_CENTRAL_FILE = 0x02014b50;
const ZIP_END = 0x06054b50;
const PACKAGE_MANIFEST = "redjango-media-package.json";

type StoredZipEntry = {
  name: string;
  blob: Blob;
  nextOffset: number;
};

async function storedZipEntry(file: File, offset: number): Promise<StoredZipEntry | null> {
  const prefix = await file.slice(offset, offset + 30).arrayBuffer();
  if (prefix.byteLength < 4) throw new Error("Archivio ZIP troncato.");
  const view = new DataView(prefix);
  const signature = view.getUint32(0, true);
  if (signature === ZIP_CENTRAL_FILE || signature === ZIP_END) return null;
  if (signature !== ZIP_LOCAL_FILE || prefix.byteLength < 30) throw new Error("Struttura ZIP non riconosciuta.");
  const flags = view.getUint16(6, true);
  const compression = view.getUint16(8, true);
  const compressedSize = view.getUint32(18, true);
  const uncompressedSize = view.getUint32(22, true);
  const nameLength = view.getUint16(26, true);
  const extraLength = view.getUint16(28, true);
  if (flags & 0x1) throw new Error("I pacchetti ZIP cifrati non sono supportati.");
  if (flags & 0x8) throw new Error("Il pacchetto usa descrittori ZIP non supportati.");
  if (compression !== 0) throw new Error("Il pacchetto deve usare file ZIP non compressi.");
  if (compressedSize === 0xffffffff || uncompressedSize === 0xffffffff) {
    throw new Error("Un singolo file del pacchetto supera il limite ZIP supportato dal browser.");
  }
  if (compressedSize !== uncompressedSize) throw new Error("Dimensioni ZIP incoerenti.");
  const nameStart = offset + 30;
  const dataStart = nameStart + nameLength + extraLength;
  const dataEnd = dataStart + compressedSize;
  if (dataEnd > file.size) throw new Error("Archivio ZIP incompleto.");
  const nameBytes = await file.slice(nameStart, nameStart + nameLength).arrayBuffer();
  const name = new TextDecoder("utf-8", { fatal: true }).decode(nameBytes);
  return { name, blob: file.slice(dataStart, dataEnd), nextOffset: dataEnd };
}

async function sha256(blob: Blob): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", await blob.arrayBuffer());
  return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
}

function portablePackage(value: unknown): PortableMediaPackage {
  const document = value as Partial<PortableMediaPackage> | null;
  if (!document || document.format !== "redjango-media-package" || document.version !== 1) {
    throw new Error("Questo non è un pacchetto media ReDjango supportato.");
  }
  if (!document.payload || !Array.isArray(document.payload.files) || !document.signature) {
    throw new Error("Manifest del pacchetto incompleto.");
  }
  return document as PortableMediaPackage;
}

export async function importMediaCachePackage(
  file: File,
  onProgress: (progress: MediaCacheProgress) => void,
): Promise<MediaPackageImportResult> {
  if (!mediaCacheSupported()) throw new Error("L'importazione richiede HTTPS o localhost e un browser compatibile.");
  let offset = 0;
  const manifestEntry = await storedZipEntry(file, offset);
  if (!manifestEntry || manifestEntry.name !== PACKAGE_MANIFEST || manifestEntry.blob.size > 10 * 1024 * 1024) {
    throw new Error("Manifest ReDjango mancante o troppo grande.");
  }
  offset = manifestEntry.nextOffset;
  const document = portablePackage(JSON.parse(await manifestEntry.blob.text()));
  const verification = await apiRequest<{
    scope: string;
    campaign: { id: number; name: string };
    files: Array<{ archivePath: string; url: string; revision: string }>;
    totalBytes: number;
  }>("/api/media/cache-package/verify/", {
    method: "POST",
    body: JSON.stringify({ package: document }),
  });
  const verified = verification.data;
  if (verified.files.length !== document.payload.files.length || verified.totalBytes !== document.payload.totalBytes) {
    throw new Error("La verifica del server non corrisponde al pacchetto.");
  }

  const storage = await mediaStorageStatus();
  if (storage.quota !== null && storage.usage !== null && document.payload.totalBytes > storage.quota - storage.usage) {
    throw new Error("Spazio browser insufficiente per importare il pacchetto in sicurezza. Svuota la vecchia cache o libera spazio.");
  }

  await sendMessage({ type: "activate", scope: verified.scope });
  const token = crypto.randomUUID().replaceAll("-", "").toLowerCase();
  await sendMessage({ type: "importBegin", scope: verified.scope, token });
  const resolved = new Map(verified.files.map((entry) => [entry.archivePath, entry]));
  const expected = new Map(document.payload.files.map((entry) => {
    const current = resolved.get(entry.archivePath);
    if (!current) throw new Error(`Il server non ha risolto ${entry.archivePath}.`);
    return [entry.archivePath, { ...entry, url: current.url, revision: current.revision }];
  }));
  const revisions: Record<string, string> = {};
  const seen = new Set<string>();
  let completed = 0;
  let completedBytes = 0;
  try {
    while (true) {
      const zipEntry = await storedZipEntry(file, offset);
      if (!zipEntry) break;
      offset = zipEntry.nextOffset;
      const entry = expected.get(zipEntry.name);
      if (!entry || seen.has(zipEntry.name)) throw new Error(`File ZIP inatteso o duplicato: ${zipEntry.name}`);
      if (zipEntry.blob.size !== entry.size) throw new Error(`Dimensione non valida: ${entry.label}`);
      const digest = await sha256(zipEntry.blob);
      if (digest !== entry.sha256) throw new Error(`Controllo integrità fallito: ${entry.label}`);
      await sendMessage({
        type: "importEntry",
        scope: verified.scope,
        token,
        url: entry.url,
        contentType: entry.contentType,
        blob: zipEntry.blob,
      });
      const normalized = new URL(entry.url, window.location.origin);
      revisions[normalized.pathname + normalized.search] = entry.revision;
      seen.add(zipEntry.name);
      completed += 1;
      completedBytes += entry.size;
      onProgress({
        completed,
        total: document.payload.files.length,
        completedBytes,
        totalBytes: document.payload.totalBytes,
        currentLabel: entry.label,
        downloaded: completed,
        skipped: 0,
        failed: 0,
      });
    }
    if (seen.size !== expected.size) throw new Error(`Pacchetto incompleto: ${seen.size}/${expected.size} file verificati.`);
    await sendMessage({
      type: "importCommit",
      scope: verified.scope,
      token,
      revisions,
      expectedCount: expected.size,
    });
    return {
      imported: completed,
      totalBytes: completedBytes,
      campaignName: verified.campaign.name,
    };
  } catch (error) {
    await sendMessage({ type: "importAbort", scope: verified.scope, token }).catch(() => undefined);
    throw error;
  }
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
