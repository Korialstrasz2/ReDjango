from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from backend.characters.services.custom_effects import EFFECT_ICONS, effect_target_values
from backend.characters.services.refresh_personaggio import normalize_stat_key
from backend.core.api import ApiError
from backend.core.models import FamigliaSkill, Skill
from backend.core.skill_services import upsert_imported_skill, validate_skill_values


SOURCE_PROJECT = "the_elder_django"
CONVERTER_VERSION = "skill-unification-v6-reviewed-batch-4"
PROFILE_FIELDS = (
    "core_fisico",
    "core_magico",
    "focus_combat",
    "range_skill",
    "area_e_multi_target",
    "natura_magica",
    "difesa",
    "attacco",
    "sociale",
    "supporto_party",
    "esplorazione_infiltrazione",
    "tecnica_crafting",
    "controllo_situazionale",
)
XP_TYPES = {
    "blu": "blue",
    "rossi": "red",
    "verdi": "green",
    "generali": "general",
    "tutti": "all",
    "tutto": "all",
}
OPERATION_TYPES = {
    "+": "add",
    "add": "add",
    "-": "subtract",
    "subtract": "subtract",
    "*": "multiply",
    "multiply": "multiply",
    "%": "percent",
    "percent": "percent",
    "min": "min",
    "max": "max",
    "cap": "cap",
    "set": "set",
}
# Elder split every magic ratio into an Ordine and a Caos variant; ReDjango keeps
# a single unified ratio. Both variants therefore land on the same target and the
# resulting duplicate operations must be collapsed, or each skill tier would apply
# twice. en_per_mana/pa_per_mana are absent on purpose: Elder deleted their
# formulas in migration 0118 and no rule reads them any more.
COLLAPSED_MAGIC_TARGETS = {
    "ogni_en_x_mana_ordine": "ogni_en_x_mana",
    "ogni_en_x_mana_caos": "ogni_en_x_mana",
    "ogni_pa_x_mana_ordine": "ogni_pa_x_mana",
    "ogni_pa_x_mana_caos": "ogni_pa_x_mana",
}
ACTIVE_COST_COLUMNS = {
    "costo_pf": "pf",
    "costo_man": "mana",
    "costo_en": "energia",
    "costo_pow": "potere",
    "costo_pa": "pa",
    "costo_st": "stanchezza",
}
SPELL_TIERS = {
    "base": "base",
    "apprendista": "apprentice",
    "maestro": "master",
}
FORMULA_RE = re.compile(
    r"^\(?m(?:\s*-\s*(?P<base>\d+(?:[.,]\d+)?))?\)?\s*(?:(?P<op>[*/])\s*(?P<factor>\d+(?:[.,]\d+)?))?$",
    re.IGNORECASE,
)
EFFECT_MANA_RE = re.compile(
    r"1\s*effetto\s*=\s*(?P<mana>\d+(?:[.,]\d+)?)\s*mana",
    re.IGNORECASE,
)
RULE_COST_RE = re.compile(
    r"(?P<amount>\d+)\s*(?P<resource>pf|mana|energia|potere|pa|stanchezza)\b",
    re.IGNORECASE,
)

COST_MENTION_RE = re.compile(
    r"(?P<amount>\d+(?:[.,]\d+)?)(?P<variable>\+)?\s*"
    r"(?P<resource>"
    r"p(?:unto|unti)?\s+(?:di\s+)?ferita|pf|"
    r"mana|"
    r"energia|en|"
    r"potere|pow|"
    r"p(?:unto|unti)?\s+azione|pa|"
    r"p(?:unto|unti)?\s+(?:di\s+)?stanchezza|pt\s+stanchezza|stanchezza|st"
    r")\b",
    re.IGNORECASE,
)

REQUIREMENT_ALIASES = {
    "counterspell": "controincantesimo",
    "range spell 1": "raggio incantesimi 1",
    "range spell 2": "raggio incantesimi 2",
    "soultrap": "cattura anima",
}

SYSTEM_MANAGED_SKILL_RULES = {
    99: {
        "unlockRequirements": [
            {"type": "stat_minimum", "stat": "intelligenza", "minimum": 15}
        ],
        "pricingModifier": {
            "type": "owned_skill_flat_discount",
            "amount": 1,
            "minimumBaseCost": 6,
            "xpTypes": ["blue"],
        },
    },
    100: {
        "unlockRequirements": [
            {"type": "stat_minimum", "stat": "forza", "minimum": 15}
        ],
        "pricingModifier": {
            "type": "owned_skill_flat_discount",
            "amount": 1,
            "minimumBaseCost": 6,
            "xpTypes": ["red"],
        },
    },
    101: {
        "unlockRequirements": [
            {"type": "stat_minimum", "stat": "agilita", "minimum": 15}
        ],
        "pricingModifier": {
            "type": "owned_skill_flat_discount",
            "amount": 1,
            "minimumBaseCost": 6,
            "xpTypes": ["green"],
        },
    },
    102: {
        "unlockRequirements": [
            {
                "type": "any_stat_minimum",
                "stats": [
                    "forza",
                    "resistenza",
                    "velocita",
                    "agilita",
                    "intelligenza",
                    "concentrazione",
                    "personalita",
                    "saggezza",
                    "fortuna",
                ],
                "minimum": 15,
            }
        ],
        "pricingModifier": {
            "type": "owned_skill_flat_discount",
            "amount": 1,
            "minimumBaseCost": 6,
            "xpTypes": ["general"],
        },
    },
}

# Administrator-approved resolutions for contradictory Elder records. These are
# intentionally source-specific: they document reviewed rules without weakening
# the generic conflict detector for future imports.
IGNORE_UNLOCK_REQUIREMENT_SOURCE_IDS = {523, 524, 525}
TEXT_ONLY_UNLOCK_REQUIREMENT_SOURCE_IDS = {
    714,
    1061,
    1108,
    1312,
    1386,
    1486,
    1499,
}
DESCRIPTION_ONLY_RULE_SOURCE_IDS = {779, 880, 881, 882, 1108, 1458}
SUPPRESS_ACTIVE_REMINDER_SOURCE_IDS = {1108}
APPROVED_REQUIREMENT_TEXT = {1205: "Rallenta"}
APPROVED_DESCRIPTION_OVERRIDES = {
    1108: (
        "Ottieni 3 PE generali e 1 PE Rosso. Puoi sbloccare questa skill fino a 2 volte; "
        "la seconda volta richiede di aver completato anche le altre 2 abilità rimaste. "
        "Indica nella Nota sullo sblocco se si tratta del primo o del secondo sblocco."
    ),
}

