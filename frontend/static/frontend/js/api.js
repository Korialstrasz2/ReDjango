export function getCsrfToken() {
    const token = document.cookie
        .split(";")
        .map((value) => value.trim())
        .find((value) => value.startsWith("csrftoken="));
    return token ? decodeURIComponent(token.slice("csrftoken=".length)) : "";
}

function createRequestId() {
    if (globalThis.crypto?.randomUUID) {
        return globalThis.crypto.randomUUID();
    }
    return `req-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function envelopeFor({ action, requestId, screen, context, payload, meta }) {
    return {
        action,
        requestId,
        context: {
            screen,
            ...context,
        },
        payload: payload || {},
        meta: {
            clientVersion: "minimum",
            ...meta,
        },
    };
}

export async function apiFetch(path, options = {}) {
    const {
        action = "core.request",
        body: providedBody,
        context = {},
        headers: providedHeaders,
        meta = {},
        method: providedMethod = "GET",
        payload,
        requestId: providedRequestId,
        screen = stateScreenFromPath(path),
        ...fetchOptions
    } = options;
    const headers = new Headers(providedHeaders || {});
    const method = providedMethod.toUpperCase();
    const requestId = providedRequestId || createRequestId();
    const envelope = envelopeFor({ action, requestId, screen, context, payload, meta });
    let body = providedBody;

    headers.set("Accept", "application/json");
    headers.set("X-ReDjango-Action", action);
    headers.set("X-ReDjango-Request-Id", requestId);
    headers.set("X-ReDjango-Client", "web-spa");
    headers.set("X-ReDjango-Screen", screen);

    if (body instanceof FormData) {
        body.set("envelope", JSON.stringify(envelope));
    } else if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
        headers.set("Content-Type", "application/json");
        body = JSON.stringify(envelope);
    }

    if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
        headers.set("X-CSRFToken", getCsrfToken());
    }

    const response = await fetch(path, {
        credentials: "same-origin",
        ...fetchOptions,
        body,
        headers,
        method,
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.ok === false) {
        const error = data.errors?.[0];
        throw new Error(error?.message || data.error || `Request failed: ${response.status}`);
    }
    return data.data || {};
}

function stateScreenFromPath(path) {
    if (path.includes("/characters/")) return "characters";
    if (path.includes("/media/")) return "media";
    return "dashboard";
}
