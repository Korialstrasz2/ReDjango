export type ApiEvent = { type: string; message: string };

type ApiEnvelope<T> = {
  ok: boolean;
  requestId: string;
  data: T;
  events: ApiEvent[];
  warnings: Array<{ message?: string }>;
  errors: Array<{ code: string; message: string; field?: string }>;
};

export class ApiClientError extends Error {
  code: string;
  field?: string;
  status: number;

  constructor(message: string, code = "request.failed", status = 400, field?: string) {
    super(message);
    this.code = code;
    this.status = status;
    this.field = field;
  }
}

export function getCsrfToken(): string {
  const token = document.cookie.split(";").map((value) => value.trim()).find((value) => value.startsWith("csrftoken="));
  return token ? decodeURIComponent(token.slice("csrftoken=".length)) : "";
}

export function requestId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `req-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<ApiEnvelope<T>> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  headers.set("X-ReDjango-Client", "web-spa-react");
  headers.set("X-ReDjango-Request-Id", headers.get("X-ReDjango-Request-Id") || requestId());
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (init.method && !["GET", "HEAD"].includes(init.method.toUpperCase())) {
    headers.set("X-CSRFToken", getCsrfToken());
  }
  const response = await fetch(path, { credentials: "same-origin", ...init, headers });
  const envelope = (await response.json().catch(() => null)) as ApiEnvelope<T> | null;
  if (!response.ok || !envelope?.ok) {
    const error = envelope?.errors?.[0];
    throw new ApiClientError(error?.message || `Richiesta non riuscita (${response.status}).`, error?.code, response.status, error?.field);
  }
  return envelope;
}

export async function getData<T>(path: string): Promise<T> {
  return (await apiRequest<T>(path)).data;
}

export async function legacyAction<T>(path: string, action: string, payload: Record<string, unknown>): Promise<ApiEnvelope<T>> {
  const id = requestId();
  return apiRequest<T>(path, {
    method: "POST",
    headers: { "X-ReDjango-Action": action, "X-ReDjango-Request-Id": id },
    body: JSON.stringify({ action, requestId: id, context: {}, payload, meta: { clientVersion: "react-v1" } })
  });
}

export async function command<T>(action: string, payload: Record<string, unknown>, screen = "personaggio"): Promise<ApiEnvelope<T>> {
  const id = requestId();
  return apiRequest<T>("/api/v1/actions", {
    method: "POST",
    headers: { "X-ReDjango-Action": action, "X-ReDjango-Request-Id": id },
    body: JSON.stringify({ action, requestId: id, context: { screen }, payload, meta: { clientVersion: "react-v1" } })
  });
}

export async function uploadMedia(
  file: File,
  title: string,
  notes: string,
  usageType = "generic",
  categoryId?: number | null,
  group = "",
  metadata: Record<string, unknown> = {},
) {
  const id = requestId();
  const form = new FormData();
  form.set("file", file);
  form.set("envelope", JSON.stringify({
    action: "media.upload",
    requestId: id,
    context: { screen: "media" },
    payload: { title, notes, usageType, categoryId, group, ...metadata },
    meta: { clientVersion: "react-v1" }
  }));
  return apiRequest<{ asset: import("./types").MediaAsset }>("/api/media/", {
    method: "POST",
    headers: { "X-ReDjango-Action": "media.upload", "X-ReDjango-Request-Id": id },
    body: form
  });
}

export async function convertImageToWebp(file: File, quality = .75): Promise<File> {
  const bitmap = await createImageBitmap(file);
  const canvas = document.createElement("canvas");
  canvas.width = bitmap.width;
  canvas.height = bitmap.height;
  const context = canvas.getContext("2d");
  if (!context) {
    bitmap.close();
    throw new ApiClientError("Il browser non riesce a preparare l'immagine WebP.", "media.webp_canvas_failed");
  }
  context.drawImage(bitmap, 0, 0, bitmap.width, bitmap.height);
  bitmap.close();
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/webp", quality));
  if (!blob) throw new ApiClientError("Conversione WebP non riuscita.", "media.webp_conversion_failed");
  const baseName = file.name.replace(/\.[^.]+$/, "") || "mappa";
  return new File([blob], `${baseName}.webp`, { type: "image/webp", lastModified: file.lastModified });
}

export const ITEM_ICON_SIZE = 128;
export const ITEM_ICON_QUALITY = .7;

/** Centre-crops an image to a square, scales it to `size` and encodes it as WebP. */
export async function prepareSquareIcon(file: File, size = ITEM_ICON_SIZE, quality = ITEM_ICON_QUALITY): Promise<File> {
  const bitmap = await createImageBitmap(file);
  const edge = Math.min(bitmap.width, bitmap.height);
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  if (!context) {
    bitmap.close();
    throw new ApiClientError("Il browser non riesce a preparare l'icona.", "media.webp_canvas_failed");
  }
  context.imageSmoothingQuality = "high";
  context.drawImage(bitmap, (bitmap.width - edge) / 2, (bitmap.height - edge) / 2, edge, edge, 0, 0, size, size);
  bitmap.close();
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/webp", quality));
  if (!blob) throw new ApiClientError("Conversione WebP non riuscita.", "media.webp_conversion_failed");
  const baseName = file.name.replace(/\.[^.]+$/, "") || "icona";
  return new File([blob], `${baseName}.webp`, { type: "image/webp", lastModified: file.lastModified });
}

export async function uploadItemSpecialIcon(itemId: number, file: File) {
  const prepared = await prepareSquareIcon(file);
  const form = new FormData();
  form.set("file", prepared);
  return apiRequest<{ item: import("./types").Item }>(`/api/oggetti/${itemId}/icona/`, {
    method: "POST",
    headers: { "X-ReDjango-Action": "item.icon.upload" },
    body: form,
  });
}

export async function deleteItemSpecialIcon(itemId: number) {
  return apiRequest<{ item: import("./types").Item }>(`/api/oggetti/${itemId}/icona/`, {
    method: "DELETE",
    headers: { "X-ReDjango-Action": "item.icon.delete" },
  });
}

export async function uploadCombatMapImage(file: File, title: string, convertToWebp: boolean) {
  const prepared = convertToWebp ? await convertImageToWebp(file, .75) : file;
  return uploadMedia(
    prepared,
    title || file.name,
    "Immagine configurata dall'editor delle mappe di combattimento.",
    "map",
    undefined,
    "Mappe combattimento",
    {
      originalName: file.name,
      originalMimeType: file.type,
      originalSizeBytes: file.size,
      convertedToWebp: convertToWebp,
      webpQuality: convertToWebp ? 75 : null,
    },
  );
}

export async function getMediaDetail(assetId: number) {
  return getData<import("./types").MediaDetailData>(`/api/media/${assetId}/`);
}

export async function moveMedia(assetId: number, categoryId: number, group: string) {
  const id = requestId();
  return apiRequest<import("./types").MediaDetailData>(`/api/media/${assetId}/`, {
    method: "PATCH",
    headers: { "X-ReDjango-Action": "media.move", "X-ReDjango-Request-Id": id },
    body: JSON.stringify({
      action: "media.move",
      requestId: id,
      context: { screen: "media" },
      payload: { categoryId, group },
      meta: { clientVersion: "react-v1" }
    })
  });
}

export async function setMediaLimitedVisibility(assetId: number, limitedVisibility: boolean) {
  const id = requestId();
  return apiRequest<import("./types").MediaDetailData>(`/api/media/${assetId}/`, {
    method: "PATCH",
    headers: { "X-ReDjango-Action": "media.setLimitedVisibility", "X-ReDjango-Request-Id": id },
    body: JSON.stringify({
      action: "media.setLimitedVisibility",
      requestId: id,
      context: { screen: "media" },
      payload: { limitedVisibility },
      meta: { clientVersion: "react-v1" }
    })
  });
}

export async function deleteMedia(assetId: number) {
  const id = requestId();
  return apiRequest<Record<string, never>>(`/api/media/${assetId}/`, {
    method: "DELETE",
    headers: { "X-ReDjango-Action": "media.delete", "X-ReDjango-Request-Id": id }
  });
}

/** Un turno dell'agente con cronologia provider-neutral, senza stato persistente sul server. */
export async function askAssistant(payload: Record<string, unknown>) {
  const id = requestId();
  return apiRequest<import("./types").AIChatResult>("/api/ai/", {
    method: "POST",
    headers: { "X-ReDjango-Action": "ai.ask", "X-ReDjango-Request-Id": id },
    body: JSON.stringify({ action: "ai.ask", requestId: id, context: { screen: "ai" }, payload, meta: { clientVersion: "react-v1" } })
  });
}

export async function generateAIImage(payload: Record<string, unknown>) {
  const id = requestId();
  return apiRequest<{ asset: import("./types").MediaAsset }>("/api/ai/images/", {
    method: "POST",
    headers: { "X-ReDjango-Action": "ai.generateImage", "X-ReDjango-Request-Id": id },
    body: JSON.stringify({ action: "ai.generateImage", requestId: id, context: { screen: "ai" }, payload, meta: { clientVersion: "react-v1" } })
  });
}

/** Una bozza di PNG: il backend non scrive nulla, restituisce solo il testo da rivedere. */
export async function generateNpcDossier(payload: Record<string, unknown>) {
  const id = requestId();
  return apiRequest<import("./types").NpcDossierResult>("/api/ai/dossier/", {
    method: "POST",
    headers: { "X-ReDjango-Action": "ai.generateDossier", "X-ReDjango-Request-Id": id },
    body: JSON.stringify({ action: "ai.generateDossier", requestId: id, context: { screen: "names" }, payload, meta: { clientVersion: "react-v1" } })
  });
}

/** Passo separato e a pagamento: formato e qualità li decide Gestione AI, non il client. */
export async function generateNpcPortrait(payload: Record<string, unknown>) {
  const id = requestId();
  return apiRequest<{ asset: import("./types").MediaAsset }>("/api/ai/dossier/portrait/", {
    method: "POST",
    headers: { "X-ReDjango-Action": "ai.generatePortrait", "X-ReDjango-Request-Id": id },
    body: JSON.stringify({ action: "ai.generatePortrait", requestId: id, context: { screen: "names" }, payload, meta: { clientVersion: "react-v1" } })
  });
}

export async function saveNpcGeneration(payload: Record<string, unknown>) {
  const id = requestId();
  return apiRequest<import("./types").AIManagementData>("/api/ai/providers/", {
    method: "POST",
    headers: { "X-ReDjango-Action": "ai.saveNpcGeneration", "X-ReDjango-Request-Id": id },
    body: JSON.stringify({ action: "ai.saveNpcGeneration", requestId: id, context: { screen: "ai" }, payload: { npcGenerationValues: payload }, meta: { clientVersion: "react-v1" } })
  });
}

export async function saveAIProvider(payload: Record<string, unknown>) {
  const id = requestId();
  return apiRequest<import("./types").AIManagementData>("/api/ai/providers/", {
    method: "POST",
    headers: { "X-ReDjango-Action": "ai.saveProvider", "X-ReDjango-Request-Id": id },
    body: JSON.stringify({ action: "ai.saveProvider", requestId: id, context: { screen: "ai" }, payload, meta: { clientVersion: "react-v1" } })
  });
}

export async function uploadAudioTrack(file: File, title: string, tags: string[], durationSeconds: number | null) {
  const id = requestId();
  const form = new FormData();
  form.set("file", file);
  form.set("envelope", JSON.stringify({
    action: "audio.uploadTrack",
    requestId: id,
    context: { screen: "audio" },
    payload: { title, tags, durationSeconds },
    meta: { clientVersion: "react-v1" }
  }));
  return apiRequest<import("./types").AudioLibraryData>("/api/audio/tracks/", {
    method: "POST",
    headers: { "X-ReDjango-Action": "audio.uploadTrack", "X-ReDjango-Request-Id": id },
    body: form,
  });
}

export async function updateAudioTrack(trackId: number, payload: Record<string, unknown>) {
  const id = requestId();
  return apiRequest<import("./types").AudioLibraryData>(`/api/audio/tracks/${trackId}/`, {
    method: "PATCH",
    headers: { "X-ReDjango-Action": "audio.updateTrack", "X-ReDjango-Request-Id": id },
    body: JSON.stringify({
      action: "audio.updateTrack",
      requestId: id,
      context: { screen: "audio" },
      payload,
      meta: { clientVersion: "react-v1" }
    })
  });
}

export async function deleteAudioTrack(trackId: number) {
  const id = requestId();
  return apiRequest<import("./types").AudioLibraryData>(`/api/audio/tracks/${trackId}/`, {
    method: "DELETE",
    headers: { "X-ReDjango-Action": "audio.deleteTrack", "X-ReDjango-Request-Id": id },
  });
}

export async function uploadTravelMap(file: File, name: string, categoryId: number | null) {
  const id = requestId();
  const form = new FormData();
  form.set("file", file);
  form.set("envelope", JSON.stringify({
    action: "travel.createMap",
    requestId: id,
    context: { screen: "travel" },
    payload: { name, categoryId, group: "Mappe globali" },
    meta: { clientVersion: "react-v1" }
  }));
  return apiRequest<{ map: import("./types").TravelMap }>("/api/travel/maps/", {
    method: "POST",
    headers: { "X-ReDjango-Action": "travel.createMap", "X-ReDjango-Request-Id": id },
    body: form,
  });
}

export async function updateTravelMap(
  mapId: number,
  operation: "saveGrid" | "saveEffects" | "saveMarkers" | "saveAll" | "setDefault",
  payload: Record<string, unknown>,
) {
  const id = requestId();
  return apiRequest<{ map: import("./types").TravelMap }>(`/api/travel/maps/${mapId}/`, {
    method: "PATCH",
    headers: { "X-ReDjango-Action": `travel.${operation}`, "X-ReDjango-Request-Id": id },
    body: JSON.stringify({
      action: `travel.${operation}`,
      requestId: id,
      context: { screen: "travel" },
      payload: { operation, ...payload },
      meta: { clientVersion: "react-v1" }
    })
  });
}
