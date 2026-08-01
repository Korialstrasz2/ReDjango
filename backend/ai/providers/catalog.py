"""Discovery live dei modelli, normalizzata per la Gestione AI."""

from __future__ import annotations

from typing import Any

from backend.core.api import ApiError

from ..models import AIProvider
from .base import get_json


CHAT_EXCLUDED_MARKERS = (
    "embedding",
    "moderation",
    "whisper",
    "transcribe",
    "text-to-speech",
    "tts-",
    "dall-e",
    "image",
    "realtime",
)


def _secret_headers(provider: AIProvider) -> dict[str, str]:
    if provider.auth_strategy == AIProvider.AUTH_NONE:
        return {}
    secret = provider.read_secret()
    if not secret:
        raise ApiError("ai.secret_missing", "Configura la chiave API prima di aggiornare i modelli.", status=409)
    if provider.kind == AIProvider.KIND_ANTHROPIC:
        return {"x-api-key": secret, "anthropic-version": "2023-06-01"}
    return {"Authorization": f"Bearer {secret}"}


def _catalog_url(provider: AIProvider) -> str:
    base = (provider.base_url or "").rstrip("/")
    if provider.kind == AIProvider.KIND_ANTHROPIC:
        return f"{base or 'https://api.anthropic.com/v1'}/models"
    if provider.kind == AIProvider.KIND_STABLE_DIFFUSION:
        if not base:
            raise ApiError("ai.base_url_missing", "Configura l'indirizzo del server Stable Diffusion.", status=409)
        return f"{base}/sdapi/v1/sd-models"
    if not base:
        raise ApiError("ai.base_url_missing", "Configura l'indirizzo del provider.", status=409)
    return f"{base}/models"


def _raw_entries(provider: AIProvider, body: Any) -> list[dict[str, Any]]:
    if provider.kind == AIProvider.KIND_STABLE_DIFFUSION:
        return [entry for entry in body if isinstance(entry, dict)] if isinstance(body, list) else []
    if isinstance(body, dict):
        data = body.get("data") if isinstance(body.get("data"), list) else body.get("models")
        return [entry for entry in (data or []) if isinstance(entry, dict)]
    return []


def _identifier(provider: AIProvider, entry: dict[str, Any]) -> str:
    if provider.kind == AIProvider.KIND_STABLE_DIFFUSION:
        return str(entry.get("model_name") or entry.get("title") or entry.get("name") or "").strip()
    return str(entry.get("id") or entry.get("name") or "").strip()


def _keep(provider: AIProvider, model_id: str, entry: dict[str, Any]) -> bool:
    lowered = model_id.casefold()
    architecture = entry.get("architecture") if isinstance(entry.get("architecture"), dict) else {}
    modalities = architecture.get("output_modalities") if isinstance(architecture.get("output_modalities"), list) else []
    if provider.purpose == AIProvider.PURPOSE_IMAGE:
        if provider.kind == AIProvider.KIND_STABLE_DIFFUSION:
            return True
        return "image" in lowered or "dall-e" in lowered or "image" in modalities
    if "text" in modalities:
        return True
    return not any(marker in lowered for marker in CHAT_EXCLUDED_MARKERS)


def _capabilities(provider: AIProvider, model_id: str, entry: dict[str, Any]) -> dict[str, bool]:
    supported = entry.get("supported_parameters") if isinstance(entry.get("supported_parameters"), list) else []
    supported_set = {str(value) for value in supported}
    lowered = model_id.casefold()
    if provider.purpose == AIProvider.PURPOSE_IMAGE:
        return {"chat": False, "tools": False, "reasoning": False, "verbosity": False, "images": True, "imageEditing": False}
    tools = True
    reasoning = provider.kind in {AIProvider.KIND_ANTHROPIC, AIProvider.KIND_OPENAI_RESPONSES}
    verbosity = provider.kind == AIProvider.KIND_OPENAI_RESPONSES and lowered.startswith("gpt-5")
    if supported_set:
        tools = bool({"tools", "tool_choice"} & supported_set)
        reasoning = reasoning or bool({"reasoning", "include_reasoning"} & supported_set)
        verbosity = verbosity or "verbosity" in supported_set
    if provider.kind == AIProvider.KIND_OPENAI_RESPONSES and not (lowered.startswith("gpt-5") or lowered.startswith("o")):
        reasoning = False
    return {"chat": True, "tools": tools, "reasoning": reasoning, "verbosity": verbosity, "images": False, "imageEditing": False}


def _integer(entry: dict[str, Any], *names: str) -> int | None:
    for name in names:
        value = entry.get(name)
        if isinstance(value, int) and value > 0:
            return value
    return None


def fetch_provider_models(provider: AIProvider) -> list[dict[str, Any]]:
    """Interroga il provider e restituisce un catalogo piccolo e stabile."""

    body = get_json(_catalog_url(provider), _secret_headers(provider), timeout=30)
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in _raw_entries(provider, body):
        model_id = _identifier(provider, entry)
        if not model_id or model_id in seen or not _keep(provider, model_id, entry):
            continue
        seen.add(model_id)
        architecture = entry.get("architecture") if isinstance(entry.get("architecture"), dict) else {}
        result.append(
            {
                "id": model_id,
                "label": str(entry.get("display_name") or entry.get("name") or entry.get("title") or model_id),
                "contextWindow": _integer(entry, "context_length", "context_window") or _integer(architecture, "context_length"),
                "capabilities": _capabilities(provider, model_id, entry),
            }
        )
    result.sort(key=lambda item: item["id"].casefold())
    if not result:
        raise ApiError("ai.models_empty", "Il provider non ha restituito modelli utilizzabili.", status=502)
    return result[:500]