APPROVED_ACTIVE_RESOLUTIONS: dict[int, dict[str, Any]] = {
    47: {"costs": {"energia": 4}},
    49: {
        "costs": {"energia": 6},
        "description": (
            "Una volta al giorno, puoi costringere un avversario a ritirare un suo tiro con svantaggio. "
            "Inoltre, Fortuna cieca 1 continua a essere utilizzabile senza svantaggio e costa 4 Energia."
        ),
    },
    352: {"costs": {}},
    990: {"costs": {"energia": 2}},
    1350: {"costs": {"energia": 2}},
    1386: {"costs": {"stanchezza": 1}},
}

APPROVED_SPELL_RESOLUTIONS: dict[int, dict[str, Any]] = {
    515: {"effectPerMana": 1 / 3, "minimumMana": 3},
    522: {"effectPerMana": 1, "minimumMana": 15},
    523: {"effectPerMana": 3, "minimumMana": 1},
    524: {"effectPerMana": 4, "minimumMana": 1},
    525: {"effectPerMana": 4, "minimumMana": 1},
    531: {"effectPerMana": 0.8, "minimumMana": 1},
    536: {"effectPerMana": 1 / 50, "minimumMana": 50},
    # These three follow the same reviewed fixed-threshold pattern as Dubbio
    # and Malia: the source formula describes Effect, while the prose defines
    # the minimum application threshold or alternate target cost.
    555: {"effectPerMana": 1 / 10, "minimumMana": 10},
    1467: {"effectPerMana": 1, "minimumMana": 10},
    1472: {"effectPerMana": 1, "minimumMana": 10},
    576: {"effectPerMana": 2, "minimumMana": 0},
}

APPROVED_GENERATED_PASSIVE_OPERATIONS: dict[int, list[dict[str, str]]] = {
    871: [{"target": "moltiplicatore_reagenti_rossi", "operation": "add", "value": "0.2", "condition": ""}],
    872: [{"target": "moltiplicatore_reagenti_rossi", "operation": "add", "value": "0.2", "condition": ""}],
    873: [{"target": "moltiplicatore_reagenti_rossi", "operation": "add", "value": "0.2", "condition": ""}],
    874: [{"target": "moltiplicatore_reagenti_blu", "operation": "add", "value": "0.2", "condition": ""}],
    875: [{"target": "moltiplicatore_reagenti_blu", "operation": "add", "value": "0.2", "condition": ""}],
    876: [{"target": "moltiplicatore_reagenti_blu", "operation": "add", "value": "0.2", "condition": ""}],
    877: [{"target": "moltiplicatore_reagenti_verdi", "operation": "add", "value": "0.2", "condition": ""}],
    878: [{"target": "moltiplicatore_reagenti_verdi", "operation": "add", "value": "0.2", "condition": ""}],
    879: [{"target": "moltiplicatore_reagenti_verdi", "operation": "add", "value": "0.2", "condition": ""}],
    884: [{"target": "moltiplicatore_reagenti_livello_3", "operation": "add", "value": "0.5", "condition": ""}],
    885: [{"target": "moltiplicatore_reagenti_livello_3", "operation": "add", "value": "0.2", "condition": ""}],
    886: [
        {"target": f"moltiplicatore_reagenti_livello_{level}", "operation": "add", "value": "0.1", "condition": ""}
        for level in range(1, 5)
    ],
    887: [
        {"target": f"moltiplicatore_reagenti_livello_{level}", "operation": "add", "value": "0.1", "condition": ""}
        for level in range(1, 5)
    ],
}
APPROVED_RESOLUTION_SOURCE_IDS = (
    set(APPROVED_ACTIVE_RESOLUTIONS)
    | set(APPROVED_SPELL_RESOLUTIONS)
    | set(APPROVED_GENERATED_PASSIVE_OPERATIONS)
    | IGNORE_UNLOCK_REQUIREMENT_SOURCE_IDS
    | TEXT_ONLY_UNLOCK_REQUIREMENT_SOURCE_IDS
    | DESCRIPTION_ONLY_RULE_SOURCE_IDS
    | set(APPROVED_REQUIREMENT_TEXT)
    | {632}
)

FORMULA_STAT_ALIASES = {
    "forza": ("forza", "for"),
    "resistenza": ("resistenza", "res"),
    "velocita": ("velocita", "vel"),
    "agilita": ("agilita", "agi"),
    "intelligenza": ("intelligenza", "int"),
    "concentrazione": ("concentrazione", "con"),
    "personalita": ("personalita", "per"),
    "saggezza": ("saggezza", "sag"),
    "fortuna": ("fortuna", "fort"),
}


@dataclass
class ImportRun:
    candidates: list[dict[str, Any]]
    summary: dict[str, Any]


def _clean(value: Any) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _json_decode(value: Any) -> Any:
    current = value
    for _index in range(6):
        if not isinstance(current, str):
            return current
        text = current.strip()
        if not text:
            return None
        try:
            current = json.loads(text)
        except json.JSONDecodeError:
            return current
    return current


def _meaningful_json(value: Any) -> bool:
    decoded = _json_decode(value)
    return decoded not in (None, "", {}, [], "{}", "null")


