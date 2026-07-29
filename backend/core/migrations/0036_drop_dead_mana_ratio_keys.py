from django.db import migrations


# Elder kept four magic ratios but deleted the formulas behind en_per_mana and
# pa_per_mana in its migration 0118; only "Mana ogni N energia" and
# "Mana ogni N PA" drive the cast cost. ReDjango carried the two dead keys over,
# so they are removed here as well.
DEAD_KEYS = ("en_per_mana", "pa_per_mana")


def drop_dead_keys(apps, schema_editor):
    GlobalModifiers = apps.get_model("core", "GlobalModifiers")
    for modifier in GlobalModifiers.objects.all():
        values = modifier.value_float
        if not isinstance(values, dict):
            continue
        remaining = {key: value for key, value in values.items() if key not in DEAD_KEYS}
        if len(remaining) != len(values):
            modifier.value_float = remaining
            modifier.save(update_fields=["value_float"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0035_remove_character_shortcut"),
    ]

    operations = [
        migrations.RunPython(drop_dead_keys, migrations.RunPython.noop),
    ]
