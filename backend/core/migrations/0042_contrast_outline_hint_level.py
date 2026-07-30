from django.db import migrations


SETTING_KEY = "accessibility.contrast_outline"


def forwards(apps, schema_editor):
    SettingDefinition = apps.get_model("core", "SettingDefinition")
    definition = SettingDefinition.objects.filter(key=SETTING_KEY).first()
    if definition is None:
        return
    definition.choices = [
        {"value": "off", "label": "Nessuno"},
        {"value": "hint", "label": "Accennato"},
        {"value": "soft", "label": "Sottile"},
        {"value": "strong", "label": "Marcato"},
    ]
    definition.save(update_fields=["choices"])


def backwards(apps, schema_editor):
    SettingDefinition = apps.get_model("core", "SettingDefinition")
    definition = SettingDefinition.objects.filter(key=SETTING_KEY).first()
    if definition is None:
        return
    definition.choices = [
        {"value": "off", "label": "Nessuno"},
        {"value": "soft", "label": "Sottile"},
        {"value": "strong", "label": "Marcato"},
    ]
    definition.save(update_fields=["choices"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0041_accessory_profiles"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
