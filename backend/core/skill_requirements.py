from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.characters.models import Personaggio
from backend.core.models import Skill


CHARACTERISTIC_LABELS = {
    "forza": "Forza",
    "resistenza": "Resistenza",
    "velocita": "Velocità",
    "agilita": "Agilità",
    "intelligenza": "Intelligenza",
    "concentrazione": "Concentrazione",
    "personalita": "Personalità",
    "saggezza": "Saggezza",
    "fortuna": "Fortuna",
}


def _requirements(skill: Skill) -> list[Mapping[str, Any]]:
    metadata = skill.metadata if isinstance(skill.metadata, Mapping) else {}
    rules = metadata.get("unlockRequirements", [])
    if not isinstance(rules, list):
        return []
    return [rule for rule in rules if isinstance(rule, Mapping)]


def _total(character: Personaggio, stat: str) -> float:
    totals = character.tot if isinstance(character.tot, Mapping) else {}
    try:
        return float(totals.get(stat, 0) or 0)
    except (TypeError, ValueError):
        return 0


def structured_requirement_reasons(character: Personaggio, skill: Skill) -> list[str]:
    reasons: list[str] = []
    for rule in _requirements(skill):
        rule_type = str(rule.get("type") or "").strip().lower()
        try:
            minimum = float(rule.get("minimum", 0) or 0)
        except (TypeError, ValueError):
            continue
        if rule_type == "stat_minimum":
            stat = str(rule.get("stat") or "").strip().lower()
            if stat not in CHARACTERISTIC_LABELS:
                continue
            current = _total(character, stat)
            if current < minimum:
                reasons.append(
                    f"Richiede {CHARACTERISTIC_LABELS[stat]} almeno {minimum:g} (attuale: {current:g})."
                )
        elif rule_type == "any_stat_minimum":
            raw_stats = rule.get("stats", [])
            stats = [
                str(stat).strip().lower()
                for stat in raw_stats
                if str(stat).strip().lower() in CHARACTERISTIC_LABELS
            ] if isinstance(raw_stats, list) else []
            if stats and not any(_total(character, stat) >= minimum for stat in stats):
                reasons.append(f"Richiede almeno una caratteristica a {minimum:g}.")
    return reasons

