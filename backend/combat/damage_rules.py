from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any


DAMAGE_RULES_CONFIG_KEY = "combat_damage_rules"
PROFILE_NAME = "Formule_base"

ATTACK_DIFFERENCE_MINIMUM = -25
ATTACK_DIFFERENCE_MAXIMUM = 45
D20_MINIMUM = 1
D20_MAXIMUM = 20
RESISTANCE_LEVEL_MINIMUM = -4
RESISTANCE_LEVEL_MAXIMUM = 9
TIER_MINIMUM = -5
TIER_MAXIMUM = 30

DEFAULT_RESISTANCE_PERCENTAGES = {
    "-4": -45,
    "-3": -35,
    "-2": -25,
    "-1": -15,
    "0": 0,
    "1": 15,
    "2": 23,
    "3": 30,
    "4": 35,
    "5": 40,
    "6": 45,
    "7": 50,
    "8": 55,
    "9": 60,
}

DEFAULT_TIER_DAMAGE_FORMULAS = {
    "-5": "1d6",
    "-4": "1d6",
    "-3": "1d6",
    "-2": "1d6",
    "-1": "1d8",
    "0": "1d8",
    "1": "2d4",
    "2": "1d10",
    "3": "1d12",
    "4": "2d6",
    "5": "1d6+1d8",
    "6": "1d8+1d10",
    "7": "2d10",
    "8": "2d12",
    "9": "2d10+1d6",
    "10": "3d10",
    "11": "4d8",
    "12": "3d10+1d6",
    "13": "3d10+1d8",
    "14": "3d10+1d12",
    "15": "4d10+1d4",
    "16": "4d10+1d8",
    "17": "5d10",
    "18": "5d10+1d4",
    "19": "5d10+1d6",
    "20": "6d10",
    "21": "5d10+1d12",
    "22": "5d12+1d6",
    "23": "5d12+1d8",
    "24": "5d12+1d10",
    "25": "6d12",
    "26": "6d12+1d4",
    "27": "6d12+1d6",
    "28": "6d12+1d8",
    "29": "6d12+1d10",
    "30": "7d12+1d4",
}

# Run-length encoding of the Elder d20 x attack-difference table.
# Each tuple is: inclusive minimum difference, inclusive maximum difference,
# percentage of rolled damage.
ELDER_DAMAGE_MULTIPLIER_RUNS = {
    1: [(-25, 45, 0)],
    2: [(-25, -1, 20), (0, 11, 60), (12, 24, 80), (25, 38, 100), (39, 45, 120)],
    3: [(-25, -1, 20), (0, 8, 60), (9, 21, 80), (22, 35, 100), (36, 45, 120)],
    4: [(-25, -1, 40), (0, 5, 60), (6, 19, 80), (20, 33, 100), (34, 45, 120)],
    5: [(-25, -1, 40), (0, 1, 60), (2, 16, 80), (17, 30, 100), (31, 45, 120)],
    6: [(-25, -1, 60), (0, 12, 80), (13, 27, 100), (28, 43, 120), (44, 45, 140)],
    7: [(-25, -1, 60), (0, 9, 80), (10, 24, 100), (25, 41, 120), (42, 45, 140)],
    8: [(-25, -10, 60), (-9, 5, 80), (6, 21, 100), (22, 38, 120), (39, 45, 140)],
    9: [(-25, -10, 60), (-9, 1, 80), (2, 18, 100), (19, 35, 120), (36, 45, 140)],
    10: [(-25, -10, 60), (-9, -1, 80), (0, 14, 100), (15, 32, 120), (33, 45, 140)],
    11: [(-25, -11, 60), (-10, -1, 80), (0, 10, 100), (11, 28, 120), (29, 45, 140)],
    12: [(-25, -12, 60), (-11, -1, 80), (0, 5, 100), (6, 25, 120), (26, 45, 140)],
    13: [(-25, -13, 60), (-12, -1, 80), (0, 0, 100), (1, 20, 120), (21, 42, 140), (43, 45, 160)],
    14: [(-25, -14, 60), (-13, -6, 80), (-5, -1, 100), (0, 16, 120), (17, 39, 140), (40, 45, 160)],
    15: [(-25, -15, 60), (-14, -7, 80), (-6, -1, 100), (0, 11, 120), (12, 34, 140), (35, 45, 160)],
    16: [(-25, -17, 60), (-16, -8, 80), (-7, -1, 100), (0, 5, 120), (6, 30, 140), (31, 45, 160)],
    17: [(-25, -19, 60), (-18, -9, 80), (-8, -1, 100), (0, 0, 120), (1, 25, 140), (26, 45, 160)],
    18: [(-25, -20, 60), (-19, -10, 80), (-9, -1, 100), (0, 0, 120), (1, 19, 140), (20, 45, 160)],
    19: [(-25, -21, 60), (-20, -10, 80), (-9, -1, 100), (0, 0, 120), (1, 13, 140), (14, 45, 160)],
    20: [(-25, -21, 60), (-20, -10, 80), (-9, -1, 100), (0, 0, 120), (1, 5, 140), (6, 40, 160), (41, 45, 180)],
}


