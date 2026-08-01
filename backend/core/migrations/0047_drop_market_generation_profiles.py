"""Retire the Mercato generation profiles; shop level is the only wealth dial.

Profiles (povero/standard/ricco/mercato-speciale) layered a second quantity,
price and rarity multiplier on top of the shop's own level and type. Level
1-10 already expresses how rich a shop is, so the profile was a parallel axis
that had to be kept in sync by hand. Rarity now comes solely from
`mercato.generator_rules`, whose distribution the profiles were derived from
anyway.

`quantityScale` lands in the same rules blob: Elder applied a hard-coded 1.55
global size factor that the port dropped, and the profiles' quantityMultiplier
was the only way to change stock size without editing every shop type. It
defaults to 1, so shop sizes are unchanged until a master tunes it.
"""

from django.db import migrations, models

PROFILES_KEY = "mercato.generation_profiles"
RULES_KEY = "mercato.generator_rules"

# Historical value, restored on reverse. Matches the pre-removal seed.
LEGACY_PROFILES = {
    "version": 1,
    "defaultProfileKey": "standard",
    "profiles": [
        {"key": "povero", "label": "Povero", "enabled": True, "quantityMultiplier": .6, "priceMultiplier": .9, "rarityProbabilities": {"1": .845, "2": .1, "3": .04, "4": .01, "5": .005}},
        {"key": "standard", "label": "Standard", "enabled": True, "quantityMultiplier": 1, "priceMultiplier": 1, "rarityProbabilities": {"1": .675, "2": .15, "3": .1, "4": .05, "5": .025}},
        {"key": "ricco", "label": "Ricco", "enabled": True, "quantityMultiplier": 1.35, "priceMultiplier": 1.1, "rarityProbabilities": {"1": .46, "2": .25, "3": .17, "4": .08, "5": .04}},
        {"key": "mercato-speciale", "label": "Mercato speciale", "enabled": True, "quantityMultiplier": 1, "priceMultiplier": 1.25, "rarityProbabilities": {"1": .275, "2": .25, "3": .25, "4": .15, "5": .075}},
    ],
}


def _set_quantity_scale(apps, present: bool):
    SettingDefinition = apps.get_model("core", "SettingDefinition")
    setting = SettingDefinition.objects.filter(key=RULES_KEY).first()
    if setting is None:
        return
    fields = []
    for field in ("value", "default_value"):
        container = getattr(setting, field)
        if not isinstance(container, dict):
            continue
        if present and "quantityScale" not in container:
            container["quantityScale"] = 1
            fields.append(field)
        elif not present and "quantityScale" in container:
            del container["quantityScale"]
            fields.append(field)
    if fields:
        setting.save(update_fields=fields)


def forwards(apps, schema_editor):
    SettingDefinition = apps.get_model("core", "SettingDefinition")
    SettingDefinition.objects.filter(key=PROFILES_KEY).delete()
    _set_quantity_scale(apps, present=True)


def backwards(apps, schema_editor):
    SettingDefinition = apps.get_model("core", "SettingDefinition")
    SettingDefinition.objects.update_or_create(
        key=PROFILES_KEY,
        defaults={
            "label": "Profili di generazione Mercato",
            "category": "mercato",
            "description": "Preset riutilizzabili per quantità, rarità e prezzi delle scorte.",
            "minimum_role": "admin",
            "value_type": "json",
            "default_value": LEGACY_PROFILES,
            "choices": [],
            "user_customizable": False,
            "master_customizable": False,
            "order": 40,
            "active": True,
        },
    )
    _set_quantity_scale(apps, present=False)


class Migration(migrations.Migration):
    dependencies = [("core", "0046_shop_types_elder_weapon_ranks")]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(model_name="negozio", name="generation_profile_key"),
    ]
