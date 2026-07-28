from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.db import transaction
from django.utils import timezone

from backend.characters.services.inventory_rules import (
    EQUIPMENT_SLOT_LABELS,
    item_compatible_with_equipment_slot,
)
from backend.characters.race_rules import RACE_NAMES
from backend.core.api import ApiError
from backend.core.competence_defaults import default_competence_state
from backend.core.models import Giocatore, Oggetto, Skill, Unit
from backend.core.security import effective_role, has_minimum_role

from .unit_generation import (
    DEFAULT_CORE_PROFILES,
    MAX_GENERATED_LEVEL,
    UNIT_KINDS,
    UNIT_STAT_CURVE_VARIABLE_KEYS,
    UNIT_STAT_PROFILE_LABELS,
    create_unit_character,
)
from .unit_management_selectors import serialize_managed_unit


def require_unit_manager(user, giocatore: Giocatore) -> None:
    if not has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER):
        raise ApiError(
            "management.units.forbidden",
            "Solo master e amministratori possono gestire le Unit.",
            status=403,
        )


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _integer(
    value: Any,
    *,
    field: str,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if value in (None, ""):
        value = default
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ApiError("management.units.integer_required", "Inserisci un numero intero valido.", field) from exc
    if minimum is not None and result < minimum:
        raise ApiError(
            "management.units.minimum",
            f"Il valore minimo consentito è {minimum}.",
            field,
        )
    if maximum is not None and result > maximum:
        raise ApiError(
            "management.units.maximum",
            f"Il valore massimo consentito è {maximum}.",
            field,
        )
    return result


def _number(
    value: Any,
    *,
    field: str,
    default: float = 0,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if value in (None, ""):
        result = default
    else:
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ApiError("management.units.number_required", "Inserisci un numero valido.", field) from exc
    if minimum is not None and result < minimum:
        raise ApiError("management.units.minimum", f"Il valore minimo consentito è {minimum}.", field)
    if maximum is not None and result > maximum:
        raise ApiError("management.units.maximum", f"Il valore massimo consentito è {maximum}.", field)
    return result


def _clean_profile(profile: Any, *, field: str, minimum: float | None = None, maximum: float | None = None) -> dict[str, float]:
    cleaned: dict[str, float] = {}
    for key, value in _mapping(profile).items():
        normalized_key = str(key).strip()
        if not normalized_key:
            continue
        cleaned[normalized_key] = _number(
            value,
            field=f"{field}.{normalized_key}",
            minimum=minimum,
            maximum=maximum,
        )
    return cleaned


def _clean_skill_unlocks(raw_entries: Any, kind: str, rules: dict[str, Any]) -> list[dict[str, Any]]:
    if kind != "humanoid":
        if _list(raw_entries):
            raise ApiError(
                "management.units.non_humanoid_skills",
                "Animali e creature non possono avere pool di Skill.",
                "skillUnlocks",
            )
        return []
    cleaned = []
    seen: set[int] = set()
    for index, raw in enumerate(_list(raw_entries)):
        entry = _mapping(raw)
        skill_id = _integer(
            entry.get("skillId"),
            field=f"skillUnlocks.{index}.skillId",
            default=0,
            minimum=1,
        )
        if skill_id in seen:
            raise ApiError(
                "management.units.duplicate_skill",
                "Una Skill può comparire una sola volta nel profilo della Unit.",
                f"skillUnlocks.{index}.skillId",
            )
        seen.add(skill_id)
        try:
            skill = Skill.objects.select_related("famiglia", "famiglia__gruppo", "spell_definition").get(
                pk=skill_id,
                archived_at__isnull=True,
            )
        except Skill.DoesNotExist as exc:
            raise ApiError(
                "management.units.skill_not_found",
                "La Skill selezionata non è disponibile.",
                f"skillUnlocks.{index}.skillId",
                404,
            ) from exc
        pool = str(entry.get("pool") or "archetype").strip().lower()
        if pool not in {"core", "archetype", "minor", "major"}:
            raise ApiError(
                "management.units.skill_pool_invalid",
                "Scegli Core, Archetipo, Perk minore o Perk maggiore.",
                f"skillUnlocks.{index}.pool",
            )
        if pool in {"minor", "major"} and not skill.famiglia.is_perk:
            raise ApiError(
                "management.units.perk_required",
                "I pool perk accettano soltanto Skill appartenenti a una famiglia Perk.",
                f"skillUnlocks.{index}.skillId",
            )
        if pool not in {"minor", "major"} and skill.famiglia.is_perk:
            raise ApiError(
                "management.units.regular_skill_required",
                "Una Skill Perk deve essere inserita nel pool minore o maggiore.",
                f"skillUnlocks.{index}.pool",
            )
        if rules["magicPolicy"] == "none":
            tags = _mapping(skill.profile_tags)
            is_magic = not skill.famiglia.is_perk and (
                skill.famiglia.gruppo.slug == "scuole-di-magia"
                or "magia" in skill.famiglia.gruppo.nome.casefold()
                or float(tags.get("core_magico") or 0) > 0
                or float(tags.get("natura_magica") or 0) > 0
            )
            try:
                skill.spell_definition
            except Exception:
                pass
            else:
                is_magic = True
            if is_magic:
                raise ApiError(
                    "management.units.magic_forbidden",
                    f"{skill.nome} è magica, ma la Unit vieta la magia.",
                    f"skillUnlocks.{index}.skillId",
                )
        family_name = skill.famiglia.nome.casefold()
        family_id = str(skill.famiglia_id)
        if skill.famiglia.is_classe:
            allowed_classes = {
                str(value).strip().casefold()
                for value in rules["allowedClassFamilies"]
                if str(value).strip()
            }
            if allowed_classes and family_name not in allowed_classes and family_id not in allowed_classes:
                raise ApiError(
                    "management.units.class_family_forbidden",
                    f"{skill.nome} appartiene a una Classe non consentita dalla Unit.",
                    f"skillUnlocks.{index}.skillId",
                )
        if skill.famiglia.is_religione:
            allowed_religions = {
                str(value).strip().casefold()
                for value in rules["allowedReligionFamilies"]
                if str(value).strip()
            }
            if not allowed_religions or (
                family_name not in allowed_religions and family_id not in allowed_religions
            ):
                raise ApiError(
                    "management.units.religion_family_forbidden",
                    f"{skill.nome} appartiene a una Religione non consentita dalla Unit.",
                    f"skillUnlocks.{index}.skillId",
                )
        minimum = _integer(
            entry.get("minLevel", 1),
            field=f"skillUnlocks.{index}.minLevel",
            default=1,
            minimum=1,
            maximum=MAX_GENERATED_LEVEL,
        )
        maximum = _integer(
            entry.get("maxLevel", MAX_GENERATED_LEVEL),
            field=f"skillUnlocks.{index}.maxLevel",
            default=MAX_GENERATED_LEVEL,
            minimum=minimum,
            maximum=MAX_GENERATED_LEVEL,
        )
        cleaned_entry = {
            "skillId": skill.id,
            "pool": "archetype" if pool in {"minor", "major"} else pool,
            "weight": _number(
                entry.get("weight"),
                field=f"skillUnlocks.{index}.weight",
                default=1,
                minimum=0.1,
                maximum=100,
            ),
            "minLevel": minimum,
            "maxLevel": maximum,
        }
        if pool in {"minor", "major"}:
            cleaned_entry["perkTier"] = pool
        if entry.get("requiredAtLevel") not in (None, ""):
            cleaned_entry["requiredAtLevel"] = _integer(
                entry.get("requiredAtLevel"),
                field=f"skillUnlocks.{index}.requiredAtLevel",
                default=minimum,
                minimum=minimum,
                maximum=maximum,
            )
        cleaned.append(cleaned_entry)
    return cleaned


def _clean_item_entry(entry: Mapping[str, Any], *, field: str, slot: str | None = None) -> dict[str, Any]:
    item_id = _integer(entry.get("itemId"), field=f"{field}.itemId", default=0, minimum=1)
    try:
        item = Oggetto.objects.get(
            pk=item_id,
            archived_at__isnull=True,
            archiviato=False,
        )
    except Oggetto.DoesNotExist as exc:
        raise ApiError(
            "management.units.item_not_found",
            "L'oggetto selezionato non è disponibile.",
            f"{field}.itemId",
            404,
        ) from exc
    if slot and not item_compatible_with_equipment_slot(item, slot):
        raise ApiError(
            "management.units.item_incompatible",
            f"{item.nome} non è compatibile con lo slot {EQUIPMENT_SLOT_LABELS[slot]}.",
            f"{field}.itemId",
        )
    minimum = _integer(
        entry.get("minLevel", 1),
        field=f"{field}.minLevel",
        default=1,
        minimum=1,
        maximum=MAX_GENERATED_LEVEL,
    )
    maximum = _integer(
        entry.get("maxLevel", MAX_GENERATED_LEVEL),
        field=f"{field}.maxLevel",
        default=MAX_GENERATED_LEVEL,
        minimum=minimum,
        maximum=MAX_GENERATED_LEVEL,
    )
    return {
        "itemId": item.id,
        "minLevel": minimum,
        "maxLevel": maximum,
        "weight": _number(
            entry.get("weight"),
            field=f"{field}.weight",
            default=1,
            minimum=0.1,
            maximum=100,
        ),
        "chance": _number(
            entry.get("chance"),
            field=f"{field}.chance",
            default=1,
            minimum=0,
            maximum=1,
        ),
    }


def _clean_equipment(values: Mapping[str, Any], kind: str) -> dict[str, Any]:
    raw_slots = _list(values.get("equipmentSlots"))
    raw_groups = _list(values.get("equipmentGroups"))
    raw_accessory_bands = _list(values.get("accessoryCountByLevel"))
    if kind != "humanoid":
        if raw_slots or raw_groups or raw_accessory_bands:
            raise ApiError(
                "management.units.non_humanoid_equipment",
                "Animali e creature non possono avere equipaggiamento.",
                "equipmentSlots",
            )
        return {}

    slots: dict[str, list[dict[str, Any]]] = {}
    seen: set[tuple[str, int]] = set()
    for index, raw in enumerate(raw_slots):
        entry = _mapping(raw)
        slot = str(entry.get("slot") or "").strip()
        if slot not in EQUIPMENT_SLOT_LABELS:
            raise ApiError(
                "management.units.slot_invalid",
                "Lo slot equipaggiamento non esiste.",
                f"equipmentSlots.{index}.slot",
            )
        cleaned = _clean_item_entry(entry, field=f"equipmentSlots.{index}", slot=slot)
        identity = (slot, cleaned["itemId"])
        if identity in seen:
            raise ApiError(
                "management.units.duplicate_item",
                "Lo stesso oggetto è già presente in questo slot.",
                f"equipmentSlots.{index}.itemId",
            )
        seen.add(identity)
        slots.setdefault(slot, []).append(cleaned)

    groups = []
    for group_index, raw in enumerate(raw_groups):
        group = _mapping(raw)
        group_slots = list(
            dict.fromkeys(
                str(slot).strip()
                for slot in _list(group.get("slots"))
                if str(slot).strip()
            )
        )
        if not group_slots or any(slot not in EQUIPMENT_SLOT_LABELS for slot in group_slots):
            raise ApiError(
                "management.units.group_slots_invalid",
                "Scegli almeno uno slot valido per il gruppo accessori.",
                f"equipmentGroups.{group_index}.slots",
            )
        legacy_count = _integer(
            group.get("count", 1),
            field=f"equipmentGroups.{group_index}.count",
            default=1,
            minimum=0,
            maximum=len(group_slots),
        )
        minimum_count = _integer(
            group.get("minCount", legacy_count),
            field=f"equipmentGroups.{group_index}.minCount",
            default=legacy_count,
            minimum=0,
            maximum=len(group_slots),
        )
        maximum_count = _integer(
            group.get("maxCount", legacy_count),
            field=f"equipmentGroups.{group_index}.maxCount",
            default=legacy_count,
            minimum=minimum_count,
            maximum=len(group_slots),
        )
        items = []
        for item_index, raw_item in enumerate(_list(group.get("items"))):
            item_entry = _mapping(raw_item)
            cleaned_item = _clean_item_entry(
                item_entry,
                field=f"equipmentGroups.{group_index}.items.{item_index}",
            )
            item = Oggetto.objects.get(pk=cleaned_item["itemId"])
            if not any(item_compatible_with_equipment_slot(item, slot) for slot in group_slots):
                raise ApiError(
                    "management.units.group_item_incompatible",
                    f"{item.nome} non è compatibile con gli slot del gruppo.",
                    f"equipmentGroups.{group_index}.items.{item_index}.itemId",
                )
            items.append(cleaned_item)
        if not items:
            raise ApiError(
                "management.units.group_empty",
                "Aggiungi almeno un oggetto al gruppo accessori.",
                f"equipmentGroups.{group_index}.items",
            )
        groups.append(
            {
                "name": str(group.get("name") or f"Gruppo {group_index + 1}").strip()[:120],
                "slots": group_slots,
                "minCount": minimum_count,
                "maxCount": maximum_count,
                "emptyChance": _number(
                    group.get("emptyChance"),
                    field=f"equipmentGroups.{group_index}.emptyChance",
                    default=0,
                    minimum=0,
                    maximum=1,
                ),
                "items": items,
            }
        )
    if not slots and not groups:
        raise ApiError(
            "management.units.equipment_required",
            "Un umanoide deve avere almeno un pool di equipaggiamento.",
            "equipmentSlots",
        )
    accessory_bands = []
    covered_levels: set[int] = set()
    guaranteed_accessories = sum(group["minCount"] for group in groups)
    accessory_capacity = sum(group["maxCount"] for group in groups)
    for index, raw in enumerate(raw_accessory_bands):
        band = _mapping(raw)
        minimum_level = _integer(
            band.get("minLevel"),
            field=f"accessoryCountByLevel.{index}.minLevel",
            default=1,
            minimum=1,
            maximum=20,
        )
        maximum_level = _integer(
            band.get("maxLevel"),
            field=f"accessoryCountByLevel.{index}.maxLevel",
            default=20,
            minimum=minimum_level,
            maximum=20,
        )
        minimum_count = _integer(
            band.get("minCount"),
            field=f"accessoryCountByLevel.{index}.minCount",
            default=0,
            minimum=0,
            maximum=30,
        )
        maximum_count = _integer(
            band.get("maxCount"),
            field=f"accessoryCountByLevel.{index}.maxCount",
            default=minimum_count,
            minimum=minimum_count,
            maximum=30,
        )
        band_levels = set(range(minimum_level, maximum_level + 1))
        if covered_levels & band_levels:
            raise ApiError(
                "management.units.accessory_level_overlap",
                "Le fasce della quantità accessori non possono sovrapporsi.",
                f"accessoryCountByLevel.{index}.minLevel",
            )
        if minimum_count < guaranteed_accessories or maximum_count > accessory_capacity:
            raise ApiError(
                "management.units.accessory_count_impossible",
                "Il totale accessori deve rispettare la somma dei minimi e la capacità dei gruppi.",
                f"accessoryCountByLevel.{index}.minCount",
            )
        covered_levels.update(band_levels)
        accessory_bands.append(
            {
                "minLevel": minimum_level,
                "maxLevel": maximum_level,
                "minCount": minimum_count,
                "maxCount": maximum_count,
            }
        )
    if accessory_bands and covered_levels != set(range(1, 21)):
        raise ApiError(
            "management.units.accessory_level_gap",
            "La curva accessori deve coprire senza vuoti tutti i livelli da 1 a 20.",
            "accessoryCountByLevel",
        )
    accessory_bands.sort(key=lambda band: band["minLevel"])
    return {
        "slots": slots,
        "groups": groups,
        "accessoryCountByLevel": accessory_bands,
        "allowDuplicates": False,
    }


def _clean_actions(raw_actions: Any, kind: str) -> list[dict[str, Any]]:
    cleaned = []
    for index, raw in enumerate(_list(raw_actions)):
        entry = _mapping(raw)
        name = str(entry.get("name") or "").strip()
        if not name:
            raise ApiError(
                "management.units.action_name_required",
                "Il nome dell'azione innata è obbligatorio.",
                f"innateActions.{index}.name",
            )
        minimum = _integer(
            entry.get("minLevel", 1),
            field=f"innateActions.{index}.minLevel",
            default=1,
            minimum=1,
            maximum=MAX_GENERATED_LEVEL,
        )
        maximum = _integer(
            entry.get("maxLevel", MAX_GENERATED_LEVEL),
            field=f"innateActions.{index}.maxLevel",
            default=MAX_GENERATED_LEVEL,
            minimum=minimum,
            maximum=MAX_GENERATED_LEVEL,
        )
        cleaned.append(
            {
                "key": str(entry.get("key") or f"azione-{index + 1}").strip()[:120],
                "name": name[:180],
                "description": str(entry.get("description") or "").strip(),
                "minLevel": minimum,
                "maxLevel": maximum,
                "costs": {
                    key: _integer(
                        value,
                        field=f"innateActions.{index}.costs.{key}",
                        default=0,
                        minimum=0,
                    )
                    for key, value in _mapping(entry.get("costs")).items()
                    if key in {"pf", "mana", "energia", "potere", "pa", "stanchezza"}
                },
                "trigger": str(entry.get("trigger") or "").strip(),
                "duration": str(entry.get("duration") or "").strip(),
                "icon": str(entry.get("icon") or "runa").strip()[:80],
            }
        )
    if kind == "humanoid" and cleaned:
        raise ApiError(
            "management.units.innate_actions_forbidden",
            "Gli Umanoidi usano le Skill; le abilità innate sono riservate ad Animali e Creature.",
            "innateActions",
        )
    return cleaned


def _clean_stat_curves(raw_curves: Any) -> list[dict[str, Any]]:
    cleaned = []
    seen: set[str] = set()
    for index, raw in enumerate(_list(raw_curves)):
        entry = _mapping(raw)
        key = str(entry.get("key") or "").strip()
        if key not in UNIT_STAT_CURVE_VARIABLE_KEYS:
            raise ApiError(
                "management.units.stat_curve_variable_invalid",
                "Scegli una variabile disponibile per la curva.",
                f"statProfile.curves.{index}.key",
            )
        if key in seen:
            raise ApiError(
                "management.units.stat_curve_variable_duplicate",
                "Ogni variabile può avere una sola curva.",
                f"statProfile.curves.{index}.key",
            )
        seen.add(key)
        profile = str(entry.get("profile") or "custom").strip().lower()
        if profile not in UNIT_STAT_PROFILE_LABELS:
            raise ApiError(
                "management.units.stat_curve_profile_invalid",
                "Il profilo della variabile non è valido.",
                f"statProfile.curves.{index}.profile",
            )
        level_1 = _number(
            entry.get("level1"),
            field=f"statProfile.curves.{index}.level1",
            minimum=-100000,
            maximum=100000,
        )
        level_20 = _number(
            entry.get("level20"),
            field=f"statProfile.curves.{index}.level20",
            minimum=-100000,
            maximum=100000,
        )
        cleaned.append(
            {
                "key": key,
                "profile": profile,
                "level1": level_1,
                "level20": level_20,
            }
        )
    return cleaned


def _clean_unit_values(values: Mapping[str, Any]) -> dict[str, Any]:
    name = str(values.get("name") or "").strip()
    if not name:
        raise ApiError("management.units.name_required", "Il nome della Unit è obbligatorio.", "name")
    generation = _mapping(values.get("generation"))
    kind = str(generation.get("kind") or "").strip().lower()
    if kind == "animal":
        kind = "creature"
    if kind not in UNIT_KINDS:
        raise ApiError(
            "management.units.kind_required",
            "Scegli Creatura o Umanoide.",
            "generation.kind",
        )
    core_key = str(generation.get("coreKey") or "").strip().lower()
    if kind == "humanoid" and core_key not in DEFAULT_CORE_PROFILES:
        raise ApiError(
            "management.units.core_required",
            "Scegli uno dei cinque Core per la progressione dell'umanoide.",
            "generation.coreKey",
        )
    magic_policy = str(generation.get("magicPolicy") or "any").strip().lower()
    if magic_policy not in {"none", "any"}:
        raise ApiError(
            "management.units.magic_policy_invalid",
            "La politica della magia non è valida.",
            "generation.magicPolicy",
        )
    rules = {
        "kind": kind,
        "coreKey": core_key if kind == "humanoid" else "",
        "coreShare": _number(
            generation.get("coreShare"),
            field="generation.coreShare",
            default=0.5,
            minimum=0.1,
            maximum=0.9,
        ),
        "startingXp": _integer(
            generation.get("startingXp", 0),
            field="generation.startingXp",
            default=0,
            minimum=0,
        ),
        "xpPerLevel": {
            "base": _integer(
                generation.get("xpBase", 20),
                field="generation.xpBase",
                default=20,
                minimum=0,
            ),
            "growth": _integer(
                generation.get("xpGrowth", 1),
                field="generation.xpGrowth",
                default=1,
                minimum=0,
            ),
        },
        "competenceXp": {
            "starting": _integer(
                generation.get("competenceStartingXp", 5),
                field="generation.competenceStartingXp",
                default=5,
                minimum=0,
            ),
            "base": _integer(
                generation.get("competenceXpBase", 15),
                field="generation.competenceXpBase",
                default=15,
                minimum=0,
            ),
            "growth": _integer(
                generation.get("competenceXpGrowth", 0),
                field="generation.competenceXpGrowth",
                default=0,
                minimum=0,
            ),
        },
        "finalSpendingPasses": _integer(
            generation.get("finalSpendingPasses", 4),
            field="generation.finalSpendingPasses",
            default=4,
            minimum=0,
            maximum=20,
        ),
        "magicPolicy": magic_policy,
        "allowedClassFamilies": [
            str(value).strip()
            for value in _list(generation.get("allowedClassFamilies"))
            if str(value).strip()
        ],
        "allowedReligionFamilies": [
            str(value).strip()
            for value in _list(generation.get("allowedReligionFamilies"))
            if str(value).strip()
        ],
        "allowedRaces": [
            race
            for race in dict.fromkeys(
                str(value).strip()
                for value in _list(generation.get("allowedRaces"))
                if str(value).strip()
            )
            if race in RACE_NAMES
        ],
        "allowHumanoidStatGrowth": bool(generation.get("allowHumanoidStatGrowth")),
    }
    archetype_tags = _clean_profile(
        values.get("archetypeTags"),
        field="archetypeTags",
        minimum=-5,
        maximum=5,
    )
    skill_unlocks = _clean_skill_unlocks(values.get("skillUnlocks"), kind, rules)
    if kind == "humanoid" and not archetype_tags and not skill_unlocks:
        raise ApiError(
            "management.units.archetype_pool_required",
            "Configura i tag dell'archetipo o almeno una Skill nel pool personalizzato.",
            "archetypeTags",
        )
    equipment_profiles = _clean_equipment(values, kind)
    actions = _clean_actions(values.get("innateActions"), kind)
    competence_profile = _clean_profile(
        values.get("competenceProfile"),
        field="competenceProfile",
        minimum=-5,
        maximum=5,
    )
    if kind != "humanoid":
        competence_profile = {}
    else:
        unknown_competences = set(competence_profile) - set(default_competence_state())
        if unknown_competences:
            raise ApiError(
                "management.units.competence_unknown",
                "Il profilo contiene una competenza non riconosciuta.",
                f"competenceProfile.{sorted(unknown_competences)[0]}",
            )
    stat_profile = _mapping(values.get("statProfile"))
    base_modifiers = _clean_profile(
        stat_profile.get("baseModifiers") or stat_profile.get("base"),
        field="statProfile.baseModifiers",
    )
    per_level_modifiers = _clean_profile(
        stat_profile.get("perLevelModifiers") or stat_profile.get("perLevel"),
        field="statProfile.perLevelModifiers",
    )
    stat_curves = _clean_stat_curves(stat_profile.get("curves"))
    if kind == "humanoid" and per_level_modifiers and not rules["allowHumanoidStatGrowth"]:
        raise ApiError(
            "management.units.humanoid_growth_requires_override",
            "La crescita statistica diretta di un umanoide richiede l'eccezione esplicita.",
            "generation.allowHumanoidStatGrowth",
        )
    milestones = []
    for index, raw_milestone in enumerate(_list(stat_profile.get("milestones"))):
        milestone = _mapping(raw_milestone)
        milestone_level = _integer(
            milestone.get("level"),
            field=f"statProfile.milestones.{index}.level",
            default=1,
            minimum=1,
            maximum=MAX_GENERATED_LEVEL,
        )
        milestone_modifiers = _clean_profile(
            milestone.get("modifiers") or milestone.get("add"),
            field=f"statProfile.milestones.{index}.modifiers",
        )
        if milestone_modifiers:
            milestones.append({"level": milestone_level, "modifiers": milestone_modifiers})
    if kind == "humanoid" and milestones and not rules["allowHumanoidStatGrowth"]:
        raise ApiError(
            "management.units.humanoid_growth_requires_override",
            "Le tappe statistiche di un umanoide richiedono l'eccezione esplicita.",
            "generation.allowHumanoidStatGrowth",
        )
    if kind == "humanoid" and stat_curves and not rules["allowHumanoidStatGrowth"]:
        raise ApiError(
            "management.units.humanoid_growth_requires_override",
            "Le curve statistiche di un umanoide richiedono l'eccezione esplicita.",
            "generation.allowHumanoidStatGrowth",
        )
    cleaned_stat_profile = {
        "baseModifiers": base_modifiers,
        "perLevelModifiers": per_level_modifiers,
        "milestones": milestones,
        "curves": stat_curves,
    }
    return {
        "nome": name[:180],
        "categoria": str(values.get("category") or "").strip()[:80],
        "archetipo_tags": archetype_tags,
        "archetipo_descrizione": str(values.get("archetypeDescription") or "").strip(),
        "profilo_competenze": competence_profile,
        "levels": _list(values.get("levels")),
        "equipment_profiles": equipment_profiles,
        "stat_profiles": cleaned_stat_profile,
        "skill_actions": actions,
        "skill_unlocks": skill_unlocks,
        "lore_description": str(values.get("loreDescription") or "").strip(),
        "generation_rules": rules,
        "notes": str(values.get("notes") or "").strip(),
    }


@transaction.atomic
def save_managed_unit(
    user,
    giocatore: Giocatore,
    values: Mapping[str, Any],
    unit_id: int | None = None,
    *,
    source_metadata: Mapping[str, Any] | None = None,
) -> tuple[Unit, bool]:
    require_unit_manager(user, giocatore)
    cleaned = _clean_unit_values(values)
    duplicate_names = Unit.objects.filter(nome__iexact=cleaned["nome"])
    if unit_id:
        duplicate_names = duplicate_names.exclude(pk=unit_id)
    if duplicate_names.exists():
        raise ApiError(
            "management.units.name_duplicate",
            "Esiste già una Unit con questo nome.",
            "name",
            409,
        )
    created = unit_id is None
    if created:
        unit = Unit()
    else:
        try:
            unit = Unit.objects.select_for_update().get(pk=unit_id)
        except Unit.DoesNotExist as exc:
            raise ApiError("management.units.not_found", "Unit non trovata.", status=404) from exc
    for field, value in cleaned.items():
        setattr(unit, field, value)
    if source_metadata is not None:
        unit.metadata = {
            **(_mapping(unit.metadata)),
            **_mapping(source_metadata),
        }
    elif created:
        unit.metadata = {"sourceProject": "redjango", "authoring": "unit-management"}
    try:
        unit.full_clean()
    except Exception as exc:
        raise ApiError(
            "management.units.invalid",
            "Controlla identità e configurazione della Unit.",
        ) from exc
    unit.save()
    return unit, created


@transaction.atomic
def set_managed_unit_archived(
    user,
    giocatore: Giocatore,
    unit_id: int,
    archived: bool,
) -> Unit:
    require_unit_manager(user, giocatore)
    try:
        unit = Unit.objects.select_for_update().get(pk=unit_id)
    except Unit.DoesNotExist as exc:
        raise ApiError("management.units.not_found", "Unit non trovata.", status=404) from exc
    unit.archived_at = timezone.now() if archived else None
    unit.save(update_fields=["archived_at", "updated_at"])
    return unit


def _unit_preview_payload(character) -> dict[str, Any]:
    trace = _mapping(_mapping(character.metadata).get("unitGeneration"))
    equipment = trace.get("equipment") if isinstance(trace.get("equipment"), list) else []
    competences = {
        key: value
        for key, value in _mapping(character.competenze).items()
        if isinstance(value, Mapping)
        and (int(value.get("barra1") or 0) or int(value.get("barra2") or 0) or int(value.get("extra") or 0))
    }
    return {
        "name": character.nome,
        "level": character.livello,
        "totals": _mapping(character.tot),
        "skills": [
            {
                "id": ownership.skill_id,
                "name": ownership.skill.nome,
                "family": ownership.skill.famiglia.nome,
                "xpSpent": sum(int(value or 0) for value in _mapping(ownership.spesa_pe).values()),
            }
            for ownership in character.skill_sbloccate.select_related("skill", "skill__famiglia").order_by(
                "skill__famiglia__ordine",
                "skill__ordine_famiglia",
                "skill__nome",
            )
        ],
        "equipment": equipment,
        "competences": competences,
        "innateActions": _list(_mapping(character.abilita).get("known")),
        "trace": trace,
    }


@transaction.atomic
def preview_managed_unit(
    user,
    giocatore: Giocatore,
    unit_id: int,
    level: int,
    variant: str,
) -> dict[str, Any]:
    require_unit_manager(user, giocatore)
    try:
        unit = Unit.objects.get(pk=unit_id)
    except Unit.DoesNotExist as exc:
        raise ApiError("management.units.not_found", "Unit non trovata.", status=404) from exc
    character = create_unit_character(unit, level, variant)
    payload = _unit_preview_payload(character)
    transaction.set_rollback(True)
    return payload


def managed_unit_detail(unit_id: int) -> dict[str, Any]:
    try:
        return serialize_managed_unit(Unit.objects.get(pk=unit_id))
    except Unit.DoesNotExist as exc:
        raise ApiError("management.units.not_found", "Unit non trovata.", status=404) from exc
