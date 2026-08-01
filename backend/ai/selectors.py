"""Proiezioni AI verso la SPA; nessun segreto lascia mai il backend."""

from __future__ import annotations

from typing import Any

from backend.core.models import Giocatore
from backend.core.security import effective_role, get_or_create_giocatore_for_user, has_minimum_role

from .defaults import AI_IMAGE_SIZES, image_generation_options
from .models import AIAgentProfile, AIConversation, AIProvider
from .npc_config import npc_generation_config
from .tools import AI_TOOLS, tool_is_available


PORTRAIT_QUALITY_LABELS = (
    ("low", "Bassa · la più economica"),
    ("medium", "Media"),
    ("high", "Alta · la più costosa"),
)


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


def provider_model_metadata(provider: AIProvider) -> dict[str, Any] | None:
    return next(
        (
            entry for entry in (provider.model_catalog if isinstance(provider.model_catalog, list) else [])
            if isinstance(entry, dict) and entry.get("id") == provider.model
        ),
        None,
    )


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
    selected = provider_model_metadata(provider)
    if selected and isinstance(selected.get("capabilities"), dict):
        for key, value in selected["capabilities"].items():
            if key in result and isinstance(value, bool):
                result[key] = value
    if options.get("disableTools"):
        result["tools"] = False
    return result


def provider_can_fetch_models(provider: AIProvider) -> bool:
    endpoint_ready = provider.kind == AIProvider.KIND_ANTHROPIC or bool(provider.base_url)
    credential_ready = provider.auth_strategy == AIProvider.AUTH_NONE or provider.has_secret
    return endpoint_ready and credential_ready


def provider_configuration_issues(provider: AIProvider) -> list[str]:
    issues: list[str] = []
    if provider.kind != AIProvider.KIND_ANTHROPIC and not provider.base_url:
        issues.append("Manca l'indirizzo API.")
    if provider.auth_strategy != AIProvider.AUTH_NONE and not provider.has_secret:
        issues.append("Manca la chiave API.")
    if provider.kind != AIProvider.KIND_STABLE_DIFFUSION and not provider.model:
        issues.append("Manca il modello.")
    if not provider.is_enabled:
        issues.append("Il provider è disattivato.")
    return issues


def provider_configuration_schema(provider: AIProvider) -> dict[str, Any]:
    capabilities = provider_capabilities(provider)
    selected = provider_model_metadata(provider) or {}
    context_window = selected.get("contextWindow")
    maximum_tokens = min(128000, context_window) if isinstance(context_window, int) and context_window > 0 else 128000
    return {
        "maxTokens": {"minimum": 256, "maximum": maximum_tokens},
        "reasoningEfforts": (["none", "low", "medium", "high", "xhigh", "max"] if capabilities["reasoning"] else []),
        "verbosityOptions": (["low", "medium", "high"] if capabilities["verbosity"] else []),
    }


def is_provider_configured(provider: AIProvider) -> bool:
    return not [issue for issue in provider_configuration_issues(provider) if "disattivato" not in issue]


def is_provider_ready(provider: AIProvider) -> bool:
    return not provider_configuration_issues(provider)


def serialize_provider(provider: AIProvider, *, include_management: bool) -> dict[str, Any]:
    options = provider.options if isinstance(provider.options, dict) else {}
    payload: dict[str, Any] = {
        "id": provider.id, "slug": provider.slug, "name": provider.name, "purpose": provider.purpose,
        "kind": provider.kind, "model": provider.model, "isEnabled": provider.is_enabled,
        "isDefault": provider.is_default, "description": str(options.get("description") or ""),
        "isConfigured": is_provider_configured(provider), "isReady": is_provider_ready(provider),
        "configurationIssues": provider_configuration_issues(provider),
        "capabilities": provider_capabilities(provider),
    }
    if provider.purpose == AIProvider.PURPOSE_IMAGE:
        payload["imageGeneration"] = image_generation_options(provider)
    if include_management:
        payload.update(
            {
                "authStrategy": provider.auth_strategy, "baseUrl": provider.base_url,
                "hasSecret": provider.has_secret,
                "suggestedModels": options.get("suggestedModels") if isinstance(options.get("suggestedModels"), list) else [],
                "modelCatalog": provider.model_catalog if isinstance(provider.model_catalog, list) else [],
                "modelCatalogRefreshedAt": provider.model_catalog_refreshed_at.isoformat() if provider.model_catalog_refreshed_at else "",
                "canFetchModels": provider_can_fetch_models(provider),
                "configurationSchema": provider_configuration_schema(provider),
                "maxTokens": options.get("maxTokens"), "effort": options.get("effort", ""),
                "verbosity": options.get("verbosity", ""), "disableTools": bool(options.get("disableTools")),
                "order": provider.order,
            }
        )
    return payload


def usable_providers(purpose: str):
    return AIProvider.objects.filter(purpose=purpose, is_enabled=True, archived_at__isnull=True).order_by("-is_default", "order", "name")


def default_provider(purpose: str) -> AIProvider | None:
    return next((entry for entry in usable_providers(purpose) if is_provider_ready(entry)), None)


