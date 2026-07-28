"""Preset dei provider AI.

Sono soltanto punti di partenza: nome, endpoint e modello restano modificabili da
`/tools/ai`. Il modello indicato è il valore di default suggerito, non un vincolo.
"""

from .models import AIProvider


AI_PROVIDER_PRESETS = [
    {
        "slug": "anthropic",
        "name": "Anthropic",
        "purpose": AIProvider.PURPOSE_CHAT,
        "kind": AIProvider.KIND_ANTHROPIC,
        "base_url": "",
        "model": "claude-opus-5",
        "models": ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"],
        "description": "API Messages di Anthropic, con uso nativo degli strumenti.",
        "order": 10,
        "is_default": True,
    },
    {
        "slug": "openai",
        "name": "OpenAI",
        "purpose": AIProvider.PURPOSE_CHAT,
        "kind": AIProvider.KIND_OPENAI_COMPATIBLE,
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-5.2",
        "models": ["gpt-5.2", "gpt-5.1", "gpt-5-mini"],
        "description": "API compatibile OpenAI. Richiede una chiave della piattaforma, non l'account ChatGPT.",
        "order": 20,
        "is_default": False,
    },
    {
        "slug": "deepseek",
        "name": "DeepSeek",
        "purpose": AIProvider.PURPOSE_CHAT,
        "kind": AIProvider.KIND_OPENAI_COMPATIBLE,
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "description": "Compatibile OpenAI. I modelli di tipo «reasoner» possono non supportare gli strumenti.",
        "order": 30,
        "is_default": False,
    },
    {
        "slug": "locale",
        "name": "Modello locale",
        "purpose": AIProvider.PURPOSE_CHAT,
        "kind": AIProvider.KIND_OPENAI_COMPATIBLE,
        "auth_strategy": AIProvider.AUTH_NONE,
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "",
        "models": [],
        "description": "Qualsiasi server compatibile OpenAI in locale, per esempio Ollama o LM Studio.",
        "order": 40,
        "is_default": False,
        "is_enabled": False,
    },
    {
        "slug": "openai-immagini",
        "name": "Immagini OpenAI",
        "purpose": AIProvider.PURPOSE_IMAGE,
        "kind": AIProvider.KIND_OPENAI_IMAGE,
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-image-1",
        "models": ["gpt-image-1"],
        "description": "Generazione e modifica di immagini con l'ultimo modello immagini di OpenAI.",
        "order": 10,
        "is_default": True,
    },
    {
        "slug": "stable-diffusion",
        "name": "Stable Diffusion locale",
        "purpose": AIProvider.PURPOSE_IMAGE,
        "kind": AIProvider.KIND_STABLE_DIFFUSION,
        "auth_strategy": AIProvider.AUTH_NONE,
        "base_url": "http://127.0.0.1:7860",
        "model": "",
        "models": [],
        "description": "API di AUTOMATIC1111 o ComfyUI in esecuzione sulla tua macchina.",
        "order": 20,
        "is_default": False,
        "is_enabled": False,
    },
]

# Dimensioni offerte dall'interfaccia. Restano una picklist perché ogni provider
# accetta un insieme chiuso di formati.
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
    """Crea i provider mancanti senza toccare quelli già configurati."""

    touched = 0
    for preset in AI_PROVIDER_PRESETS:
        defaults = {
            "name": preset["name"],
            "purpose": preset["purpose"],
            "kind": preset["kind"],
            "auth_strategy": preset.get("auth_strategy", AIProvider.AUTH_API_KEY),
            "base_url": preset["base_url"],
            "model": preset["model"],
            "options": {
                "description": preset["description"],
                "suggestedModels": preset["models"],
            },
            "is_enabled": preset.get("is_enabled", True),
            "is_default": preset["is_default"],
            "order": preset["order"],
            "metadata": {"seed_kind": "ai_provider"},
        }
        _, created = AIProvider.objects.get_or_create(slug=preset["slug"], defaults=defaults)
        if created:
            touched += 1
    return touched
