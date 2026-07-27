from __future__ import annotations

import heapq
import math
import random
import re
from collections.abc import Callable

from .damage_rules import (
    ATTACK_DIFFERENCE_MAXIMUM,
    ATTACK_DIFFERENCE_MINIMUM,
    DEFAULT_RESISTANCE_PERCENTAGES,
    DEFAULT_TIER_DAMAGE_FORMULAS,
    ELDER_DAMAGE_MULTIPLIER_RUNS,
    RESISTANCE_LEVEL_MAXIMUM,
    RESISTANCE_LEVEL_MINIMUM,
    configured_damage_rules,
)

HEX_DIRECTIONS = ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1))
DAMAGE_TYPES = ("Contundente", "Perforante", "Taglio", "Gelo", "Fuoco", "Elettro", "Puro")
# Backward-compatible exports for callers that imported the former constants.
RESISTANCE_PERCENT = {
    int(level): percentage
    for level, percentage in DEFAULT_RESISTANCE_PERCENTAGES.items()
}
TIER_DAMAGE_FORMULAS = {
    int(tier): formula
    for tier, formula in DEFAULT_TIER_DAMAGE_FORMULAS.items()
}
LEGACY_DAMAGE_MULTIPLIERS = ELDER_DAMAGE_MULTIPLIER_RUNS


def offset_to_axial(cell: tuple[int, int], orientation: str = "pointy") -> tuple[int, int]:
    q, r = cell
    if orientation == "flat":
        return q, r - (q - (q & 1)) // 2
    return q - (r - (r & 1)) // 2, r


def axial_to_offset(cell: tuple[int, int], orientation: str = "pointy") -> tuple[int, int]:
    q, r = cell
    if orientation == "flat":
        return q, r + (q - (q & 1)) // 2
    return q + (r - (r & 1)) // 2, r


def hex_distance(start: tuple[int, int], end: tuple[int, int], orientation: str = "pointy") -> int:
    aq, ar = offset_to_axial(start, orientation)
    bq, br = offset_to_axial(end, orientation)
    return int((abs(aq - bq) + abs(ar - br) + abs((aq + ar) - (bq + br))) / 2)


def _cube_round(x: float, y: float, z: float) -> tuple[int, int]:
    rx, ry, rz = round(x), round(y), round(z)
    dx, dy, dz = abs(rx - x), abs(ry - y), abs(rz - z)
    if dx > dy and dx > dz:
        rx = -ry - rz
    elif dy > dz:
        ry = -rx - rz
    else:
        rz = -rx - ry
    return int(rx), int(rz)


def direct_hex_line(start: tuple[int, int], end: tuple[int, int], orientation: str = "pointy") -> list[tuple[int, int]]:
    distance = hex_distance(start, end, orientation)
    if distance == 0:
        return [start]
    ax, az = offset_to_axial(start, orientation)
    ay = -ax - az
    bx, bz = offset_to_axial(end, orientation)
    by = -bx - bz
    return [
        axial_to_offset(_cube_round(
            ax + (bx - ax) * step / distance,
            ay + (by - ay) * step / distance,
            az + (bz - az) * step / distance,
        ), orientation)
        for step in range(distance + 1)
    ]


def fastest_path(
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    in_bounds: Callable[[tuple[int, int]], bool],
    step_cost: Callable[[tuple[int, int]], float | None],
    base_cost: float = 1.0,
    orientation: str = "pointy",
) -> tuple[list[tuple[int, int]], float] | None:
    frontier: list[tuple[float, tuple[int, int]]] = [(0.0, start)]
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    cost_so_far = {start: 0.0}
    while frontier:
        _priority, current = heapq.heappop(frontier)
        if current == end:
            break
        current_axial = offset_to_axial(current, orientation)
        for dq, dr in HEX_DIRECTIONS:
            neighbor = axial_to_offset((current_axial[0] + dq, current_axial[1] + dr), orientation)
            if not in_bounds(neighbor):
                continue
            terrain_cost = step_cost(neighbor)
            if terrain_cost is None:
                continue
            candidate = cost_so_far[current] + base_cost * terrain_cost
            if candidate >= cost_so_far.get(neighbor, math.inf):
                continue
            cost_so_far[neighbor] = candidate
            priority = candidate + hex_distance(neighbor, end, orientation) * base_cost
            heapq.heappush(frontier, (priority, neighbor))
            came_from[neighbor] = current
    if end not in came_from:
        return None
    current = end
    path = []
    while current is not None:
        path.append(current)
        current = came_from[current]
    path.reverse()
    return path, round(cost_so_far[end], 3)


