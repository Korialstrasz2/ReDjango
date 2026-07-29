from django.db import migrations


def seed_effect_presets(apps, schema_editor):
    from backend.characters.effect_preset_defaults import DEFAULT_EFFECT_PRESETS

    EffettoPreset = apps.get_model("characters", "EffettoPreset")
    for definition in DEFAULT_EFFECT_PRESETS:
        EffettoPreset.objects.update_or_create(
            nome=definition["name"],
            defaults={
                "descrizione": definition["description"],
                "origine": definition["origin"],
                "icona": definition["icon"],
                "temporaneo": True,
                "categoria": definition["category"],
                "ordine": definition["order"],
                "operazioni": definition["operations"],
            },
        )


def remove_effect_presets(apps, schema_editor):
    from backend.characters.effect_preset_defaults import DEFAULT_EFFECT_PRESETS

    EffettoPreset = apps.get_model("characters", "EffettoPreset")
    EffettoPreset.objects.filter(
        nome__in=[definition["name"] for definition in DEFAULT_EFFECT_PRESETS]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("characters", "0026_effettopreset")]

    operations = [migrations.RunPython(seed_effect_presets, remove_effect_presets)]
