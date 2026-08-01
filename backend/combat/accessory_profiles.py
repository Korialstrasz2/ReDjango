from __future__ import annotations

import random
import re
from collections.abc import Mapping
from typing import Any

from backend.characters.models import Personaggio
from backend.characters.services.inventory_rules import (
    equipment_slot_is_active,
    equipment_slot_kind,
)
from backend.core.models import AccessoryProfile, Oggetto


ELDER_ACCESSORY_SLOTS = [
    "orecchino_1",
    "orecchino_2",
    "orecchino_3",
    "anello_1",
    "anello_2",
    "anello_3",
    "amuleto",
    "cintura",
    "mantello",
    "fascia",
    "spilla",
]

ELDER_ACCESSORY_COUNT_CURVE = [
    {"maxLevel": 1, "count": 3},
    {"maxLevel": 2, "count": 4},
    {"maxLevel": 3, "count": 5},
    {"maxLevel": 5, "count": 6},
    {"maxLevel": 7, "count": 7},
    {"maxLevel": 9, "count": 8},
    {"maxLevel": 12, "count": 9},
    {"maxLevel": 15, "count": 10},
    {"maxLevel": 20, "count": 13},
]

ELDER_REPEATABLE_KINDS = ["pf_item", "mana_item", "energia_item", "potere_item"]


def _rules(
    core: list[str],
    variants: list[list[str]],
) -> dict[str, Any]:
    return {
        "slots": ELDER_ACCESSORY_SLOTS,
        "countCurve": ELDER_ACCESSORY_COUNT_CURVE,
        "countJitter": [-1, 0, 1],
        "itemLevelJitter": [-2, -1, 0, 1, 2],
        # Elder concatenates core + variant + core + core. Repeating the core
        # three times is its weighting mechanism; duplicates inside core add
        # still more weight (notably pf_item for several physical profiles).
        "coreWeight": 3,
        "coreKinds": core,
        "variantPools": variants,
        "repeatableKinds": ELDER_REPEATABLE_KINDS,
    }


