from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from backend.characters.models import PERSONAGGIO_TOT_KEYS
from backend.characters.services.refresh_personaggio import (
    CHARACTERISTIC_MODIFIER_KEYS,
    DEFAULT_PROFILE_NAME,
    extract_formula_map,
    extract_quick_stat_adjustment,
)

from .defaults import (
    CHARACTERISTIC_ADJUSTMENT_DEFAULTS,
    FORMULE_BASE_FORMULAS,
    FORMULE_BASE_VALUE_FLOAT,
    QUICK_STAT_ADJUSTMENT_DEFAULTS,
    QUICK_STAT_ADJUSTMENT_TARGET_CHOICES,
    SKILL_PRICING_CONFIG_KEY,
    SKILL_PRICING_DEFAULTS,
)
from .guides_it import CHARACTER_VARIABLE_GROUPS
from .models import GlobalModifiers


PROFILE_NOTES_FIELD_ID = "profile.rule_notes"
QUICK_FIELD_IDS = {
    "fatigue_percent_per_point": "quick.fatigue_percent_per_point",
    "fatigue_fixed_per_point": "quick.fatigue_fixed_per_point",
    "general_modifier_percent_per_point": "quick.general_modifier_percent_per_point",
    "general_modifier_fixed_per_point": "quick.general_modifier_fixed_per_point",
    "targets": "quick.targets",
}
SKILL_FIELD_IDS = {key: f"skill.{key}" for key in SKILL_PRICING_DEFAULTS}
ADJUSTMENT_FIELD_IDS = {
    key: f"adjustment.{key}"
    for key in CHARACTERISTIC_ADJUSTMENT_DEFAULTS
}

# These values are always recalculated by the engine, so a base value would be ignored.
NON_EDITABLE_BASE_KEYS = CHARACTERISTIC_MODIFIER_KEYS | {"malus_carico"}

