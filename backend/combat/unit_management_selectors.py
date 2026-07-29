from __future__ import annotations

from typing import Any

from django.db.models import Q

from backend.characters.services.inventory_rules import EQUIPMENT_SLOT_LABELS
from backend.characters.race_rules import RACE_NAMES, subraces_for
from backend.core.competence_defaults import COMPETENCE_DEFINITIONS
from backend.core.models import FamigliaSkill, Oggetto, Skill, Unit

from .unit_generation import (
    CORE_LABELS,
    DEFAULT_CORE_PROFILES,
    UNIT_KINDS,
    UNIT_STAT_CURVE_VARIABLES,
    UNIT_STAT_PROFILE_LABELS,
    unit_catalog_entry,
)


ARCHETYPE_TAGS = (
    ("core_fisico", "Core fisico"),
    ("core_magico", "Core magico"),
    ("focus_combat", "Combattimento"),
    ("range_skill", "Distanza"),
    ("area_e_multi_target", "Area e bersagli multipli"),
    ("natura_magica", "Natura magica"),
    ("difesa", "Difesa"),
    ("attacco", "Attacco"),
    ("sociale", "Sociale"),
    ("supporto_party", "Supporto al gruppo"),
    ("esplorazione_infiltrazione", "Esplorazione e infiltrazione"),
    ("tecnica_crafting", "Tecnica e crafting"),
    ("controllo_situazionale", "Controllo situazionale"),
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _identifier(value: Any) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return 0
    return result if result > 0 else 0


def _skill_option(skill: Skill) -> dict[str, Any]:
    return {
        "id": skill.id,
        "name": skill.nome,
        "family": skill.famiglia.nome,
        "group": skill.famiglia.gruppo.nome,
        "isClass": skill.famiglia.is_classe,
        "isReligion": skill.famiglia.is_religione,
        "isPerk": skill.famiglia.is_perk,
        "baseXpCost": skill.costo_pe,
    }


def _item_option(item: Oggetto) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.nome,
        "types": [
            value
            for value in (item.tipo_1, item.tipo_2, item.tipo_3, item.tipo_4)
            if value
        ],
        "rarity": item.rarita,
    }


def unit_management_overview() -> dict[str, Any]:
    return {
        "units": [
            {
                **unit_catalog_entry(unit),
                "archived": unit.archived_at is not None,
                "updatedAt": unit.updated_at.isoformat() if unit.updated_at else None,
                "sourceProject": _mapping(unit.metadata).get("sourceProject", ""),
                "sourceIds": _mapping(unit.metadata).get("sourceIds", []),
            }
            for unit in Unit.objects.order_by("archived_at", "categoria", "nome")
        ],
        "configuration": {
            "kinds": [{"value": key, "label": label} for key, label in UNIT_KINDS.items()],
            "cores": [
                {
                    "value": key,
                    "label": CORE_LABELS[key],
                    "profile": profile,
                }
                for key, profile in DEFAULT_CORE_PROFILES.items()
            ],
            "tags": [
                {"key": key, "label": label, "minimum": -5, "maximum": 5}
                for key, label in ARCHETYPE_TAGS
            ],
            "equipmentSlots": [
                {"value": key, "label": label}
                for key, label in EQUIPMENT_SLOT_LABELS.items()
            ],
            "competences": [
                {"key": entry["key"], "label": entry["name"]}
                for entry in COMPETENCE_DEFINITIONS
            ],
            "magicPolicies": [
                {"value": "none", "label": "Nessuna magia"},
                {"value": "any", "label": "Magia consentita"},
            ],
            "classFamilies": [
                {"value": family.nome, "label": family.nome}
                for family in FamigliaSkill.objects.filter(
                    is_classe=True,
                    archived_at__isnull=True,
                ).order_by("gruppo__ordine", "ordine", "nome")
            ],
            "religionFamilies": [
                {"value": family.nome, "label": family.nome}
                for family in FamigliaSkill.objects.filter(
                    is_religione=True,
                    archived_at__isnull=True,
                ).order_by("gruppo__ordine", "ordine", "nome")
            ],
            "races": [
                {
                    "value": race,
                    "label": race,
                    "subraces": [
                        {"value": subrace, "label": subrace}
                        for subrace in subraces_for(race)
                    ],
                }
                for race in RACE_NAMES
            ],
            "statCurveProfiles": [
                {"value": key, "label": label}
                for key, label in UNIT_STAT_PROFILE_LABELS.items()
            ],
            "statCurveVariables": list(UNIT_STAT_CURVE_VARIABLES),
        },
    }


def unit_option_search(kind: str, query: str, limit: int = 80) -> dict[str, Any]:
    query = query.strip()
    limit = max(1, min(200, int(limit or 80)))
    if kind == "skill":
        queryset = (
            Skill.objects.filter(archived_at__isnull=True)
            .select_related("famiglia", "famiglia__gruppo")
            .order_by("nome")
        )
        if query:
            queryset = queryset.filter(
                Q(nome__icontains=query)
                | Q(famiglia__nome__icontains=query)
                | Q(famiglia__gruppo__nome__icontains=query)
            )
        return {"kind": kind, "options": [_skill_option(entry) for entry in queryset[:limit]]}
    if kind == "item":
        queryset = Oggetto.objects.filter(
            archived_at__isnull=True,
            archiviato=False,
        ).order_by("nome")
        if query:
            queryset = queryset.filter(
                Q(nome__icontains=query)
                | Q(tipo_1__icontains=query)
                | Q(tipo_2__icontains=query)
                | Q(tipo_3__icontains=query)
                | Q(tipo_4__icontains=query)
            )
        return {"kind": kind, "options": [_item_option(entry) for entry in queryset[:limit]]}
    return {"kind": kind, "options": []}