def resolved_agent_provider(agent: AIAgentProfile) -> tuple[AIProvider | None, list[str]]:
    if agent.provider_id:
        issues = provider_configuration_issues(agent.provider)
        return (agent.provider if not issues else None), issues
    provider = default_provider(AIProvider.PURPOSE_CHAT)
    return (provider, []) if provider else (None, ["Nessun provider chat predefinito è pronto."])


def accessible_agents(user, giocatore: Giocatore):
    role = effective_role(user, giocatore)
    return [
        agent for agent in AIAgentProfile.objects.select_related("provider").filter(is_enabled=True, archived_at__isnull=True)
        if has_minimum_role(role, agent.minimum_role)
    ]


def serialize_agent(agent: AIAgentProfile, user, giocatore: Giocatore, *, management: bool = False) -> dict[str, Any]:
    configured = set(agent.allowed_tools if isinstance(agent.allowed_tools, list) else [])
    tools = [tool for tool in AI_TOOLS if tool.name in configured and tool_is_available(tool, user, giocatore)]
    effective_provider, availability_issues = resolved_agent_provider(agent)
    payload = {
        "id": agent.id, "slug": agent.slug, "name": agent.name, "description": agent.description,
        "minimumRole": agent.minimum_role, "providerId": agent.provider_id,
        "providerName": agent.provider.name if agent.provider else "",
        "model": agent.provider.model if agent.provider else "",
        "effectiveProviderName": effective_provider.name if effective_provider else "",
        "effectiveModel": effective_provider.model if effective_provider else "",
        "isReady": effective_provider is not None,
        "availabilityIssues": availability_issues,
        "toolNames": [tool.name for tool in tools], "maxIterations": agent.max_iterations,
        "routingMode": agent.routing_mode,
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
    chat = [entry for entry in usable_providers("chat") if is_provider_ready(entry)]
    images = [entry for entry in usable_providers("image") if is_provider_ready(entry)]
    agents = [
        agent for agent in accessible_agents(user, giocatore)
        if resolved_agent_provider(agent)[0] is not None
    ]
    conversations = AIConversation.objects.filter(user=user, archived_at__isnull=True).select_related("agent")[:3]
    return {
        "agents": [serialize_agent(entry, user, giocatore) for entry in agents],
        "chatProviders": [serialize_provider(entry, include_management=False) for entry in chat],
        "imageProviders": [serialize_provider(entry, include_management=False) for entry in images],
        "tools": [tool_payload(tool) for tool in AI_TOOLS if tool_is_available(tool, user, giocatore)],
        "conversations": [serialize_conversation(entry) for entry in conversations],
        "canManage": can_manage_ai(user, giocatore), "ready": bool(agents),
        "readiness": {"chat": bool(agents), "images": bool(images)},
        "runPolicy": {"maximumSeconds": 120, "maximumTokens": 64000, "maximumToolCalls": 24},
        "npcGeneration": npc_generation_config(),
    }


def serialize_conversation(conversation: AIConversation) -> dict[str, Any]:
    return {
        "id": conversation.id,
        "title": conversation.title,
        "agentId": conversation.agent_id,
        "history": conversation.history if isinstance(conversation.history, list) else [],
        "bubbles": conversation.transcript if isinstance(conversation.transcript, list) else [],
        "updatedAt": conversation.updated_at.isoformat(),
    }


def ai_management_payload(user, giocatore: Giocatore) -> dict[str, Any]:
    providers = AIProvider.objects.filter(archived_at__isnull=True).order_by("purpose", "order", "name")
    agents = AIAgentProfile.objects.select_related("provider").filter(archived_at__isnull=True).order_by("order", "name")
    can_manage_credentials = can_manage_ai_credentials(user, giocatore)
    serialized_providers = [serialize_provider(entry, include_management=True) for entry in providers]
    if not can_manage_credentials:
        for provider in serialized_providers:
            provider["baseUrl"] = ""
    return {
        "providers": serialized_providers,
        "agents": [serialize_agent(entry, user, giocatore, management=True) for entry in agents],
        "kinds": [{"value": value, "label": label} for value, label in AIProvider.KIND_CHOICES],
        "purposes": [{"value": value, "label": label} for value, label in AIProvider.PURPOSE_CHOICES],
        "authStrategies": [{"value": value, "label": label} for value, label in AIProvider.AUTH_CHOICES],
        "roles": [{"value": value, "label": label} for value, label in Giocatore.ROLE_CHOICES],
        "routingModes": [{"value": value, "label": label} for value, label in AIAgentProfile.ROUTING_CHOICES],
        "tools": [tool_payload(tool) for tool in AI_TOOLS],
        "canManage": can_manage_ai(user, giocatore),
        "canManageCredentials": can_manage_credentials,
        "npcGeneration": npc_generation_config(),
        "portraitQualities": [{"value": value, "label": label} for value, label in PORTRAIT_QUALITY_LABELS],
        "imageSizes": [dict(entry) for entry in AI_IMAGE_SIZES],
    }
