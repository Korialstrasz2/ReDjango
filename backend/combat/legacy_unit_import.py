from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
import unicodedata
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.db import transaction

from backend.characters.race_rules import RACE_NAMES
from backend.core.models import Giocatore, Oggetto, Unit

from .unit_generation import UNIT_STAT_CURVE_VARIABLES
from .unit_management_services import _clean_unit_values, save_managed_unit


SOURCE_PROJECT = "the_elder_django"
SOURCE_TABLE = "django_slim_unit"
CONVERTER_VERSION = "elder-unit-dossier-v1"
LEGACY_EQUIPMENT_FIELDS = {
    "vestito": "vestiti",
    "armatura": "armatura",
    "chainmail": "chainmail",
    "veste": "veste",
    "scudo": "scudo",
    "arma": "arma",
}
EMPTY_ITEM_NAMES = {"", "vuoto", "nessuno", "nessuna"}
SUPPORTED_ACTION_RESOURCES = {
    "pa": "pa",
    "en": "energia",
    "energia": "energia",
    "mana": "mana",
    "pow": "potere",
    "potere": "potere",
    "pf": "pf",
    "st": "stanchezza",
    "stanchezza": "stanchezza",
}
UNSUPPORTED_MECHANIC_PATTERNS = {
    "unsupported_poison_damage": re.compile(r"\bdann[oi]\s+da\s+veleno\b", re.IGNORECASE),
    "unsupported_strength_damage": re.compile(
        r"\b(?:dann[oi]\s+(?:alla|di)\s+forza|strength damage)\b",
        re.IGNORECASE,
    ),
}
FACTION_LOCK_TOKENS = (
    "imperial",
    "redoran",
    "morag tong",
    "thalmor",
    "confraternita",
    "stormcloak",
    "manto della tempesta",
    "blades",
)
ICONIC_LOCK_TOKENS = ("indoril", "daedric", "daedrico")
ROLE_CORE = {
    "guerriero": "warrior",
    "tank": "warrior",
    "arciere": "warrior",
    "assassino": "stealth",
    "mago": "mage",
    "battlemage": "specialist",
    "extra": "specialist",
}
ROLE_TAGS = {
    "guerriero": {
        "core_fisico": 5,
        "core_magico": -3,
        "focus_combat": 5,
        "range_skill": -2,
        "difesa": 3,
        "attacco": 4,
        "natura_magica": -4,
    },
    "tank": {
        "core_fisico": 5,
        "core_magico": -2,
        "focus_combat": 5,
        "range_skill": -3,
        "difesa": 5,
        "attacco": 2,
        "supporto_party": 3,
    },
    "arciere": {
        "core_fisico": 3,
        "core_magico": -3,
        "focus_combat": 5,
        "range_skill": 5,
        "difesa": 1,
        "attacco": 4,
        "esplorazione_infiltrazione": 3,
    },
    "assassino": {
        "core_fisico": 3,
        "core_magico": -2,
        "focus_combat": 4,
        "range_skill": 0,
        "difesa": 1,
        "attacco": 5,
        "esplorazione_infiltrazione": 5,
        "controllo_situazionale": 3,
    },
    "mago": {
        "core_fisico": -3,
        "core_magico": 5,
        "focus_combat": 3,
        "range_skill": 4,
        "difesa": 1,
        "attacco": 3,
        "natura_magica": 5,
        "controllo_situazionale": 4,
    },
    "battlemage": {
        "core_fisico": 3,
        "core_magico": 4,
        "focus_combat": 5,
        "range_skill": 2,
        "difesa": 3,
        "attacco": 4,
        "natura_magica": 4,
    },
    "extra": {
        "core_fisico": 1,
        "core_magico": 1,
        "focus_combat": 3,
        "controllo_situazionale": 3,
    },
}
ROLE_COMPETENCES = {
    "guerriero": {"strategia_militare": 3, "intimidire": 2, "percezione": 1, "sapienza_magica": -3},
    "tank": {"strategia_militare": 4, "intuizione": 2, "intimidire": 2, "sapienza_magica": -2},
    "arciere": {
        "percezione": 4,
        "sopravvivenza": 3,
        "furtivita": 2,
        "conoscenze_naturaegeografia": 2,
        "sapienza_magica": -4,
    },
    "assassino": {"furtivita": 5, "rapidita_di_mano": 4, "percezione": 3, "raggirare": 2},
    "mago": {"sapienza_magica": 5, "intuizione": 2, "conoscenze_religioni": 1, "ingegneria": 1},
    "battlemage": {"sapienza_magica": 4, "strategia_militare": 3, "percezione": 2, "intuizione": 1},
    "extra": {"percezione": 2, "intuizione": 2},
}
RACE_ALIASES = {"Orco": "Orsimer"}


