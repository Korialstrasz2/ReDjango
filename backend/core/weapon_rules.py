from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping


HEAVINESS_MODIFIERS = {
    "leggera": {"attacco": 4, "pa": 1, "tier": -3},
    "media": {},
    "pesante": {"attacco": -4, "tier": 3, "energia": 1},
}

LENGTH_MODIFIERS = {
    "corta": {"paPerAttacco": 3, "effects": {"tier": -2, "ap": 3}},
    "media": {"paPerAttacco": 4, "effects": {"tier": 1}},
    "lunga": {"paPerAttacco": 6, "effects": {"tier": 5, "ap_percento": 10}},
    "maninude": {"paPerAttacco": 2, "effects": {}},
}

DAMAGE_MODIFIERS = {
    "perforante": {"tier": 1},
    "taglio": {"pa": 1},
    "contundente": {"energia": 1},
}

MATERIALS = {
    "leggera": ["legno", "chitina", "elfico", "ossa", "dreugh", "vetro", "adamantio"],
    "pesante": ["ferro", "acciaio", "nordico", "orchesco", "dwemer", "ebano", "daedrico"],
}

MATERIAL_MODIFIERS = {
    "leggera": {"pa": 2, "attacco": 1},
    "pesante": {"energia": 2, "tier": 1},
}

COST_BANDS = {
    "A": {
        "label": "Una mano piccola",
        "weight": 4,
        "prices": {
            "leggera": [50, 150, 350, 700, 1500, 4000, 8000],
            "pesante": [70, 180, 400, 900, 1800, 5000, 10000],
        },
    },
    "B": {
        "label": "Una mano media",
        "weight": 8,
        "prices": {
            "leggera": [70, 180, 400, 900, 1800, 5000, 10000],
            "pesante": [80, 200, 500, 1000, 2000, 6000, 11000],
        },
    },
    "C": {
        "label": "Due mani, asta o tiro grande",
        "weight": 12,
        "prices": {
            "leggera": [100, 250, 550, 1100, 2100, 7000, 13000],
            "pesante": [120, 280, 600, 1300, 2500, 8000, 15000],
        },
    },
    "D": {
        "label": "Da lancio",
        "weight": 3,
        "prices": {
            "leggera": [20, 50, 120, 230, 500, 1300, 2500],
            "pesante": [25, 60, 130, 300, 600, 1700, 3500],
        },
    },
}

SKILL_MAPPINGS = {
    "length": {
        "corta": "atk_skill_corte",
        "media": "atk_skill_medie1",
        "lunga": "atk_skill_lunghe",
    },
    "power": {
        "precisa": "atk_skill_precise",
        "media": "atk_skill_medie2",
        "potente": "atk_skill_potenti",
    },
    "damageType": {
        "perforante": "atk_skill_perforante",
        "taglio": "atk_skill_taglio",
        "contundente": "atk_skill_contundente",
    },
}


def _key(value: Any) -> str:
    return str(value or "").strip().casefold()


