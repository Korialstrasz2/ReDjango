"""Seed the "Bevande" preset category from the 2026-08-01 special-rules pass.

These are the 25 drink/drug presets curated alongside the last "speciale"
batch (see `Builder_docs/ITEM_SPECIAL_RULES_REVIEW_GUIDE.md`). Scoped to just
the new names, mirroring 0028's targeted style rather than 0027's full-table
seed.
"""

from django.db import migrations

BEVANDE_PRESET_NAMES = (
    "Sbornia",
    "Idromele Nordico",
    "Vino Surilie",
    "Shein",
    "Birra Rovo Nero",
    "Brandy Coloviano",
    "Vino delle Summerset",
    "Sweet Roll",
    "Vino Economico",
    "Vino Pregiato",
    "Distillato di Marshmarrow",
    "Distillato Nord",
    "Skooma",
    "Skooma (contraccolpo)",
    "Zucchero Lunare",
    "Zucchero Lunare (contraccolpo)",
    "Zucchero Lunare (khajiit)",
    "Vino Sangue di Sanguine",
    "Vino Sangue di Sanguine (conversione)",
    "Flin",
    "Flin (contraccolpo)",
    "Liquore Lacrime di Sanguine",
    "Cognac Bretone",
    "Mazte",
    "Distillato Del Tempio di Sanguine",
)


def seed_bevande_presets(apps, schema_editor):
    from backend.characters.effect_preset_defaults import DEFAULT_EFFECT_PRESETS

    EffettoPreset = apps.get_model("characters", "EffettoPreset")
    by_name = {definition["name"]: definition for definition in DEFAULT_EFFECT_PRESETS}
    for name in BEVANDE_PRESET_NAMES:
        definition = by_name[name]
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


def remove_bevande_presets(apps, schema_editor):
    EffettoPreset = apps.get_model("characters", "EffettoPreset")
    EffettoPreset.objects.filter(nome__in=BEVANDE_PRESET_NAMES).delete()


class Migration(migrations.Migration):
    dependencies = [("characters", "0030_personaggio_caratteristica_preferita")]

    operations = [migrations.RunPython(seed_bevande_presets, remove_bevande_presets)]