def _critical_rolls(value: str) -> set[int]:
    return {
        number for token in re.split(r"[^0-9]+", str(value or ""))
        if token and 1 <= (number := int(token)) <= 20
    }


def _damage_multiplier(
    roll: int,
    attack_difference: int,
    damage_rules: dict,
) -> float:
    row = damage_rules["damageMultipliers"].get(str(roll), [])
    index = attack_difference - ATTACK_DIFFERENCE_MINIMUM
    if not 0 <= index < len(row):
        return 0
    return float(row[index]) / 100


def _roll_formula(formula: str, rng) -> int:
    total = 0
    for sign, count, sides, flat in re.findall(r"([+-]?)\s*(?:(\d*)d(\d+)|(\d+))", formula.lower()):
        direction = -1 if sign == "-" else 1
        if sides:
            total += direction * sum(rng.randint(1, int(sides)) for _ in range(int(count or 1)))
        else:
            total += direction * int(flat)
    return total


def _attribute_bonus(totals: dict, keys) -> int:
    allowed = {"forza", "resistenza", "velocita", "agilita", "intelligenza", "concentrazione", "personalita", "saggezza"}
    return sum(math.floor((int(totals.get(key) or 10) - 10) / 2) for key in keys or [] if key in allowed)


def _mitigate_damage(
    attacker_tot: dict,
    defender_tot: dict,
    damage_type: str,
    raw_damage: int,
    payload: dict,
    damage_rules: dict,
) -> dict:
    penetration_flat = int(payload.get("penetrationFlat") or 0) + int(attacker_tot.get("ap") or 0)
    penetration_percent = int(payload.get("penetrationPercent") or 0) + int(attacker_tot.get("ap_percento") or 0)
    key = damage_type.lower()
    source_resistance_level = int(defender_tot.get(f"res_{key}") or 0)
    resistance_level = max(
        RESISTANCE_LEVEL_MINIMUM,
        min(RESISTANCE_LEVEL_MAXIMUM, source_resistance_level),
    )
    resistance_percent = float(
        damage_rules["resistancePercentages"][str(resistance_level)]
    )
    if damage_type == "Puro":
        flat_reduction = 0
        resistance_percent = 0
    elif damage_type in ("Contundente", "Perforante", "Taglio"):
        flat_reduction = int(defender_tot.get("rd_fis") or 0)
    else:
        flat_reduction = int(defender_tot.get(f"rd_{key}") or 0)
    if damage_type == "Puro":
        final_damage = raw_damage
    else:
        after_resistance = raw_damage * (100 - resistance_percent) / 100
        after_flat = max(0, math.floor(after_resistance - flat_reduction))
        removed = max(0, math.floor(raw_damage - after_flat))
        recovered = 0
        if damage_type in ("Contundente", "Perforante", "Taglio"):
            recovered = min(removed, max(0, math.floor(removed * penetration_percent / 100) + penetration_flat))
        final_damage = max(0, after_flat + recovered)
    return {
        "rawDamage": raw_damage,
        "flatReduction": flat_reduction,
        "penetrationFlat": penetration_flat,
        "penetrationPercent": penetration_percent,
        "effectiveFlatReduction": max(0, raw_damage - final_damage),
        "sourceResistanceLevel": source_resistance_level,
        "resistanceLevel": resistance_level,
        "resistancePercent": resistance_percent,
        "finalDamage": final_damage,
    }


def resolve_direct_damage_values(attacker, defender, payload: dict) -> dict:
    damage_type = str(payload.get("damageType") or "Contundente").title()
    if damage_type not in DAMAGE_TYPES:
        raise ValueError("Tipo di danno non valido.")
    raw_damage = max(0, int(payload.get("rawDamage") or 0))
    attacker_tot = attacker.tot if isinstance(attacker.tot, dict) else {}
    defender_tot = defender.tot if isinstance(defender.tot, dict) else {}
    damage_rules = configured_damage_rules()
    return {
        "damageType": damage_type,
        **_mitigate_damage(
            attacker_tot,
            defender_tot,
            damage_type,
            raw_damage,
            payload,
            damage_rules,
        ),
    }