def serialize_managed_unit(unit: Unit) -> dict[str, Any]:
    rules = _mapping(unit.generation_rules)
    skills = {
        skill.id: skill
        for skill in Skill.objects.filter(
            id__in=[
                _identifier(entry.get("skillId"))
                for entry in _list(unit.skill_unlocks)
                if isinstance(entry, dict) and _identifier(entry.get("skillId"))
            ]
        ).select_related("famiglia", "famiglia__gruppo")
    }
    equipment = _mapping(unit.equipment_profiles)
    item_ids: set[int] = set()
    for entries in _mapping(equipment.get("slots")).values():
        for entry in _list(entries):
            if isinstance(entry, dict) and str(entry.get("itemId", "")).isdigit():
                item_ids.add(_identifier(entry["itemId"]))
    for group in _list(equipment.get("groups")):
        for entry in _list(_mapping(group).get("items")):
            if isinstance(entry, dict) and str(entry.get("itemId", "")).isdigit():
                item_ids.add(_identifier(entry["itemId"]))
    items = Oggetto.objects.filter(id__in=item_ids).in_bulk()

    skill_unlocks = []
    for entry in _list(unit.skill_unlocks):
        if not isinstance(entry, dict):
            continue
        skill = skills.get(_identifier(entry.get("skillId")))
        skill_unlocks.append(
            {
                **entry,
                "skillName": skill.nome if skill else "Skill non trovata",
                "family": skill.famiglia.nome if skill else "",
                "group": skill.famiglia.gruppo.nome if skill else "",
            }
        )

    equipment_slots = []
    for slot, entries in _mapping(equipment.get("slots")).items():
        for entry in _list(entries):
            if not isinstance(entry, dict):
                entry = {"itemId": entry}
            item = items.get(_identifier(entry.get("itemId")))
            equipment_slots.append(
                {
                    "slot": slot,
                    **entry,
                    "chance": entry.get("chance", 1),
                    "itemName": item.nome if item else "Oggetto non trovato",
                }
            )

    equipment_groups = []
    for raw_group in _list(equipment.get("groups")):
        group = _mapping(raw_group)
        group_items = []
        for raw_item in _list(group.get("items")):
            item_entry = _mapping(raw_item) if isinstance(raw_item, dict) else {"itemId": raw_item}
            item = items.get(_identifier(item_entry.get("itemId")))
            group_items.append(
                {
                    **item_entry,
                    "chance": item_entry.get("chance", 1),
                    "itemName": item.nome if item else "Oggetto non trovato",
                }
            )
        equipment_groups.append(
            {
                **group,
                "minCount": group.get("minCount", group.get("count", 1)),
                "maxCount": group.get("maxCount", group.get("count", 1)),
                "emptyChance": group.get("emptyChance", 0),
                "items": group_items,
            }
        )

    return {
        "id": unit.id,
        "name": unit.nome,
        "category": unit.categoria,
        "archetypeDescription": unit.archetipo_descrizione,
        "competenceProfile": _mapping(unit.profilo_competenze),
        "archetypeTags": _mapping(unit.archetipo_tags),
        "statProfile": _mapping(unit.stat_profiles),
        "skillUnlocks": skill_unlocks,
        "equipmentSlots": equipment_slots,
        "equipmentGroups": equipment_groups,
        "accessoryCountByLevel": _list(equipment.get("accessoryCountByLevel")),
        "innateActions": _list(unit.skill_actions),
        "levels": _list(unit.levels),
        "loreDescription": unit.lore_description,
        "notes": unit.notes,
        "archived": unit.archived_at is not None,
        "generation": {
            "kind": rules.get("kind", ""),
            "coreKey": rules.get("coreKey", ""),
            "coreShare": rules.get("coreShare", 0.5),
            "startingXp": rules.get("startingXp", 0),
            "xpBase": _mapping(rules.get("xpPerLevel")).get("base", 20),
            "xpGrowth": _mapping(rules.get("xpPerLevel")).get("growth", 1),
            "competenceStartingXp": _mapping(rules.get("competenceXp")).get("starting", 5),
            "competenceXpBase": _mapping(rules.get("competenceXp")).get("base", 15),
            "competenceXpGrowth": _mapping(rules.get("competenceXp")).get("growth", 0),
            "finalSpendingPasses": rules.get("finalSpendingPasses", 4),
            "magicPolicy": rules.get("magicPolicy", "any"),
            "allowedClassFamilies": _list(rules.get("allowedClassFamilies")),
            "allowedReligionFamilies": _list(rules.get("allowedReligionFamilies")),
            "allowedRaces": _list(rules.get("allowedRaces")),
            "allowedSubraces": _list(rules.get("allowedSubraces")),
            "allowHumanoidStatGrowth": bool(rules.get("allowHumanoidStatGrowth")),
        },
        "metadata": _mapping(unit.metadata),
        "catalog": unit_catalog_entry(unit),
    }
