from __future__ import annotations

import math
import random
import re
from collections import Counter
from typing import Any

from django.db import transaction

from backend.core.alchemy_defaults import (
    ALCHEMY_COLOR_BY_KEY,
    ALCHEMY_COLOR_BY_SHORT,
    ALCHEMY_POTION_EFFECTS,
    alchemy_stock_key,
)
from backend.core.api import ApiError
from backend.core.models import ReagenteAlchemico

from ..models import Personaggio, VoceContenitoreInventario


MAX_BREW_INGREDIENTS = 4
MAX_SET_BONUS = 20.0


def normalize_stock_key(value: Any) -> str | None:
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
    raw_color = verbose.group(1)
    short = "r" if raw_color.startswith("ross") else "v" if raw_color.startswith("verd") else "b"
    return f"{short}{verbose.group(2)}"


def _locked_character_and_container(character_id: int):
    try:
        character = Personaggio.objects.select_for_update().get(pk=character_id)
    except Personaggio.DoesNotExist as exc:
        raise ApiError("alchemy.character_not_found", "Personaggio non trovato.", status=404) from exc
    from .extended_inventory import personal_container

    return character, personal_container(character, lock=True)


def _multiplier(totals: Any, key: str) -> float:
    if not isinstance(totals, dict):
        return 0.0
    try:
        value = float(totals.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0.0
    return value if math.isfinite(value) else 0.0


def potion_level_for_potency(potency: float) -> int:
    if potency < 3:
        return 0
    return min(10, int(potency // 3))


def calculate_brew(
    character: Personaggio,
    selections: list[dict[str, Any]],
    potion_color: str,
    effect: str,
    set_bonus: float,
) -> dict[str, Any]:
    if not 1 <= len(selections) <= MAX_BREW_INGREDIENTS:
        raise ApiError(
            "alchemy.ingredients_invalid",
            "Seleziona da uno a quattro reagenti.",
            "ingredients",
        )
    if potion_color not in ALCHEMY_COLOR_BY_KEY:
        raise ApiError("alchemy.color_invalid", "Scegli un colore di pozione valido.", "potionColor")
    if effect not in ALCHEMY_POTION_EFFECTS[potion_color]:
        raise ApiError("alchemy.effect_invalid", "Scegli un effetto valido per questo colore.", "effect")
    try:
        set_bonus = float(set_bonus)
    except (TypeError, ValueError) as exc:
        raise ApiError("alchemy.set_bonus_invalid", "Il bonus del set deve essere un numero.", "setBonus") from exc
    if not math.isfinite(set_bonus) or not 0 <= set_bonus <= MAX_SET_BONUS:
        raise ApiError(
            "alchemy.set_bonus_invalid",
            f"Il bonus del set deve essere compreso tra 0 e {MAX_SET_BONUS:g}.",
            "setBonus",
        )

    normalized: list[dict[str, Any]] = []
    for index, selection in enumerate(selections):
        color = str(selection.get("color") or "")
        try:
            level = int(selection.get("level"))
        except (TypeError, ValueError) as exc:
            raise ApiError(
                "alchemy.ingredient_invalid",
                "Uno dei reagenti selezionati non è valido.",
                f"ingredients.{index}",
            ) from exc
        if color not in ALCHEMY_COLOR_BY_KEY or level not in range(1, 5):
            raise ApiError(
                "alchemy.ingredient_invalid",
                "Ogni reagente deve avere un colore e un livello da 1 a 4.",
                f"ingredients.{index}",
            )
        normalized.append({"color": color, "level": level, "stockKey": alchemy_stock_key(color, level)})
    if not any(selection["color"] == potion_color for selection in normalized):
        raise ApiError(
            "alchemy.color_missing",
            "La miscela deve contenere almeno un reagente del colore della pozione.",
            "potionColor",
        )

    totals = character.tot if isinstance(character.tot, dict) else {}
    level_contributions = []
    for selection in normalized:
        value = _multiplier(totals, f"moltiplicatore_reagenti_livello_{selection['level']}")
        level_contributions.append({**selection, "value": value})
    level_total = sum(entry["value"] for entry in level_contributions)
    color_suffix = {"rosso": "rossi", "verde": "verdi", "blu": "blu"}[potion_color]
    ability_bonus = _multiplier(totals, f"moltiplicatore_reagenti_{color_suffix}")
    potency = round(max(0.0, level_total * (set_bonus + ability_bonus)), 2)
    potion_level = potion_level_for_potency(potency)
    return {
        "potionColor": potion_color,
        "potionColorLabel": ALCHEMY_COLOR_BY_KEY[potion_color]["label"],
        "effect": effect,
        "ingredients": level_contributions,
        "levelTotal": round(level_total, 2),
        "setBonus": round(set_bonus, 2),
        "abilityBonus": round(ability_bonus, 2),
        "potency": potency,
        "potionLevel": potion_level,
        "potionLevelLabel": f"Livello {potion_level}" if potion_level else "Sotto soglia",
        "formula": "somma livelli × (bonus set + abilità colore)",
    }


@transaction.atomic
def brew_alchemy(
    character_id: int,
    selections: list[dict[str, Any]],
    potion_color: str,
    effect: str,
    set_bonus: float,
) -> tuple[Personaggio, dict[str, Any]]:
    character, container = _locked_character_and_container(character_id)
    result = calculate_brew(character, selections, potion_color, effect, set_bonus)
    from .extended_inventory import reagent_stock_for_container

    stock = reagent_stock_for_container(container)
    requested = Counter(entry["stockKey"] for entry in result["ingredients"])
    for key, quantity in requested.items():
        if stock[key] < quantity:
            color = ALCHEMY_COLOR_BY_SHORT[key[0]]["label"]
            raise ApiError(
                "alchemy.stock_insufficient",
                f"Non ci sono abbastanza reagenti {color} di livello {key[1]}.",
                "ingredients",
                409,
            )
    for key, quantity in requested.items():
        entry = container.voci.select_for_update().get(reagent_stock_key=key)
        if entry.quantita == quantity:
            entry.delete()
        else:
            entry.quantita -= quantity
            entry.save(update_fields=["quantita", "updated_at"])
    result["consumed"] = dict(requested)
    return character, result


@transaction.atomic
def extract_alchemy_reagent(character_id: int) -> tuple[Personaggio, dict[str, Any]]:
    character, container = _locked_character_and_container(character_id)
    catalog = list(ReagenteAlchemico.objects.filter(attivo=True, archived_at__isnull=True))
    if not catalog:
        raise ApiError(
            "alchemy.catalog_empty",
            "Il catalogo dei reagenti non contiene elementi attivi.",
            status=409,
        )
    reagent = random.choice(catalog)
    from .extended_inventory import reagent_stock_for_container

    stock = reagent_stock_for_container(container)
    key = alchemy_stock_key(reagent.colore, reagent.livello)
    capacity, occupied = container.capacita, container.voci.count()
    if stock[key] <= 0 and occupied >= capacity:
        raise ApiError(
            "alchemy.bag_full",
            "Alchimia è piena: libera uno spazio prima di aggiungere un nuovo tipo di reagente.",
            status=409,
        )
    entry = container.voci.select_for_update().filter(reagent_stock_key=key).first()
    if entry:
        entry.quantita += 1
        entry.save(update_fields=["quantita", "updated_at"])
    else:
        occupied_slots = set(container.voci.values_list("slot", flat=True))
        slot = next(candidate for candidate in range(1, capacity + 1) if candidate not in occupied_slots)
        VoceContenitoreInventario.objects.create(
            contenitore=container,
            slot=slot,
            reagent_stock_key=key,
            quantita=1,
        )
    return character, {
        "id": reagent.id,
        "name": reagent.nome,
        "color": reagent.colore,
        "colorLabel": reagent.get_colore_display(),
        "level": reagent.livello,
        "stockKey": key,
    }
