"""Read model del banco Forgiatura."""

from __future__ import annotations

from typing import Any

from backend.core.forge_defaults import (
    FORGE_CATEGORIES,
    IMPROVEMENT_CATALOG,
    MATERIAL_BY_KEY,
    PRACTICAL_ITEM_TYPES,
    PRACTICAL_LEATHER_BASE,
    PRACTICAL_LEATHER_PER_LEVEL,
    UNIMPROVABLE_ITEM_TYPES,
    item_forge_category,
)
from backend.core.models import Oggetto

from .crafting_capability import (
    forge_capabilities,
    forge_table_rules,
    improvement_budget,
    material_unlock_sources,
    specialist_material,
    unlocked_materials,
)
from .models import Personaggio
from .services.forge import best_smith_tools, ingot_stock
from .services.item_instances import instance_block, next_improvement_cost, owned_instances


def _material_rows(character: Personaggio) -> list[dict[str, Any]]:
    unlocked = unlocked_materials(character)
    sources = material_unlock_sources()
    stock = ingot_stock(character)
    tools = best_smith_tools(character)
    rows = []
    for key, material in MATERIAL_BY_KEY.items():
        is_unlocked = key in unlocked
        rows.append(
            {
                "key": key,
                "label": material["label"],
                "tier": material["tier"],
                "branch": material["branch"],
                "quantity": stock.get(key, 0),
                "unlocked": is_unlocked,
                "unlockedBy": unlocked.get(key, ""),
                "requiresSkill": "" if is_unlocked else sources.get(key, ""),
                "toolsReady": tools["level"] >= material["tier"],
            }
        )
    return sorted(rows, key=lambda row: (row["tier"], row["branch"], row["label"]))


def _blueprints(character: Personaggio) -> list[dict[str, Any]]:
    """Modelli forgiabili nei materiali che il personaggio sa lavorare.

    Si parte dai materiali sbloccati invece che da tutto il catalogo: 5.895
    righe filtrate a mano sarebbero una query inutile, e comunque il banco
    mostra solo ciò che si può davvero battere.
    """
    unlocked = unlocked_materials(character)
    if not unlocked:
        return []
    stock = ingot_stock(character)
    tools = best_smith_tools(character)
    rows = []
    queryset = (
        Oggetto.objects.filter(
            modello=True,
            archiviato=False,
            archived_at__isnull=True,
            tipo_2__in=list(unlocked),
        )
        .only("id", "nome", "tipo_1", "tipo_2", "valore", "peso", "icona")
        .order_by("tipo_1", "nome")
    )
    for item in queryset:
        category_key = item_forge_category(item.tipo_1)
        if not category_key:
            continue
        material_key = (item.tipo_2 or "").lower()
        material = MATERIAL_BY_KEY.get(material_key)
        if material is None:
            continue
        category = FORGE_CATEGORIES[category_key]
        ingots = int(category["ingots"])
        has_tools = tools["level"] >= material["tier"]
        has_stock = stock.get(material_key, 0) >= ingots
        blocked = ""
        if not has_tools:
            blocked = f"Servono strumenti da fabbro di livello {material['tier']}."
        elif not has_stock:
            blocked = f"Servono {ingots} unità di {material['label']}."
        rows.append(
            {
                "itemId": item.id,
                "name": item.nome,
                "icon": item.icona,
                "type": item.tipo_1,
                "category": category_key,
                "categoryLabel": category["label"],
                "material": material_key,
                "materialLabel": material["label"],
                "tier": material["tier"],
                "ingots": ingots,
                "hours": ingots,
                "quantity": int(category.get("yield", 1)),
                "value": item.valore or 0,
                "canForge": not blocked,
                "blockedReason": blocked,
            }
        )
    return rows


