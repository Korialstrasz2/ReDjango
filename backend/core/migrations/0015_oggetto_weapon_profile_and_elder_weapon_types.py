from django.db import migrations, models


def seed_elder_weapon_types(apps, schema_editor):
    TipoArma = apps.get_model("core", "TipoArma")
    from backend.core.weapon_presets import WEAPON_TYPE_PRESETS

    for preset in WEAPON_TYPE_PRESETS:
        weapon_type, _ = TipoArma.objects.get_or_create(nome=preset["name"])
        current_rules = weapon_type.rules if isinstance(weapon_type.rules, dict) else {}
        weapon_type.lunghezza = preset["length"]
        weapon_type.potenza = preset["power"]
        weapon_type.bonus_1 = preset["bonus1"]
        weapon_type.bonus_2 = preset["bonus2"]
        weapon_type.rules = {
            **current_rules,
            "source": "the_elder_django",
            "presetVersion": 1,
            "profile": preset["profile"],
        }
        weapon_type.save(update_fields=["lunghezza", "potenza", "bonus_1", "bonus_2", "rules", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [("core", "0014_archive_obsolete_skill_groups")]

    operations = [
        migrations.AddField(
            model_name="oggetto",
            name="weapon_profile",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(seed_elder_weapon_types, migrations.RunPython.noop),
    ]