ACCESSORY_PROFILE_DEFAULTS: dict[str, dict[str, Any]] = {
    "guerriero": {
        "name": "Guerriero",
        "description": "Profilo fisico offensivo derivato dal preset guerriero di Elder Django.",
        "rules": _rules(
            ["pf_item", "pf_item", "attacco_item", "difesa_item", "forza_extra"],
            [
                ["res_fuoco", "res_gelo", "res_elettro", "rd_fis", "velocita_extra", "agilita_extra", "stanchezzabase", "rigenerazionepf", "resistenza_extra"],
                ["energia_item", "mod.gen.", "rigenerazionepf", "blink", "luce", "personalita_extra", "potere_item", "saggezza_extra"],
                ["raggioarcano", "estrazione", "contingenza", "materializzazione", "shapeshifting", "scudoarcano", "reroll", "immaginispeculari", "fortuna_extra"],
            ],
        ),
    },
    "tank": {
        "name": "Difensore / Tank",
        "description": "Profilo resistente derivato dal preset tank di Elder Django.",
        "rules": _rules(
            ["pf_item", "pf_item", "difesa_item", "rd_fis", "resistenza_extra"],
            [
                ["res_fuoco", "res_elettro", "res_gelo", "rigenerazionepf", "stanchezzabase", "energia_item", "velocita_extra", "agilita_extra"],
                ["contingenza", "blink", "mod.gen.", "scudoarcano", "saggezza_extra", "potere_item", "personalita_extra", "luce", "waterbreathing"],
                ["rigenerazionepf", "fortuna_extra", "reroll", "materializzazione", "darkvision", "sostentamento", "shapeshifting", "immaginispeculari", "estrazione"],
            ],
        ),
    },
    "mago": {
        "name": "Mago",
        "description": "Profilo arcano derivato dal preset mago di Elder Django.",
        "rules": _rules(
            ["pf_item", "mana_item", "intelligenza_extra", "concentrazione_extra", "potere_item"],
            [
                ["castsilenzioso", "castimmobile", "rangespell(tutte)", "sifone_di_mana", "rigenerazionemana", "blink", "counterspell", "scudoarcano"],
                ["pontedimana", "recast", "raggioarcano", "immaginispeculari", "mod.gen.", "reroll", "luce", "darkvision", "saggezza_extra"],
                ["telecinesi", "shapeshifting", "illusioneminore", "materializzazione", "personalita_extra", "fortuna_extra", "agilita_extra", "rigenerazionemana", "res_elettro"],
            ],
        ),
    },
    "battlemage": {
        "name": "Mago da battaglia",
        "description": "Profilo ibrido derivato dal preset battlemage di Elder Django.",
        "rules": _rules(
            ["pf_item", "pf_item", "mana_item", "attacco_item", "potere_item", "concentrazione_extra"],
            [
                ["pf_item", "difesa_item", "rigenerazionepf", "rigenerazionemana", "blink", "raggioarcano", "resistenza_extra"],
                ["castsilenzioso", "castimmobile", "sifone_di_mana", "mod.gen.", "rangespell(singola)", "velocita_extra", "agilita_extra", "scudoarcano", "recast"],
                ["res_fuoco", "res_gelo", "res_elettro", "rd_fis", "fortuna_extra", "materializzazione", "shapeshifting", "immaginispeculari", "personalita_extra"],
            ],
        ),
    },
    "arciere": {
        "name": "Arciere",
        "description": "Profilo da distanza derivato dal preset arciere di Elder Django.",
        "rules": _rules(
            ["pf_item", "attacco_item", "velocita_extra", "agilita_extra", "concentrazione_extra"],
            [
                ["pf_item", "difesa_item", "energia_item", "resistenza_extra", "stanchezzabase", "rigenerazionepf", "res_gelo", "res_elettro", "res_fuoco"],
                ["mod.gen.", "reroll", "blink", "luce", "fortuna_extra", "saggezza_extra", "personalita_extra", "rd_fis"],
                ["raggioarcano", "shapeshifting", "materializzazione", "estrazione", "immaginispeculari", "darkvision", "sostentamento", "waterbreathing", "resistenza_extra"],
            ],
        ),
    },
    "assassino": {
        "name": "Ladro / Assassino",
        "description": "Profilo furtivo derivato dal preset assassino di Elder Django.",
        "rules": _rules(
            ["pf_item", "pf_item", "attacco_item", "agilita_extra", "velocita_extra", "fortuna_extra"],
            [
                ["pf_item", "energia_item", "stanchezzabase", "rigenerazionepf", "blink", "darkvision", "illusioneminore", "res_elettro", "res_fuoco"],
                ["mod.gen.", "reroll", "shapeshifting", "materializzazione", "resistenza_extra", "saggezza_extra", "personalita_extra", "luce", "estrazione"],
                ["raggioarcano", "contingenza", "immaginispeculari", "fortuna_extra", "scudoarcano", "rigenerazionepf", "res_gelo"],
            ],
        ),
    },
    "supporto": {
        "name": "Supporto",
        "description": "Settimo profilo ReDjango per guaritori, sacerdoti e specialisti di supporto; conserva la struttura e i pesi Elder.",
        "rules": _rules(
            ["pf_item", "mana_item", "potere_item", "saggezza_extra", "concentrazione_extra"],
            [
                ["rigenerazionepf", "rigenerazionemana", "difesa_item", "resistenza_extra", "sostentamento", "luce", "waterbreathing"],
                ["energia_item", "reroll", "fortuna_extra", "personalita_extra", "contingenza", "blink", "scudoarcano", "immaginispeculari", "darkvision"],
                ["res_fuoco", "res_gelo", "res_elettro", "mod.gen.", "estrazione", "materializzazione", "shapeshifting", "raggioarcano", "telecinesi"],
            ],
        ),
    },
}