def _hash_source(source: dict[str, Any]) -> str:
    encoded = json.dumps(source, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _read_source(path: Path) -> list[dict[str, Any]]:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        rows = connection.execute(
            """
            SELECT
                s.*,
                f.nome AS source_family_name,
                f.gruppo AS source_family_group,
                f.note AS source_family_notes,
                p.id AS profile_id,
                p.notes AS profile_notes,
                p.core_fisico, p.core_magico, p.focus_combat, p.range_skill,
                p.area_e_multi_target, p.natura_magica, p.difesa, p.attacco,
                p.sociale, p.supporto_party, p.esplorazione_infiltrazione,
                p.tecnica_crafting, p.controllo_situazionale,
                e.id AS proposal_id,
                e.nome AS proposal_name,
                e.note_proposte,
                e.effetto_proposto,
                e.confidence AS proposal_confidence,
                e.attivabile_collegato_id AS active_id,
                a.nome AS active_name,
                a.origine AS active_origin,
                a.icona AS active_icon,
                a.descrizione AS active_description,
                a.effetto_1, a.effetto_2, a.effetto_3, a.effetto_4,
                a.costo_en, a.costo_man, a.costo_pa, a.costo_pf, a.costo_pow, a.costo_st,
                a.gruppo AS active_group,
                a.messaggio_a_fine_turno,
                a.messaggio_ad_esecuzione,
                a.durata_turni,
                a.effetto_attivabile
            FROM django_slim_skill s
            LEFT JOIN django_slim_famigliaskill f ON f.id = s.famiglia_id
            LEFT JOIN django_slim_skillprofiletags p ON p.skill_id = s.id
            LEFT JOIN django_slim_effettisbloccabili e ON e.skill_collegata_id = s.id
            LEFT JOIN django_slim_attivabile a ON a.id = e.attivabile_collegato_id
            ORDER BY s.id, e.id
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def _search_key(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", _clean(value).casefold())
    without_accents = "".join(character for character in normalized if not unicodedata.combining(character))
    return re.sub(r"\s+", " ", without_accents.replace("’", "'")).strip()


def _rewrite_passive_formula(value: Any) -> str:
    rewritten = _clean(value)
    rewritten = re.sub(
        r"\(f\)\s*Personaggio\.livello",
        "personaggio.livello",
        rewritten,
        flags=re.IGNORECASE,
    )
    for stat in FORMULA_STAT_ALIASES:
        rewritten = re.sub(
            rf"\(f\)\s*Personaggio\.modificatore_{stat}",
            f"final.mod_{stat}",
            rewritten,
            flags=re.IGNORECASE,
        )
    return rewritten


def _decimal_literal(value: Any) -> Decimal | None:
    cleaned = _clean(value).replace(",", ".")
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", cleaned):
        return None
    try:
        return Decimal(cleaned)
    except Exception:
        return None


def _number_tokens(text: str) -> list[Decimal]:
    values: list[Decimal] = []
    for match in re.finditer(r"(?<!\w)\d+(?:[.,]\d+)?(?!\w)", text):
        try:
            values.append(Decimal(match.group().replace(",", ".")))
        except Exception:
            continue
    return values


def _formula_value_evidenced(value: str, evidence: str) -> bool:
    formula_key = _search_key(value)
    evidence_key = _search_key(evidence)
    referenced_stats = re.findall(r"final\.mod_([a-z_]+)", formula_key)
    if "personaggio.livello" in formula_key and "livell" not in evidence_key:
        return False
    for stat in referenced_stats:
        aliases = FORMULA_STAT_ALIASES.get(stat, (stat,))
        if not any(re.search(rf"\b{re.escape(alias)}\b", evidence_key) for alias in aliases):
            return False
    if not referenced_stats and "personaggio.livello" not in formula_key:
        return False
    significant_coefficients = {
        number
        for number in _number_tokens(formula_key)
        if number not in {Decimal("0"), Decimal("1")}
    }
    return significant_coefficients.issubset(set(_number_tokens(evidence_key)))


def _passive_value_evidenced(value: str, evidence: str, target: str) -> bool:
    numeric = _decimal_literal(value)
    if numeric is None:
        return _formula_value_evidenced(value, evidence)
    evidence_key = _search_key(evidence).replace(",", ".")
    numbers = _number_tokens(evidence_key)
    if numeric in numbers:
        return True
    cumulative_wording = any(
        marker in evidence_key
        for marker in ("oltre ai bonus", "invece di", "ulteriore", "aggiuntiv")
    )
    if cumulative_wording:
        for left in numbers:
            for right in numbers:
                if left > right and left - right == abs(numeric):
                    return True
    if abs(numeric) == Decimal("1") and any(
        marker in evidence_key for marker in ("ulteriore", "aggiuntiv", "uno slot", "un ulteriore")
    ):
        target_words = [part for part in target.split("_") if len(part) > 2 and part not in {"max", "skill"}]
        target_roots = {word.rstrip("io") for word in target_words}
        return not target_words or any(root and root in evidence_key for root in target_roots)
    if abs(numeric) == Decimal("1") and Decimal("2") in numbers and target.endswith("_max"):
        target_root = target.removesuffix("_max").rstrip("io")
        return bool(target_root and target_root in evidence_key)
    return False


def _canonical_cost_resource(value: str) -> str:
    key = _search_key(value)
    if key in {"pf", "punto ferita", "punti ferita"}:
        return "pf"
    if key == "mana":
        return "mana"
    if key in {"energia", "en"}:
        return "energia"
    if key in {"potere", "pow"}:
        return "potere"
    if key in {"pa", "punto azione", "punti azione"}:
        return "pa"
    return "stanchezza"


def _cost_mentions(value: Any) -> list[dict[str, Any]]:
    text = _clean(value)
    key = _search_key(text)
    mentions: list[dict[str, Any]] = []
    for match in COST_MENTION_RE.finditer(text):
        amount = Decimal(match.group("amount").replace(",", "."))
        before = _search_key(text[max(0, match.start() - 28):match.start()])
        after = _search_key(text[match.end():match.end() + 36])
        variable = bool(match.group("variable"))
        variable = variable or bool(
            re.search(
                r"^(?:/|ogni\b|(?:a|per)\s+(?:turno|round|casella|passo|bersaglio|effetto|d8)\b)",
                after,
            )
        )
        variable = variable or any(
            marker in after
            for marker in ("aggiuntiv", " extra", "in meno", "oltre al costo", "oltre i costi")
        )
        variable = variable or before.rstrip().endswith("/")
        variable = variable or "variabil" in key
        variable = variable or (
            any(marker in before or marker in after for marker in ("prima", "dopo"))
            and "prima" in key
            and "dopo" in key
        )
        mentions.append(
            {
                "resource": _canonical_cost_resource(match.group("resource")),
                "amount": amount,
                "variable": variable,
            }
        )
    if len(mentions) > 1 and (re.search(r"\s(?:o|oppure)\s", key) or "alternativ" in key):
        for mention in mentions:
            mention["variable"] = True
    return mentions


def _cost_evidence_text(row: dict[str, Any]) -> str:
    parts = [_clean(row.get("costo"))]
    for field in ("descrizione", "active_description"):
        text = _clean(row.get(field))
        if not text:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
            if re.search(r"\b(?:cost\w*|spend\w*|pag\w*|consum\w*)\b", sentence, re.IGNORECASE):
                parts.append(sentence)
    return " ".join(part for part in parts if part)


def _structured_active_costs(row: dict[str, Any], blockers: list[str]) -> dict[str, int]:
    raw_costs = {
        resource: int(row[column])
        for column, resource in ACTIVE_COST_COLUMNS.items()
        if row.get(column) not in (None, 0, "0")
    }
    if not raw_costs:
        return {}
    evidence_text = _cost_evidence_text(row)
    mentions = _cost_mentions(evidence_text)
    parsed_spell = parse_spell_formula(row.get("formula_effetto")) if row.get("magia") else None
    costs: dict[str, int] = {}
    conflict = False
    for resource, amount in raw_costs.items():
        resource_mentions = [entry for entry in mentions if entry["resource"] == resource]
        fixed_mentions = [entry for entry in resource_mentions if not entry["variable"]]
        variable_mentions = [entry for entry in resource_mentions if entry["variable"]]
        expected = Decimal(amount)
        if (
            resource == "mana"
            and parsed_spell is not None
            and parsed_spell["base_mana"] > 0
            and expected == parsed_spell["base_mana"]
            and not any(entry["amount"] == expected for entry in resource_mentions)
        ):
            continue
        matching_fixed = [entry for entry in fixed_mentions if entry["amount"] == expected]
        other_fixed = [entry for entry in fixed_mentions if entry["amount"] != expected]
        if matching_fixed:
            costs[resource] = amount
            if other_fixed:
                conflict = True
            continue
        if variable_mentions and not fixed_mentions:
            continue
        if fixed_mentions:
            conflict = True
            continue
        same_amount_other_resource = any(
            not entry["variable"] and entry["amount"] == expected
            for entry in mentions
            if entry["resource"] != resource
        )
        if same_amount_other_resource and not any(
            entry["amount"] == expected
            and entry["resource"] != resource
            and other_resource == entry["resource"]
            and Decimal(other_amount) == entry["amount"]
            for other_resource, other_amount in raw_costs.items()
            for entry in mentions
        ):
            conflict = True
            continue
        costs[resource] = amount
    if conflict:
        blockers.append("active_cost_conflict")
    return costs


def _merged_collapsed_value(existing: str, incoming: str) -> str:
    """Merge the Ordine and Caos halves of one collapsed magic ratio.

    They are almost always identical; when Elder gave them different numbers the
    unified ratio takes their average, which is the same rule the character
    importer applies to manually written Elder effects.
    """
    if existing == incoming:
        return existing
    try:
        average = (Decimal(existing) + Decimal(incoming)) / 2
    except (ArithmeticError, ValueError):
        return f"(({existing}) + ({incoming})) / 2"
    return format(average.normalize(), "f")


def _passive(row: dict[str, Any], blockers: list[str], warnings: list[str]) -> list[dict[str, Any]]:
    payload = _json_decode(row.get("effetto_proposto"))
    if not isinstance(payload, dict) or payload.get("tipo") in (None, "nessuno"):
        return []
    if payload.get("tipo") != "effetto_extra" or not isinstance(payload.get("effetto_extra"), dict):
        blockers.append("passive_payload_type_unknown")
        return []
    extra = payload["effetto_extra"]
    operations: list[dict[str, str]] = []
    collapsed_slots: dict[tuple[str, str], int] = {}
    for operation in extra.get("effetti") or []:
        if not isinstance(operation, dict):
            blockers.append("passive_operation_invalid")
            continue
        raw_target = _clean(operation.get("name")).lower()
        target = COLLAPSED_MAGIC_TARGETS.get(raw_target, normalize_stat_key(raw_target))
        mapped_operation = OPERATION_TYPES.get(_clean(operation.get("operation")).lower())
        value = _rewrite_passive_formula(operation.get("value"))
        if target not in effect_target_values():
            blockers.append(f"passive_target_unsupported:{target or 'empty'}")
        if mapped_operation is None:
            blockers.append("passive_operation_unsupported")
        if not value:
            blockers.append("passive_value_missing")
        if not (target in effect_target_values() and mapped_operation and value):
            continue
        if raw_target not in COLLAPSED_MAGIC_TARGETS:
            operations.append(
                {"target": target, "operation": mapped_operation, "value": value, "condition": ""}
            )
            continue
        # Ordine and Caos both collapse onto one ReDjango target: merge them into a
        # single operation instead of applying the same bonus twice.
        slot = collapsed_slots.get((target, mapped_operation))
        if slot is None:
            collapsed_slots[(target, mapped_operation)] = len(operations)
            operations.append(
                {"target": target, "operation": mapped_operation, "value": value, "condition": ""}
            )
        else:
            operations[slot]["value"] = _merged_collapsed_value(operations[slot]["value"], value)
    if not operations:
        blockers.append("passive_has_no_valid_operations")
        return []
    description = _clean(extra.get("descrizione"))
    evidence = " ".join(
        value
        for value in (description, _clean(row.get("descrizione")), _clean(row.get("note")))
        if value
    )
    if any(
        not _passive_value_evidenced(operation["value"], evidence, operation["target"])
        for operation in operations
    ):
        blockers.append("passive_value_not_evidenced_in_prose")
    icon = _clean(extra.get("icona")).lower()
    allowed_icons = {value for value, _label, _category, _keywords in EFFECT_ICONS}
    if icon.endswith("_extra"):
        icon = icon.removesuffix("_extra")
    if icon not in allowed_icons:
        icon = "runa"
        warnings.append("passive_icon_fell_back_to_runa")
    return [
        {
            "id": f"passivo-legacy-proposta-{row['proposal_id']}",
            "name": _clean(extra.get("nome")) or _clean(row.get("proposal_name")) or _clean(row.get("nome")),
            "description": description or _clean(row.get("descrizione")),
            "icon": icon,
            "operations": operations,
        }
    ]


def _active(row: dict[str, Any], blockers: list[str], warnings: list[str]) -> list[dict[str, Any]]:
    if not row.get("active_id"):
        return []
    if _meaningful_json(row.get("effetto_attivabile")):
        blockers.append("active_executable_payload_not_empty")
    costs = _structured_active_costs(row, blockers)
    description = max(
        (_clean(row.get("active_description")), _clean(row.get("descrizione")), _clean(row.get("note"))),
        key=len,
    )
    if not description:
        blockers.append("active_description_missing")
    icon = _clean(row.get("active_icon")).lower()
    allowed_icons = {value for value, _label, _category, _keywords in EFFECT_ICONS}
    if icon not in allowed_icons:
        icon = "runa"
        warnings.append("active_icon_fell_back_to_runa")
    supporting_notes = [
        _clean(row.get(key))
        for key in ("effetto_1", "effetto_2", "effetto_3", "effetto_4", "messaggio_ad_esecuzione", "messaggio_a_fine_turno")
        if _clean(row.get(key))
    ]
    return [
        {
            "id": f"azione-legacy-attivabile-{row['active_id']}",
            "name": _clean(row.get("active_name")) or _clean(row.get("nome")),
            "description": description,
            "trigger": "",
            "duration": (
                f"{row['durata_turni']} turni" if row.get("durata_turni") not in (None, 0) else ""
            ),
            "usageNotes": "\n".join(supporting_notes),
            "costs": costs,
            "icon": icon,
        }
    ]


def parse_spell_formula(value: Any) -> dict[str, Decimal] | None:
    normalized = _clean(value).replace(",", ".").replace(" ", "")
    match = FORMULA_RE.fullmatch(normalized)
    if not match:
        return None
    base = Decimal(match.group("base") or "0")
    factor = Decimal(match.group("factor") or "1")
    if factor <= 0:
        return None
    operation = match.group("op")
    effect_per_mana = Decimal(1) / factor if operation == "/" else factor
    return {"base_mana": base, "effect_per_mana": effect_per_mana}


def _spell_rule_effect_per_mana(row: dict[str, Any]) -> Decimal | None:
    text = _clean(row.get("costo")).replace(",", ".").casefold()
    if not text:
        return None
    mana_first = re.search(
        r"(?P<mana>\d+(?:\.\d+)?)\s*mana\s*(?:/|ogni)\s*"
        r"(?P<effect>\d+(?:\.\d+)?)\s*(?:pf|dann\w*|mt\b|metr\w*|effett\w*|punt\w*\s+st)",
        text,
    )
    if mana_first:
        mana = Decimal(mana_first.group("mana"))
        effect = Decimal(mana_first.group("effect"))
        if mana > 0:
            return effect / mana
    effect_first = re.search(
        r"(?P<effect>\d+(?:\.\d+)?)\s*%[^.;]{0,48}?(?:/|per)\s*"
        r"(?P<mana>\d+(?:\.\d+)?)\s*mana",
        text,
    )
    if effect_first:
        mana = Decimal(effect_first.group("mana"))
        effect = Decimal(effect_first.group("effect"))
        if mana > 0:
            return effect / mana
    one_effect = re.search(
        r"(?P<mana>\d+(?:\.\d+)?)\s*mana\s*/\s*(?:un\s+|1\s+)?punt\w*\s+(?:di\s+)?st",
        text,
    )
    if one_effect:
        mana = Decimal(one_effect.group("mana"))
        if mana > 0:
            return Decimal(1) / mana
    return None


def _spell_minimum_mana(row: dict[str, Any], parsed: dict[str, Decimal]) -> Decimal:
    original_cost_text = _clean(row.get("costo"))
    cost_text = original_cost_text.replace(",", ".")
    explicit: Decimal | None = None
    threshold_list = re.match(r"\s*(\d+)\s*[,;]\s*\d+.*\bmana\b", original_cost_text, re.IGNORECASE)
    mana_match = re.search(r"(\d+(?:\.\d+)?)\s*mana\b", cost_text, re.IGNORECASE)
    if threshold_list:
        explicit = Decimal(threshold_list.group(1))
    elif mana_match:
        explicit = Decimal(mana_match.group(1))
    elif "mana" in cost_text.casefold():
        leading = re.match(r"\s*(\d+(?:\.\d+)?)", cost_text)
        if leading:
            explicit = Decimal(leading.group(1))
    if explicit is None and row.get("costo_man") not in (None, 0, "0"):
        explicit = Decimal(str(row["costo_man"]))
    return max(parsed["base_mana"], explicit if explicit is not None else parsed["base_mana"])


def _spell(row: dict[str, Any], blockers: list[str]) -> dict[str, Any] | None:
    if not bool(row.get("magia")):
        return None
    parsed = parse_spell_formula(row.get("formula_effetto"))
    if parsed is None:
        blockers.append("spell_formula_not_supported")
        return None
    tier = SPELL_TIERS.get(_clean(row.get("livello_magia")).lower())
    if tier is None:
        blockers.append("spell_tier_unknown")
        tier = "base"
    active_effect = EFFECT_MANA_RE.search(_clean(row.get("effetto_1")))
    if active_effect:
        stated_mana = Decimal(active_effect.group("mana").replace(",", "."))
        expected_mana = Decimal(1) / parsed["effect_per_mana"]
        if abs(stated_mana - expected_mana) > Decimal("0.05"):
            rule_effect = _spell_rule_effect_per_mana(row)
            if rule_effect is None or abs(rule_effect - parsed["effect_per_mana"]) > Decimal("0.000001"):
                blockers.append("spell_formula_conflicts_with_active_effect")
    else:
        rule_effect = _spell_rule_effect_per_mana(row)
        if rule_effect is not None and abs(rule_effect - parsed["effect_per_mana"]) > Decimal("0.000001"):
            blockers.append("spell_formula_conflicts_with_active_effect")
    minimum_mana = _spell_minimum_mana(row, parsed)
    return {
        "tier": tier,
        "range": _clean(row.get("raggio")),
        "effectUnit": "Effetto",
        "baseMana": float(parsed["base_mana"]),
        "effectPerMana": float(parsed["effect_per_mana"]),
        "minimumMana": float(minimum_mana),
        "rounding": "none",
        "legacyFormula": _clean(row.get("formula_effetto")),
        "costNotes": _clean(row.get("costo")),
        "combatConfiguration": {
            "prepared": True,
            "spendsResources": False,
            "source": "legacy_spell_formula",
        },
    }


def _apply_approved_resolution(
    row: dict[str, Any],
    passives: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    spell: dict[str, Any] | None,
    blockers: list[str],
) -> None:
    """Apply only administrator-reviewed, source-specific conflict resolutions."""

    source_id = int(row["id"])
    active_resolution = APPROVED_ACTIVE_RESOLUTIONS.get(source_id)
    if active_resolution and actions:
        action = actions[0]
        action["costs"] = dict(active_resolution["costs"])
        action["description"] = active_resolution.get("description") or _clean(row.get("descrizione"))
        blockers[:] = [blocker for blocker in blockers if blocker != "active_cost_conflict"]

    spell_resolution = APPROVED_SPELL_RESOLUTIONS.get(source_id)
    if spell_resolution and spell is not None:
        spell.update(spell_resolution)
        blockers[:] = [
            blocker
            for blocker in blockers
            if blocker != "spell_formula_conflicts_with_active_effect"
        ]

    if source_id in IGNORE_UNLOCK_REQUIREMENT_SOURCE_IDS:
        blockers[:] = [
            blocker
            for blocker in blockers
            if blocker != "requirement_not_exact_skill_name"
        ]

    if source_id in TEXT_ONLY_UNLOCK_REQUIREMENT_SOURCE_IDS:
        blockers[:] = [
            blocker
            for blocker in blockers
            if blocker != "requirement_not_exact_skill_name"
        ]

    if source_id == 632 and passives:
        for operation in passives[0].get("operations", []):
            if operation.get("target") == "potere":
                operation["value"] = "final.mod_concentrazione+0"
        blockers[:] = [
            blocker
            for blocker in blockers
            if blocker != "passive_value_not_evidenced_in_prose"
        ]


def _approved_generated_passives(row: dict[str, Any]) -> list[dict[str, Any]]:
    operations = APPROVED_GENERATED_PASSIVE_OPERATIONS.get(int(row["id"]))
    if not operations:
        return []
    return [
        {
            "id": f"passivo-legacy-risolto-{row['id']}",
            "name": _clean(row.get("nome")),
            "description": _clean(row.get("descrizione")),
            "icon": "pozione",
            "operations": [dict(operation) for operation in operations],
        }
    ]


def _requirement_source_ids(requirement: str, source_names: dict[str, int]) -> list[int] | None:
    requirement_key = _search_key(requirement)
    aliased_key = REQUIREMENT_ALIASES.get(requirement_key, requirement_key)
    if aliased_key in source_names:
        return [source_names[aliased_key]]
    tokens = [_search_key(token) for token in re.split(r"[,;]", requirement) if _clean(token)]
    if len(tokens) <= 1:
        return None
    resolved: list[int] = []
    for token in tokens:
        token = REQUIREMENT_ALIASES.get(token, token)
        source_id = source_names.get(token)
        if source_id is None:
            return None
        resolved.append(source_id)
    return list(dict.fromkeys(resolved))


def _candidate(
    row: dict[str, Any],
    *,
    family_ids: dict[tuple[str, str], int],
    source_names: dict[str, int],
    target_names: dict[str, int],
    target_numbers: dict[int, int],
    target_slugs: set[str],
    source_slug_counts: Counter,
    existing_source_skill: Skill | None,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    family_key = (_clean(row.get("source_family_group")), _clean(row.get("source_family_name")))
    family_id = family_ids.get(family_key)
    if family_id is None:
        blockers.append("target_family_missing")
    xp_type = XP_TYPES.get(_clean(row.get("tipo_pe")).lower())
    if xp_type is None:
        blockers.append("xp_type_unknown")
        xp_type = "all"
    name = _clean(row.get("nome"))
    number = int(row.get("numero") or 0)
    base_slug = slugify(name) or f"skill-{row['id']}"
    candidate_slug = existing_source_skill.slug if existing_source_skill else (
        f"{base_slug}-{row['id']}"
        if source_slug_counts[base_slug] > 1 or base_slug in target_slugs
        else base_slug
    )
    existing_target_id = existing_source_skill.id if existing_source_skill else None
    if name in target_names and target_names[name] != existing_target_id:
        blockers.append("target_name_collision")
    if number in target_numbers and target_numbers[number] != existing_target_id:
        blockers.append("target_number_collision")
    requirement = APPROVED_REQUIREMENT_TEXT.get(int(row["id"]), _clean(row.get("requisiti")))
    prerequisite_source_ids: list[int] = []
    system_rules = SYSTEM_MANAGED_SKILL_RULES.get(int(row["id"]), {})
    if (
        requirement
        and not system_rules.get("unlockRequirements")
        and int(row["id"]) not in IGNORE_UNLOCK_REQUIREMENT_SOURCE_IDS
        and int(row["id"]) not in TEXT_ONLY_UNLOCK_REQUIREMENT_SOURCE_IDS
    ):
        resolved_requirements = _requirement_source_ids(requirement, source_names)
        if resolved_requirements is None:
            blockers.append("requirement_not_exact_skill_name")
        elif row["id"] in resolved_requirements:
            blockers.append("self_prerequisite")
        else:
            prerequisite_source_ids.extend(resolved_requirements)
    passives = _passive(row, blockers, warnings)
    passives.extend(_approved_generated_passives(row))
    actions = _active(row, blockers, warnings)
    if int(row["id"]) in SUPPRESS_ACTIVE_REMINDER_SOURCE_IDS:
        actions = []
    spell = _spell(row, blockers)
    _apply_approved_resolution(row, passives, actions, spell, blockers)
    if (
        not passives
        and not actions
        and spell is None
        and not system_rules
        and int(row["id"]) not in DESCRIPTION_ONLY_RULE_SOURCE_IDS
    ):
        blockers.append("no_structured_feature")
    if _clean(row.get("effetto_da_aggiungere")):
        blockers.append("transitional_effect_field_not_empty")
    profile_tags = {
        field: int(row.get(field) or 0)
        for field in PROFILE_FIELDS
        if row.get("profile_id") is not None
    }
    source = {key: row.get(key) for key in sorted(row)}
    metadata = {
        "sourceProject": SOURCE_PROJECT,
        "sourceTable": "django_slim_skill",
        "sourceId": row["id"],
        "sourceFamilyId": row.get("famiglia_id"),
        "sourceProfileId": row.get("profile_id"),
        "sourceEffettiSbloccabiliId": row.get("proposal_id"),
        "sourceAttivabileId": row.get("active_id"),
        "sourceHash": _hash_source(source),
        "converterVersion": CONVERTER_VERSION,
        "orderChaosCollapsed": True,
    }
    metadata.update(system_rules)
    if int(row["id"]) in APPROVED_RESOLUTION_SOURCE_IDS:
        metadata["approvedMigrationResolution"] = "reviewed-batch-2"
    if int(row["id"]) in DESCRIPTION_ONLY_RULE_SOURCE_IDS:
        metadata["descriptionOnlyRule"] = True
    if (
        existing_source_skill
        and isinstance(existing_source_skill.metadata, dict)
        and existing_source_skill.metadata.get("sourceHash") != metadata["sourceHash"]
    ):
        blockers.append("source_changed_since_last_import")
    values = {
        "name": name,
        "slug": candidate_slug,
        "number": number,
        "familyId": family_id or 0,
        "familyOrder": int(row.get("ordine_famiglia") or 0),
        "magic": spell is not None,
        "baseXpCost": max(0, int(row.get("costo_pe") or 0)),
        "xpType": xp_type,
        "rulesCost": _clean(row.get("costo")),
        "description": APPROVED_DESCRIPTION_OVERRIDES.get(
            int(row["id"]),
            _clean(row.get("descrizione")),
        ),
        "requirementsText": (
            "" if int(row["id"]) in IGNORE_UNLOCK_REQUIREMENT_SOURCE_IDS else requirement
        ),
        "prerequisiteIds": [],
        "profileTags": profile_tags,
        "profileNotes": _clean(row.get("profile_notes")),
        "passiveEffects": passives,
        "activeReminders": actions,
        "spell": spell,
        "icon": actions[0]["icon"] if actions else passives[0]["icon"] if passives else "runa",
        "notes": (
            "Modificatori del bersaglio gestiti durante il gioco. Fonte Elder: " + requirement
            if int(row["id"]) in IGNORE_UNLOCK_REQUIREMENT_SOURCE_IDS and requirement
            else _clean(row.get("note"))
        ),
        "metadata": metadata,
    }
    unique_blockers = list(dict.fromkeys(blockers))
    decision = "auto_import" if not unique_blockers else "needs_review"
    if any(blocker in unique_blockers for blocker in ("target_family_missing", "target_name_collision", "target_number_collision")):
        decision = "admin_required"
    return {
        "sourceId": row["id"],
        "name": name,
        "decision": decision,
        "blockers": unique_blockers,
        "warnings": list(dict.fromkeys(warnings)),
        "prerequisiteSourceIds": prerequisite_source_ids,
        "values": values,
        "source": source,
    }


def _prerequisite_cycle_ids(candidates: list[dict[str, Any]]) -> set[int]:
    graph = {
        candidate["sourceId"]: list(candidate["prerequisiteSourceIds"])
        for candidate in candidates
        if candidate["decision"] == "auto_import"
    }
    state: dict[int, int] = {}
    stack: list[int] = []
    cycle_ids: set[int] = set()

    def visit(source_id: int) -> None:
        current_state = state.get(source_id, 0)
        if current_state == 2:
            return
        if current_state == 1:
            if source_id in stack:
                cycle_ids.update(stack[stack.index(source_id):])
            return
        state[source_id] = 1
        stack.append(source_id)
        for prerequisite_id in graph.get(source_id, []):
            if prerequisite_id in graph:
                visit(prerequisite_id)
        stack.pop()
        state[source_id] = 2

    for source_id in graph:
        visit(source_id)
    return cycle_ids


def build_import_run(source_path: Path, *, validate: bool = True) -> ImportRun:
    rows = _read_source(source_path)
    row_counts = Counter(int(row["id"]) for row in rows)
    duplicate_ids = {source_id for source_id, count in row_counts.items() if count > 1}
    first_rows: dict[int, dict[str, Any]] = {}
    for row in rows:
        first_rows.setdefault(int(row["id"]), row)
    source_names = {_search_key(row.get("nome")): source_id for source_id, row in first_rows.items()}
    source_slug_counts = Counter(
        slugify(_clean(row.get("nome"))) or f"skill-{source_id}"
        for source_id, row in first_rows.items()
    )
    family_ids = {
        (family.gruppo.nome, family.nome): family.id
        for family in FamigliaSkill.objects.filter(
            archived_at__isnull=True,
            gruppo__archived_at__isnull=True,
        ).select_related("gruppo")
    }
    target_skills = list(Skill.objects.all())
    target_names = {skill.nome: skill.id for skill in target_skills}
    target_numbers = {skill.numero: skill.id for skill in target_skills}
    target_slugs = {skill.slug for skill in target_skills}
    target_by_source = {
        (skill.metadata.get("sourceProject"), skill.metadata.get("sourceId")): skill
        for skill in target_skills
        if isinstance(skill.metadata, dict)
        and skill.metadata.get("sourceProject")
        and skill.metadata.get("sourceId") is not None
    }
    candidates = [
        _candidate(
            row,
            family_ids=family_ids,
            source_names=source_names,
            target_names=target_names,
            target_numbers=target_numbers,
            target_slugs=target_slugs,
            source_slug_counts=source_slug_counts,
            existing_source_skill=target_by_source.get((SOURCE_PROJECT, row["id"])),
        )
        for row in first_rows.values()
    ]
    for candidate in candidates:
        if candidate["sourceId"] in duplicate_ids:
            candidate["blockers"].append("multiple_proposals_for_skill")
            candidate["decision"] = "needs_review"
        if validate and candidate["decision"] == "auto_import":
            try:
                validate_skill_values(
                    candidate["values"],
                    instance=target_by_source.get((SOURCE_PROJECT, candidate["sourceId"])),
                )
            except ApiError as error:
                candidate["blockers"].append(f"target_validation:{error.code}:{error.field or ''}")
                candidate["decision"] = "needs_review"
    candidates_by_source_id = {candidate["sourceId"]: candidate for candidate in candidates}
    for source_id in _prerequisite_cycle_ids(candidates):
        candidate = candidates_by_source_id[source_id]
        candidate["blockers"].append("prerequisite_cycle")
        candidate["decision"] = "needs_review"
    changed = True
    while changed:
        changed = False
        for candidate in candidates:
            if candidate["decision"] != "auto_import":
                continue
            blocked_prerequisites = [
                source_id
                for source_id in candidate["prerequisiteSourceIds"]
                if candidates_by_source_id[source_id]["decision"] != "auto_import"
            ]
            if blocked_prerequisites:
                candidate["blockers"].append("prerequisite_not_in_auto_import_queue")
                candidate["decision"] = "needs_review"
                changed = True
    decision_counts = Counter(candidate["decision"] for candidate in candidates)
    blocker_counts = Counter(
        blocker for candidate in candidates for blocker in candidate["blockers"]
    )
    summary = {
        "sourcePath": str(source_path.resolve()),
        "sourceSkillCount": len(first_rows),
        "candidateCount": len(candidates),
        "decisionCounts": dict(sorted(decision_counts.items())),
        "blockerCounts": dict(sorted(blocker_counts.items())),
        "spellCount": sum(1 for candidate in candidates if candidate["values"].get("spell")),
        "characterOwnershipsImported": 0,
        "orderChaosMechanicsImported": 0,
    }
    return ImportRun(candidates=candidates, summary=summary)


@transaction.atomic
def apply_import_run(run: ImportRun) -> dict[str, int]:
    suspended_source_ids = [
        candidate["sourceId"]
        for candidate in run.candidates
        if candidate["decision"] != "auto_import"
    ]
    suspended = Skill.objects.filter(
        archived_at__isnull=True,
        metadata__sourceProject=SOURCE_PROJECT,
        metadata__sourceId__in=suspended_source_ids,
    ).update(archived_at=timezone.now())
    poc_archived = Skill.objects.filter(
        nome__startswith="POC -",
        archived_at__isnull=True,
    ).update(archived_at=timezone.now())
    imported_by_source_id: dict[int, Skill] = {}
    unchanged = 0
    for candidate in run.candidates:
        if candidate["decision"] != "auto_import":
            continue
        values = {**candidate["values"], "prerequisiteIds": []}
        metadata = values["metadata"]
        existing = Skill.objects.filter(
            archived_at__isnull=True,
            metadata__sourceProject=metadata["sourceProject"],
            metadata__sourceId=metadata["sourceId"],
            metadata__sourceHash=metadata["sourceHash"],
            metadata__converterVersion=metadata["converterVersion"],
        ).first()
        if existing:
            imported_by_source_id[candidate["sourceId"]] = existing
            unchanged += 1
        else:
            imported_by_source_id[candidate["sourceId"]] = upsert_imported_skill(values)
    for candidate in run.candidates:
        skill = imported_by_source_id.get(candidate["sourceId"])
        if skill is None:
            continue
        prerequisite_ids = [
            imported_by_source_id[source_id].id
            for source_id in candidate["prerequisiteSourceIds"]
            if source_id in imported_by_source_id
        ]
        skill.prerequisiti.set(prerequisite_ids)
    return {
        "imported": len(imported_by_source_id),
        "skippedForReview": sum(
            1 for candidate in run.candidates if candidate["decision"] != "auto_import"
        ),
        "characterOwnershipsImported": 0,
        "pocSkillsArchived": poc_archived,
        "reviewSkillsSuspended": suspended,
        "unchanged": unchanged,
    }


@transaction.atomic
def validate_import_write_path(run: ImportRun) -> dict[str, int]:
    result = apply_import_run(run)
    repeated_run = build_import_run(Path(run.summary["sourcePath"]))
    repeated_result = apply_import_run(repeated_run)
    if repeated_result["unchanged"] != result["imported"]:
        raise RuntimeError("La seconda esecuzione non è idempotente.")
    result["idempotentUnchanged"] = repeated_result["unchanged"]
    transaction.set_rollback(True)
    return result


def write_import_artifacts(run: ImportRun, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    artifacts = {
        "summary.json": run.summary,
        "all_candidates.json": run.candidates,
        "auto_import.json": [candidate for candidate in run.candidates if candidate["decision"] == "auto_import"],
        "needs_review.json": [candidate for candidate in run.candidates if candidate["decision"] == "needs_review"],
        "admin_required.json": [candidate for candidate in run.candidates if candidate["decision"] == "admin_required"],
    }
    for filename, payload in artifacts.items():
        path = output_dir / filename
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        paths.append(path)
    return paths
