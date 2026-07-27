from django.db import migrations


KEY_GROUPS = [
    ("en_per_mana", "en_per_mana_ordine", "en_per_mana_caos"),
    ("pa_per_mana", "pa_per_mana_ordine", "pa_per_mana_caos"),
    ("ogni_en_x_mana", "ogni_en_x_mana_ordine", "ogni_en_x_mana_caos"),
    ("ogni_pa_x_mana", "ogni_pa_x_mana_ordine", "ogni_pa_x_mana_caos"),
]


def _merged_value(primary, fallback):
    if primary in (None, 0, 0.0) and fallback not in (None, 0, 0.0):
        return fallback
    return primary or 0


def merge_global_modifier_keys(apps, schema_editor):
    GlobalModifiers = apps.get_model("core", "GlobalModifiers")

    for modifier in GlobalModifiers.objects.all():
        value_float = modifier.value_float or {}
        if not isinstance(value_float, dict):
            continue

        changed = False
        for canonical_key, ordine_key, caos_key in KEY_GROUPS:
            canonical_value = _merged_value(value_float.get(ordine_key), value_float.get(caos_key))
            if value_float.get(canonical_key) != canonical_value:
                value_float[canonical_key] = canonical_value
                changed = True
            for old_key in (ordine_key, caos_key):
                if old_key in value_float:
                    del value_float[old_key]
                    changed = True

        if changed:
            modifier.value_float = value_float
            modifier.save(update_fields=["value_float"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_external_v2_links"),
    ]

    operations = [
        migrations.RunPython(merge_global_modifier_keys, migrations.RunPython.noop),
    ]
