from django.db import migrations


def seed_openrouter(apps, schema_editor):
    Provider = apps.get_model("ai", "AIProvider")
    Provider.objects.get_or_create(
        slug="openrouter",
        defaults={
            "name": "OpenRouter",
            "purpose": "chat",
            "kind": "openai_compatible",
            "auth_strategy": "api_key",
            "base_url": "https://openrouter.ai/api/v1",
            "model": "~openai/gpt-latest",
            "options": {
                "description": "Catalogo multi-provider OpenRouter tramite Chat Completions compatibile OpenAI. Inserisci qualsiasi model slug OpenRouter.",
                "suggestedModels": ["~openai/gpt-latest"],
            },
            "is_enabled": False,
            "is_default": False,
            "order": 40,
            "metadata": {"seed_kind": "ai_provider"},
        },
    )


class Migration(migrations.Migration):
    dependencies = [("ai", "0002_alter_aiprovider_kind_aiagentprofile")]

    operations = [migrations.RunPython(seed_openrouter, migrations.RunPython.noop)]
