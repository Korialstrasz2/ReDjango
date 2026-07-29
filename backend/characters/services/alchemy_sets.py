from __future__ import annotations

import re
from typing import Any

from backend.core.api import ApiError
from backend.core.models import Oggetto

from ..models import ContenitoreInventario, Personaggio, VoceContenitoreInventario


ALCHEMY_SET_TYPE = "setalchemico"
BASE_SET_BONUS = 1.0
SET_SOURCE_LABELS = {
    "backpack": "Zaino",
    "utility": "Alchimia&Contenitori",
    "campaign": "Risorse gruppo",
}
# Personal storage wins over the shared one when the same set sits in both.
SET_SOURCE_ORDER = ("backpack", "utility", "campaign")
PERCENT_PATTERN = re.compile(r"([+-]?)\s*(\d+(?:[.,]\d+)?)\s*%")


def is_alchemy_set(item: Oggetto | None) -> bool:
    if item is None:
        return False
    return any(
        str(getattr(item, f"tipo_{index}", "") or "").strip().lower() == ALCHEMY_SET_TYPE
        for index in range(1, 5)
    )


def alchemy_set_bonus(item: Oggetto) -> float:
    """Elder sets describe themselves as "+ 25% effetto": that percentage rides on
    top of the bare workbench, whose bonus is 1."""
    match = PERCENT_PATTERN.search(item.descrizione or "")
    if not match:
        return BASE_SET_BONUS
    percent = float(match.group(2).replace(",", "."))
    if match.group(1) == "-":
        percent = -percent
    return round(max(0.0, BASE_SET_BONUS + percent / 100), 4)


def _backpack_item_ids(character: Personaggio) -> list[int]:
    container = character.zaino
    if container is None:
        return []
    return [
        item_id
        for index in range(1, 51)
        if (item_id := getattr(container, f"slot_{index}_id", None))
    ]


def _extended_container_item_ids(character: Personaggio, group: str) -> list[int]:
    if group == "campaign":
        if not character.campagna_id:
            return []
        filters = {
            "scope": ContenitoreInventario.SCOPE_CAMPAIGN,
            "campagna_id": character.campagna_id,
        }
    else:
        filters = {
            "scope": ContenitoreInventario.SCOPE_PERSONAL,
            "personaggio": character,
        }
    return list(
        VoceContenitoreInventario.objects.filter(
            contenitore__in=ContenitoreInventario.objects.filter(**filters),
            oggetto__isnull=False,
        ).values_list("oggetto_id", flat=True)
    )


def _serialize_set(item: Oggetto, source: str) -> dict[str, Any]:
    bonus = alchemy_set_bonus(item)
    return {
        "id": item.id,
        "name": item.nome,
        "bonus": bonus,
        "bonusPercent": round((bonus - BASE_SET_BONUS) * 100, 2),
        "source": source,
        "sourceLabel": SET_SOURCE_LABELS[source],
        "shared": source == "campaign",
        "rarity": item.rarita,
        "rarityLabel": item.get_rarita_display() if item.rarita is not None else "",
        "value": item.valore or 0,
        "description": item.descrizione,
    }


def available_alchemy_sets(character: Personaggio) -> list[dict[str, Any]]:
    """Every alchemy set the character can reach, best quality first."""
    by_source = {
        "backpack": _backpack_item_ids(character),
        "utility": _extended_container_item_ids(character, "utility"),
        "campaign": _extended_container_item_ids(character, "campaign"),
    }
    candidate_ids = {item_id for ids in by_source.values() for item_id in ids}
    if not candidate_ids:
        return []
    items = Oggetto.objects.filter(id__in=candidate_ids).in_bulk()
    found: dict[int, dict[str, Any]] = {}
    for source in SET_SOURCE_ORDER:
        for item_id in by_source[source]:
            item = items.get(item_id)
            if item_id in found or not is_alchemy_set(item):
                continue
            found[item_id] = _serialize_set(item, source)
    return sorted(found.values(), key=lambda entry: (-entry["bonus"], -entry["value"], entry["name"]))


def auto_selected_alchemy_set(sets: list[dict[str, Any]]) -> dict[str, Any] | None:
    return sets[0] if sets else None


def resolve_alchemy_set(
    character: Personaggio,
    set_item_id: Any,
) -> tuple[dict[str, Any] | None, float]:
    """Server-side truth for the brew bonus: an unowned set can never be spent."""
    if set_item_id in (None, ""):
        return None, BASE_SET_BONUS
    try:
        wanted = int(set_item_id)
    except (TypeError, ValueError) as exc:
        raise ApiError(
            "alchemy.set_invalid",
            "Il set alchemico scelto non è valido.",
            "setItemId",
        ) from exc
    for entry in available_alchemy_sets(character):
        if entry["id"] == wanted:
            return entry, entry["bonus"]
    raise ApiError(
        "alchemy.set_not_available",
        "Il set alchemico scelto non è nell'inventario né fra le risorse del gruppo.",
        "setItemId",
        409,
    )
