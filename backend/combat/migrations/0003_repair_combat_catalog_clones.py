from django.db import migrations


LEGACY_METADATA_KEYS = (
    "combat_owned_item_ids",
    "combat_cloned_item_ids",
    "combat_cloned_effect_ids",
)


def _catalog_clone_mapping(catalog_model, clone_ids):
    mapping = {}
    for clone in catalog_model.objects.filter(pk__in=clone_ids):
        metadata = clone.metadata if isinstance(clone.metadata, dict) else {}
        source_id = metadata.get("combat_clone_source_id")
        try:
            source_id = int(source_id)
        except (TypeError, ValueError):
            continue
        if source_id != clone.pk and catalog_model.objects.filter(pk=source_id).exists():
            mapping[clone.pk] = source_id
    return mapping


def _recorded_ids(raw_values):
    values = set()
    if not isinstance(raw_values, (list, tuple, set)):
        return values
    for raw_value in raw_values:
        try:
            values.add(int(raw_value))
        except (TypeError, ValueError):
            continue
    return values


def _replace_catalog_references(container_models, catalog_model, mapping):
    for container_model in container_models:
        relation_fields = [
            field
            for field in container_model._meta.concrete_fields
            if field.is_relation and field.related_model is catalog_model
        ]
        for clone_id, source_id in mapping.items():
            for field in relation_fields:
                container_model.objects.filter(
                    **{f"{field.name}_id": clone_id}
                ).update(**{f"{field.name}_id": source_id})


def repair_combat_catalog_clones(apps, schema_editor):
    Personaggio = apps.get_model("characters", "Personaggio")
    Equip = apps.get_model("characters", "Equip")
    Zaino = apps.get_model("characters", "Zaino")
    Faretra = apps.get_model("characters", "Faretra")
    EffettiPersonaggio = apps.get_model("characters", "EffettiPersonaggio")
    Oggetto = apps.get_model("core", "Oggetto")
    Effetto = apps.get_model("core", "Effetto")

    clone_characters = []
    item_clone_ids = set()
    effect_clone_ids = set()
    for character in Personaggio.objects.all().iterator():
        metadata = character.metadata if isinstance(character.metadata, dict) else {}
        if not metadata.get("combat_clone_source_id"):
            continue
        clone_characters.append((character, metadata))
        item_clone_ids.update(_recorded_ids(metadata.get("combat_cloned_item_ids")))
        effect_clone_ids.update(_recorded_ids(metadata.get("combat_cloned_effect_ids")))

    item_mapping = _catalog_clone_mapping(Oggetto, item_clone_ids)
    effect_mapping = _catalog_clone_mapping(Effetto, effect_clone_ids)
    _replace_catalog_references((Equip, Zaino, Faretra), Oggetto, item_mapping)
    _replace_catalog_references((EffettiPersonaggio,), Effetto, effect_mapping)

    Oggetto.objects.filter(pk__in=item_mapping).delete()
    Effetto.objects.filter(pk__in=effect_mapping).delete()

    for character, metadata in clone_characters:
        cleaned = dict(metadata)
        for key in LEGACY_METADATA_KEYS:
            cleaned.pop(key, None)
        if cleaned != metadata:
            character.metadata = cleaned
            character.save(update_fields=["metadata"])


class Migration(migrations.Migration):

    dependencies = [
        ("combat", "0002_maphex_revealed_mapmetadata_fog_enabled_and_more"),
    ]

    operations = [
        migrations.RunPython(repair_combat_catalog_clones, migrations.RunPython.noop),
    ]
