from __future__ import annotations

import hashlib
import random
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from django.db import transaction

from backend.characters.models import (
    EffettiPersonaggio,
    EffettoPersonalizzato,
    Equip,
    Faretra,
    Note,
    OperazioneEffettoPersonalizzato,
    Personaggio,
    Zaino,
)
from backend.characters.services.refresh_personaggio import refresh_personaggio
from backend.characters.race_rules import RACE_NAMES, subraces_for
from backend.core.api import ApiError
from backend.core.competence_defaults import default_competence_state
from backend.core.models import Oggetto, Skill, Unit
from backend.core.skill_pricing import skill_price
from backend.core.skill_requirements import structured_requirement_reasons
from backend.core.skill_services import unlock_skill


UNIT_KINDS = {
    "creature": "Creatura",
    "humanoid": "Umanoide",
}

# These vectors deliberately use the profile dimensions already present on the
# imported Skill catalogue.  A Unit can override any vector through
# generation_rules.coreProfile, so adding or renaming a campaign-specific core
# does not require a migration.
DEFAULT_CORE_PROFILES: dict[str, dict[str, float]] = {
    "warrior": {
        "core_fisico": 4,
        "focus_combat": 3,
        "attacco": 2,
        "difesa": 2,
        "range_skill": 1,
    },
    "mage": {
        "core_magico": 4,
        "natura_magica": 3,
        "area_e_multi_target": 2,
        "controllo_situazionale": 2,
        "supporto_party": 1,
    },
    "stealth": {
        "esplorazione_infiltrazione": 4,
        "range_skill": 2,
        "controllo_situazionale": 2,
        "core_fisico": 1,
        "tecnica_crafting": 1,
    },
    "support": {
        "supporto_party": 4,
        "sociale": 3,
        "controllo_situazionale": 2,
        "core_magico": 1,
        "difesa": 1,
    },
    "specialist": {
        "tecnica_crafting": 4,
        "esplorazione_infiltrazione": 2,
        "controllo_situazionale": 2,
        "sociale": 1,
        "supporto_party": 1,
    },
}

CORE_LABELS = {
    "warrior": "Guerriero",
    "mage": "Mago",
    "stealth": "Furtivo",
    "support": "Supporto",
    "specialist": "Specialista",
}

DEFAULT_XP_BASE = 20
DEFAULT_XP_GROWTH = 1
DEFAULT_CORE_SHARE = 0.5
DEFAULT_MAX_SKILLS_PER_POOL_PER_LEVEL = 2
MAX_GENERATED_LEVEL = 20
AUTO_VARIANT_VALUES = {"", "auto", "casuale", "random"}
PERK_MILESTONE_SCHEDULE = {
    1: {"minor": "+1 caratteristica"},
    2: {"minor": "+1 caratteristica", "major": "Migliore (1)"},
    3: {"minor": "+1 caratteristica"},
    4: {"minor": "+1 caratteristica", "major": "Migliore (2)"},
    5: {"minor": "Sblocca 1 classe"},
    6: {"minor": "+1 caratteristica", "major": "Abile"},
    7: {"minor": "Sblocca 1 classe"},
    8: {"minor": "+1 caratteristica", "major": "Seconda Chance"},
    9: {"minor": "una volta a combat, hai +3 PA, instant"},
    10: {"minor": "+1 caratteristica", "major": "Muletto"},
    11: {"minor": "Il primo tiro 1 della giornata è rerollato gratuitamente."},
    12: {"minor": "+1 caratteristica", "major": "Organizzato"},
    13: {"minor": "estrarre da zaino costa 1 pa non 3"},
    14: {"minor": "+1 caratteristica", "major": "Riposo Rigenerante"},
    15: {"minor": "+4 punti exp generali"},
    16: {"minor": "+1 caratteristica", "major": "Sfuggente 1"},
    17: {"minor": "+1 fortuna."},
    18: {"minor": "+1 caratteristica", "major": "Sfuggente 2"},
    19: {
        "minor": (
            "Quando dormi recuperi anche il 100% dei punti energia. "
            "Se eri già full en, hai +20% en al risveglio."
        )
    },
    20: {"minor": "+1 caratteristica"},
}
CHARACTERISTIC_PERK_NAMES = {
    "+1 caratteristica",
    "migliore (1)",
    "migliore (2)",
    "migliore (3)",
    "migliore (4)",
    "migliore (5)",
}
CORE_CHARACTERISTIC_WEIGHTS = {
    "warrior": {"forza": 5, "resistenza": 4, "agilita": 3, "velocita": 2, "fortuna": 1},
    "mage": {"intelligenza": 5, "concentrazione": 4, "saggezza": 3, "fortuna": 1},
    "stealth": {"agilita": 5, "velocita": 4, "fortuna": 3, "concentrazione": 2},
    "support": {"personalita": 5, "saggezza": 4, "intelligenza": 2, "fortuna": 1},
    "specialist": {"intelligenza": 4, "concentrazione": 4, "agilita": 2, "fortuna": 1},
}
UNIT_STAT_PROFILE_LABELS = {
    "very_low": "Molto basso",
    "low": "Basso",
    "medium": "Medio",
    "high": "Alto",
    "very_high": "Molto alto",
    "custom": "Personalizzato",
}


def _preset_ranges(*ranges: tuple[float, float]) -> dict[str, dict[str, float]]:
    return {
        key: {"level1": level_1, "level20": level_20}
        for key, (level_1, level_20) in zip(
            ("very_low", "low", "medium", "high", "very_high"),
            ranges,
            strict=True,
        )
    }


_PRIMARY_PRESETS = _preset_ranges((4, 10), (6, 16), (8, 22), (11, 30), (15, 40))
_PF_PRESETS = _preset_ranges((10, 50), (14, 75), (18, 100), (25, 150), (35, 225))
_POOL_PRESETS = _preset_ranges((3, 20), (4, 25), (6, 30), (8, 35), (10, 40))
_PA_PRESETS = _preset_ranges((5, 15), (6, 20), (7, 25), (9, 32), (12, 40))
_COMBAT_PRESETS = _preset_ranges((6, 25), (8, 40), (10, 55), (12, 75), (15, 100))
_RESISTANCE_PRESETS = _preset_ranges((-4, 0), (-2, 1), (0, 2), (1, 4), (2, 5))
_REDUCTION_PRESETS = _preset_ranges((0, 1), (0, 2), (1, 3), (1, 5), (2, 7))
_TIER_PRESETS = _preset_ranges((2, 6), (3, 9), (4, 12), (5, 15), (6, 18))


def _curve_variable(key: str, label: str, presets: Mapping[str, Mapping[str, float]]) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "presets": {name: dict(values) for name, values in presets.items()},
    }


