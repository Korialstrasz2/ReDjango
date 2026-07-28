from django.db import migrations


SETTING_KEY = "accessibility.text_color_aware_outline"


def add_setting(apps, schema_editor):
    SettingDefinition = apps.get_model("core", "SettingDefinition")
    SettingDefinition.objects.get_or_create(
        key=SETTING_KEY,
        defaults={
            "label": "Contrasto adattivo al colore del testo",
            "category": "accessibilità",
            "description": (
                "Calcola il bordo bianco o nero dal colore effettivo di ogni testo, "
                "invece di usare un solo colore per tutto il tema."
            ),
            "minimum_role": "user",
            "value_type": "bool",
            "default_value": False,
            "value": False,
            "choices": [],
            "user_customizable": True,
            "master_customizable": True,
            "ui_token": "text-color-aware-outline",
            "active": True,
            "order": 30,
            "metadata": {
                "seed_kind": "setting_definition",
                "seed_version": "12",
            },
        },
    )


def remove_setting(apps, schema_editor):
    SettingDefinition = apps.get_model("core", "SettingDefinition")
    SettingDefinition.objects.filter(key=SETTING_KEY).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0030_negozio_generation_profile_key"),
    ]

    operations = [
        migrations.RunPython(add_setting, remove_setting),
    ]
