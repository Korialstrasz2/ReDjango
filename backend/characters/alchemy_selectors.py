from __future__ import annotations

from typing import Any

from backend.core.alchemy_defaults import (
    ALCHEMY_COLOR_BY_KEY,
    ALCHEMY_COLOR_DEFINITIONS,
    ALCHEMY_POTION_EFFECTS,
    alchemy_stock_key,
)
from backend.core.models import ReagenteAlchemico

from .models import Personaggio
from .services.alchemy_sets import (
    BASE_SET_BONUS,
    auto_selected_alchemy_set,
    available_alchemy_sets,
)
from .services.extended_inventory import personal_container, reagent_stock_for_container


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def alchemy_creation_payload(character: Personaggio) -> dict[str, Any]:
    container = personal_container(character)
    stock = reagent_stock_for_container(container)
    metadata = container.metadata if isinstance(container.metadata, dict) else {}
    unclassified = metadata.get("legacyUnclassifiedReagents", {})
    if not isinstance(unclassified, dict):
        unclassified = {}
    stock_rows = []
    for color in ALCHEMY_COLOR_DEFINITIONS:
        for level in range(1, 5):
            key = alchemy_stock_key(color["key"], level)
            stock_rows.append(
                {
                    "key": key,
                    "color": color["key"],
                    "colorLabel": color["label"],
                    "level": level,
                    "quantity": stock[key],
                }
            )
    unknown_rows = [
        {"key": key, "label": key.replace("_", " ").strip(), "quantity": max(0, int(_number(value)))}
        for key, value in unclassified.items()
    ]
    from .services.extended_inventory import personal_storage_usage

    capacity, occupied = personal_storage_usage(character)
    totals = character.tot if isinstance(character.tot, dict) else {}
    color_multipliers = []
    suffixes = {"rosso": "rossi", "verde": "verdi", "blu": "blu"}
    for color in ALCHEMY_COLOR_DEFINITIONS:
        key = f"moltiplicatore_reagenti_{suffixes[color['key']]}"
        color_multipliers.append(
            {"key": key, "color": color["key"], "label": color["label"], "value": _number(totals.get(key))}
        )
    level_multipliers = [
        {
            "key": f"moltiplicatore_reagenti_livello_{level}",
            "level": level,
            "label": f"Livello {level}",
            "value": _number(totals.get(f"moltiplicatore_reagenti_livello_{level}")),
        }
        for level in range(1, 5)
    ]
    catalog = [
        {
            "id": reagent.id,
            "name": reagent.nome,
            "color": reagent.colore,
            "colorLabel": ALCHEMY_COLOR_BY_KEY[reagent.colore]["label"],
            "level": reagent.livello,
            "stockKey": alchemy_stock_key(reagent.colore, reagent.livello),
        }
        for reagent in ReagenteAlchemico.objects.filter(attivo=True, archived_at__isnull=True)
    ]
    sets = available_alchemy_sets(character)
    auto_set = auto_selected_alchemy_set(sets)
    return {
        "character": {"id": character.id, "name": character.nome, "level": character.livello},
        "bag": {
            "id": container.id,
            "capacity": capacity,
            "occupied": occupied,
            "remaining": max(0, capacity - occupied),
            "stock": stock_rows,
            "unclassified": unknown_rows,
        },
        "multipliers": {"colors": color_multipliers, "levels": level_multipliers},
        "sets": sets,
        "catalog": catalog,
        "potionFamilies": [
            {
                "color": color["key"],
                "label": color["label"],
                "effects": list(ALCHEMY_POTION_EFFECTS[color["key"]]),
            }
            for color in ALCHEMY_COLOR_DEFINITIONS
        ],
        "thresholds": [
            {"level": level, "minimumPotency": level * 3}
            for level in range(1, 11)
        ],
        "notes": character.note.crafting if character.note else "",
        "rules": {
            "maxIngredients": 4,
            "defaultSetBonus": auto_set["bonus"] if auto_set else BASE_SET_BONUS,
            "defaultSetId": auto_set["id"] if auto_set else None,
            "baseSetBonus": BASE_SET_BONUS,
            "formula": "(somma dei moltiplicatori di livello) × (bonus del set + abilità del colore)",
        },
    }
