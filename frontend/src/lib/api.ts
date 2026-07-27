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
