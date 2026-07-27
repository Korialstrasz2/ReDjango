from django.db import migrations


PROFILE_NAME = "Formule_base"
CONFIG_KEY = "quick_stat_adjustments"


def use_elder_quick_stat_adjustments(apps, schema_editor):
    GlobalModifiers = apps.get_model("core", "GlobalModifiers")
    profile = GlobalModifiers.objects.filter(
        name=PROFILE_NAME,
        archived_at__isnull=True,
    ).first()
    if profile is None:
        return

    value_string = (
        dict(profile.value_string)
        if isinstance(profile.value_string, dict)
        else {}
    )
    configured = value_string.get(CONFIG_KEY, {})
    configured = dict(configured) if isinstance(configured, dict) else {}

    # Preserve deliberate administrator customizations while upgrading the
    # original ReDjango defaults to the active Elder rules.
    if configured.get("fatigue_percent_per_point", 8) == 8:
        configured["fatigue_percent_per_point"] = 3
    if configured.get("general_modifier_percent_per_point", 12) == 12:
        configured["general_modifier_percent_per_point"] = 4
    configured.setdefault("fatigue_fixed_per_point", 1)
    configured.setdefault("general_modifier_fixed_per_point", 1.5)

    value_string[CONFIG_KEY] = configured
    if value_string.get("adjustment.stanchezza") == "final.stanchezza * 8":
        value_string["adjustment.stanchezza"] = "final.stanchezza * 3"
    if (
        value_string.get("adjustment.modificatore_generale")
        == "final.modificatore_generale * 12"
    ):
        value_string["adjustment.modificatore_generale"] = (
            "final.modificatore_generale * 4"
        )
    if value_string.get("adjustment.stanchezza_fixed") in (None, "0"):
        value_string["adjustment.stanchezza_fixed"] = "1"
    if value_string.get("adjustment.modificatore_generale_fixed") in (None, "0"):
        value_string["adjustment.modificatore_generale_fixed"] = "1.5"

    profile.value_string = value_string
    profile.save(update_fields=["value_string", "updated_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0024_negozio_in_evidenza_negozio_price_modifier_percent"),
    ]

    operations = [
        migrations.RunPython(
            use_elder_quick_stat_adjustments,
            migrations.RunPython.noop,
        ),
    ]
