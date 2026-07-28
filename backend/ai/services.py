from __future__ import annotations

import base64
from typing import Any

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils.text import slugify

from backend.core.api import ApiError
from backend.core.models import Giocatore
from backend.media_library.models import UploadedImage
from backend.media_library.services import create_uploaded_image

from .agent import run_agent
from .defaults import AI_IMAGE_QUALITIES, AI_IMAGE_SIZES
from .models import AIProvider
from .providers import image_provider_for
from .providers.images import decode_image
from .selectors import can_manage_ai, default_provider


MAXIMUM_MESSAGE_CHARACTERS = 8000
MAXIMUM_PROMPT_CHARACTERS = 2000
VALID_ROLES = {"user", "assistant", "tool"}


def _require_manager(user, giocatore: Giocatore) -> None:
    if not can_manage_ai(user, giocatore):
        raise ApiError(
            "ai.master_required",
            "Solo Master e Amministratori possono configurare l'AI.",
            status=403,
        )


def _resolve_provider(purpose: str, provider_id: object) -> AIProvider:
    if provider_id in (None, ""):
        provider = default_provider(purpose)
        if provider is None:
            raise ApiError(
                "ai.provider_missing",
                "Nessun provider AI è configurato. Aprine uno da Gestione AI.",
                status=409,
            )
        return provider
    try:
        return AIProvider.objects.get(
            pk=int(provider_id),
            purpose=purpose,
            is_enabled=True,
            archived_at__isnull=True,
        )
    except (TypeError, ValueError, AIProvider.DoesNotExist) as exc:
        raise ApiError("ai.provider_not_found", "Provider AI non disponibile.", "providerId", 404) from exc


def sanitize_history(raw: object) -> list[dict[str, Any]]:
    """Accetta soltanto la forma neutra della conversazione.

    Il client rimanda indietro la cronologia che gli abbiamo dato, incluso il
    contenuto grezzo del provider: senza di quello un giro di strumenti non può
    proseguire. Ruoli sconosciuti e messaggi troppo lunghi vengono scartati.
    """

    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        raise ApiError("ai.history_invalid", "La conversazione non è valida.", "history")
    history: list[dict[str, Any]] = []
    for entry in raw[-60:]:
        if not isinstance(entry, dict) or entry.get("role") not in VALID_ROLES:
            continue
        cleaned: dict[str, Any] = {
            "role": entry["role"],
            "content": str(entry.get("content") or "")[:MAXIMUM_MESSAGE_CHARACTERS],
        }
        if entry["role"] == "assistant":
            calls = entry.get("toolCalls")
            cleaned["toolCalls"] = calls if isinstance(calls, list) else []
            if entry.get("raw") is not None:
                cleaned["raw"] = entry["raw"]
        elif entry["role"] == "tool":
            cleaned["toolCallId"] = str(entry.get("toolCallId") or "")[:120]
            cleaned["name"] = str(entry.get("name") or "")[:80]
            cleaned["isError"] = bool(entry.get("isError"))
        history.append(cleaned)
    return history


def ask_assistant(user, giocatore: Giocatore, payload: dict) -> dict[str, Any]:
    message = str(payload.get("message") or "").strip()
    if not message:
        raise ApiError("ai.message_required", "Scrivi una domanda per l'assistente.", "message")
    provider = _resolve_provider(AIProvider.PURPOSE_CHAT, payload.get("providerId"))
    history = sanitize_history(payload.get("history"))
    history.append({"role": "user", "content": message[:MAXIMUM_MESSAGE_CHARACTERS]})
    result = run_agent(provider, history, user, giocatore)
    result["provider"] = {"id": provider.id, "name": provider.name, "model": provider.model}
    return result


