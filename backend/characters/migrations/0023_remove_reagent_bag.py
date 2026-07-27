import re

from django.db import migrations


def normalize_stock_key(value):
    key = str(value or "").strip().lower().replace(" ", "_")
    direct = re.fullmatch(r"([rvb])([1-4])", key)
    if direct:
        return direct.group(0)
    verbose = re.fullmatch(
        r"(?:ingredienti?_)?(rossi?|verdi?|blu)_?(?:livello_?)?([1-4])",
        key,
    )
    if not verbose:
        return None
    color = verbose.group(1)
    short = "r" if color.startswith("ross") else "v" if color.startswith("verd") else "b"
    return f"{short}{verbose.group(2)}"


def legacy_item_stock_key(item):
    if item is None:
        return None
    text = " ".join(
        str(getattr(item, field, "") or "")
        for field in ("nome", "tipo_1", "tipo_2", "tipo_3", "tipo_4", "lv_loot")
    ).casefold()
    if "reagent" not in text:
        return None
    short = "r" if "ross" in text else "v" if "verd" in text else "b" if "blu" in text else ""
    level = re.search(r"(?:lv|livello)?\s*([1-4])\b", text)
    return f"{short}{level.group(1)}" if short and level else None


def merge_reagents_into_personal_containers(apps, schema_editor):
    Personaggio = apps.get_model("characters", "Personaggio")
    Contenitore = apps.get_model("characters", "ContenitoreInventario")
    Voce = apps.get_model("characters", "VoceContenitoreInventario")

    for character in Personaggio.objects.select_related("borsa_reagenti").iterator():
        container, _ = Contenitore.objects.get_or_create(
            scope="personal",
            personaggio=character,
            defaults={
                "nome": f"Alchimia&Contenitori · {character.nome}"[:160],
                "capacita": 15,
                "senza_peso": True,
            },
        )
        canonical = {
            entry.reagent_stock_key: entry
            for entry in Voce.objects.filter(contenitore=container).exclude(reagent_stock_key="")
        }
        target = {key: entry.quantita for key, entry in canonical.items()}
        unknown = {}
        bag = character.borsa_reagenti
        if bag and isinstance(bag.ingredienti, dict):
            for raw_key, raw_value in bag.ingredienti.items():
                key = normalize_stock_key(raw_key)
                try:
                    quantity = max(0, int(raw_value))
                except (TypeError, ValueError):
                    quantity = 0
                if key:
                    # Migration 0022 already copied bag stock. max avoids doubling it.
                    target[key] = max(target.get(key, 0), quantity)
                else:
                    unknown[str(raw_key)] = raw_value

        for entry in list(
            Voce.objects.filter(contenitore=container, reagent_stock_key="", oggetto__isnull=False)
            .select_related("oggetto")
        ):
            key = legacy_item_stock_key(entry.oggetto)
            if key:
                target[key] = target.get(key, 0) + entry.quantita
                entry.delete()

        used_slots = set(
            Voce.objects.filter(contenitore=container).values_list("slot", flat=True)
        )
        for key, quantity in sorted(target.items()):
            existing = canonical.get(key)
            if quantity <= 0:
                if existing:
                    existing.delete()
                continue
            if existing:
                if existing.quantita != quantity:
                    existing.quantita = quantity
                    existing.save(update_fields=["quantita", "updated_at"])
                used_slots.add(existing.slot)
                continue
            slot = next(
                (candidate for candidate in range(1, max(container.capacita, 15) + 1) if candidate not in used_slots),
                None,
            )
            if slot is None:
                slot = max(used_slots, default=0) + 1
            Voce.objects.create(
                contenitore=container,
                slot=slot,
                reagent_stock_key=key,
                quantita=quantity,
            )
            used_slots.add(slot)

        required_capacity = max(used_slots, default=0)
        legacy_capacity = max(0, int(bag.slot_max_reagenti or 0)) if bag else 0
        if required_capacity > container.capacita or legacy_capacity > container.capacita:
            container.capacita = max(container.capacita, required_capacity, legacy_capacity)
        metadata = container.metadata if isinstance(container.metadata, dict) else {}
        if unknown:
            metadata["legacyUnclassifiedReagents"] = unknown
        container.metadata = metadata
        container.save(update_fields=["capacita", "metadata", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("characters", "0022_inventory_containers"),
    ]

    operations = [
        migrations.RunPython(
            merge_reagents_into_personal_containers,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="personaggio",
            name="borsa_reagenti",
        ),
        migrations.DeleteModel(
            name="BorsaReagenti",
        ),
    ]