def recommended_accessory_profile_key(
    core_key: str,
    tags: Mapping[str, Any] | None = None,
    name: str = "",
) -> str:
    profile = dict(tags) if isinstance(tags, Mapping) else {}
    if core_key == "mage":
        return "mago"
    if core_key == "support":
        return "supporto"
    if core_key == "stealth":
        return "arciere" if float(profile.get("range_skill") or 0) >= 4 else "assassino"
    if core_key == "specialist":
        physical = float(profile.get("core_fisico") or 0)
        magic = float(profile.get("core_magico") or 0)
        return "battlemage" if physical >= 3 and magic >= 3 else "supporto"
    if core_key == "warrior":
        defense = float(profile.get("difesa") or 0)
        attack = float(profile.get("attacco") or 0)
        defensive_name = any(token in name.casefold() for token in ("guardia", "soldato", "ordinatore", "cavaliere"))
        return "tank" if defense >= 5 or (defense >= 4 and attack <= 3 and defensive_name) else "guerriero"
    return "guerriero"


def seed_accessory_profiles() -> int:
    touched = 0
    for key, definition in ACCESSORY_PROFILE_DEFAULTS.items():
        profile, created = AccessoryProfile.objects.get_or_create(
            key=key,
            defaults={
                "nome": definition["name"],
                "descrizione": definition["description"],
                "rules": definition["rules"],
                "metadata": {"source": "elder-django-accessory-profiles-v1"},
            },
        )
        if created:
            touched += 1
            continue
        updates = []
        if not profile.rules:
            profile.rules = definition["rules"]
            updates.append("rules")
        if updates:
            profile.save(update_fields=[*updates, "updated_at"])
            touched += 1
    return touched


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _integer(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _item_level(item: Oggetto) -> int | None:
    match = re.fullmatch(r"\s*Livello\s+(\d+)\s*", str(item.tipo_4 or ""), re.IGNORECASE)
    if not match:
        return None
    return max(1, min(10, int(match.group(1))))


def _closest_level_item(
    candidates: list[Oggetto],
    desired_level: int,
    rng: random.Random,
) -> Oggetto | None:
    by_level: dict[int, list[Oggetto]] = {}
    for item in candidates:
        level = _item_level(item)
        if level is not None:
            by_level.setdefault(level, []).append(item)
    for level in range(desired_level, 11):
        if by_level.get(level):
            return rng.choice(sorted(by_level[level], key=lambda item: item.id))
    for level in range(desired_level - 1, 0, -1):
        if by_level.get(level):
            return rng.choice(sorted(by_level[level], key=lambda item: item.id))
    return None


def _base_accessory_count(rules: Mapping[str, Any], level: int) -> int:
    for raw in _list(rules.get("countCurve")):
        band = dict(raw) if isinstance(raw, Mapping) else {}
        if level <= _integer(band.get("maxLevel"), 20):
            return max(0, _integer(band.get("count"), 0))
    return 13


def equip_accessory_profile(
    character: Personaggio,
    profile: AccessoryProfile,
    level: int,
    rng: random.Random,
    report: dict[str, Any],
) -> None:
    if character.equip_id is None:
        return
    rules = dict(profile.rules) if isinstance(profile.rules, Mapping) else {}
    configured_slots = [str(slot) for slot in _list(rules.get("slots")) if str(slot)]
    slots = [
        slot
        for slot in configured_slots
        if hasattr(character.equip, f"{slot}_id")
        and equipment_slot_is_active(slot, character.tot if isinstance(character.tot, dict) else {})
    ]
    occupied_slots = [slot for slot in slots if getattr(character.equip, f"{slot}_id", None)]
    open_slots = [slot for slot in slots if slot not in occupied_slots]
    jitter_values = [_integer(value, 0) for value in _list(rules.get("countJitter"))] or [-1, 0, 1]
    target = max(1, min(len(slots), _base_accessory_count(rules, level) + rng.choice(jitter_values)))
    requested = max(0, min(len(open_slots), target - len(occupied_slots)))
    chosen_slots = rng.sample(open_slots, requested)

    variant_pools = [_list(pool) for pool in _list(rules.get("variantPools")) if _list(pool)]
    selected_variant = rng.choice(variant_pools) if variant_pools else []
    core_kinds = [str(kind) for kind in _list(rules.get("coreKinds")) if str(kind)]
    core_weight = max(1, _integer(rules.get("coreWeight"), 3))
    weighted_kinds = [*core_kinds * core_weight, *[str(kind) for kind in selected_variant if str(kind)]]
    repeatable = {str(kind) for kind in _list(rules.get("repeatableKinds"))}
    level_jitter = [_integer(value, 0) for value in _list(rules.get("itemLevelJitter"))] or [-2, -1, 0, 1, 2]

    physical_types = {equipment_slot_kind(slot) for slot in slots}
    catalog = list(
        Oggetto.objects.filter(
            tipo_1__in=physical_types,
            archived_at__isnull=True,
            archiviato=False,
        ).order_by("id")
    )
    used_kinds = {
        item.tipo_2
        for slot in occupied_slots
        if (item := getattr(character.equip, slot, None)) is not None and item.tipo_2
    }
    profile_trace = {
        "key": profile.key,
        "name": profile.nome,
        "target": target,
        "alreadyEquipped": len(occupied_slots),
        "selectedVariant": list(selected_variant),
        "generated": 0,
    }

    for slot in chosen_slots:
        item_type = equipment_slot_kind(slot)
        shuffled_kinds = list(weighted_kinds)
        rng.shuffle(shuffled_kinds)
        selected_item = None
        selected_kind = ""
        requested_level = None
        fallback = False
        for kind in shuffled_kinds:
            if kind in used_kinds and kind not in repeatable:
                continue
            expected_level = min(10, max(1, (level + 1) // 2))
            requested_level = max(1, min(10, expected_level + rng.choice(level_jitter)))
            selected_item = _closest_level_item(
                [item for item in catalog if item.tipo_1 == item_type and item.tipo_2 == kind],
                requested_level,
                rng,
            )
            if selected_item is not None:
                selected_kind = kind
                break
        if selected_item is None:
            fallback = True
            expected_level = min(10, max(1, (level + 1) // 2))
            requested_level = max(1, min(10, expected_level + rng.choice(level_jitter)))
            fallback_items = [
                item
                for item in catalog
                if item.tipo_1 == item_type
                and (not item.tipo_2 or item.tipo_2 not in used_kinds or item.tipo_2 in repeatable)
            ]
            selected_item = _closest_level_item(fallback_items, requested_level, rng)
            if selected_item is None and fallback_items:
                # Elder ultimately accepts an un-tiered item of the right
                # physical type (most notably mantles).
                selected_item = rng.choice(sorted(fallback_items, key=lambda item: item.id))
            if selected_item is not None:
                selected_kind = selected_item.tipo_2
        if selected_item is None:
            report["warnings"].append(
                f"Nessun accessorio compatibile per {slot} nel profilo {profile.nome}."
            )
            continue
        setattr(character.equip, slot, selected_item)
        if selected_kind:
            used_kinds.add(selected_kind)
        report["equipment"].append(
            {
                "slot": slot,
                "itemId": selected_item.id,
                "name": selected_item.nome,
                "source": "accessoryProfile",
                "profileKey": profile.key,
                "effectKind": selected_kind,
                "requestedItemLevel": requested_level,
                "itemLevel": _item_level(selected_item),
                "fallback": fallback,
            }
        )
        profile_trace["generated"] += 1
    character.equip.save()
    report["accessoryProfile"] = profile_trace
