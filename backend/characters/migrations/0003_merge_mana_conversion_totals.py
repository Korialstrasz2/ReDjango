from django.db import migrations


FIELD_PAIRS = [
    ("en_per_mana_ordine_tot", "en_per_mana_caos_tot"),
    ("pa_per_mana_ordine_tot", "pa_per_mana_caos_tot"),
    ("ogni_en_x_mana_ordine_tot", "ogni_en_x_mana_caos_tot"),
    ("ogni_pa_x_mana_ordine_tot", "ogni_pa_x_mana_caos_tot"),
]


def _merged_value(primary, fallback):
    if primary in (None, 0, 0.0) and fallback not in (None, 0, 0.0):
        return fallback
    return primary or 0


def merge_split_totals(apps, schema_editor):
    Personaggio = apps.get_model("characters", "Personaggio")
    field_names = [field for pair in FIELD_PAIRS for field in pair]

    for personaggio in Personaggio.objects.all().only("id", *field_names):
        update_fields = []
        for ordine_field, caos_field in FIELD_PAIRS:
            merged = _merged_value(getattr(personaggio, ordine_field), getattr(personaggio, caos_field))
            if getattr(personaggio, ordine_field) != merged:
                setattr(personaggio, ordine_field, merged)
                update_fields.append(ordine_field)
        if update_fields:
            personaggio.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ("characters", "0002_borsareagenti_equip_faretra_note_personaggio_zaino_and_more"),
    ]

    operations = [
        migrations.RunPython(merge_split_totals, migrations.RunPython.noop),
        migrations.RenameField(
            model_name="personaggio",
            old_name="en_per_mana_ordine_tot",
            new_name="en_per_mana_tot",
        ),
        migrations.RenameField(
            model_name="personaggio",
            old_name="pa_per_mana_ordine_tot",
            new_name="pa_per_mana_tot",
        ),
        migrations.RenameField(
            model_name="personaggio",
            old_name="ogni_en_x_mana_ordine_tot",
            new_name="ogni_en_x_mana_tot",
        ),
        migrations.RenameField(
            model_name="personaggio",
            old_name="ogni_pa_x_mana_ordine_tot",
            new_name="ogni_pa_x_mana_tot",
        ),
        migrations.RemoveField(
            model_name="personaggio",
            name="en_per_mana_caos_tot",
        ),
        migrations.RemoveField(
            model_name="personaggio",
            name="pa_per_mana_caos_tot",
        ),
        migrations.RemoveField(
            model_name="personaggio",
            name="ogni_en_x_mana_caos_tot",
        ),
        migrations.RemoveField(
            model_name="personaggio",
            name="ogni_pa_x_mana_caos_tot",
        ),
    ]