NON_NEGATIVE_BASE_KEYS = {
    "pf", "mana", "energia", "potere", "pa", "attacco", "difesa",
    "rd_fis", "rd_fuoco", "rd_gelo", "rd_elettro", "ap", "ap_percento",
    "slot_magici", "slot_non_magici", "monete_per_slot", "tier",
    "en_per_mana", "pa_per_mana", "ogni_en_x_mana", "ogni_pa_x_mana",
    "sconto_mana_per_potere", "sconto_pa_per_potere", "mod_carico",
    "mod_peso_equip", "orecchini_max", "anelli_max", "sacchi_max",
    "moltiplicatore_reagenti_livello_1", "moltiplicatore_reagenti_livello_2",
    "moltiplicatore_reagenti_livello_3", "moltiplicatore_reagenti_livello_4",
}


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    ascii_value = "".join(
        character for character in normalized
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")


def _display_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


def _profile_values(
    profile: GlobalModifiers | None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    floats = dict(FORMULE_BASE_VALUE_FLOAT)
    strings: dict[str, Any] = {}
    notes = ""
    if profile is not None:
        if isinstance(profile.value_float, dict):
            floats.update(profile.value_float)
        if isinstance(profile.value_string, dict):
            strings.update(profile.value_string)
        notes = profile.rule_notes
    return floats, strings, notes


def get_game_variable_profile() -> GlobalModifiers | None:
    return GlobalModifiers.objects.filter(
        name=DEFAULT_PROFILE_NAME,
        archived_at__isnull=True,
    ).first()


def game_variable_revision(profile: GlobalModifiers | None) -> str:
    return profile.updated_at.isoformat() if profile and profile.updated_at else ""


def editable_formula_targets(strings: Mapping[str, Any]) -> list[str]:
    formulas = extract_formula_map(strings)
    ordered = list(FORMULE_BASE_FORMULAS)
    ordered.extend(
        key
        for key in formulas
        if key not in ordered and key in PERSONAGGIO_TOT_KEYS
    )
    return ordered


def game_variable_field_map(
    profile: GlobalModifiers | None = None,
) -> dict[str, dict[str, Any]]:
    floats, strings, notes = _profile_values(profile)
    current_formulas = extract_formula_map(strings)
    quick = extract_quick_stat_adjustment(strings)
    configured_pricing = strings.get(SKILL_PRICING_CONFIG_KEY, {})
    if not isinstance(configured_pricing, Mapping):
        configured_pricing = {}

    guide_entries = {
        key: {
            "group": group_label,
            "label": label,
            "description": description,
        }
        for group_label, entries in CHARACTER_VARIABLE_GROUPS
        for key, label, description in entries
    }
    formula_dependencies: dict[str, list[str]] = {
        key: [] for key in PERSONAGGIO_TOT_KEYS
    }
    for result_key, formula in current_formulas.items():
        for source_key in PERSONAGGIO_TOT_KEYS:
            if re.search(
                rf"\b(?:base|pre|final)\.{re.escape(source_key)}\b",
                str(formula),
            ):
                formula_dependencies.setdefault(source_key, []).append(result_key)

    fields: dict[str, dict[str, Any]] = {}
    for key in FORMULE_BASE_VALUE_FLOAT:
        if key in NON_EDITABLE_BASE_KEYS:
            continue
        guide = guide_entries.get(key, {})
        value = floats.get(key, 0)
        default = FORMULE_BASE_VALUE_FLOAT.get(key, 0)
        dependencies = formula_dependencies.get(key, [])
        influence = (
            "È richiamata dalle formule di: "
            + ", ".join(
                guide_entries.get(item, {}).get("label", item)
                for item in dependencies
            )
            + "."
            if dependencies
            else (
                "È il valore iniziale usato dal motore prima di oggetti, "
                "effetti e regole derivate."
            )
        )
        step = (
            1
            if isinstance(default, int) and not isinstance(default, bool)
            else 0.1
        )
        fields[f"base.{key}"] = {
            "id": f"base.{key}",
            "key": key,
            "label": guide.get("label", key.replace("_", " ").capitalize()),
            "section": "base",
            "group": guide.get("group", "Altre variabili"),
            "valueType": "integer" if step == 1 else "number",
            "value": value,
            "defaultValue": default,
            "constraints": {
                "minimum": 0 if key in NON_NEGATIVE_BASE_KEYS else -1_000_000,
                "maximum": 1_000_000,
                "step": step,
            },
            "choices": [],
            "guide": {
                "summary": guide.get(
                    "description",
                    "Valore tecnico iniziale del profilo globale.",
                ),
                "influence": influence,
                "currentRule": f"Valore base attuale: {_display_number(value)}.",
                "technicalKey": f"base.{key}",
            },
        }

    for key in editable_formula_targets(strings):
        guide = guide_entries.get(key, {})
        formula = current_formulas.get(
            key,
            FORMULE_BASE_FORMULAS.get(key, ""),
        )
        fields[f"formula.{key}"] = {
            "id": f"formula.{key}",
            "key": key,
            "label": f"Formula {guide.get('label', key.replace('_', ' '))}",
            "section": "formulas",
            "group": "Formule delle statistiche",
            "valueType": "formula",
            "value": formula,
            "defaultValue": FORMULE_BASE_FORMULAS.get(key, ""),
            "constraints": {"maximumLength": 500},
            "choices": [],
            "guide": {
                "summary": (
                    f"Calcola {guide.get('label', key)} dopo caratteristiche "
                    "ed effetti. Se resta vuota, viene usato direttamente il valore base."
                ),
                "influence": guide.get(
                    "description",
                    "Determina il valore finale della statistica.",
                ),
                "currentRule": (
                    f"Formula attuale: {formula or 'nessuna formula; usa il valore base'}."
                ),
                "technicalKey": f"formulas.{key}",
            },
        }

    adjustment_fields = {
        "livello": (
            "Contributo del livello alle caratteristiche",
            "Calcolato una volta e aggiunto a tutte le caratteristiche, compresa Fortuna.",
        ),
        "fortuna": (
            "Contributo di Fortuna alle caratteristiche",
            "Calcolato dopo il contributo del livello e aggiunto a tutte le caratteristiche tranne Fortuna.",
        ),
    }
    for key, (label, influence) in adjustment_fields.items():
        field_id = ADJUSTMENT_FIELD_IDS[key]
        formula = strings.get(field_id, CHARACTERISTIC_ADJUSTMENT_DEFAULTS[key])
        fields[field_id] = {
            "id": field_id,
            "key": key,
            "label": label,
            "section": "rules",
            "group": "Progressione delle caratteristiche",
            "valueType": "formula",
            "value": str(formula),
            "defaultValue": CHARACTERISTIC_ADJUSTMENT_DEFAULTS[key],
            "constraints": {"maximumLength": 500},
            "choices": [],
            "guide": {
                "summary": influence,
                "influence": influence,
                "currentRule": f"Formula attuale: {formula or 'nessuna; non applicata'}.",
                "technicalKey": field_id,
            },
        }

    quick_labels = {
        "fatigue_percent_per_point": "Malus Stanchezza per punto",
        "fatigue_fixed_per_point": "Malus fisso per Stanchezza",
        "general_modifier_percent_per_point": (
            "Bonus Modificatore generale per punto"
        ),
        "general_modifier_fixed_per_point": (
            "Bonus fisso per Modificatore generale"
        ),
    }
    quick_summaries = {
        "fatigue_percent_per_point": (
            "Percentuale sottratta per ogni punto di Stanchezza."
        ),
        "fatigue_fixed_per_point": (
            "Valore fisso sottratto dopo la percentuale per ogni punto di Stanchezza."
        ),
        "general_modifier_percent_per_point": (
            "Percentuale aggiunta per ogni punto di Modificatore generale."
        ),
        "general_modifier_fixed_per_point": (
            "Valore fisso aggiunto dopo la percentuale per ogni punto di Modificatore generale."
        ),
    }
    for key in (
        "fatigue_percent_per_point",
        "fatigue_fixed_per_point",
        "general_modifier_percent_per_point",
        "general_modifier_fixed_per_point",
    ):
        value = quick[key]
        field_id = QUICK_FIELD_IDS[key]
        is_fatigue = key.startswith("fatigue_")
        is_percent = "_percent_" in key
        sign = "−" if is_fatigue else "+"
        unit = "%" if is_percent else " punti"
        fields[field_id] = {
            "id": field_id,
            "key": key,
            "label": quick_labels[key],
            "section": "rules",
            "group": "Stanchezza e modificatore generale",
            "valueType": "number",
            "value": value,
            "defaultValue": QUICK_STAT_ADJUSTMENT_DEFAULTS[key],
            "constraints": {
                "minimum": 0,
                "maximum": 100 if is_percent else 1_000_000,
                "step": 0.1,
                "suffix": "%" if is_percent else "",
            },
            "choices": [],
            "guide": {
                "summary": quick_summaries[key],
                "influence": (
                    "Agisce su tutte le statistiche selezionate nel campo "
                    "«Statistiche influenzate»."
                ),
                "currentRule": (
                    f"Impatto attuale: {sign}{_display_number(value)}{unit} per punto."
                ),
                "technicalKey": f"quick_stat_adjustments.{key}",
            },
        }

    target_choices = [
        {"value": key, "label": label}
        for key, label in QUICK_STAT_ADJUSTMENT_TARGET_CHOICES
    ]
    fields[QUICK_FIELD_IDS["targets"]] = {
        "id": QUICK_FIELD_IDS["targets"],
        "key": "targets",
        "label": "Statistiche influenzate",
        "section": "rules",
        "group": "Stanchezza e modificatore generale",
        "valueType": "multi_select",
        "value": sorted(quick["targets"]),
        "defaultValue": list(QUICK_STAT_ADJUSTMENT_DEFAULTS["targets"]),
        "constraints": {},
        "choices": target_choices,
        "guide": {
            "summary": (
                "Sceglie quali risultati finali ricevono il malus di Stanchezza "
                "e il bonus del Modificatore generale."
            ),
            "influence": (
                "Le statistiche non selezionate ignorano entrambe le percentuali."
            ),
            "currentRule": (
                f"{len(quick['targets'])} statistiche attualmente influenzate."
            ),
            "technicalKey": "quick_stat_adjustments.targets",
        },
    }

    pricing_fields = {
        "modifier_base": (
            "Divisore base del rincaro",
            "Valore iniziale del divisore che aumenta il costo della Skill.",
        ),
        "modifier_max": (
            "Divisore massimo del rincaro",
            "Limite superiore del divisore, usato per contenere la crescita del prezzo.",
        ),
        "scaling_factor": (
            "Fattore livello",
            "Peso con cui il livello del personaggio aumenta il prezzo calcolato.",
        ),
        "scaling_divisor": (
            "Divisore livello",
            "Riduce o amplifica l'incidenza del livello sul prezzo finale.",
        ),
        "spent_xp_discount_cap": (
            "PE spesi per azzerare il rincaro",
            "Soglia oltre la quale resta soltanto il costo base della Skill.",
        ),
    }
    for key, (label, summary) in pricing_fields.items():
        value = configured_pricing.get(key, SKILL_PRICING_DEFAULTS[key])
        minimum = 0 if key == "scaling_factor" else 0.01
        fields[SKILL_FIELD_IDS[key]] = {
            "id": SKILL_FIELD_IDS[key],
            "key": key,
            "label": label,
            "section": "rules",
            "group": "Prezzo dinamico delle Skill",
            "valueType": "number",
            "value": value,
            "defaultValue": SKILL_PRICING_DEFAULTS[key],
            "constraints": {
                "minimum": minimum,
                "maximum": 100_000,
                "step": 0.01,
            },
            "choices": [],
            "guide": {
                "summary": summary,
                "influence": (
                    "Cambia il prezzo mostrato e verificato durante lo sblocco "
                    "delle Skill."
                ),
                "currentRule": f"Valore attuale: {_display_number(value)}.",
                "technicalKey": f"{SKILL_PRICING_CONFIG_KEY}.{key}",
            },
        }

    fields[PROFILE_NOTES_FIELD_ID] = {
        "id": PROFILE_NOTES_FIELD_ID,
        "key": "rule_notes",
        "label": "Note sulle regole",
        "section": "notes",
        "group": "Documentazione del profilo",
        "valueType": "text",
        "value": notes,
        "defaultValue": "",
        "constraints": {"maximumLength": 4000},
        "choices": [],
        "guide": {
            "summary": (
                "Annotazioni amministrative che spiegano provenienza, "
                "decisioni e limiti del profilo."
            ),
            "influence": (
                "Non modifica direttamente i calcoli, ma conserva il contesto "
                "delle modifiche importanti."
            ),
            "currentRule": (
                "Visibile agli amministratori che gestiscono il profilo."
            ),
            "technicalKey": "GlobalModifiers.rule_notes",
        },
    }
    return fields


def _ordered_groups(
    fields: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    used: set[str] = set()
    group_order = [
        *(group_label for group_label, _entries in CHARACTER_VARIABLE_GROUPS),
        "Altre variabili",
        "Formule delle statistiche",
        "Stanchezza e modificatore generale",
        "Prezzo dinamico delle Skill",
        "Progressione delle caratteristiche",
        "Documentazione del profilo",
    ]
    for label in group_order:
        entries = [
            field for field in fields.values()
            if field["group"] == label
        ]
        if not entries:
            continue
        used.add(label)
        groups.append({
            "id": _slug(label),
            "label": label,
            "section": entries[0]["section"],
            "fields": entries,
        })
    for label in sorted({field["group"] for field in fields.values()} - used):
        entries = [
            field for field in fields.values()
            if field["group"] == label
        ]
        groups.append({
            "id": _slug(label),
            "label": label,
            "section": entries[0]["section"],
            "fields": entries,
        })
    return groups


def game_variables_payload(
    profile: GlobalModifiers | None = None,
) -> dict[str, Any]:
    profile = profile if profile is not None else get_game_variable_profile()
    fields = game_variable_field_map(profile)
    groups = _ordered_groups(fields)
    return {
        "profile": {
            "name": DEFAULT_PROFILE_NAME,
            "revision": game_variable_revision(profile),
            "updatedAt": (
                profile.updated_at.isoformat()
                if profile and profile.updated_at
                else None
            ),
        },
        "sections": [
            {"id": "all", "label": "Tutte"},
            {"id": "base", "label": "Valori base"},
            {"id": "formulas", "label": "Formule"},
            {"id": "rules", "label": "Regole globali"},
            {"id": "notes", "label": "Note"},
        ],
        "groups": groups,
        "summary": {
            "fieldCount": len(fields),
            "baseCount": sum(
                field["section"] == "base" for field in fields.values()
            ),
            "formulaCount": sum(
                field["section"] == "formulas" for field in fields.values()
            ),
            "ruleCount": sum(
                field["section"] == "rules" for field in fields.values()
            ),
        },
        "calculationOrder": [
            "Valori base",
            "Formule ed effetti",
            "Carico e specializzazioni",
            "Stanchezza e Modificatore generale",
            "Arrotondamenti finali",
        ],
    }
