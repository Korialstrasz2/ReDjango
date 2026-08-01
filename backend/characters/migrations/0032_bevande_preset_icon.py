"""Point the Bevande presets at an icon that actually has artwork.

`pozione` is a valid icon value but ships no asset, so `_effect_icon_image_url`
resolved it to an empty string and every seeded Bevande preset failed
`EffectPresetTests.test_seeded_presets_are_all_temporary_and_expose_an_icon`.
`cibo` is the icon the Cibo and Bagni presets already use, and it has a PNG.
"""

from django.db import migrations

OLD_ICON = "pozione"
NEW_ICON = "cibo"
CATEGORY = "Bevande"


def set_icon(apps, schema_editor):
    EffettoPreset = apps.get_model("characters", "EffettoPreset")
    EffettoPreset.objects.filter(categoria=CATEGORY, icona=OLD_ICON).update(icona=NEW_ICON)


def restore_icon(apps, schema_editor):
    EffettoPreset = apps.get_model("characters", "EffettoPreset")
    EffettoPreset.objects.filter(categoria=CATEGORY, icona=NEW_ICON).update(icona=OLD_ICON)


class Migration(migrations.Migration):
    dependencies = [("characters", "0031_seed_bevande_presets")]

    operations = [migrations.RunPython(set_icon, restore_icon)]
