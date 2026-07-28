from django.db import migrations


SETTING_KEY = "accessibility.contrast_outline"


def _convert(apps, forward: bool):
    SettingDefinition = apps.get_model("core", "SettingDefinition")
    SettingOverride = apps.get_model("core", "SettingOverride")

    definition = SettingDefinition.objects.filter(key=SETTING_KEY).first()
    if definition is None:
        return

    if forward:
        definition.value_type = "select"
        definition.default_value = "off"
        definition.choices = [
            {"value": "off", "label": "Nessuno"},
            {"value": "soft", "label": "Sottile"},
            {"value": "strong", "label": "Marcato"},
        ]
        if isinstance(definition.value, bool) or definition.value is None:
            definition.value = "strong" if definition.value else "off"
    else:
        definition.value_type = "bool"
        definition.default_value = False
        definition.choices = []
        definition.value = definition.value in {"soft", "strong"}
    definition.save()

    for override in SettingOverride.objects.filter(setting=definition):
        if forward:
            override.value = "strong" if override.value else "off"
        else:
            override.value = override.value in {"soft", "strong"}
        override.save(update_fields=["value"])


def forwards(apps, schema_editor):
    _convert(apps, forward=True)


def backwards(apps, schema_editor):
    _convert(apps, forward=False)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0026_theme_lore_background_theme_market_background_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