@transaction.atomic
def generate_image(user, giocatore: Giocatore, payload: dict) -> UploadedImage:
    """Genera o rielabora un'immagine e la archivia nell'Archivio immagini."""

    _require_manager(user, giocatore)
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ApiError("ai.prompt_required", "Descrivi l'immagine da generare.", "prompt")
    provider = _resolve_provider(AIProvider.PURPOSE_IMAGE, payload.get("providerId"))

    size = str(payload.get("size") or AI_IMAGE_SIZES[0]["value"])
    if size not in {entry["value"] for entry in AI_IMAGE_SIZES}:
        raise ApiError("ai.size_invalid", "Formato immagine non valido.", "size")
    quality = str(payload.get("quality") or "medium")
    if quality not in {entry["value"] for entry in AI_IMAGE_QUALITIES}:
        raise ApiError("ai.quality_invalid", "Qualità immagine non valida.", "quality")

    source = ""
    source_id = payload.get("sourceImageId")
    if source_id not in (None, ""):
        try:
            original = UploadedImage.objects.get(pk=int(source_id), archived_at__isnull=True)
        except (TypeError, ValueError, UploadedImage.DoesNotExist) as exc:
            raise ApiError("ai.source_not_found", "Immagine di partenza non trovata.", "sourceImageId", 404) from exc
        with original.file.open("rb") as handle:
            source = base64.b64encode(handle.read()).decode("ascii")

    client = image_provider_for(provider)
    encoded = client.generate(prompt=prompt[:MAXIMUM_PROMPT_CHARACTERS], size=size, quality=quality, source_image_base64=source)
    content = decode_image(encoded)

    title = str(payload.get("title") or prompt)[:180].strip() or "Immagine generata"
    filename = f"{slugify(title) or 'immagine-ai'}.png"
    uploaded = SimpleUploadedFile(filename, content, content_type="image/png")
    asset = create_uploaded_image(
        user,
        uploaded,
        {
            "title": title,
            "usageType": str(payload.get("usageType") or "generic"),
            "categoryId": payload.get("categoryId"),
            "group": str(payload.get("group") or "Immagini AI"),
            "notes": f"Generata da {provider.name} ({provider.model or 'modello predefinito'}).",
        },
    )
    # `prompt` e `source` esistono già su UploadedImage: l'immagine porta con sé
    # come è nata, senza inventare un nuovo modello.
    asset.prompt = prompt[:MAXIMUM_PROMPT_CHARACTERS]
    asset.source = "ai_generated"
    asset.save(update_fields=["prompt", "source", "updated_at"])
    return asset


@transaction.atomic
def save_provider(user, giocatore: Giocatore, values: dict) -> AIProvider:
    _require_manager(user, giocatore)
    if not isinstance(values, dict):
        raise ApiError("ai.values_invalid", "I dati del provider non sono validi.", "values")

    provider_id = values.get("id")
    if provider_id in (None, ""):
        raise ApiError("ai.provider_required", "Scegli il provider da configurare.", "id")
    try:
        provider = AIProvider.objects.get(pk=int(provider_id), archived_at__isnull=True)
    except (TypeError, ValueError, AIProvider.DoesNotExist) as exc:
        raise ApiError("ai.provider_not_found", "Provider AI non trovato.", "id", 404) from exc

    fields = ["updated_at"]
    if "name" in values:
        name = str(values.get("name") or "").strip()[:120]
        if not name:
            raise ApiError("ai.name_required", "Inserisci un nome per il provider.", "name")
        provider.name = name
        fields.append("name")
    if "baseUrl" in values:
        base_url = str(values.get("baseUrl") or "").strip()[:300]
        if base_url and not base_url.startswith(("http://", "https://")):
            raise ApiError("ai.base_url_invalid", "L'indirizzo deve iniziare con http:// o https://.", "baseUrl")
        provider.base_url = base_url
        fields.append("base_url")
    if "model" in values:
        provider.model = str(values.get("model") or "").strip()[:160]
        fields.append("model")
    if "isEnabled" in values:
        provider.is_enabled = bool(values.get("isEnabled"))
        fields.append("is_enabled")
    if "isDefault" in values and values.get("isDefault"):
        AIProvider.objects.filter(purpose=provider.purpose).exclude(pk=provider.pk).update(is_default=False)
        provider.is_default = True
        fields.append("is_default")

    options = dict(provider.options) if isinstance(provider.options, dict) else {}
    for key, option in (("maxTokens", "maxTokens"), ("effort", "effort"), ("disableTools", "disableTools")):
        if key in values:
            options[option] = values.get(key)
    if options != provider.options:
        provider.options = options
        fields.append("options")

    # La chiave si scrive e non si rilegge mai: stringa vuota significa
    # «non toccare», il valore speciale «__clear__» la rimuove.
    if "secret" in values:
        secret = str(values.get("secret") or "")
        if secret == "__clear__":
            provider.secret_ciphertext = ""
            fields.append("secret_ciphertext")
        elif secret.strip():
            provider.set_secret(secret)
            fields.append("secret_ciphertext")

    provider.save(update_fields=fields)
    return provider


def test_provider(user, giocatore: Giocatore, provider_id: object) -> dict[str, Any]:
    """Prova di connessione: una domanda banale, senza strumenti."""

    _require_manager(user, giocatore)
    try:
        provider = AIProvider.objects.get(pk=int(provider_id), archived_at__isnull=True)
    except (TypeError, ValueError, AIProvider.DoesNotExist) as exc:
        raise ApiError("ai.provider_not_found", "Provider AI non trovato.", "providerId", 404) from exc

    if provider.purpose == AIProvider.PURPOSE_IMAGE:
        return {
            "ok": True,
            "message": "Configurazione salvata. Le immagini si verificano generandone una.",
        }

    from .providers import chat_provider_for

    client = chat_provider_for(provider)
    turn = client.complete(
        system="Rispondi con una sola parola.",
        history=[{"role": "user", "content": "Scrivi soltanto: pronto"}],
        tools=[],
    )
    return {"ok": True, "message": f"{provider.name} ha risposto: {turn.text[:120] or '(risposta vuota)'}"}