def _improvable(character: Personaggio) -> list[dict[str, Any]]:
    rows = []
    for item in owned_instances(character, kinds=("forged",)):
        block = instance_block(item)
        material_key = block.get("material", "")
        budget = improvement_budget(character, material_key)
        category_key = block.get("category", "") or item_forge_category(item.tipo_1)
        kind = FORGE_CATEGORIES.get(category_key, {}).get("kind", "weapon")
        unimprovable = (item.tipo_1 or "").lower() in UNIMPROVABLE_ITEM_TYPES
        applied = [
            {
                "key": entry.get("key", ""),
                "stack": int(entry.get("stack", 0)),
                "pointsPaid": int(entry.get("pointsPaid", 0)),
            }
            for entry in block.get("improvements", [])
        ]
        rows.append(
            {
                "instanceId": item.id,
                "name": item.nome,
                "icon": item.icona,
                "type": item.tipo_1,
                "material": material_key,
                "materialLabel": MATERIAL_BY_KEY.get(material_key, {}).get("label", material_key),
                "tier": int(block.get("materialTier", 0)),
                "kind": kind,
                "weight": item.peso or 0,
                "pointsSpent": int(block.get("pointsSpent", 0)),
                "pointsMax": budget["max"],
                "budgetFormula": budget["formula"],
                "fatigueBonus": budget["fatigueBonus"],
                "improvable": not unimprovable,
                "blockedReason": "Cotte di maglia e vesti non si migliorano." if unimprovable else "",
                "improvements": applied,
                "tableRules": [line for line in (item.regole_speciali or "").splitlines() if line.strip()],
                "options": [
                    {
                        "key": definition["key"],
                        "label": definition["label"],
                        "baseCost": definition["cost"],
                        "nextCost": next_improvement_cost(item, definition["key"]),
                        "mode": definition["apply"]["mode"],
                        "stack": next(
                            (row["stack"] for row in applied if row["key"] == definition["key"]),
                            0,
                        ),
                    }
                    for definition in IMPROVEMENT_CATALOG
                    if kind in definition["kinds"]
                ],
            }
        )
    return rows


def _practical_blueprints(character: Personaggio) -> list[dict[str, Any]]:
    level = int(forge_capabilities(character)["practicalLevel"])
    if level <= 0:
        return []
    stock = ingot_stock(character).get("pelle", 0)
    rows = []
    queryset = (
        Oggetto.objects.filter(
            modello=True,
            archiviato=False,
            archived_at__isnull=True,
            tipo_1__in=PRACTICAL_ITEM_TYPES,
        )
        .only("id", "nome", "tipo_1", "valore", "icona")
        .order_by("tipo_1", "valore")[:40]
    )
    for item in queryset:
        leather = PRACTICAL_LEATHER_BASE
        rows.append(
            {
                "itemId": item.id,
                "name": item.nome,
                "icon": item.icona,
                "type": item.tipo_1,
                "leather": leather,
                "canForge": stock >= leather,
                "blockedReason": "" if stock >= leather else f"Servono {leather} unità di pelle.",
            }
        )
    return rows


def forge_payload(character: Personaggio) -> dict[str, Any]:
    capabilities = forge_capabilities(character)
    tools = best_smith_tools(character)
    materials = _material_rows(character)
    unlocked = [row for row in materials if row["unlocked"]]
    return {
        "character": {
            "id": character.id,
            "name": character.nome,
            "level": character.livello,
            "fatigue": int(character.stanchezza_accumulata or 0),
        },
        "capability": {
            **capabilities,
            "specialistMaterial": specialist_material(character),
            "maxTier": max((row["tier"] for row in unlocked), default=0),
            "unlockedCount": len(unlocked),
        },
        "tools": tools,
        "materials": materials,
        "blueprints": _blueprints(character),
        "practical": _practical_blueprints(character),
        "improvable": _improvable(character),
        "tableRules": forge_table_rules(character),
        "notes": character.note.crafting if character.note else "",
        "rules": {
            "doubling": "Ripetere lo stesso miglioramento raddoppia il costo: 1, 2, 4, 8.",
            "resistances": "Resistenze diverse non raddoppiano fra loro; la stessa due volte sì.",
            "hours": "Forgiare costa un'ora per lingotto usato. Migliorare costa sempre due ore.",
            "unimprovable": "Le cotte di maglia e le vesti non possono essere migliorate.",
        },
    }
