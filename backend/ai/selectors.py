"""Proiezioni dei provider verso la SPA.

La regola che conta: il segreto non esce mai da qui. L'interfaccia riceve
`hasSecret`, un booleano — mai il valore, nemmeno mascherato.
"""

from __future__ import annotations

from typing import Any

from backend.core.models import Giocatore
from backend.core.security import effective_role, get_or_create_giocatore_for_user, has_minimum_role

from .defaults import AI_IMAGE_QUALITIES, AI_IMAGE_SIZES
from .models import AIProvider
from .tools import AI_TOOLS


def can_use_ai(user, giocatore: Giocatore | None = None) -> bool:
    """Tutti possono usare l'assistente: gli strumenti filtrano per ruolo da soli."""

    return bool(user and user.is_authenticated)


def can_manage_ai(user, giocatore: Giocatore | None = None) -> bool:
    if not user:
        return False
    giocatore = giocatore or get_or_create_giocatore_for_user(user)
    return has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)


def is_provider_configured(provider: AIProvider) -> bool:
    """Un provider è utilizzabile quando ha la credenziale che il suo tipo richiede."""

    if provider.auth_strategy == AIProvider.AUTH_NONE:
        return bool(provider.base_url)
    return provider.has_secret


def serialize_provider(provider: AIProvider, *, include_management: bool) -> dict[str, Any]:
    options = provider.options if isinstance(provider.options, dict) else {}
    payload: dict[str, Any] = {
        "id": provider.id,
        "slug": provider.slug,
        "name": provider.name,
        "purpose": provider.purpose,
        "kind": provider.kind,
        "model": provider.model,
        "isEnabled": provider.is_enabled,
        "isDefault": provider.is_default,
        "description": str(options.get("description") or ""),
        # Se una credenziale serva ed esista è informazione d'interfaccia, non un
        # segreto: senza, la chat mostrerebbe un campo che fallisce al primo invio.
        "isConfigured": is_provider_configured(provider),
    }
    if include_management:
        payload.update(
            {
                "authStrategy": provider.auth_strategy,
                "baseUrl": provider.base_url,
                "hasSecret": provider.has_secret,
                "suggestedModels": options.get("suggestedModels") if isinstance(options.get("suggestedModels"), list) else [],
                "maxTokens": options.get("maxTokens"),
                "effort": options.get("effort", ""),
                "disableTools": bool(options.get("disableTools")),
                "order": provider.order,
            }
        )
    return payload


def usable_providers(purpose: str):
    return AIProvider.objects.filter(
        purpose=purpose,
        is_enabled=True,
        archived_at__isnull=True,
    ).order_by("-is_default", "order", "name")


def default_provider(purpose: str) -> AIProvider | None:
    """Il primo provider davvero utilizzabile: uno senza credenziale non è un default."""

    return next((entry for entry in usable_providers(purpose) if is_provider_configured(entry)), None)


def ai_workspace_payload(user, giocatore: Giocatore) -> dict[str, Any]:
    """Ciò che serve al modale della chat: provider utilizzabili e strumenti disponibili."""

    manage = can_manage_ai(user, giocatore)
    chat = [entry for entry in usable_providers(AIProvider.PURPOSE_CHAT) if is_provider_configured(entry)]
    images = [entry for entry in usable_providers(AIProvider.PURPOSE_IMAGE) if is_provider_configured(entry)]
    return {
        "chatProviders": [serialize_provider(entry, include_management=False) for entry in chat],
        "imageProviders": [serialize_provider(entry, include_management=False) for entry in images],
        "tools": [{"name": tool.name, "description": tool.description} for tool in AI_TOOLS],
        "imageSizes": AI_IMAGE_SIZES,
        "imageQualities": AI_IMAGE_QUALITIES,
        "canManage": manage,
        "ready": bool(chat),
    }


def ai_management_payload(user, giocatore: Giocatore) -> dict[str, Any]:
    providers = AIProvider.objects.filter(archived_at__isnull=True).order_by("purpose", "order", "name")
    return {
        "providers": [serialize_provider(entry, include_management=True) for entry in providers],
        "kinds": [{"value": value, "label": label} for value, label in AIProvider.KIND_CHOICES],
        "purposes": [{"value": value, "label": label} for value, label in AIProvider.PURPOSE_CHOICES],
        "authStrategies": [{"value": value, "label": label} for value, label in AIProvider.AUTH_CHOICES],
        "tools": [{"name": tool.name, "description": tool.description} for tool in AI_TOOLS],
        "canManage": can_manage_ai(user, giocatore),
    }
