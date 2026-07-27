from django.db import migrations


SLOT_NUMBERS = range(1, 51)


def _safe_weight(value):
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def sort_saved_inventories(apps, schema_editor):
    Oggetto = apps.get_model("core", "Oggetto")
    weights = {item_id: _safe_weight(weight) for item_id, weight in Oggetto.objects.values_list("id", "peso")}

    for model_name in ("Zaino", "Faretra"):
        Container = apps.get_model("characters", model_name)
        for container in Container.objects.all().iterator():
            entries = [
                (index, getattr(container, f"slot_{index}_id"))
                for index in SLOT_NUMBERS
                if getattr(container, f"slot_{index}_id") is not None
            ]
            entries.sort(key=lambda entry: -weights.get(entry[1], 0.0))
            ordered_ids = [item_id for _source_index, item_id in entries]
            updates = {}
            for index in SLOT_NUMBERS:
                desired_id = ordered_ids[index - 1] if index <= len(ordered_ids) else None
                if getattr(container, f"slot_{index}_id") != desired_id:
                    updates[f"slot_{index}_id"] = desired_id
            if updates:
                Container.objects.filter(pk=container.pk).update(**updates)


class Migration(migrations.Migration):
    dependencies = [("characters", "0009_simplify_note_sections")]

    operations = [migrations.RunPython(sort_saved_inventories, migrations.RunPython.noop)]