def _expanded_elder_damage_multipliers() -> dict[str, list[int]]:
    return {
        str(roll): [
            next(
                percentage
                for minimum, maximum, percentage in ELDER_DAMAGE_MULTIPLIER_RUNS[roll]
                if minimum <= difference <= maximum
            )
            for difference in range(
                ATTACK_DIFFERENCE_MINIMUM,
                ATTACK_DIFFERENCE_MAXIMUM + 1,
            )
        ]
        for roll in range(D20_MINIMUM, D20_MAXIMUM + 1)
    }


DEFAULT_DAMAGE_RULES = {
    "version": 1,
    "bounds": {
        "attackDifferenceMinimum": ATTACK_DIFFERENCE_MINIMUM,
        "attackDifferenceMaximum": ATTACK_DIFFERENCE_MAXIMUM,
        "d20Minimum": D20_MINIMUM,
        "d20Maximum": D20_MAXIMUM,
        "resistanceLevelMinimum": RESISTANCE_LEVEL_MINIMUM,
        "resistanceLevelMaximum": RESISTANCE_LEVEL_MAXIMUM,
        "tierMinimum": TIER_MINIMUM,
        "tierMaximum": TIER_MAXIMUM,
    },
    "resistancePercentages": DEFAULT_RESISTANCE_PERCENTAGES,
    "tierDamageFormulas": DEFAULT_TIER_DAMAGE_FORMULAS,
    "damageMultipliers": _expanded_elder_damage_multipliers(),
}


def default_damage_rules() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_DAMAGE_RULES)


def configured_damage_rules(profile=None) -> dict[str, Any]:
    """Return a complete, safe rules object while preserving saved overrides."""
    if profile is None:
        from backend.core.models import GlobalModifiers

        profile = GlobalModifiers.objects.filter(
            name=PROFILE_NAME,
            archived_at__isnull=True,
        ).first()
    raw = (
        profile.value_string.get(DAMAGE_RULES_CONFIG_KEY)
        if profile and isinstance(profile.value_string, Mapping)
        else None
    )
    if not isinstance(raw, Mapping):
        return default_damage_rules()

    configured = default_damage_rules()
    raw_resistances = raw.get("resistancePercentages")
    if isinstance(raw_resistances, Mapping):
        for level in configured["resistancePercentages"]:
            value = raw_resistances.get(level)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                configured["resistancePercentages"][level] = value

    raw_tiers = raw.get("tierDamageFormulas")
    if isinstance(raw_tiers, Mapping):
        for tier in configured["tierDamageFormulas"]:
            value = raw_tiers.get(tier)
            if isinstance(value, str) and value.strip():
                configured["tierDamageFormulas"][tier] = value.strip()

    raw_grid = raw.get("damageMultipliers")
    if isinstance(raw_grid, Mapping):
        expected_length = (
            ATTACK_DIFFERENCE_MAXIMUM - ATTACK_DIFFERENCE_MINIMUM + 1
        )
        for roll in configured["damageMultipliers"]:
            row = raw_grid.get(roll)
            if not isinstance(row, list) or len(row) != expected_length:
                continue
            if all(
                isinstance(value, (int, float)) and not isinstance(value, bool)
                for value in row
            ):
                configured["damageMultipliers"][roll] = list(row)
    return configured
