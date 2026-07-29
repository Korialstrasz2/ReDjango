from django.db import migrations


def configure_gpt_image_2(apps, schema_editor):
    Provider = apps.get_model("ai", "AIProvider")
    provider = Provider.objects.filter(slug="openai-immagini").first()
    if provider is None:
        return

    options = dict(provider.options or {})
    options["suggestedModels"] = ["gpt-image-2", "gpt-image-2-2026-04-21"]
    fields = ["options"]
    if provider.model == "gpt-image-1":
        provider.model = "gpt-image-2"
        fields.append("model")
    provider.options = options
    provider.save(update_fields=fields)


class Migration(migrations.Migration):
    dependencies = [("ai", "0004_refresh_provider_model_catalogues")]

    operations = [migrations.RunPython(configure_gpt_image_2, migrations.RunPython.noop)]
