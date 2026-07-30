"""Preset aggiornabili per provider e profilo agente iniziale."""

from .models import AIAgentProfile, AIProvider
from .tools import AI_TOOLS


AI_PROVIDER_PRESETS = [
    {
        "slug": "anthropic", "name": "Anthropic", "purpose": "chat", "kind": AIProvider.KIND_ANTHROPIC,
        "base_url": "", "model": "claude-opus-4-1-20250805",
        "models": [
            "claude-opus-4-1-20250805", "claude-opus-4-20250514", "claude-sonnet-4-20250514",
            "claude-3-7-sonnet-20250219", "claude-3-5-haiku-20241022",
        ],
        "description": "API Messages di Anthropic, con uso nativo degli strumenti.",
        "order": 10, "is_default": True,
    },
    {
        "slug": "openai", "name": "OpenAI", "purpose": "chat", "kind": AIProvider.KIND_OPENAI_RESPONSES,
        "base_url": "https://api.openai.com/v1", "model": "gpt-5.1",
        "models": [
            "gpt-5.1", "gpt-5", "gpt-5-mini", "gpt-5-nano", "gpt-4.1",
            "gpt-4.1-mini", "gpt-4.1-nano", "o3", "o4-mini",
        ],
        "description": "OpenAI Responses API, adatta a ragionamento, strumenti e flussi agentici.",
        "order": 20, "is_default": False,
    },
    {
        "slug": "deepseek", "name": "DeepSeek", "purpose": "chat", "kind": AIProvider.KIND_OPENAI_COMPATIBLE,
        "base_url": "https://api.deepseek.com/v1", "model": "deepseek-v4-flash",
        "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
        "description": "Chat Completions compatibile OpenAI; le capacità dipendono dal modello.",
        "order": 30, "is_default": False,
    },
    {
        "slug": "openrouter", "name": "OpenRouter", "purpose": "chat", "kind": AIProvider.KIND_OPENAI_COMPATIBLE,
        "base_url": "https://openrouter.ai/api/v1", "model": "~openai/gpt-latest",
        "models": [
            "openrouter/auto", "~openai/gpt-latest", "anthropic/claude-opus-4.5",
            "anthropic/claude-sonnet-4.5", "openai/gpt-5.1",
            "google/gemini-3.1-pro-preview", "deepseek/deepseek-v3.2",
            "meta-llama/llama-4-maverick", "mistralai/mistral-large-3",
        ],
        "description": "Catalogo multi-provider OpenRouter tramite Chat Completions compatibile OpenAI. Inserisci qualsiasi model slug OpenRouter.",
        "order": 40, "is_default": False, "is_enabled": False,
    },
    {
        "slug": "locale", "name": "Modello locale", "purpose": "chat", "kind": AIProvider.KIND_OPENAI_COMPATIBLE,
        "auth_strategy": AIProvider.AUTH_NONE, "base_url": "http://127.0.0.1:11434/v1", "model": "",
        "models": ["llama3.3", "qwen3", "qwen2.5", "gemma3", "mistral", "mixtral", "deepseek-r1", "phi4", "gpt-oss"],
        "description": "Endpoint locale compatibile OpenAI, per esempio Ollama o LM Studio.",
        "order": 50, "is_default": False, "is_enabled": False,
    },
    {
        "slug": "openai-immagini", "name": "Immagini OpenAI", "purpose": "image", "kind": AIProvider.KIND_OPENAI_IMAGE,
        "base_url": "https://api.openai.com/v1", "model": "gpt-image-2",
        "models": ["gpt-image-2", "gpt-image-2-2026-04-21"],
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
    # 640x1024 sono esattamente 655.360 pixel: il minimo fatturabile di
    # gpt-image-2 e quindi il ritratto più economico ottenibile. Non esiste un
    # 512x512: sta sotto la soglia e l'API lo rifiuta.
    {"value": "640x1024", "label": "Ritratto 640x1024 (minimo)"},
    {"value": "1024x1024", "label": "Quadrata 1024"},
    {"value": "1024x1536", "label": "Verticale 1024x1536"},
    {"value": "1536x1024", "label": "Orizzontale 1536x1024"},
]
AI_IMAGE_QUALITIES = [
    {"value": "low", "label": "Bassa"},
    {"value": "medium", "label": "Media"},
    {"value": "high", "label": "Alta"},
]


def image_generation_options(provider: AIProvider) -> dict[str, object]:
    """Return only the resolution and quality options accepted by this tool."""

    options = provider.options if isinstance(provider.options, dict) else {}
    configured = options.get("imageGeneration")
    if isinstance(configured, dict):
        sizes = configured.get("sizes")
        qualities = configured.get("qualities")
        if isinstance(sizes, list) and isinstance(qualities, list) and sizes and qualities:
            return {
                "sizes": sizes,
                "qualities": qualities,
                "defaultSize": configured.get("defaultSize") or sizes[0]["value"],
                "defaultQuality": configured.get("defaultQuality") or qualities[0]["value"],
            }

    return {
        "sizes": AI_IMAGE_SIZES,
        "qualities": AI_IMAGE_QUALITIES,
        "defaultSize": "1024x1024",
        "defaultQuality": "medium",
    }


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
            provider.model = preset["model"]
            fields.extend(["kind", "model"])
        legacy_defaults = {
            "anthropic": {"claude-opus-5"},
            "openai": {"gpt-5.6-sol"},
            "deepseek": {"deepseek-chat", "deepseek-reasoner"},
            "openai-immagini": {"gpt-image-1"},
        }
        if provider.model in legacy_defaults.get(preset["slug"], set()):
            provider.model = preset["model"]
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
