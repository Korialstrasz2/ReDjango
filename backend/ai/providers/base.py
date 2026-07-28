"""Contratto comune fra i provider.

La conversazione viaggia in una forma neutra; ogni adattatore la traduce nel proprio
formato di rete. Il turno dell'assistente conserva anche il contenuto grezzo del
provider (`raw`), perché una conversazione resta sempre sullo stesso provider e
rimandare indietro i blocchi esattamente come sono arrivati è l'unico modo sicuro
di continuare un giro di strumenti.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from backend.core.api import ApiError


REQUEST_TIMEOUT_SECONDS = 180


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatTurn:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = ""
    raw: Any = None
    usage: dict[str, Any] = field(default_factory=dict)


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str], *, timeout: int = REQUEST_TIMEOUT_SECONDS) -> dict[str, Any]:
    """POST JSON con la libreria standard: nessuna dipendenza HTTP aggiuntiva."""

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = ""
        try:
            body = json.loads(error.read().decode("utf-8"))
            detail = str(body.get("error", {}).get("message") or body.get("message") or "")
        except (ValueError, OSError):
            detail = ""
        raise ApiError(
            "ai.provider_error",
            f"Il provider ha risposto {error.code}." + (f" {detail}" if detail else ""),
            status=502,
        ) from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ApiError(
            "ai.provider_unreachable",
            "Il provider non è raggiungibile. Controlla indirizzo, rete e chiave.",
            status=502,
        ) from error


def chat_provider_for(provider):
    from ..models import AIProvider
    from .anthropic_provider import AnthropicChatProvider
    from .openai_provider import OpenAICompatibleChatProvider

    if provider.kind == AIProvider.KIND_ANTHROPIC:
        return AnthropicChatProvider(provider)
    if provider.kind == AIProvider.KIND_OPENAI_COMPATIBLE:
        return OpenAICompatibleChatProvider(provider)
    raise ApiError("ai.kind_unsupported", f"Il provider «{provider.name}» non è un provider di chat.", status=409)


def image_provider_for(provider):
    from ..models import AIProvider
    from .images import OpenAIImageProvider, StableDiffusionImageProvider

    if provider.kind == AIProvider.KIND_OPENAI_IMAGE:
        return OpenAIImageProvider(provider)
    if provider.kind == AIProvider.KIND_STABLE_DIFFUSION:
        return StableDiffusionImageProvider(provider)
    raise ApiError("ai.kind_unsupported", f"Il provider «{provider.name}» non genera immagini.", status=409)
