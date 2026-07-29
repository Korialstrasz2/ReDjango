"""Preset aggiornabili per provider e profilo agente iniziale."""

from .models import AIAgentProfile, AIProvider
from .tools import AI_TOOLS


AI_PROVIDER_PRESETS = [
    {
        "slug": "anthropic", "name": "Anthropic", "purpose": "chat", "kind": AIProvider.KIND_ANTHROPIC,
        "base_url": "", "model": "claude-opus-5",
        "models": ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"],
        "description": "API Messages di Anthropic, con uso nativo degli strumenti.",
        "order": 10, "is_default": True,
    },
    {
        "slug": "openai", "name": "OpenAI", "purpose": "chat", "kind": AIProvider.KIND_OPENAI_RESPONSES,
        "base_url": "https://api.openai.com/v1", "model": "gpt-5.6-sol",
        "models": ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"],
        "description": "OpenAI Responses API, adatta a ragionamento, strumenti e flussi agentici.",
        "order": 20, "is_default": False,
    },
    {
        "slug": "deepseek", "name": "DeepSeek", "purpose": "chat", "kind": AIProvider.KIND_OPENAI_COMPATIBLE,
        "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "description": "Chat Completions compatibile OpenAI; le capacità dipendono dal modello.",
        "order": 30, "is_default": False,
    },
    {
        "slug": "locale", "name": "Modello locale", "purpose": "chat", "kind": AIProvider.KIND_OPENAI_COMPATIBLE,
        "auth_strategy": AIProvider.AUTH_NONE, "base_url": "http://127.0.0.1:11434/v1", "model": "",
        "models": [], "description": "Endpoint locale compatibile OpenAI, per esempio Ollama o LM Studio.",
        "order": 40, "is_default": False, "is_enabled": False,
    },
    {
        "slug": "openai-immagini", "name": "Immagini OpenAI", "purpose": "image", "kind": AIProvider.KIND_OPENAI_IMAGE,
        "base_url": "https://api.openai.com/v1", "model": "gpt-image-2",
        "models": ["gpt-image-2", "gpt-image-1"],
        "description": "Generazione immagini OpenAI. La modifica da immagine resta in lavorazione.",
        "order": 10, "is_default": True,
    },
    {
        "slug": "stable-diffusion", "name": "Stable Diffusion locale", "purpose": "image",
        "kind": AIProvider.KIND_STABLE_DIFFUSION, "auth_strategy": AIProvider.AUTH_NONE,
        "base_url": "http://127.0.0.1:7860", "model": "", "models": [],
        "description": "API AUTOMATIC1111 locale. L'integrazione ComfyUI resta in lavorazione.",
        "order": 20, "is_default": False, "is_enabled": False,
    },
]

AI_IMAGE_SIZES = [
    {"value": "1024x1024", "label": "Quadrata 1024"},
    {"value": "1024x1536", "label": "Verticale 1024x1536"},
    {"value": "1536x1024", "label": "Orizzontale 1536x1024"},
]
AI_IMAGE_QUALITIES = [
    {"value": "low", "label": "Bassa"},
    {"value": "medium", "label": "Media"},
    {"value": "high", "label": "Alta"},
]


def seed_ai_providers() -> int:
    """Crea i preset e aggiorna solo metadata e vecchi default riconoscibili."""

    touched = 0
    for preset in AI_PROVIDER_PRESETS:
        defaults = {
            "name": preset["name"], "purpose": preset["purpose"], "kind": preset["kind"],
            "auth_strategy": preset.get("auth_strategy", AIProvider.AUTH_API_KEY),
            "base_url": preset["base_url"], "model": preset["model"],
            "options": {"description": preset["description"], "suggestedModels": preset["models"]},
            "is_enabled": preset.get("is_enabled", True), "is_default": preset["is_default"],
            "order": preset["order"], "metadata": {"seed_kind": "ai_provider"},
        }
        provider, created = AIProvider.objects.get_or_create(slug=preset["slug"], defaults=defaults)
        if created:
            touched += 1
            continue
        options = dict(provider.options) if isinstance(provider.options, dict) else {}
        options.update({"description": preset["description"], "suggestedModels": preset["models"]})
        provider.options = options
        fields = ["options", "updated_at"]
        if preset["slug"] == "openai" and provider.kind == AIProvider.KIND_OPENAI_COMPATIBLE and provider.model == "gpt-5.2":
            provider.kind = AIProvider.KIND_OPENAI_RESPONSES
            provider.model = "gpt-5.6-sol"
            fields.extend(["kind", "model"])
        if preset["slug"] == "openai-immagini" and provider.model == "gpt-image-1":
            provider.model = "gpt-image-2"
            fields.append("model")
        provider.save(update_fields=fields)

    _, created = AIAgentProfile.objects.get_or_create(
        slug="assistente-campagna",
        defaults={
            "name": "Assistente campagna",
            "description": "Ricerca e spiega dati della campagna usando soltanto strumenti di lettura.",
            "instructions": "Aiuta giocatori e Master a capire personaggi, oggetti, regole e stato della campagna. Indica in modo naturale quali dati hai consultato.",
            "minimum_role": "user",
            "provider": None,
            "allowed_tools": [tool.name for tool in AI_TOOLS],
            "max_iterations": 6,
            "is_enabled": True,
            "is_default": True,
            "metadata": {"seed_kind": "ai_agent"},
        },
    )
    return touched + int(created)