@dataclass
class UnitImportRun:
    candidates: list[dict[str, Any]]
    summary: dict[str, Any]


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    return " ".join(
        "".join(character for character in text if not unicodedata.combining(character)).split()
    )


def _clean(value: Any) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _json(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if not isinstance(value, str):
        return value
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default
    return parsed


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_source(source_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[int, dict[str, Any]]]:
    resolved = source_path.resolve(strict=True)
    connection = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        units = [dict(row) for row in connection.execute(f"SELECT * FROM {SOURCE_TABLE} ORDER BY id")]
        lore = [
            dict(row)
            for row in connection.execute(
                "SELECT id, unit_id, nome, descrizione, immagine FROM django_slim_unitlore ORDER BY id"
            )
        ]
        skills = {
            int(row["id"]): dict(row)
            for row in connection.execute("SELECT * FROM django_slim_skillnpc ORDER BY id")
        }
    finally:
        connection.close()
    return units, lore, skills


def _group_rows(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(_normalize(row.get("nome")), []).append(row)
    return sorted(groups.values(), key=lambda group: (_normalize(group[0].get("nome")), int(group[0]["id"])))


def _strip_html(value: Any) -> str:
    return " ".join(
        html.unescape(re.sub(r"<[^>]+>", " ", _clean(value))).split()
    )


def _lore_for_group(group: list[dict[str, Any]], lore_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_ids = {int(row["id"]) for row in group}
    normalized_name = _normalize(group[0].get("nome"))
    result = [
        {
            "id": int(row["id"]),
            "unitId": int(row["unit_id"]) if row.get("unit_id") is not None else None,
            "name": _clean(row.get("nome")),
            "description": _strip_html(row.get("descrizione")),
            "image": _clean(row.get("immagine")),
        }
        for row in lore_rows
        if row.get("unit_id") in source_ids or _normalize(row.get("nome")) == normalized_name
    ]
    return result


def _legacy_actions(group: list[dict[str, Any]], skill_rows: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[int] = set()
    actions: list[dict[str, Any]] = []
    for row in group:
        for index in range(1, 8):
            source_id = row.get(f"skill_{index}_id")
            if not source_id or int(source_id) in seen or int(source_id) not in skill_rows:
                continue
            seen.add(int(source_id))
            source = skill_rows[int(source_id)]
            actions.append(
                {
                    "sourceId": int(source_id),
                    "name": _clean(source.get("nome")),
                    "description": _clean(source.get("descrizione")),
                    "effect": _clean(source.get("effetto")),
                    "cost": _clean(source.get("costo")),
                    "boost": _clean(source.get("boost")),
                }
            )
    return actions


def _parse_action_costs(value: Any) -> dict[str, int]:
    costs: dict[str, int] = {}
    for amount, raw_resource in re.findall(r"(\d+)\s*([A-Za-zÀ-ÿ]+)", _clean(value)):
        resource = SUPPORTED_ACTION_RESOURCES.get(_normalize(raw_resource))
        if resource:
            costs[resource] = int(amount)
    return costs


def _action_payload(action: Mapping[str, Any]) -> dict[str, Any]:
    description_parts = [
        _clean(action.get("description")),
        _clean(action.get("effect")),
    ]
    if _clean(action.get("boost")):
        description_parts.append(f"Boost Elder: {_clean(action.get('boost'))}")
    return {
        "key": f"elder-skillnpc-{int(action['sourceId'])}",
        "name": _clean(action.get("name"))[:180],
        "description": " ".join(part for part in description_parts if part),
        "minLevel": 1,
        "maxLevel": 20,
        "costs": _parse_action_costs(action.get("cost")),
        "trigger": "Azione",
        "duration": "",
        "icon": "runa",
    }


def _mechanic_findings(actions: list[dict[str, Any]]) -> list[str]:
    findings = []
    for action in actions:
        text = " ".join(
            _clean(action.get(field))
            for field in ("description", "effect", "boost")
        )
        for code, pattern in UNSUPPORTED_MECHANIC_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{code}:skillnpc:{action['sourceId']}")
    return list(dict.fromkeys(findings))


def _stat_presets() -> dict[str, dict[str, dict[str, float]]]:
    return {
        str(entry["key"]): {
            str(profile): {
                "level1": float(values["level1"]),
                "level20": float(values["level20"]),
            }
            for profile, values in dict(entry["presets"]).items()
        }
        for entry in UNIT_STAT_CURVE_VARIABLES
    }


def _literal_number(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _profile_name(presets: Mapping[str, Mapping[str, float]], level_1: float, level_20: float) -> str:
    for name, values in presets.items():
        if float(values["level1"]) == level_1 and float(values["level20"]) == level_20:
            return str(name)
    return "custom"


def _curve_from_legacy(
    source_key: str,
    raw_profile: Any,
    presets_by_key: Mapping[str, Mapping[str, Mapping[str, float]]],
) -> dict[str, Any] | None:
    key = source_key.removesuffix("_tot")
    if key not in presets_by_key:
        return None
    values = raw_profile if isinstance(raw_profile, (list, tuple)) else []
    if not values:
        return None
    score = _literal_number(values[0])
    if score is None:
        return None
    mode = values[1] if len(values) > 1 else "linear"
    literal = _literal_number(mode)
    presets = presets_by_key[key]
    if literal is not None:
        level_1 = level_20 = literal
    else:
        progress = max(0.0, min(1.0, (score - 1.0) / 9.0))
        low = presets["very_low"]
        high = presets["very_high"]
        level_1 = round(float(low["level1"]) + (float(high["level1"]) - float(low["level1"])) * progress, 2)
        level_20 = round(float(low["level20"]) + (float(high["level20"]) - float(low["level20"])) * progress, 2)
    return {
        "key": key,
        "profile": _profile_name(presets, level_1, level_20),
        "level1": level_1,
        "level20": level_20,
    }


def _creature_curves(group: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    profiles = [
        _json(row.get("profili_attributi_formule"), {})
        for row in group
        if isinstance(_json(row.get("profili_attributi_formule"), {}), dict)
    ]
    warnings: list[str] = []
    if not profiles:
        return [], ["creature_stat_profile_missing"]
    if any(profile != profiles[0] for profile in profiles[1:]):
        warnings.append("creature_stat_profiles_differ_between_source_rows")
    presets = _stat_presets()
    curves = []
    for source_key, raw_profile in profiles[0].items():
        curve = _curve_from_legacy(str(source_key), raw_profile, presets)
        if curve is None:
            warnings.append(f"unsupported_stat_profile:{source_key}")
        else:
            curves.append(curve)
    return curves, list(dict.fromkeys(warnings))


def _item_catalog() -> tuple[dict[str, Oggetto], dict[int, Oggetto]]:
    items = list(Oggetto.objects.filter(archived_at__isnull=True, archiviato=False))
    return {_normalize(item.nome): item for item in items}, {item.id: item for item in items}


def _equipment_payload(
    group: list[dict[str, Any]],
    items_by_name: Mapping[str, Oggetto],
    *,
    creature: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], list[str]]:
    grouped_entries: dict[tuple[str, int], dict[str, Any]] = {}
    receipts: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    for row in group:
        levels = [
            int(level)
            for level in _json(row.get("levels"), [])
            if str(level).strip().isdigit() and 1 <= int(level) <= 20
        ]
        minimum = min(levels) if levels else 1
        maximum = max(levels) if levels else 20
        for source_field, slot in LEGACY_EQUIPMENT_FIELDS.items():
            for raw_name in _json(row.get(source_field), []):
                name = _clean(raw_name)
                if _normalize(name) in EMPTY_ITEM_NAMES:
                    continue
                item = items_by_name.get(_normalize(name))
                receipt = {
                    "query": "current-item-by-normalized-name",
                    "parameters": {"name": name},
                    "resultIds": [item.id] if item else [],
                }
                receipts.append(receipt)
                if item is None:
                    blockers.append(f"equipment_item_missing:{name}")
                    continue
                identity = (slot, item.id)
                if identity not in grouped_entries:
                    grouped_entries[identity] = {
                        "slot": slot,
                        "itemId": item.id,
                        "minLevel": minimum,
                        "maxLevel": maximum,
                        "weight": 1,
                        "chance": 1,
                    }
                else:
                    grouped_entries[identity]["minLevel"] = min(
                        grouped_entries[identity]["minLevel"], minimum
                    )
                    grouped_entries[identity]["maxLevel"] = max(
                        grouped_entries[identity]["maxLevel"], maximum
                    )
    entries = sorted(
        grouped_entries.values(),
        key=lambda entry: (entry["slot"], entry["minLevel"], entry["itemId"]),
    )
    if creature and entries:
        warnings.append("creature_legacy_equipment_requires_innate_action_review")
        entries = []
    if not creature and not entries:
        blockers.append("humanoid_equipment_missing")
    return entries, receipts, list(dict.fromkeys(blockers)), list(dict.fromkeys(warnings))


def _rigidity(group: list[dict[str, Any]]) -> str:
    names = " ".join(
        _normalize(item)
        for row in group
        for field in LEGACY_EQUIPMENT_FIELDS
        for item in _json(row.get(field), [])
    )
    if any(token in names for token in ICONIC_LOCK_TOKENS):
        return "iconic-locked"
    if any(token in names for token in FACTION_LOCK_TOKENS):
        return "faction-locked"
    if str(group[0].get("preset") or "").casefold() == "randomized":
        return "open"
    return "path-locked"


def _allowed_races(group: list[dict[str, Any]]) -> list[str]:
    result = []
    for row in group:
        race = _clean(row.get("razza"))
        race = RACE_ALIASES.get(race, race)
        if race in RACE_NAMES and race not in result:
            result.append(race)
    return result


def _source_snapshot(
    group: list[dict[str, Any]],
    lore: list[dict[str, Any]],
    actions: list[dict[str, Any]],
) -> dict[str, Any]:
    source_rows = []
    for row in group:
        source_rows.append(
            {
                key: (
                    _json(value, value)
                    if key
                    in {
                        "levels",
                        "vestito",
                        "armatura",
                        "chainmail",
                        "veste",
                        "scudo",
                        "arma",
                        "profili_attributi_formule",
                    }
                    else value
                )
                for key, value in sorted(row.items())
            }
        )
    return {"rows": source_rows, "lore": lore, "skillNpc": actions}


def _identity_brief(
    group: list[dict[str, Any]],
    *,
    creature: bool,
    rigidity: str,
    lore: list[dict[str, Any]],
) -> dict[str, Any]:
    role = _normalize(group[0].get("archetipo"))
    return {
        "fantasy": lore[0]["description"][:500] if lore else _clean(group[0].get("nome")),
        "role": "creature" if creature else role,
        "range": "ranged" if role in {"arciere", "mago"} else "mixed" if role == "battlemage" else "melee",
        "magic": "innate-only" if creature else "allowed" if role in {"mago", "battlemage"} else "none",
        "rigidity": "none" if creature else rigidity,
        "must": [],
        "mustNot": (
            ["SkillPersonaggio", "equipment", "competences"]
            if creature
            else ["innate creature actions"]
        ),
    }


def _humanoid_proposal(
    group: list[dict[str, Any]],
    lore: list[dict[str, Any]],
    equipment: list[dict[str, Any]],
) -> dict[str, Any]:
    role = _normalize(group[0].get("archetipo"))
    core = ROLE_CORE.get(role, "specialist")
    return {
        "name": _clean(group[0].get("nome")),
        "category": _clean(group[0].get("categoria")),
        "archetypeDescription": (
            lore[0]["description"][:1000]
            if lore
            else f"Umanoide Elder con ruolo {role or 'specialista'}."
        ),
        "archetypeTags": ROLE_TAGS.get(role, ROLE_TAGS["extra"]),
        "competenceProfile": ROLE_COMPETENCES.get(role, ROLE_COMPETENCES["extra"]),
        "skillUnlocks": [],
        "equipmentSlots": equipment,
        "equipmentGroups": [],
        "accessoryCountByLevel": [],
        "innateActions": [],
        "statProfile": {
            "baseModifiers": {},
            "perLevelModifiers": {},
            "milestones": [],
            "curves": [],
        },
        "levels": [],
        "loreDescription": lore[0]["description"] if lore else "",
        "notes": (
            "Proposta iniziale generata dal dossier Elder. I pool Skill espliciti "
            "devono essere curati e approvati prima dell'importazione."
        ),
        "generation": {
            "kind": "humanoid",
            "coreKey": core,
            "coreShare": 0.5,
            "startingXp": 0,
            "xpBase": 20,
            "xpGrowth": 1,
            "competenceStartingXp": 5,
            "competenceXpBase": 15,
            "competenceXpGrowth": 0,
            "finalSpendingPasses": 4,
            "magicPolicy": "any" if role in {"mago", "battlemage"} else "none",
            "allowedClassFamilies": [],
            "allowedReligionFamilies": [],
            "allowedRaces": _allowed_races(group),
            "allowHumanoidStatGrowth": False,
        },
    }


def _creature_proposal(
    group: list[dict[str, Any]],
    lore: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    curves: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "name": _clean(group[0].get("nome")),
        "category": _clean(group[0].get("categoria")),
        "archetypeDescription": (
            lore[0]["description"][:1000]
            if lore
            else "Creatura Elder convertita con curve lineari e azioni innate."
        ),
        "archetypeTags": {},
        "competenceProfile": {},
        "skillUnlocks": [],
        "equipmentSlots": [],
        "equipmentGroups": [],
        "accessoryCountByLevel": [],
        "innateActions": [_action_payload(action) for action in actions],
        "statProfile": {
            "baseModifiers": {},
            "perLevelModifiers": {},
            "milestones": [],
            "curves": curves,
        },
        "levels": [],
        "loreDescription": lore[0]["description"] if lore else "",
        "notes": (
            "Proposta iniziale generata dal dossier Elder. Verificare azioni aggiuntive "
            "giustificate da lore e tipo, usando soltanto regole ReDjango esistenti."
        ),
        "generation": {"kind": "creature"},
    }


def _existing_by_provenance() -> tuple[dict[frozenset[int], Unit], dict[str, Unit]]:
    by_source_ids: dict[frozenset[int], Unit] = {}
    by_name: dict[str, Unit] = {}
    for unit in Unit.objects.all():
        by_name[_normalize(unit.nome)] = unit
        metadata = unit.metadata if isinstance(unit.metadata, dict) else {}
        if metadata.get("sourceProject") != SOURCE_PROJECT:
            continue
        source_ids = metadata.get("sourceIds") or (
            [metadata["sourceId"]] if metadata.get("sourceId") is not None else []
        )
        parsed = frozenset(
            int(source_id)
            for source_id in source_ids
            if str(source_id).strip().isdigit()
        )
        if parsed:
            by_source_ids[parsed] = unit
    return by_source_ids, by_name


def build_import_run(source_path: Path, *, validate: bool = True) -> UnitImportRun:
    source_rows, lore_rows, skill_rows = _read_source(source_path)
    items_by_name, _items_by_id = _item_catalog()
    existing_by_source, existing_by_name = _existing_by_provenance()
    candidates = []
    for group in _group_rows(source_rows):
        source_ids = [int(row["id"]) for row in group]
        source_id_set = frozenset(source_ids)
        lore = _lore_for_group(group, lore_rows)
        actions = _legacy_actions(group, skill_rows)
        creature = _normalize(group[0].get("archetipo")) == "entita"
        rigidity = _rigidity(group)
        equipment, item_receipts, blockers, warnings = _equipment_payload(
            group,
            items_by_name,
            creature=creature,
        )
        curves: list[dict[str, Any]] = []
        if creature:
            curves, curve_warnings = _creature_curves(group)
            warnings.extend(curve_warnings)
            blockers.extend(_mechanic_findings(actions))
            proposal = _creature_proposal(group, lore, actions, curves)
        else:
            proposal = _humanoid_proposal(group, lore, equipment)
            warnings.append("humanoid_explicit_skill_pools_require_authoring")
        snapshot = _source_snapshot(group, lore, actions)
        source_hash = _stable_hash(snapshot)
        proposal_hash = _stable_hash(proposal)
        conversion_key = f"{SOURCE_PROJECT}:{SOURCE_TABLE}:{','.join(map(str, source_ids))}"
        existing = existing_by_source.get(source_id_set)
        name_collision = existing_by_name.get(_normalize(group[0].get("nome")))
        if name_collision is not None and existing is None:
            blockers.append(f"target_name_owned_by_other_unit:{name_collision.id}")
        if validate and not blockers:
            try:
                _clean_unit_values(proposal)
            except Exception as error:
                code = getattr(error, "code", type(error).__name__)
                field = getattr(error, "field", "")
                blockers.append(f"target_validation:{code}:{field or ''}")
        decision = "admin_required" if blockers else "needs_review"
        if (
            existing is not None
            and isinstance(existing.metadata, dict)
            and existing.metadata.get("seed_kind") == "elder_unit"
        ):
            decision = "approved_existing"
        candidate = {
            "schemaVersion": 1,
            "conversionKey": conversion_key,
            "decision": decision,
            "sourceIds": source_ids,
            "name": _clean(group[0].get("nome")),
            "kind": "creature" if creature else "humanoid",
            "sourceHash": source_hash,
            "proposalHash": proposal_hash,
            "converterVersion": CONVERTER_VERSION,
            "identityBrief": _identity_brief(
                group,
                creature=creature,
                rigidity=rigidity,
                lore=lore,
            ),
            "catalogReceipts": item_receipts,
            "blockers": list(dict.fromkeys(blockers)),
            "warnings": list(dict.fromkeys(warnings)),
            "sourceSnapshot": snapshot,
            "proposal": proposal,
            "authoringQueries": {
                "skills": (
                    []
                    if creature
                    else [
                        {
                            "catalog": "core_skill",
                            "purpose": "Build explicit Core and archetype pools",
                            "role": _normalize(group[0].get("archetipo")),
                        }
                    ]
                ),
                "loreActions": (
                    [
                        {
                            "purpose": "Find lore-supported innate actions",
                            "rule": "Only existing ReDjango mechanic vocabulary",
                        }
                    ]
                    if creature
                    else []
                ),
            },
            "existingUnitId": existing.id if existing else None,
            "approval": None,
        }
        candidates.append(candidate)
    counts = Counter(candidate["decision"] for candidate in candidates)
    kind_counts = Counter(candidate["kind"] for candidate in candidates)
    blocker_counts = Counter(
        blocker.split(":", 1)[0]
        for candidate in candidates
        for blocker in candidate["blockers"]
    )
    summary = {
        "sourcePath": str(source_path.resolve()),
        "sourceRowCount": len(source_rows),
        "unitFamilyCount": len(candidates),
        "kindCounts": dict(sorted(kind_counts.items())),
        "decisionCounts": dict(sorted(counts.items())),
        "blockerCounts": dict(sorted(blocker_counts.items())),
        "converterVersion": CONVERTER_VERSION,
    }
    return UnitImportRun(candidates=candidates, summary=summary)


def write_import_artifacts(run: UnitImportRun, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    dossier_dir = output_dir / "dossiers"
    dossier_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    artifacts = {
        "summary.json": run.summary,
        "all_candidates.json": run.candidates,
        "needs_review.json": [
            candidate for candidate in run.candidates if candidate["decision"] == "needs_review"
        ],
        "admin_required.json": [
            candidate for candidate in run.candidates if candidate["decision"] == "admin_required"
        ],
        "approval_template.json": {
            "schemaVersion": 1,
            "approvals": [
                {
                    "conversionKey": candidate["conversionKey"],
                    "proposalHash": candidate["proposalHash"],
                    "approved": candidate["decision"] == "approved_existing",
                    "approvedBy": "seed" if candidate["decision"] == "approved_existing" else "",
                    "notes": "",
                }
                for candidate in run.candidates
            ],
        },
    }
    for filename, payload in artifacts.items():
        path = output_dir / filename
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        paths.append(path)
    for candidate in run.candidates:
        source_slug = "-".join(map(str, candidate["sourceIds"]))
        path = dossier_dir / f"{source_slug}.json"
        path.write_text(
            json.dumps(candidate, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        paths.append(path)
    return paths


def load_approvals(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    approvals = payload.get("approvals") if isinstance(payload, dict) else None
    if not isinstance(approvals, list):
        raise ValueError("Il file approvazioni deve contenere una lista 'approvals'.")
    result = {}
    for raw in approvals:
        if not isinstance(raw, dict) or not raw.get("conversionKey"):
            continue
        result[str(raw["conversionKey"])] = dict(raw)
    return result


def _approved_candidates(
    run: UnitImportRun,
    approvals: Mapping[str, Mapping[str, Any]],
) -> list[tuple[dict[str, Any], Mapping[str, Any]]]:
    result = []
    for candidate in run.candidates:
        approval = approvals.get(candidate["conversionKey"])
        if not approval or not bool(approval.get("approved")):
            continue
        if str(approval.get("proposalHash") or "") != candidate["proposalHash"]:
            raise ValueError(
                f"Hash proposta non valido per {candidate['conversionKey']}. "
                "Rigenera e riesamina il dossier."
            )
        approved_by = _clean(approval.get("approvedBy"))
        if not approved_by:
            raise ValueError(f"Manca approvedBy per {candidate['conversionKey']}.")
        if candidate["blockers"]:
            raise ValueError(
                f"{candidate['conversionKey']} ha ancora blocker: {', '.join(candidate['blockers'])}"
            )
        result.append((candidate, approval))
    return result


@transaction.atomic
def apply_import_run(
    run: UnitImportRun,
    approvals: Mapping[str, Mapping[str, Any]],
    *,
    user,
    giocatore: Giocatore,
) -> dict[str, int]:
    approved = _approved_candidates(run, approvals)
    created = updated = unchanged = 0
    for candidate, approval in approved:
        existing = None
        if candidate.get("existingUnitId"):
            existing = Unit.objects.filter(pk=candidate["existingUnitId"]).first()
        if existing is None:
            existing = Unit.objects.filter(
                metadata__sourceProject=SOURCE_PROJECT,
                metadata__sourceIds=candidate["sourceIds"],
            ).first()
        metadata = {
            "sourceProject": SOURCE_PROJECT,
            "sourceTable": SOURCE_TABLE,
            "sourceIds": candidate["sourceIds"],
            "sourceHash": candidate["sourceHash"],
            "proposalHash": candidate["proposalHash"],
            "converterVersion": CONVERTER_VERSION,
            "conversionKey": candidate["conversionKey"],
            "approvedBy": _clean(approval.get("approvedBy")),
            "approvalNotes": _clean(approval.get("notes")),
        }
        if (
            existing is not None
            and isinstance(existing.metadata, dict)
            and existing.metadata.get("proposalHash") == candidate["proposalHash"]
            and existing.metadata.get("sourceHash") == candidate["sourceHash"]
        ):
            unchanged += 1
            continue
        _unit, was_created = save_managed_unit(
            user,
            giocatore,
            candidate["proposal"],
            existing.id if existing else None,
            source_metadata=metadata,
        )
        if was_created:
            created += 1
        else:
            updated += 1
    return {
        "approved": len(approved),
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "notApproved": len(run.candidates) - len(approved),
    }


@transaction.atomic
def validate_import_write_path(
    run: UnitImportRun,
    approvals: Mapping[str, Mapping[str, Any]],
    *,
    user,
    giocatore: Giocatore,
) -> dict[str, int]:
    result = apply_import_run(run, approvals, user=user, giocatore=giocatore)
    repeated = apply_import_run(run, approvals, user=user, giocatore=giocatore)
    if repeated["unchanged"] != result["approved"]:
        raise RuntimeError("La seconda esecuzione Unit non è idempotente.")
    result["idempotentUnchanged"] = repeated["unchanged"]
    transaction.set_rollback(True)
    return result