def resolve_attack_values(attacker, defender, payload: dict, *, rng: random.Random | None = None) -> dict:
    rng = rng or random.SystemRandom()
    damage_rules = configured_damage_rules()
    damage_type = str(payload.get("damageType") or "Contundente").title()
    if damage_type not in DAMAGE_TYPES:
        raise ValueError("Tipo di danno non valido.")
    attacker_tot = attacker.tot if isinstance(attacker.tot, dict) else {}
    defender_tot = defender.tot if isinstance(defender.tot, dict) else {}
    attack_bonus = int(payload.get("attackBonus") or 0)
    damage_bonus = int(payload.get("damageBonus") or 0)
    damage_tier_bonus = int(payload.get("damageTierBonus") or 0)
    damage_percent_bonus = int(payload.get("damagePercentBonus") or 0)
    attack_roll = int(payload.get("attackRoll") or rng.randint(1, 20))
    if not 1 <= attack_roll <= 20:
        raise ValueError("Il tiro d20 deve essere compreso tra 1 e 20.")
    attack_value = int(attacker_tot.get("attacco") or 0) + attack_bonus
    defense = int(defender_tot.get("difesa") or 0)
    attacker_luck = int(attacker_tot.get("fortuna") or 10)
    defender_luck = int(defender_tot.get("fortuna") or 10)
    attacker_luck_modifier = math.floor((max(12, attacker_luck) - 10) / 2)
    defender_luck_modifier = math.floor((defender_luck - 10) / 2)
    attack_difference = max(
        ATTACK_DIFFERENCE_MINIMUM,
        min(
            ATTACK_DIFFERENCE_MAXIMUM,
            -3
            + attack_value
            + attack_roll
            - defense
            + attacker_luck_modifier
            - 1
            - defender_luck_modifier,
        ),
    )
    damage_multiplier = _damage_multiplier(
        attack_roll,
        attack_difference,
        damage_rules,
    )
    hit = attack_roll != 1 and damage_multiplier > 0
    tier = int(attacker_tot.get("tier") or 0) + damage_tier_bonus if hit else 0
    critical_level = "none"
    critical_bonus = 0.0
    if hit and tier > 0:
        luck_delta = attacker_luck - 10
        if attack_difference > -10:
            luck_delta -= 1
        elif attack_difference > -15:
            luck_delta -= 3
        elif attack_difference > -20:
            luck_delta -= 5
        if attack_roll in _critical_rolls(attacker.crit_minor if hasattr(attacker, "crit_minor") else attacker.crit_min):
            critical_level, critical_bonus = "minor", max(0, .4 + .05 * luck_delta)
        elif attack_roll in _critical_rolls(attacker.crit_nor):
            critical_level, critical_bonus = "normal", max(0, .6 + .07 * luck_delta)
        elif attack_roll in _critical_rolls(attacker.crit_mag):
            critical_level, critical_bonus = "major", max(0, .8 + .1 * luck_delta)
    attribute_bonus = _attribute_bonus(attacker_tot, payload.get("attributeKeys") or [])
    fixed_damage = max(0, int(payload.get("rawDamage") or 0))
    damage_formula = damage_rules["tierDamageFormulas"].get(str(tier))
    if fixed_damage:
        damage_roll = fixed_damage
        raw_after_critical = fixed_damage
        applied_multiplier = 1.0
        damage_formula_label = str(fixed_damage)
    elif hit and damage_formula:
        damage_roll = _roll_formula(damage_formula, rng)
        applied_multiplier = max(0, damage_multiplier + critical_bonus)
        raw_after_critical = max(0, math.floor((damage_roll + damage_bonus + attribute_bonus) * applied_multiplier))
        damage_formula_label = f"({damage_formula}+{damage_bonus + attribute_bonus}) x {applied_multiplier:.2f}"
    else:
        damage_roll = 0
        raw_after_critical = 0
        applied_multiplier = 0
        damage_formula_label = (
            "Fallimento critico"
            if attack_roll == 1
            else "Nessun danno"
        )
    if raw_after_critical and damage_percent_bonus:
        raw_after_critical = max(0, math.floor(raw_after_critical * (100 + damage_percent_bonus) / 100))
    mitigation = _mitigate_damage(
        attacker_tot,
        defender_tot,
        damage_type,
        raw_after_critical,
        payload,
        damage_rules,
    )
    return {
        "damageType": damage_type,
        "attackRoll": attack_roll,
        "attackTotal": attack_value + attack_roll,
        "defense": defense,
        "hit": hit,
        "margin": attack_difference,
        "attackDifference": attack_difference,
        "critical": critical_level,
        "criticalMultiplier": round(critical_bonus, 3),
        "damageMultiplier": round(damage_multiplier, 3),
        "appliedMultiplier": round(applied_multiplier, 3),
        "damageTier": tier,
        "damageFormula": damage_formula_label,
        "damageRoll": damage_roll,
        "damageBonus": damage_bonus,
        "attributeBonus": attribute_bonus,
        "damagePercentBonus": damage_percent_bonus,
        **mitigation,
    }
