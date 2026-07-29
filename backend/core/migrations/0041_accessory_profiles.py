import django.db.models.deletion
from django.db import migrations, models


def seed_profiles_and_assign_units(apps, schema_editor):
    from backend.combat.accessory_profiles import (
        ACCESSORY_PROFILE_DEFAULTS,
        recommended_accessory_profile_key,
    )

    AccessoryProfile = apps.get_model("core", "AccessoryProfile")
    Unit = apps.get_model("core", "Unit")
    profiles = {}
    for key, definition in ACCESSORY_PROFILE_DEFAULTS.items():
        profiles[key], _created = AccessoryProfile.objects.update_or_create(
            key=key,
            defaults={
                "nome": definition["name"],
                "descrizione": definition["description"],
                "rules": definition["rules"],
                "metadata": {"source": "elder-django-accessory-profiles-v1"},
            },
        )
    for unit in Unit.objects.filter(accessory_profile__isnull=True):
        rules = unit.generation_rules if isinstance(unit.generation_rules, dict) else {}
        if rules.get("kind") != "humanoid":
            continue
        tags = unit.archetipo_tags if isinstance(unit.archetipo_tags, dict) else {}
        key = recommended_accessory_profile_key(
            str(rules.get("coreKey") or ""),
            tags,
            unit.nome,
        )
        unit.accessory_profile = profiles[key]
        unit.save(update_fields=["accessory_profile", "updated_at"])


def remove_seeded_profiles(apps, schema_editor):
    AccessoryProfile = apps.get_model("core", "AccessoryProfile")
    Unit = apps.get_model("core", "Unit")
    seeded = AccessoryProfile.objects.filter(
        metadata__source="elder-django-accessory-profiles-v1"
    )
    Unit.objects.filter(accessory_profile__in=seeded).update(accessory_profile=None)
    seeded.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0040_drop_skill_migration_review"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccessoryProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("archived_at", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("key", models.SlugField(max_length=80, unique=True)),
                ("nome", models.CharField(max_length=120, unique=True)),
                ("descrizione", models.TextField(blank=True)),
                ("rules", models.JSONField(blank=True, default=dict)),
                ("notes", models.TextField(blank=True)),
            ],
            options={
                "ordering": ["nome"],
            },
        ),
        migrations.AddField(
            model_name="unit",
            name="accessory_profile",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="units",
                to="core.accessoryprofile",
            ),
        ),
        migrations.RunPython(seed_profiles_and_assign_units, remove_seeded_profiles),
    ]
