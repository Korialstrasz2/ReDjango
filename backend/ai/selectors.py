"""Proiezioni AI verso la SPA; nessun segreto lascia mai il backend."""

from __future__ import annotations

from typing import Any

from backend.core.models import Giocatore
from backend.core.security import effective_role, get_or_create_giocatore_for_user, has_minimum_role

from .defaults import image_generation_options
from .models import AIAgentProfile, AIProvider
from .tools import AI_TOOLS, tool_is_available


def can_use_ai(user, giocatore: Giocatore | None = None) -> bool:
    return bool(user and user.is_authenticated)


def can_manage_ai(user, giocatore: Giocatore | None = None) -> bool:
    if not user:
        return False
    giocatore = giocatore or get_or_create_giocatore_for_user(user)
    return has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)


def can_manage_ai_credentials(user, giocatore: Giocatore | None = None) -> bool:
    if not user:
        return False
    giocatore = giocatore or get_or_create_giocatore_for_user(user)
    return has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_ADMIN)


def provider_capabilities(provider: AIProvider) -> dict[str, bool]:
    by_kind = {
        AIProvider.KIND_ANTHROPIC: {"chat": True, "tools": True, "reasoning": True},
        AIProvider.KIND_OPENAI_RESPONSES: {"chat": True, "tools": True, "reasoning": True, "verbosity": True},
        AIProvider.KIND_OPENAI_COMPATIBLE: {"chat": True, "tools": True},
        AIProvider.KIND_OPENAI_IMAGE: {"images": True, "imageEditing": False},
        AIProvider.KIND_STABLE_DIFFUSION: {"images": True, "imageEditing": False},
    }
    result = {"chat": False, "tools": False, "reasoning": False, "verbosity": False, "images": False, "imageEditing": False}
    result.update(by_kind.get(provider.kind, {}))
    options = provider.options if isinstance(provider.options, dict) else {}
    for key, value in (options.get("capabilities") or {}).items():
        if key in result and isinstance(value, bool):
            result[key] = value
    if options.get("disableTools"):
        result["tools"] = False
    return result


def is_provider_configured(provider: AIProvider) -> bool:
    if provider.auth_strategy == AIProvider.AUTH_NONE:
        return bool(provider.base_url)
    return provider.has_secret


def serialize_provider(provider: AIProvider, *, include_management: bool) -> dict[str, Any]:
    options = provider.options if isinstance(provider.options, dict) else {}
    payload: dict[str, Any] = {
        "id": provider.id, "slug": provider.slug, "name": provider.name, "purpose": provider.purpose,
        "kind": provider.kind, "model": provider.model, "isEnabled": provider.is_enabled,
        "isDefault": provider.is_default, "description": str(options.get("description") or ""),
        "isConfigured": is_provider_configured(provider), "capabilities": provider_capabilities(provider),
    }
    if provider.purpose == AIProvider.PURPOSE_IMAGE:
        payload["imageGeneration"] = image_generation_options(provider)
    if include_management:
        payload.update(
            {
                "authStrategy": provider.auth_strategy, "baseUrl": provider.base_url,
                "hasSecret": provider.has_secret,
                "suggestedModels": options.get("suggestedModels") if isinstance(options.get("suggestedModels"), list) else [],
                "maxTokens": options.get("maxTokens"), "effort": options.get("effort", ""),
                "verbosity": options.get("verbosity", ""), "disableTools": bool(options.get("disableTools")),
                "order": provider.order,
            }
        )
    return payload


def usable_providers(purpose: str):
    return AIProvider.objects.filter(purpose=purpose, is_enabled=True, archived_at__isnull=True).order_by("-is_default", "order", "name")


def default_provider(purpose: str) -> AIProvider | None:
    return next((entry for entry in usable_providers(purpose) if is_provider_configured(entry)), None)


def accessible_agents(user, giocatore: Giocatore):
    role = effective_role(user, giocatore)
    return [
        agent for agent in AIAgentProfile.objects.select_related("provider").filter(is_enabled=True, archived_at__isnull=True)
        if has_minimum_role(role, agent.minimum_role)
    ]


def serialize_agent(agent: AIAgentProfile, user, giocatore: Giocatore, *, management: bool = False) -> dict[str, Any]:
    configured = set(agent.allowed_tools if isinstance(agent.allowed_tools, list) else [])
    tools = [tool for tool in AI_TOOLS if tool.name in configured and tool_is_available(tool, user, giocatore)]
    payload = {
        "id": agent.id, "slug": agent.slug, "name": agent.name, "description": agent.description,
        "minimumRole": agent.minimum_role, "providerId": agent.provider_id,
        "providerName": agent.provider.name if agent.provider else "",
        "model": agent.provider.model if agent.provider else "",
        "toolNames": [tool.name for tool in tools], "maxIterations": agent.max_iterations,
        "isEnabled": agent.is_enabled, "isDefault": agent.is_default,
    }
    if management:
        payload["instructions"] = agent.instructions
        payload["configuredToolNames"] = list(configured)
        payload["order"] = agent.order
    return payload


def tool_payload(tool) -> dict[str, Any]:
    return {
        "name": tool.name, "description": tool.description, "scope": tool.scope,
        "minimumRole": tool.minimum_role, "readOnly": tool.read_only,
    }


def ai_workspace_payload(user, giocatore: Giocatore) -> dict[str, Any]:
    chat = [entry for entry in usable_providers("chat") if is_provider_configured(entry)]
    images = [entry for entry in usable_providers("image") if is_provider_configured(entry)]
    agents = [
        agent for agent in accessible_agents(user, giocatore)
        if (agent.provider or default_provider("chat")) and is_provider_configured(agent.provider or default_provider("chat"))
    ]
    return {
        "agents": [serialize_agent(entry, user, giocatore) for entry in agents],
        "chatProviders": [serialize_provider(entry, include_management=False) for entry in chat],
        "imageProviders": [serialize_provider(entry, include_management=False) for entry in images],
        "tools": [tool_payload(tool) for tool in AI_TOOLS if tool_is_available(tool, user, giocatore)],
        "canManage": can_manage_ai(user, giocatore), "ready": bool(agents),
    }


def ai_management_payload(user, giocatore: Giocatore) -> dict[str, Any]:
    providers = AIProvider.objects.filter(archived_at__isnull=True).order_by("purpose", "order", "name")
    agents = AIAgentProfile.objects.select_related("provider").filter(archived_at__isnull=True).order_by("order", "name")
    return {
        "providers": [serialize_provider(entry, include_management=True) for entry in providers],
        "agents": [serialize_agent(entry, user, giocatore, management=True) for entry in agents],
        "kinds": [{"value": value, "label": label} for value, label in AIProvider.KIND_CHOICES],
        "purposes": [{"value": value, "label": label} for value, label in AIProvider.PURPOSE_CHOICES],
        "authStrategies": [{"value": value, "label": label} for value, label in AIProvider.AUTH_CHOICES],
        "roles": [{"value": value, "label": label} for value, label in Giocatore.ROLE_CHOICES],
        "tools": [tool_payload(tool) for tool in AI_TOOLS],
        "canManage": can_manage_ai(user, giocatore),
        "canManageCredentials": can_manage_ai_credentials(user, giocatore),
    }
