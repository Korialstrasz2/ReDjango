"""Repair the spell economy stats imported from Elder Django.

Two import artifacts made every imported caster far cheaper than the original
rules allow, because the values feeding the cast cost were inflated:

1. Elder stored each magic ratio twice, once for Ordine and once for Caos.
   ReDjango collapses both onto a single unified ratio, so a skill tier that
   raised "ogni_en_x_mana" by 2 arrived as two separate +2 operations and every
   tier applied twice.
2. Elder had no automatic skill passives, so players kept a manual effect that
   summed their tiers by hand ("Cast Leggero +9"). ReDjango derives those bonuses
   from the owned skills, so importing the manual effect on top counted them
   a second time.

Both are repaired here. The second rule only removes an operation when its value
matches the total the character's own skills already grant, so a manual bonus
that no skill explains (Master's lone "ogni_en_x_mana +2") is preserved.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.characters.models import (
    EffettoPersonalizzato,
    OperazioneEffettoPersonalizzato,
    Personaggio,
    SkillPersonaggio,
)
from backend.characters.services.refresh_personaggio import refresh_personaggio
from backend.core.models import Skill


# Targets that Elder split into an Ordine and a Caos variant.
COLLAPSED_TARGETS = frozenset({"ogni_en_x_mana", "ogni_pa_x_mana"})
# Every stat the quick combat actions modal reads to price a cast.
SPELL_ECONOMY_TARGETS = frozenset(
    {"ogni_en_x_mana", "ogni_pa_x_mana", "sconto_mana_per_potere", "sconto_pa_per_potere"}
)
ELDER_MANUAL_ORIGIN_PREFIX = "Elder Django #"
TOLERANCE = Decimal("0.000001")


def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError, AttributeError):
        return None


def _operation_key(target: Any, operation: Any, value: Any, condition: Any) -> tuple[str, str, str, str]:
    return (str(target or ""), str(operation or ""), str(value or "").strip(), str(condition or "").strip())


def deduplicated_skill_passives(skill: Skill) -> tuple[list[Any], int]:
    """Skill passives with the Ordine/Caos twin of each collapsed operation dropped."""
    passives = skill.effetti_passivi if isinstance(skill.effetti_passivi, list) else []
    repaired: list[Any] = []
    removed = 0
    for passive in passives:
        operations = passive.get("operations") if isinstance(passive, dict) else None
        if not isinstance(operations, list):
            repaired.append(passive)
            continue
        kept: list[Any] = []
        seen: set[tuple[str, str, str, str]] = set()
        for operation in operations:
            if not isinstance(operation, dict) or operation.get("target") not in COLLAPSED_TARGETS:
                kept.append(operation)
                continue
            key = _operation_key(
                operation.get("target"),
                operation.get("operation"),
                operation.get("value"),
                operation.get("condition"),
            )
            if key in seen:
                removed += 1
                continue
            seen.add(key)
            kept.append(operation)
        repaired.append({**passive, "operations": kept})
    return repaired, removed


def skill_derived_spell_economy(character: Personaggio) -> dict[str, Decimal]:
    """Totals the character's own skills add to each spell economy stat.

    Duplicated Ordine/Caos operations are collapsed while reading, so the answer
    is the same before and after the stored definitions have been repaired.
    """
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    ownerships = SkillPersonaggio.objects.filter(personaggio=character).select_related("skill")
    for ownership in ownerships:
        passives, _removed = deduplicated_skill_passives(ownership.skill)
        for passive in passives:
            operations = passive.get("operations") if isinstance(passive, dict) else None
            for operation in operations if isinstance(operations, list) else []:
                if not isinstance(operation, dict):
                    continue
                target = str(operation.get("target") or "")
                if target not in SPELL_ECONOMY_TARGETS or operation.get("operation") != "add":
                    continue
                value = _decimal(operation.get("value"))
                if value is not None:
                    totals[target] += value
    return dict(totals)


def redundant_manual_operation(target: Any, operation: Any, value: Any, skill_totals: dict[str, Decimal]) -> bool:
    """True when a manual Elder bonus only restates what the skills already grant."""
    if str(target or "") not in SPELL_ECONOMY_TARGETS or operation != "add":
        return False
    expected = skill_totals.get(str(target))
    amount = _decimal(value)
    if expected is None or amount is None or expected <= 0:
        return False
    return abs(amount - expected) <= TOLERANCE


def _duplicate_operation_ids(effect: EffettoPersonalizzato) -> list[int]:
    seen: set[tuple[str, str, str, str]] = set()
    duplicates: list[int] = []
    for operation in effect.operazioni.all():
        if operation.bersaglio not in COLLAPSED_TARGETS:
            continue
        key = _operation_key(
            operation.bersaglio, operation.operazione, operation.valore, operation.condizione
        )
        if key in seen:
            duplicates.append(operation.id)
            continue
        seen.add(key)
    return duplicates


def repair_spell_economy(*, apply: bool = False) -> dict[str, Any]:
    repaired_skills: list[dict[str, Any]] = []
    for skill in Skill.objects.all():
        passives, removed = deduplicated_skill_passives(skill)
        if not removed:
            continue
        repaired_skills.append({"skill": skill.nome, "removedOperations": removed})
        if apply:
            skill.effetti_passivi = passives
            skill.save(update_fields=["effetti_passivi", "updated_at"])

    stale_operation_ids: list[int] = []
    stale_effect_ids: list[int] = []
    duplicates_removed = 0
    manual_report: list[dict[str, Any]] = []
    touched_characters: set[int] = set()

    for character in Personaggio.objects.all():
        skill_totals = skill_derived_spell_economy(character)
        effects = EffettoPersonalizzato.objects.filter(personaggio=character).prefetch_related("operazioni")
        for effect in effects:
            duplicates = _duplicate_operation_ids(effect)
            if duplicates:
                stale_operation_ids.extend(duplicates)
                duplicates_removed += len(duplicates)
                touched_characters.add(character.id)
            if not effect.origine.startswith(ELDER_MANUAL_ORIGIN_PREFIX):
                continue
            operations = list(effect.operazioni.all())
            redundant = [
                operation
                for operation in operations
                if redundant_manual_operation(
                    operation.bersaglio, operation.operazione, operation.valore, skill_totals
                )
            ]
            if not redundant:
                continue
            stale_operation_ids.extend(operation.id for operation in redundant)
            touched_characters.add(character.id)
            if len(redundant) == len(operations):
                stale_effect_ids.append(effect.id)
            manual_report.append(
                {
                    "character": character.nome,
                    "effect": effect.nome,
                    "operations": [
                        {"target": operation.bersaglio, "value": str(operation.valore)}
                        for operation in redundant
                    ],
                    "effectRemoved": len(redundant) == len(operations),
                }
            )

    if apply:
        OperazioneEffettoPersonalizzato.objects.filter(id__in=stale_operation_ids).delete()
        EffettoPersonalizzato.objects.filter(id__in=stale_effect_ids).delete()
        for character in Personaggio.objects.filter(id__in=touched_characters):
            refresh_personaggio(character)

    return {
        "repairedSkills": repaired_skills,
        "duplicateSkillOperationsRemoved": duplicates_removed,
        "redundantManualEffects": manual_report,
        "affectedCharacters": sorted(touched_characters),
    }
