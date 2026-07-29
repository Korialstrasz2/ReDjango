from __future__ import annotations

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
from .models import AIAgentProfile, AIProvider
from .providers import image_provider_for
from .providers.images import decode_image
from .selectors import can_manage_ai, can_manage_ai_credentials, default_provider
from .tools import AI_TOOLS_BY_NAME


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


def _require_credential_manager(user, giocatore: Giocatore) -> None:
    if not can_manage_ai_credentials(user, giocatore):
        raise ApiError(
            "ai.admin_required",
            "Solo un Amministratore può modificare chiavi e indirizzi dei provider.",
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
    """Accetta soltanto la forma provider-neutral della conversazione."""

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
    agent_id = payload.get("agentId")
    agents = AIAgentProfile.objects.filter(is_enabled=True, archived_at__isnull=True)
    try:
        agent = agents.get(pk=int(agent_id)) if agent_id not in (None, "") else agents.order_by("-is_default", "order", "name").first()
    except (TypeError, ValueError, AIAgentProfile.DoesNotExist) as exc:
        raise ApiError("ai.agent_not_found", "Agente AI non disponibile.", "agentId", 404) from exc
    if agent is None:
        raise ApiError("ai.agent_missing", "Nessun agente AI è configurato.", status=409)
    from backend.core.security import effective_role, has_minimum_role
    if not has_minimum_role(effective_role(user, giocatore), agent.minimum_role):
        raise ApiError("ai.agent_forbidden", "Non hai il ruolo richiesto da questo agente.", "agentId", 403)
    provider = agent.provider if agent.provider and agent.provider.is_enabled else default_provider(AIProvider.PURPOSE_CHAT)
    if provider is None or not provider.is_enabled:
        raise ApiError("ai.provider_missing", "Il provider dell'agente non è disponibile.", status=409)
    history = sanitize_history(payload.get("history"))
    history.append({"role": "user", "content": message[:MAXIMUM_MESSAGE_CHARACTERS]})
    result = run_agent(provider, history, user, giocatore, agent)
    result["provider"] = {"id": provider.id, "name": provider.name, "model": provider.model}
    result["agent"] = {"id": agent.id, "name": agent.name}
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
        raise ApiError(
            "ai.image_editing_wip",
            "La modifica di immagini è ancora in lavorazione; per ora puoi generarne una nuova.",
            "sourceImageId",
            409,
        )

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
        _require_credential_manager(user, giocatore)
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
    for key, option in (
        ("maxTokens", "maxTokens"),
        ("effort", "effort"),
        ("verbosity", "verbosity"),
        ("disableTools", "disableTools"),
    ):
        if key in values:
            options[option] = values.get(key)
    if options != provider.options:
        provider.options = options
        fields.append("options")

    # La chiave si scrive e non si rilegge mai: stringa vuota significa
    # «non toccare», il valore speciale «__clear__» la rimuove.
    if "secret" in values:
        _require_credential_manager(user, giocatore)
        secret = str(values.get("secret") or "")
        if secret == "__clear__":
            provider.secret_ciphertext = ""
            fields.append("secret_ciphertext")
        elif secret.strip():
            provider.set_secret(secret)
            fields.append("secret_ciphertext")

    provider.save(update_fields=fields)
    return provider


@transaction.atomic
def save_agent(user, giocatore: Giocatore, values: dict) -> AIAgentProfile:
    _require_manager(user, giocatore)
    if not isinstance(values, dict):
        raise ApiError("ai.values_invalid", "I dati dell'agente non sono validi.", "values")
    agent_id = values.get("id")
    if agent_id in (None, ""):
        agent = AIAgentProfile()
    else:
        try:
            agent = AIAgentProfile.objects.get(pk=int(agent_id), archived_at__isnull=True)
        except (TypeError, ValueError, AIAgentProfile.DoesNotExist) as exc:
            raise ApiError("ai.agent_not_found", "Agente AI non trovato.", "id", 404) from exc

    name = str(values.get("name", agent.name) or "").strip()[:120]
    if not name:
        raise ApiError("ai.name_required", "Inserisci un nome per l'agente.", "name")
    if not agent.pk:
        base_slug = slugify(name)[:100] or "agente"
        slug = base_slug
        suffix = 2
        while AIAgentProfile.objects.filter(slug=slug).exists():
            slug = f"{base_slug[:95]}-{suffix}"
            suffix += 1
        agent.slug = slug
    minimum_role = str(values.get("minimumRole", agent.minimum_role))
    if minimum_role not in dict(Giocatore.ROLE_CHOICES):
        raise ApiError("ai.role_invalid", "Ruolo minimo non valido.", "minimumRole")
    try:
        max_iterations = int(values.get("maxIterations", agent.max_iterations))
    except (TypeError, ValueError) as exc:
        raise ApiError("ai.iterations_invalid", "Il limite deve essere un numero.", "maxIterations") from exc
    if not 1 <= max_iterations <= 12:
        raise ApiError("ai.iterations_invalid", "Il limite deve essere compreso tra 1 e 12.", "maxIterations")
    tool_names = values.get("toolNames", agent.allowed_tools)
    if not isinstance(tool_names, list) or any(name not in AI_TOOLS_BY_NAME for name in tool_names):
        raise ApiError("ai.tools_invalid", "La selezione degli strumenti non è valida.", "toolNames")
    provider_id = values.get("providerId", agent.provider_id)
    try:
        provider = AIProvider.objects.get(pk=int(provider_id), purpose="chat", archived_at__isnull=True) if provider_id else None
    except (TypeError, ValueError, AIProvider.DoesNotExist) as exc:
        raise ApiError("ai.provider_not_found", "Provider chat non trovato.", "providerId", 404) from exc

    agent.name = name
    agent.description = str(values.get("description", agent.description) or "")[:1000]
    agent.instructions = str(values.get("instructions", agent.instructions) or "")[:8000]
    agent.minimum_role = minimum_role
    agent.provider = provider
    agent.allowed_tools = list(dict.fromkeys(tool_names))
    agent.max_iterations = max_iterations
    agent.is_enabled = bool(values.get("isEnabled", agent.is_enabled))
    if values.get("isDefault"):
        AIAgentProfile.objects.exclude(pk=agent.pk).update(is_default=False)
        agent.is_default = True
    agent.save()
    return agent


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
