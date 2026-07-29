from django.db import migrations


MODEL_CATALOGUES = {
    "anthropic": [
        "claude-opus-4-1-20250805",
        "claude-opus-4-20250514",
        "claude-sonnet-4-20250514",
        "claude-3-7-sonnet-20250219",
        "claude-3-5-haiku-20241022",
    ],
    "openai": [
        "gpt-5.1", "gpt-5", "gpt-5-mini", "gpt-5-nano", "gpt-4.1",
        "gpt-4.1-mini", "gpt-4.1-nano", "o3", "o4-mini",
    ],
    "deepseek": ["deepseek-v4-flash", "deepseek-v4-pro"],
    "openrouter": [
        "openrouter/auto", "~openai/gpt-latest", "anthropic/claude-opus-4.5",
        "anthropic/claude-sonnet-4.5", "openai/gpt-5.1",
        "google/gemini-3.1-pro-preview", "deepseek/deepseek-v3.2",
        "meta-llama/llama-4-maverick", "mistralai/mistral-large-3",
    ],
    "locale": ["llama3.3", "qwen3", "qwen2.5", "gemma3", "mistral", "mixtral", "deepseek-r1", "phi4", "gpt-oss"],
    "openai-immagini": ["gpt-image-1", "gpt-image-1-mini"],
}

DEFAULT_REPLACEMENTS = {
    "anthropic": ({"claude-opus-5"}, "claude-opus-4-1-20250805"),
    "openai": ({"gpt-5.6-sol"}, "gpt-5.1"),
    "deepseek": ({"deepseek-chat", "deepseek-reasoner"}, "deepseek-v4-flash"),
    "openai-immagini": ({"gpt-image-2"}, "gpt-image-1"),
}


def refresh_model_catalogues(apps, schema_editor):
    Provider = apps.get_model("ai", "AIProvider")
    for slug, models in MODEL_CATALOGUES.items():
        provider = Provider.objects.filter(slug=slug).first()
        if provider is None:
            continue
        options = dict(provider.options or {})
        options["suggestedModels"] = models
        fields = ["options"]
        legacy_models, replacement = DEFAULT_REPLACEMENTS.get(slug, (set(), ""))
        if provider.model in legacy_models:
            provider.model = replacement
            fields.append("model")
        provider.options = options
        provider.save(update_fields=fields)


class Migration(migrations.Migration):
    dependencies = [("ai", "0003_seed_openrouter_provider")]

    operations = [migrations.RunPython(refresh_model_catalogues, migrations.RunPython.noop)]