def normalize_weapon_profile(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    profile = dict(value)
    normalized: dict[str, Any] = {}
    choices = {
        "heaviness": {"leggera", "media", "pesante"},
        "length": {"corta", "media", "lunga", "maninude"},
        "power": {"precisa", "media", "potente", "maninude"},
        "damageType": {"perforante", "taglio", "contundente", "magico", "natura"},
        "materialFamily": {"leggera", "pesante"},
        "costBand": {"A", "B", "C", "D"},
        "combatMode": {"melee", "ranged", "throwable", "magic", "unarmed", "nature"},
        "handling": {"one_handed", "two_handed", "special"},
    }
    for field, allowed in choices.items():
        raw = str(profile.get(field) or "").strip()
        candidate = raw.upper() if field == "costBand" else raw.casefold()
        if candidate in allowed:
            normalized[field] = candidate
    material = _key(profile.get("material"))
    if material:
        normalized["material"] = material
    try:
        tier = int(profile.get("materialTier") or 0)
    except (TypeError, ValueError):
        tier = 0
    if 1 <= tier <= 7:
        normalized["materialTier"] = tier
    for field in ("rangeMeters", "baseRangeMeters", "magazineSize", "reloadBaseCost", "reloadPerProjectileCost"):
        try:
            number = int(profile.get(field) or 0)
        except (TypeError, ValueError):
            number = 0
        if number > 0:
            normalized[field] = number
    ammunition_type = _key(profile.get("ammunitionType"))
    if ammunition_type in {"freccia", "dardo", "proiettile"}:
        normalized["ammunitionType"] = ammunition_type
    for field in ("specialRules", "bonusNotes"):
        raw = profile.get(field)
        if isinstance(raw, list):
            normalized[field] = [str(entry).strip() for entry in raw if str(entry).strip()]
    if normalized.get("length") in {"corta", "media"}:
        normalized["handling"] = "one_handed"
    elif normalized.get("length") == "lunga":
        normalized["handling"] = "two_handed"
    return normalized


def suggested_weapon_values(profile: Mapping[str, Any] | None) -> dict[str, Any]:
    normalized = normalize_weapon_profile(profile)
    totals: defaultdict[str, float] = defaultdict(float)
    for target, amount in HEAVINESS_MODIFIERS.get(normalized.get("heaviness", ""), {}).items():
        totals[target] += amount
    length = LENGTH_MODIFIERS.get(normalized.get("length", ""), {})
    for target, amount in length.get("effects", {}).items():
        totals[target] += amount
    for target, amount in DAMAGE_MODIFIERS.get(normalized.get("damageType", ""), {}).items():
        totals[target] += amount
    material_family = normalized.get("materialFamily", "")
    for target, amount in MATERIAL_MODIFIERS.get(material_family, {}).items():
        totals[target] += amount

    effects = [
        {
            "target": target,
            "operation": "add",
            "value": int(amount) if amount.is_integer() else amount,
            "source": "weapon_builder",
        }
        for target, amount in totals.items()
        if amount
    ]
    band = COST_BANDS.get(normalized.get("costBand", ""), {})
    material_tier = normalized.get("materialTier")
    prices = band.get("prices", {}).get(material_family, []) if band else []
    return {
        "effects": effects,
        "paPerAttacco": length.get("paPerAttacco"),
        "price": prices[material_tier - 1] if material_tier and len(prices) >= material_tier else None,
        "weight": band.get("weight"),
    }


def weapon_configuration_payload() -> dict[str, Any]:
    return {
        "axes": {
            "heaviness": {
                "label": "Categoria (pesantezza)",
                "options": [
                    {"value": key, "label": key.title(), "modifiers": modifiers}
                    for key, modifiers in HEAVINESS_MODIFIERS.items()
                ],
            },
            "length": {
                "label": "Lunghezza",
                "options": [
                    {"value": key, "label": key.title(), **values}
                    for key, values in LENGTH_MODIFIERS.items()
                    if key != "maninude"
                ],
            },
            "power": {
                "label": "Precisione / potenza",
                "options": [
                    {"value": key, "label": key.title(), "skill": SKILL_MAPPINGS["power"][key]}
                    for key in ("precisa", "media", "potente")
                ],
            },
            "damageType": {
                "label": "Tipo di danno",
                "options": [
                    {"value": key, "label": key.title(), "modifiers": modifiers}
                    for key, modifiers in DAMAGE_MODIFIERS.items()
                ],
            },
        },
        "materials": [
            {
                "family": family,
                "modifiers": MATERIAL_MODIFIERS[family],
                "tiers": [{"tier": index, "name": name} for index, name in enumerate(names, 1)],
            }
            for family, names in MATERIALS.items()
        ],
        "costBands": [
            {"value": key, **value}
            for key, value in COST_BANDS.items()
        ],
        "skillMappings": SKILL_MAPPINGS,
        "rules": {
            "bonusesAreBaked": True,
            "categoryChangesDoNotRewriteEffects": True,
            "handednessInferredFromLength": True,
            "throwable": {
                "baseRangeMeters": 4,
                "beyondBaseAttackPenaltyPerCell": -2,
                "maximumRange": "forza_meters",
                "meleeAttackPenalty": -4,
                "drawInMeleeProvokesOpportunityAttack": True,
            },
            "ranged": {
                "baseRangeMeters": 9,
                "beyondBaseAttackPenaltyPerCell": -2,
                "meleeAttackPenalty": -7,
                "reloadInMeleeProvokesOpportunityAttack": True,
            },
            "dualWield": {
                "secondarySlot": "scudo",
                "exactlyOnePrimary": True,
                "switchActionPointCost": 0,
                "alternateAttackDiscount": 1,
            },
        },
    }