UNIT_STAT_CURVE_VARIABLES = (
    _curve_variable("pf", "Punti ferita", _PF_PRESETS),
    _curve_variable("mana", "Mana", _PF_PRESETS),
    _curve_variable("energia", "Energia", _POOL_PRESETS),
    _curve_variable("potere", "Potere", _POOL_PRESETS),
    _curve_variable("pa", "Punti azione", _PA_PRESETS),
    _curve_variable("attacco", "Attacco", _COMBAT_PRESETS),
    _curve_variable("difesa", "Difesa", _COMBAT_PRESETS),
    *(
        _curve_variable(key, label, _PRIMARY_PRESETS)
        for key, label in (
            ("fortuna", "Fortuna"),
            ("forza", "Forza"),
            ("resistenza", "Resistenza"),
            ("velocita", "Velocità"),
            ("agilita", "Agilità"),
            ("intelligenza", "Intelligenza"),
            ("concentrazione", "Concentrazione"),
            ("personalita", "Personalità"),
            ("saggezza", "Saggezza"),
        )
    ),
    *(
        _curve_variable(key, label, _RESISTANCE_PRESETS)
        for key, label in (
            ("res_contundente", "Resistenza contundente"),
            ("res_taglio", "Resistenza al taglio"),
            ("res_perforante", "Resistenza perforante"),
            ("res_fuoco", "Resistenza al fuoco"),
            ("res_gelo", "Resistenza al gelo"),
            ("res_elettro", "Resistenza elettrica"),
        )
    ),
    *(
        _curve_variable(key, label, _REDUCTION_PRESETS)
        for key, label in (
            ("rd_fis", "Riduzione fisica"),
            ("rd_fuoco", "Riduzione fuoco"),
            ("rd_gelo", "Riduzione gelo"),
            ("rd_elettro", "Riduzione elettrica"),
            ("ap", "Perforazione armatura"),
        )
    ),
    _curve_variable("tier", "Tier", _TIER_PRESETS),
)
UNIT_STAT_CURVE_VARIABLE_KEYS = {entry["key"] for entry in UNIT_STAT_CURVE_VARIABLES}
COMPETENCE_WEIGHT_TABLE = {
    -5: 0.0,
    -4: 0.02,
    -3: 0.05,
    -2: 0.1,
    -1: 0.25,
    0: 0.75,
    1: 2.0,
    2: 4.0,
    3: 8.0,
    4: 14.0,
    5: 22.0,
}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _integer(value: Any, fallback: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = fallback
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def _number(value: Any, fallback: float = 0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _unit_rules(unit: Unit) -> dict[str, Any]:
    return _mapping(unit.generation_rules)


def unit_kind(unit: Unit) -> str:
    value = str(_unit_rules(unit).get("kind") or "").strip().lower()
    if value == "animal":
        value = "creature"
    return value if value in UNIT_KINDS else ""


def unit_core_key(unit: Unit) -> str:
    return str(_unit_rules(unit).get("coreKey") or "").strip().lower()


def unit_catalog_entry(unit: Unit) -> dict[str, Any]:
    kind = unit_kind(unit)
    core_key = unit_core_key(unit)
    rules = _unit_rules(unit)
    has_equipment = bool(_equipment_slots(unit) or _list(_mapping(unit.equipment_profiles).get("groups")))
    has_archetype_profile = bool(
        _list(unit.skill_unlocks)
        or _profile_vector(unit.archetipo_tags)
        or _profile_vector(rules.get("archetypeProfile"))
    )
    non_humanoid_is_clean = not has_equipment and not _list(unit.skill_unlocks)
    humanoid_is_ready = bool(
        (core_key or _profile_vector(rules.get("coreProfile")))
        and has_equipment
        and has_archetype_profile
    )
    return {
        "id": unit.id,
        "name": unit.nome,
        "category": unit.categoria,
        "description": unit.archetipo_descrizione or unit.lore_description,
        "generationKind": kind,
        "generationKindLabel": UNIT_KINDS.get(kind, "Non configurato"),
        "coreKey": core_key,
        "coreLabel": CORE_LABELS.get(core_key, core_key.replace("_", " ").title()),
        "hasEquipment": kind == "humanoid" and has_equipment,
        "hasSkills": kind == "humanoid",
        "ready": bool(kind) and (humanoid_is_ready if kind == "humanoid" else non_humanoid_is_clean),
    }


def _stable_seed(unit: Unit, variant: str) -> int:
    identity = f"unit:{unit.pk}:variant:{variant or 'standard'}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(identity).digest()[:8], "big")


def _resolved_variant(raw_variant: str) -> tuple[str, bool]:
    requested = str(raw_variant or "").strip()[:80]
    if requested.casefold() in AUTO_VARIANT_VALUES:
        return f"auto-{uuid4().hex}", True
    return requested, False


def _unique_character_name(base: str) -> str:
    clean = str(base or "Unità").strip()[:170] or "Unità"
    if not Personaggio.objects.filter(nome=clean).exists():
        return clean
    suffix = 2
    while Personaggio.objects.filter(nome=f"{clean[:160]} {suffix}").exists():
        suffix += 1
    return f"{clean[:160]} {suffix}"


def _profile_vector(value: Any) -> dict[str, float]:
    return {
        str(key): number
        for key, raw in _mapping(value).items()
        if (number := _number(raw)) != 0
    }


def _skill_generation_tags(skill: Skill) -> dict[str, Any]:
    tags = _mapping(skill.profile_tags)
    return _mapping(tags.get("generation"))


def _profile_score(skill: Skill, vector: Mapping[str, float]) -> float:
    tags = _mapping(skill.profile_tags)
    score = 0.0
    for key, desired in vector.items():
        skill_value = _number(tags.get(key))
        if desired >= 0:
            score += desired * skill_value
        else:
            # A negative archetype preference is an exclusion pressure, not
            # an affinity with equally negative Skill metadata.
            score -= abs(desired) * max(skill_value, 0)
    return score


def _is_magic_skill(skill: Skill) -> bool:
    if skill.famiglia.is_perk:
        return False
    tags = _mapping(skill.profile_tags)
    family_group = skill.famiglia.gruppo
    if family_group.slug == "scuole-di-magia" or "magia" in family_group.nome.casefold():
        return True
    try:
        skill.spell_definition
    except Exception:
        pass
    else:
        return True
    return _number(tags.get("core_magico")) > 0 or _number(tags.get("natura_magica")) > 0


def _skill_allowed_by_policy(unit: Unit, skill: Skill) -> bool:
    rules = _unit_rules(unit)
    magic_policy = str(rules.get("magicPolicy") or "any").strip().lower()
    if magic_policy == "none" and _is_magic_skill(skill):
        return False

    family_id = skill.famiglia_id
    family_name = skill.famiglia.nome.casefold()
    if skill.famiglia.is_classe:
        allowed = {
            str(value).strip().casefold()
            for value in _list(rules.get("allowedClassFamilies"))
            if str(value).strip()
        }
        if not allowed or (str(family_id) not in allowed and family_name not in allowed):
            return False
    if skill.famiglia.is_religione:
        allowed = {
            str(value).strip().casefold()
            for value in _list(rules.get("allowedReligionFamilies"))
            if str(value).strip()
        }
        if not allowed or (str(family_id) not in allowed and family_name not in allowed):
            return False
    return True


def _entry_skill_id(raw: Any) -> int | None:
    value = raw.get("skillId") if isinstance(raw, Mapping) else raw
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _entry_perk_tier(raw: Any, skill: Skill | None = None) -> str:
    entry = _mapping(raw)
    value = str(entry.get("perkTier") or entry.get("role") or "").strip().lower()
    if value in {"minor", "minor_perk", "perk_minor"}:
        return "minor"
    if value in {"major", "major_perk", "perk_major"}:
        return "major"
    if skill is None or not skill.famiglia.is_perk:
        return ""
    generated = str(_skill_generation_tags(skill).get("perkTier") or "").strip().lower()
    if generated in {"minor", "major"}:
        return generated
    family_name = skill.famiglia.nome.casefold()
    if "minor" in family_name:
        return "minor"
    if "maggior" in family_name or "major" in family_name:
        return "major"
    return ""


def _candidate(
    skill: Skill,
    *,
    source: str,
    weight: float,
    raw: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    raw = raw or {}
    generated = _skill_generation_tags(skill)
    return {
        "skill": skill,
        "source": source,
        "weight": max(0.1, _number(raw.get("weight"), _number(generated.get("weight"), weight))),
        "minLevel": _integer(raw.get("minLevel", generated.get("minLevel")), 1, minimum=1),
        "maxLevel": _integer(
            raw.get("maxLevel", generated.get("maxLevel")),
            MAX_GENERATED_LEVEL,
            minimum=1,
        ),
        "requiredAtLevel": (
            _integer(raw.get("requiredAtLevel"), 0, minimum=1)
            if raw.get("requiredAtLevel") not in (None, "")
            else None
        ),
    }


def _explicit_skill_entries(unit: Unit, skills_by_id: Mapping[int, Skill]) -> list[tuple[Skill, dict[str, Any]]]:
    result: list[tuple[Skill, dict[str, Any]]] = []
    for raw in _list(unit.skill_unlocks):
        skill_id = _entry_skill_id(raw)
        skill = skills_by_id.get(skill_id) if skill_id is not None else None
        if skill is not None:
            result.append((skill, _mapping(raw)))
    return result


def _core_profile(unit: Unit) -> dict[str, float]:
    rules = _unit_rules(unit)
    configured = _profile_vector(rules.get("coreProfile"))
    if configured:
        return configured
    return dict(DEFAULT_CORE_PROFILES.get(unit_core_key(unit), {}))


def _archetype_profile(unit: Unit) -> dict[str, float]:
    configured = _profile_vector(_unit_rules(unit).get("archetypeProfile"))
    return configured or _profile_vector(unit.archetipo_tags)


def _core_affinity(skill: Skill, core_key: str, vector: Mapping[str, float]) -> float:
    generated = _skill_generation_tags(skill)
    cores = generated.get("cores")
    if isinstance(cores, Mapping) and core_key in cores:
        return max(0.1, _number(cores.get(core_key), 1))
    if isinstance(cores, (list, tuple)) and core_key in {str(value) for value in cores}:
        return max(0.1, _number(generated.get("weight"), 1))
    return _profile_score(skill, vector)


def _expand_prerequisites(candidates: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    by_id = {entry["skill"].id: entry for entry in candidates}
    queue = list(candidates)
    while queue:
        parent = queue.pop()
        for prerequisite in parent["skill"].prerequisiti.all():
            if prerequisite.famiglia.is_perk or prerequisite.id in by_id:
                continue
            entry = _candidate(
                prerequisite,
                source=source,
                weight=max(parent["weight"] + 1, 2),
                raw={
                    "minLevel": 1,
                    "maxLevel": parent["maxLevel"],
                    "requiredAtLevel": parent["requiredAtLevel"],
                },
            )
            by_id[prerequisite.id] = entry
            queue.append(entry)
    return list(by_id.values())


def _skill_pools(unit: Unit, all_skills: list[Skill]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    core_vector = _core_profile(unit)
    archetype_vector = _archetype_profile(unit)
    skills_by_id = {skill.id: skill for skill in all_skills}
    explicit = _explicit_skill_entries(unit, skills_by_id)

    def explicit_weight(skill: Skill, vector: Mapping[str, float]) -> float:
        return max(10, _profile_score(skill, vector) * 10)

    explicit_archetype = [
        _candidate(skill, source="archetype", weight=explicit_weight(skill, archetype_vector), raw=raw)
        for skill, raw in explicit
        if not skill.famiglia.is_perk
        and _skill_allowed_by_policy(unit, skill)
        and str(raw.get("pool") or "archetype").strip().lower() != "core"
        and not _entry_perk_tier(raw, skill)
    ]
    explicit_core = [
        _candidate(skill, source="core", weight=explicit_weight(skill, core_vector), raw=raw)
        for skill, raw in explicit
        if not skill.famiglia.is_perk
        and _skill_allowed_by_policy(unit, skill)
        and str(raw.get("pool") or "").strip().lower() == "core"
        and not _entry_perk_tier(raw, skill)
    ]
    core_candidates = _expand_prerequisites(explicit_core, "core")
    archetype_candidates = _expand_prerequisites(explicit_archetype, "archetype")

    perks: dict[str, list[dict[str, Any]]] = {"minor": [], "major": []}
    for tier in perks:
        explicit_tier = [
            _candidate(
                skill,
                source=f"perk:{tier}",
                weight=max(1, _profile_score(skill, core_vector) + _profile_score(skill, archetype_vector)),
                raw=raw,
            )
            for skill, raw in explicit
            if _entry_perk_tier(raw, skill) == tier
        ]
        if explicit_tier:
            perks[tier] = explicit_tier
            continue
        scored = []
        for skill in all_skills:
            if _entry_perk_tier({}, skill) != tier:
                continue
            if not _skill_allowed_by_policy(unit, skill):
                continue
            score = _profile_score(skill, core_vector) + _profile_score(skill, archetype_vector)
            scored.append(_candidate(skill, source=f"perk:{tier}", weight=max(0.1, score)))
        scored.sort(key=lambda entry: (-entry["weight"], entry["skill"].id))
        # The canonical Elder AI schedule is resolved by current Skill name.
        # Keep the complete perk catalogue here so a low profile score cannot
        # trim a scheduled perk and silently replace it with an unrelated one.
        perks[tier] = scored
    return core_candidates, archetype_candidates, perks


def _weighted_choice(rng: random.Random, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(candidates, key=lambda entry: entry["skill"].id)
    total = sum(max(0.1, _number(entry.get("weight"), 1)) for entry in ordered)
    marker = rng.random() * total
    for entry in ordered:
        marker -= max(0.1, _number(entry.get("weight"), 1))
        if marker <= 0:
            return entry
    return ordered[-1]


def _passive_ids(skill: Skill) -> list[str]:
    return [
        str(passive.get("id"))
        for passive in _list(skill.effetti_passivi)
        if isinstance(passive, Mapping) and passive.get("id")
    ]


def _owned_skill_ids(character: Personaggio) -> set[int]:
    return set(character.skill_sbloccate.filter(archived_at__isnull=True).values_list("skill_id", flat=True))


def _candidate_is_available(entry: Mapping[str, Any], character: Personaggio, level: int, owned_ids: set[int]) -> bool:
    skill: Skill = entry["skill"]
    if skill.id in owned_ids or not entry["minLevel"] <= level <= entry["maxLevel"]:
        return False
    if any(prerequisite.id not in owned_ids for prerequisite in skill.prerequisiti.all()):
        return False
    return not structured_requirement_reasons(character, skill)


def _grant_perk(
    character: Personaggio,
    candidates: list[dict[str, Any]],
    tier: str,
    level: int,
    rng: random.Random,
    report: dict[str, Any],
) -> None:
    owned_ids = _owned_skill_ids(character)
    available = [
        entry
        for entry in candidates
        if _candidate_is_available(entry, character, level, owned_ids)
    ]
    if not available:
        report["warnings"].append(f"Nessun perk {tier} compatibile disponibile al livello {level}.")
        return
    entry = _weighted_choice(rng, available)
    skill = entry["skill"]
    unlock_skill(
        character.id,
        skill.id,
        {"general": 0, "red": 0, "green": 0, "blue": 0},
        _passive_ids(skill),
        note=f"Concesso dalla progressione Unit: perk {tier}, livello {level}.",
    )
    report["perks"].append(
        {"skillId": skill.id, "name": skill.nome, "tier": tier, "level": level}
    )


def _characteristic_improvement(
    character: Personaggio,
    unit: Unit,
    skill: Skill,
    level: int,
    rng: random.Random,
) -> str:
    weights = CORE_CHARACTERISTIC_WEIGHTS.get(
        unit_core_key(unit),
        CORE_CHARACTERISTIC_WEIGHTS["specialist"],
    )
    targets = sorted(weights)
    target = rng.choices(targets, weights=[weights[key] for key in targets], k=1)[0]
    effect = EffettoPersonalizzato.objects.create(
        personaggio=character,
        nome=f"{skill.nome} · livello {level}"[:180],
        descrizione=f"Miglioramento di {target} concesso dalla progressione perk della Unit.",
        origine=f"Unit perk: {skill.nome}"[:180],
        icona=target,
        temporaneo=False,
        ordine=character.effetti_personalizzati.count(),
    )
    OperazioneEffettoPersonalizzato.objects.create(
        effetto=effect,
        ordine=0,
        bersaglio=target,
        operazione="add",
        valore="1",
        condizione="",
    )
    return target


def _grant_progression_perk(
    character: Personaggio,
    unit: Unit,
    candidates: list[dict[str, Any]],
    tier: str,
    level: int,
    rng: random.Random,
    report: dict[str, Any],
    *,
    use_milestone: bool,
) -> None:
    scheduled_name = (
        str(_mapping(PERK_MILESTONE_SCHEDULE.get(level)).get(tier) or "").strip()
        if use_milestone
        else ""
    )
    scheduled = next(
        (
            entry
            for entry in candidates
            if entry["skill"].nome.casefold() == scheduled_name.casefold()
        ),
        None,
    )
    if scheduled is None:
        _grant_perk(character, candidates, tier, level, rng, report)
        return

    skill = scheduled["skill"]
    owned_ids = _owned_skill_ids(character)
    repeatable_characteristic = skill.nome.casefold() in CHARACTERISTIC_PERK_NAMES
    if skill.id not in owned_ids:
        if not _candidate_is_available(scheduled, character, level, owned_ids):
            _grant_perk(character, candidates, tier, level, rng, report)
            return
        unlock_skill(
            character.id,
            skill.id,
            {"general": 0, "red": 0, "green": 0, "blue": 0},
            _passive_ids(skill),
            note=f"Concesso dalla progressione perk Unit: {tier}, livello {level}.",
        )
    elif not repeatable_characteristic:
        _grant_perk(character, candidates, tier, level, rng, report)
        return

    improvement = (
        _characteristic_improvement(character, unit, skill, level, rng)
        if repeatable_characteristic
        else ""
    )
    report["perks"].append(
        {
            "skillId": skill.id,
            "name": skill.nome,
            "tier": tier,
            "level": level,
            "repeatable": repeatable_characteristic,
            "improvement": improvement,
        }
    )


def _use_milestone_progression(rng: random.Random) -> bool:
    """Choose the unified perk path independently for each generated level."""
    return rng.random() < 0.5


def _spend_pool(
    character: Personaggio,
    candidates: list[dict[str, Any]],
    source: str,
    level: int,
    bank: int,
    rng: random.Random,
    report: dict[str, Any],
    *,
    limit: int,
) -> int:
    purchased = 0
    while purchased < limit:
        owned_ids = _owned_skill_ids(character)
        affordable: list[tuple[dict[str, Any], int]] = []
        for entry in candidates:
            if not _candidate_is_available(entry, character, level, owned_ids):
                continue
            cost = max(0, int(skill_price(entry["skill"], character)["calculatedCost"]))
            if cost <= bank:
                affordable.append((entry, cost))
        if not affordable:
            break
        due = [
            pair
            for pair in affordable
            if pair[0].get("requiredAtLevel") is not None
            and int(pair[0]["requiredAtLevel"]) <= level
        ]
        choices = due or affordable
        entry = _weighted_choice(rng, [pair[0] for pair in choices])
        cost = next(pair_cost for pair_entry, pair_cost in choices if pair_entry is entry)
        skill = entry["skill"]
        character.pe_generali = int(character.pe_generali or 0) + cost
        character.save(update_fields=["pe_generali", "updated_at"])
        unlock_skill(
            character.id,
            skill.id,
            {"general": cost, "red": 0, "green": 0, "blue": 0},
            _passive_ids(skill),
            note=f"Acquistata dalla progressione Unit: {source}, livello {level}.",
        )
        character.refresh_from_db()
        bank -= cost
        purchased += 1
        report["skills"].append(
            {
                "skillId": skill.id,
                "name": skill.nome,
                "source": source,
                "level": level,
                "cost": cost,
            }
        )
    return bank


def _spend_level_budget(
    character: Personaggio,
    core_candidates: list[dict[str, Any]],
    archetype_candidates: list[dict[str, Any]],
    level: int,
    bank: int,
    rng: random.Random,
    report: dict[str, Any],
    *,
    core_share: float,
    limit_per_pool: int,
) -> int:
    bought = {"core": 0, "archetype": 0}
    blocked: set[str] = set()
    pools = {"core": core_candidates, "archetype": archetype_candidates}
    while len(blocked) < 2:
        spent_core = sum(entry["cost"] for entry in report["skills"] if entry["source"] == "core")
        spent_archetype = sum(entry["cost"] for entry in report["skills"] if entry["source"] == "archetype")
        spent_total = spent_core + spent_archetype
        current_core_share = spent_core / spent_total if spent_total else 0
        preferred = "core" if current_core_share < core_share else "archetype"
        order = (preferred, "archetype" if preferred == "core" else "core")
        progressed = False
        for source in order:
            if source in blocked or bought[source] >= limit_per_pool:
                blocked.add(source)
                continue
            before = bank
            purchases_before = len(report["skills"])
            bank = _spend_pool(
                character,
                pools[source],
                source,
                level,
                bank,
                rng,
                report,
                limit=1,
            )
            if bank < before or len(report["skills"]) > purchases_before:
                bought[source] += 1
                progressed = True
                break
            blocked.add(source)
        if not progressed:
            break
    return bank


def _spend_remaining_budget(
    character: Personaggio,
    core_candidates: list[dict[str, Any]],
    archetype_candidates: list[dict[str, Any]],
    level: int,
    bank: int,
    rng: random.Random,
    report: dict[str, Any],
    *,
    core_share: float,
    passes: int,
) -> int:
    for _pass in range(passes):
        before = bank
        bank = _spend_level_budget(
            character,
            core_candidates,
            archetype_candidates,
            level,
            bank,
            rng,
            report,
            core_share=core_share,
            limit_per_pool=20,
        )
        if bank == before:
            break
    return bank


def _xp_at_level(level: int, rules: Mapping[str, Any]) -> int:
    if level == 1:
        return _integer(rules.get("startingXp"), 0, minimum=0)
    profile = _mapping(rules.get("xpPerLevel"))
    base = _integer(profile.get("base"), DEFAULT_XP_BASE, minimum=0)
    growth = _integer(profile.get("growth"), DEFAULT_XP_GROWTH, minimum=0)
    return base + (level - 1) * growth


def _competence_xp_at_level(level: int, rules: Mapping[str, Any]) -> int:
    profile = _mapping(rules.get("competenceXp"))
    if level == 1:
        return _integer(profile.get("starting"), 0, minimum=0)
    return _integer(profile.get("base"), 0, minimum=0) + (level - 1) * _integer(
        profile.get("growth"),
        0,
        minimum=0,
    )


def _generated_competences(
    unit: Unit,
    level: int,
    rules: Mapping[str, Any],
    rng: random.Random,
) -> tuple[dict[str, dict[str, int]], dict[str, Any]]:
    raw_profile = _mapping(unit.profilo_competenze)
    state = default_competence_state()
    direct_state = {
        key: value
        for key, value in raw_profile.items()
        if key in state and isinstance(value, Mapping)
    }
    if direct_state:
        for key, value in direct_state.items():
            state[key] = {
                "barra1": _integer(value.get("barra1"), 0, minimum=0, maximum=7),
                "barra2": _integer(value.get("barra2"), 0, minimum=0, maximum=7),
                "extra": _integer(value.get("extra"), 0),
            }
        return state, {"earned": 0, "spent": 0, "remaining": 0, "mode": "fixed"}

    weighted = []
    for key in state:
        score = _integer(raw_profile.get(key), 0, minimum=-5, maximum=5)
        weight = COMPETENCE_WEIGHT_TABLE[score]
        if weight > 0:
            weighted.append({"key": key, "weight": weight})
    earned = sum(_competence_xp_at_level(current, rules) for current in range(1, level + 1))
    remaining = earned
    spent = 0
    while remaining > 0 and weighted:
        candidates = []
        for entry in weighted:
            current = state[entry["key"]]
            if entry["key"] == "sopravvivenza":
                bar = "barra1"
            else:
                bar = "barra1" if current["barra1"] <= current["barra2"] else "barra2"
            rank = current[bar]
            if rank >= 7:
                continue
            cost = rank + 1
            if cost <= remaining:
                candidates.append({**entry, "bar": bar, "cost": cost})
        if not candidates:
            break
        total = sum(entry["weight"] for entry in candidates)
        marker = rng.random() * total
        chosen = candidates[-1]
        for entry in sorted(candidates, key=lambda candidate: candidate["key"]):
            marker -= entry["weight"]
            if marker <= 0:
                chosen = entry
                break
        state[chosen["key"]][chosen["bar"]] += 1
        remaining -= chosen["cost"]
        spent += chosen["cost"]
    return state, {
        "earned": earned,
        "spent": spent,
        "remaining": remaining,
        "mode": "weighted",
    }


def _level_actions(unit: Unit, level: int) -> list[dict[str, Any]]:
    raw_actions = unit.skill_actions
    if isinstance(raw_actions, Mapping):
        raw_actions = raw_actions.get("known", [])
    result = []
    for index, raw in enumerate(_list(raw_actions)):
        if not isinstance(raw, Mapping):
            continue
        minimum = _integer(raw.get("minLevel"), 1, minimum=1)
        maximum = _integer(raw.get("maxLevel"), MAX_GENERATED_LEVEL, minimum=1)
        if not minimum <= level <= maximum:
            continue
        name = str(raw.get("name") or raw.get("nome") or "").strip()
        if not name:
            continue
        result.append(
            {
                "key": str(raw.get("key") or f"unit-{unit.id}-action-{index + 1}"),
                "name": name[:180],
                "description": str(raw.get("description") or raw.get("descrizione") or ""),
                "costs": _mapping(raw.get("costs")),
                "trigger": str(raw.get("trigger") or ""),
                "duration": str(raw.get("duration") or ""),
                "icon": str(raw.get("icon") or "runa"),
                "unlockedAtLevel": minimum,
                "sourceUnitId": unit.id,
            }
        )
    return result


def _curve_progress(level: int, level_1: float, level_20: float) -> float:
    return max(0.0, min(1.0, (level - 1) / (MAX_GENERATED_LEVEL - 1)))


def _stat_curve_values(unit: Unit, level: int, kind: str) -> tuple[dict[str, float], list[dict[str, Any]]]:
    if kind == "humanoid" and not bool(_unit_rules(unit).get("allowHumanoidStatGrowth")):
        return {}, []
    values: dict[str, float] = {}
    trace = []
    for raw in _list(_mapping(unit.stat_profiles).get("curves")):
        curve_entry = _mapping(raw)
        key = str(curve_entry.get("key") or "").strip()
        if key not in UNIT_STAT_CURVE_VARIABLE_KEYS:
            continue
        level_1 = _number(curve_entry.get("level1"))
        level_20 = _number(curve_entry.get("level20"), level_1)
        progress = _curve_progress(level, level_1, level_20)
        value = round(level_1 + (level_20 - level_1) * progress)
        values[key] = value
        trace.append(
            {
                "key": key,
                "profile": str(curve_entry.get("profile") or "custom"),
                "level1": level_1,
                "level20": level_20,
                "value": value,
            }
        )
    return values, trace


def _stat_modifiers(unit: Unit, level: int, kind: str) -> dict[str, float]:
    profile = _mapping(unit.stat_profiles)
    base = _profile_vector(profile.get("baseModifiers") or profile.get("base"))
    allow_humanoid_growth = bool(_unit_rules(unit).get("allowHumanoidStatGrowth"))
    direct_growth_allowed = kind != "humanoid" or allow_humanoid_growth
    if direct_growth_allowed:
        per_level = _profile_vector(profile.get("perLevelModifiers") or profile.get("perLevel"))
        for key, value in per_level.items():
            base[key] = base.get(key, 0) + value * max(0, level - 1)
        for milestone in _list(profile.get("milestones")):
            if not isinstance(milestone, Mapping) or _integer(milestone.get("level"), 1, minimum=1) > level:
                continue
            for key, value in _profile_vector(milestone.get("modifiers") or milestone.get("add")).items():
                base[key] = base.get(key, 0) + value
        for band in _list(unit.levels):
            if not isinstance(band, Mapping):
                continue
            minimum = _integer(band.get("minLevel", band.get("level")), 1, minimum=1)
            maximum = _integer(band.get("maxLevel", band.get("level")), minimum, minimum=minimum)
            if minimum <= level <= maximum:
                for key, value in _profile_vector(band.get("modifiers") or band.get("stats")).items():
                    base[key] = base.get(key, 0) + value
    return base


def _create_chassis_effect(
    character: Personaggio,
    unit: Unit,
    modifiers: Mapping[str, float],
    curve_values: Mapping[str, float],
) -> None:
    usable = {key: value for key, value in modifiers.items() if value}
    absolute = {key: value for key, value in curve_values.items()}
    if not usable and not absolute:
        return
    effect = EffettoPersonalizzato.objects.create(
        personaggio=character,
        nome=f"{unit.nome} · chassis"[:180],
        descrizione="Profilo fisico deterministico dell'archetipo Unit.",
        origine=f"Unit: {unit.nome}"[:180],
        icona="runa",
        temporaneo=False,
        ordine=0,
    )
    OperazioneEffettoPersonalizzato.objects.bulk_create(
        [
            OperazioneEffettoPersonalizzato(
                effetto=effect,
                ordine=index,
                bersaglio=key,
                operazione="add",
                valore=str(value),
                condizione="",
            )
            for index, (key, value) in enumerate(sorted(usable.items()))
        ]
        + [
            OperazioneEffettoPersonalizzato(
                effetto=effect,
                ordine=len(usable) + index,
                bersaglio=key,
                operazione="strong_set",
                valore=str(value),
                condizione="",
            )
            for index, (key, value) in enumerate(sorted(absolute.items()))
        ]
    )


def _equipment_slots(unit: Unit) -> dict[str, Any]:
    profile = _mapping(unit.equipment_profiles)
    slots = profile.get("slots")
    if isinstance(slots, Mapping):
        return dict(slots)
    return {
        key: value
        for key, value in profile.items()
        if key not in {"groups", "accessoryCountByLevel", "allowDuplicates", "notes"}
        and isinstance(value, (list, tuple))
    }


def _valid_equipment_slot(slot: str) -> bool:
    try:
        field = Equip._meta.get_field(slot)
    except Exception:
        return False
    return bool(field.is_relation and field.related_model is Oggetto)


def _eligible_item_entries(raw_entries: Any, level: int, items_by_id: Mapping[int, Oggetto]) -> list[dict[str, Any]]:
    result = []
    for raw in _list(raw_entries):
        entry = _mapping(raw) if isinstance(raw, Mapping) else {"itemId": raw}
        item_id = _entry_skill_id({"skillId": entry.get("itemId")})
        item = items_by_id.get(item_id) if item_id is not None else None
        if item is None:
            continue
        minimum = _integer(entry.get("minLevel"), 1, minimum=1)
        maximum = _integer(entry.get("maxLevel"), MAX_GENERATED_LEVEL, minimum=1)
        if minimum <= level <= maximum:
            result.append(
                {
                    "item": item,
                    "weight": max(0.1, _number(entry.get("weight"), 1)),
                    "chance": max(0, min(1, _number(entry.get("chance"), 1))),
                }
            )
    return result


def _choose_item(
    entries: list[dict[str, Any]],
    rng: random.Random,
    used_ids: set[int],
    allow_duplicates: bool,
) -> Oggetto | None:
    available = [entry for entry in entries if rng.random() <= entry.get("chance", 1)]
    choices = available if allow_duplicates else [entry for entry in available if entry["item"].id not in used_ids]
    if not choices:
        return None
    ordered = sorted(choices, key=lambda entry: entry["item"].id)
    total = sum(entry["weight"] for entry in ordered)
    marker = rng.random() * total
    for entry in ordered:
        marker -= entry["weight"]
        if marker <= 0:
            return entry["item"]
    return ordered[-1]["item"]


def _accessory_count_for_level(
    raw_bands: Any,
    level: int,
    rng: random.Random,
    maximum: int,
) -> int | None:
    for raw in _list(raw_bands):
        band = _mapping(raw)
        minimum_level = _integer(band.get("minLevel"), 1, minimum=1, maximum=MAX_GENERATED_LEVEL)
        maximum_level = _integer(
            band.get("maxLevel"),
            MAX_GENERATED_LEVEL,
            minimum=minimum_level,
            maximum=MAX_GENERATED_LEVEL,
        )
        if not minimum_level <= level <= maximum_level:
            continue
        minimum_count = _integer(band.get("minCount"), 0, minimum=0, maximum=maximum)
        maximum_count = _integer(
            band.get("maxCount"),
            minimum_count,
            minimum=minimum_count,
            maximum=maximum,
        )
        return rng.randint(minimum_count, maximum_count)
    return None


def _equip_humanoid(character: Personaggio, unit: Unit, level: int, rng: random.Random, report: dict[str, Any]) -> None:
    profile = _mapping(unit.equipment_profiles)
    slots = _equipment_slots(unit)
    item_ids: set[int] = set()
    for entries in slots.values():
        for raw in _list(entries):
            item_id = _entry_skill_id({"skillId": _mapping(raw).get("itemId")}) if isinstance(raw, Mapping) else _entry_skill_id(raw)
            if item_id is not None:
                item_ids.add(item_id)
    for group in _list(profile.get("groups")):
        if not isinstance(group, Mapping):
            continue
        for raw in _list(group.get("items")):
            item_id = _entry_skill_id({"skillId": _mapping(raw).get("itemId")}) if isinstance(raw, Mapping) else _entry_skill_id(raw)
            if item_id is not None:
                item_ids.add(item_id)
    items_by_id = {
        item.id: item
        for item in Oggetto.objects.filter(
            id__in=item_ids,
            archived_at__isnull=True,
            archiviato=False,
        )
    }
    allow_duplicates = bool(profile.get("allowDuplicates"))
    used_ids: set[int] = set()
    for slot, raw_entries in slots.items():
        if not _valid_equipment_slot(slot):
            report["warnings"].append(f"Slot equipaggiamento Unit non valido: {slot}.")
            continue
        item = _choose_item(
            _eligible_item_entries(raw_entries, level, items_by_id),
            rng,
            used_ids,
            allow_duplicates,
        )
        if item is None:
            continue
        setattr(character.equip, slot, item)
        used_ids.add(item.id)
        report["equipment"].append({"slot": slot, "itemId": item.id, "name": item.nome})

    prepared_groups = []
    for raw_group in _list(profile.get("groups")):
        group = _mapping(raw_group)
        group_slots = [str(slot) for slot in _list(group.get("slots")) if _valid_equipment_slot(str(slot))]
        legacy_count = _integer(group.get("count"), 1, minimum=0, maximum=len(group_slots))
        minimum_count = _integer(group.get("minCount"), legacy_count, minimum=0, maximum=len(group_slots))
        maximum_count = _integer(
            group.get("maxCount"),
            legacy_count,
            minimum=minimum_count,
            maximum=len(group_slots),
        )
        entries = _eligible_item_entries(group.get("items"), level, items_by_id)
        prepared_groups.append(
            {
                "group": group,
                "slots": group_slots,
                "minimum": minimum_count,
                "maximum": maximum_count,
                "entries": entries,
                "assigned": 0,
            }
        )

    accessory_target = _accessory_count_for_level(
        profile.get("accessoryCountByLevel"),
        level,
        rng,
        sum(entry["maximum"] for entry in prepared_groups),
    )

    def equip_group(entry: dict[str, Any], requested: int) -> int:
        assigned = 0
        group_slots = entry["slots"]
        entries = entry["entries"]
        open_slots = [slot for slot in group_slots if getattr(character.equip, slot + "_id", None) is None]
        rng.shuffle(open_slots)
        for slot in open_slots[:requested]:
            item = _choose_item(entries, rng, used_ids, allow_duplicates)
            if item is None:
                continue
            setattr(character.equip, slot, item)
            used_ids.add(item.id)
            report["equipment"].append({"slot": slot, "itemId": item.id, "name": item.nome})
            assigned += 1
        entry["assigned"] += assigned
        return assigned

    if accessory_target is None:
        for entry in prepared_groups:
            count = rng.randint(entry["minimum"], entry["maximum"])
            if rng.random() < max(0, min(1, _number(entry["group"].get("emptyChance"), 0))):
                count = 0
            equip_group(entry, count)
    else:
        # Group minima let authors guarantee identity-defining categories
        # (for example at least one ring), then the Elder-style total adds
        # level-scaled variety across every remaining accessory slot.
        for entry in prepared_groups:
            equip_group(entry, entry["minimum"])
        equipped = sum(entry["assigned"] for entry in prepared_groups)
        while equipped < accessory_target:
            available_groups = [
                entry
                for entry in prepared_groups
                if entry["assigned"] < entry["maximum"]
                and entry["entries"]
                and any(
                    getattr(character.equip, slot + "_id", None) is None
                    for slot in entry["slots"]
                )
            ]
            if not available_groups:
                break
            entry = rng.choice(available_groups)
            before = entry["assigned"]
            equipped += equip_group(entry, 1)
            if entry["assigned"] == before:
                entry["maximum"] = entry["assigned"]
    character.equip.save()


def _validate_unit(unit: Unit, level: int) -> tuple[str, dict[str, Any]]:
    rules = _unit_rules(unit)
    kind = unit_kind(unit)
    if not kind:
        raise ApiError(
            "combat.unit_kind_required",
            "Configura generation_rules.kind come creature o humanoid.",
            "unitId",
            409,
        )
    if not 1 <= level <= MAX_GENERATED_LEVEL:
        raise ApiError(
            "combat.unit_level_out_of_range",
            f"È possibile generare solo dal livello 1 al livello {MAX_GENERATED_LEVEL}.",
            "level",
            409,
        )
    if kind != "humanoid":
        if _list(unit.skill_unlocks) or _equipment_slots(unit) or _list(_mapping(unit.equipment_profiles).get("groups")):
            raise ApiError(
                "combat.unit_non_humanoid_loadout",
                "Le creature non possono avere pool di Skill o equipaggiamento.",
                "unitId",
                409,
            )
        if _mapping(unit.profilo_competenze):
            raise ApiError(
                "combat.unit_non_humanoid_competences",
                "Le creature non possono avere una progressione Competenze.",
                "unitId",
                409,
            )
        return kind, rules
    if _list(unit.skill_actions):
        raise ApiError(
            "combat.unit_humanoid_actions",
            "Gli Umanoidi usano il catalogo Skill e non possono avere azioni innate.",
            "unitId",
            409,
        )
    if not unit_core_key(unit) and not _profile_vector(rules.get("coreProfile")):
        raise ApiError(
            "combat.unit_core_required",
            "Un umanoide deve indicare coreKey o un coreProfile personalizzato.",
            "unitId",
            409,
        )
    if not _equipment_slots(unit) and not _list(_mapping(unit.equipment_profiles).get("groups")):
        raise ApiError(
            "combat.unit_equipment_pool_required",
            "Un umanoide deve avere almeno un pool di equipaggiamento esplicito.",
            "unitId",
            409,
        )
    return kind, rules


@transaction.atomic
def create_unit_character(unit: Unit, level: int, variant: str = "") -> Personaggio:
    level = _integer(level, 1, minimum=1, maximum=MAX_GENERATED_LEVEL)
    kind, rules = _validate_unit(unit, level)
    resolved_variant, automatic_variant = _resolved_variant(variant)
    seed = _stable_seed(unit, resolved_variant)
    rng = random.Random(seed)
    name = _unique_character_name(unit.nome)
    humanoid = kind == "humanoid"
    race_rng = random.Random(f"{seed}:race")
    allowed_races = [race for race in _list(rules.get("allowedRaces")) if race in RACE_NAMES]
    selected_race = race_rng.choice(allowed_races or list(RACE_NAMES)) if humanoid else ""
    available_subraces = list(subraces_for(selected_race))
    selected_subrace = race_rng.choice(available_subraces) if available_subraces else ""
    competence_state, competence_report = (
        _generated_competences(unit, level, rules, rng)
        if humanoid
        else ({}, {"earned": 0, "spent": 0, "remaining": 0, "mode": "none"})
    )
    equip = Equip.objects.create(nome=f"{name} · Equip") if humanoid else None
    character = Personaggio.objects.create(
        nome=name,
        nome_interno=f"unit-{unit.id}-{uuid4().hex[:12]}",
        tipologia="nemico",
        razza_1=selected_race,
        razza_2=selected_subrace,
        livello=1,
        equip=equip,
        zaino=Zaino.objects.create(nome=f"{name} · Zaino") if humanoid else None,
        faretra=Faretra.objects.create(nome=f"{name} · Faretra") if humanoid else None,
        note=Note.objects.create(nome=f"{name} · Note"),
        effetti=EffettiPersonaggio.objects.create(nome=f"{name} · Effetti"),
        abilita={"known": _level_actions(unit, level), "skills": []},
        competenze=competence_state,
        pe_abilita=competence_report["remaining"],
        metadata={
            "generatedFromUnitId": unit.id,
            "generatedFromUnitName": unit.nome,
            "generationKind": kind,
            "generationVariant": resolved_variant,
            "generationVariantAutomatic": automatic_variant,
            "generationSeed": seed,
        },
    )
    report: dict[str, Any] = {
        "version": 2,
        "unitId": unit.id,
        "kind": kind,
        "level": level,
        "coreKey": unit_core_key(unit),
        "xp": {
            "coreShare": max(0, min(1, _number(rules.get("coreShare"), DEFAULT_CORE_SHARE))),
            "earned": 0,
            "allocatedCore": 0,
            "allocatedArchetype": 0,
            "remainingCore": 0,
            "remainingArchetype": 0,
            "remainingGeneral": 0,
        },
        "skills": [],
        "perks": [],
        "equipment": [],
        "innateActions": [entry["name"] for entry in _level_actions(unit, level)],
        "competences": competence_report,
        "warnings": [],
        "race": {
            "primary": selected_race,
            "subrace": selected_subrace,
            "allowed": allowed_races,
            "allAvailable": not allowed_races,
        },
    }
    curve_values, curve_trace = _stat_curve_values(unit, level, kind)
    report["statCurves"] = curve_trace
    _create_chassis_effect(
        character,
        unit,
        _stat_modifiers(unit, level, kind),
        curve_values,
    )
    refresh_personaggio(character)
    character.refresh_from_db()

    if humanoid:
        all_skills = list(
            Skill.objects.filter(archived_at__isnull=True)
            .select_related("famiglia", "famiglia__gruppo", "spell_definition")
            .prefetch_related("prerequisiti")
        )
        core_pool, archetype_pool, perk_pools = _skill_pools(unit, all_skills)
        if not core_pool:
            raise ApiError(
                "combat.unit_core_pool_empty",
                "Il Core scelto non trova Skill compatibili. Configura i tag profilo o skill_unlocks.",
                "unitId",
                409,
            )
        if not archetype_pool:
            raise ApiError(
                "combat.unit_archetype_pool_empty",
                "L'archetipo non ha una metà personalizzata: configura archetipo_tags o skill_unlocks.",
                "unitId",
                409,
            )
        xp_bank = 0
        fractional_core = 0.0
        share = report["xp"]["coreShare"]
        for current_level in range(1, level + 1):
            character.livello = current_level
            earned = _xp_at_level(current_level, rules)
            fractional_core += earned * share
            core_gain = int(fractional_core)
            fractional_core -= core_gain
            archetype_gain = earned - core_gain
            report["xp"]["earned"] += earned
            report["xp"]["allocatedCore"] += core_gain
            report["xp"]["allocatedArchetype"] += archetype_gain
            xp_bank += earned
            character.save(update_fields=["livello", "updated_at"])
            xp_bank = _spend_level_budget(
                character,
                core_pool,
                archetype_pool,
                current_level,
                xp_bank,
                rng,
                report,
                core_share=share,
                limit_per_pool=DEFAULT_MAX_SKILLS_PER_POOL_PER_LEVEL,
            )
            use_milestone = _use_milestone_progression(rng)
            _grant_progression_perk(
                character,
                unit,
                perk_pools["minor"],
                "minor",
                current_level,
                rng,
                report,
                use_milestone=use_milestone,
            )
            if current_level % 2 == 0:
                _grant_progression_perk(
                    character,
                    unit,
                    perk_pools["major"],
                    "major",
                    current_level,
                    rng,
                    report,
                    use_milestone=use_milestone,
                )
            character.refresh_from_db()
        xp_bank = _spend_remaining_budget(
            character,
            core_pool,
            archetype_pool,
            level,
            xp_bank,
            rng,
            report,
            core_share=share,
            passes=_integer(rules.get("finalSpendingPasses"), 4, minimum=0, maximum=20),
        )
        expected_minor = level
        expected_major = level // 2
        actual_minor = sum(entry["tier"] == "minor" for entry in report["perks"])
        actual_major = sum(entry["tier"] == "major" for entry in report["perks"])
        if actual_minor != expected_minor or actual_major != expected_major:
            raise ApiError(
                "combat.unit_perk_pool_incomplete",
                (
                    "Il pool perk non può rispettare la progressione richiesta: "
                    f"servono {expected_minor} minori e {expected_major} maggiori, "
                    f"ma sono stati trovati {actual_minor} minori e {actual_major} maggiori compatibili."
                ),
                "unitId",
                409,
            )
        character.pe_generali = xp_bank
        report["xp"]["remainingGeneral"] = xp_bank
        if xp_bank:
            report["warnings"].append(
                f"{xp_bank} PE generali restano disponibili: nessuna Skill configurata è acquistabile."
            )
        _equip_humanoid(character, unit, level, rng, report)
        character.save(update_fields=["pe_generali", "updated_at"])
        refresh_personaggio(character)
        character.refresh_from_db()
    else:
        character.livello = level
        character.save(update_fields=["livello", "updated_at"])
        refresh_personaggio(character)
        character.refresh_from_db()

    character.metadata = {
        **_mapping(character.metadata),
        "unitGeneration": report,
    }
    character.save(update_fields=["metadata", "updated_at"])
    return character
