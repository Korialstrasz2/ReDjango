from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core import signing
from django.db import transaction

from backend.characters.models import PERSONAGGIO_TOT_KEYS, Personaggio
from backend.characters.services.refresh_personaggio import (
    CHARACTERISTICS,
    DERIVED_STAT_ORDER,
    PRE_FORMULA_BASE_STATS,
    CalculationExpressionError,
    build_base_values,
    build_pre_snapshot,
    calculate_characteristic_modifiers,
    apply_characteristic_adjustments,
    evaluate_number,
    normalize_number,
    refresh_personaggio,
)

from .api import ApiError
from .defaults import (
    FORMULE_BASE_FORMULAS,
    FORMULE_BASE_VALUE_FLOAT,
    QUICK_STAT_ADJUSTMENT_CONFIG_KEY,
    QUICK_STAT_ADJUSTMENT_TARGET_CHOICES,
    SKILL_PRICING_CONFIG_KEY,
    CHARACTERISTIC_ADJUSTMENT_DEFAULTS,
)
from .game_variable_selectors import (
    NON_EDITABLE_BASE_KEYS,
    PROFILE_NOTES_FIELD_ID,
    ADJUSTMENT_FIELD_IDS,
    QUICK_FIELD_IDS,
    SKILL_FIELD_IDS,
    editable_formula_targets,
    game_variable_field_map,
    game_variable_revision,
    game_variables_payload,
    get_game_variable_profile,
)
from .models import Giocatore, GlobalModifiers
from .security import effective_role, has_minimum_role


VARIABLE_PREVIEW_SALT = "redjango.game-variables.preview.v1"
VARIABLE_PREVIEW_MAX_AGE_SECONDS = 15 * 60
ALLOWED_QUICK_TARGETS = {
    key for key, _label in QUICK_STAT_ADJUSTMENT_TARGET_CHOICES
}


def require_game_variable_admin(user, giocatore: Giocatore) -> None:
    if not has_minimum_role(
        effective_role(user, giocatore),
        Giocatore.ROLE_ADMIN,
    ):
        raise ApiError(
            "management.variables.forbidden",
            "Solo gli amministratori possono gestire le variabili globali di gioco.",
            status=403,
        )


def _decimal_number(raw: Any, field_id: str, label: str) -> int | float:
    if isinstance(raw, bool) or raw in (None, ""):
        raise ApiError(
            "management.variables.number_required",
            f"{label}: inserisci un numero.",
            field_id,
        )
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ApiError(
            "management.variables.number_required",
            f"{label}: inserisci un numero valido.",
            field_id,
        ) from exc
    if not value.is_finite():
        raise ApiError(
            "management.variables.number_required",
            f"{label}: il numero deve essere finito.",
            field_id,
        )
    return int(value) if value == value.to_integral_value() else float(value)


def _validate_number(
    raw: Any,
    field: Mapping[str, Any],
) -> int | float:
    field_id = str(field["id"])
    value = _decimal_number(raw, field_id, str(field["label"]))
    constraints = field.get("constraints", {})
    minimum = constraints.get("minimum") if isinstance(
        constraints,
        Mapping,
    ) else None
    maximum = constraints.get("maximum") if isinstance(
        constraints,
        Mapping,
    ) else None
    if minimum is not None and value < minimum:
        raise ApiError(
            "management.variables.below_minimum",
            f"{field['label']}: il valore minimo è {minimum}.",
            field_id,
        )
    if maximum is not None and value > maximum:
        raise ApiError(
            "management.variables.above_maximum",
            f"{field['label']}: il valore massimo è {maximum}.",
            field_id,
        )
    if (
        field.get("valueType") == "integer"
        and not float(value).is_integer()
    ):
        raise ApiError(
            "management.variables.integer_required",
            f"{field['label']}: inserisci un numero intero.",
            field_id,
        )
    return int(value) if field.get("valueType") == "integer" else value


def _dummy_personaggio_context() -> dict[str, int]:
    return {
        "id": 1,
        "pk": 1,
        "livello": 1,
        "eta": 20,
        "monete": 0,
        "danno": 0,
        "mana_speso": 0,
        "energia_spesa": 0,
        "potere_speso": 0,
        "stanchezza_accumulata": 0,
        "mana_in_sifone": 0,
        "pe_generali": 0,
        "pe_rossi": 0,
        "pe_verdi": 0,
        "pe_blu": 0,
        "pe_abilita": 0,
    }


def _validate_formula_pipeline(
    base_values: Mapping[str, Any],
    formulas: Mapping[str, str],
    adjustment_formulas: Mapping[str, str],
) -> None:
    base = build_base_values(base_values)
    pre = build_pre_snapshot(base)
    final: dict[str, Any] = {
        key: base.get(key, 0)
        for key in CHARACTERISTICS
    }
    try:
        apply_characteristic_adjustments(
            final,
            base=base,
            pre=pre,
            personaggio_context=_dummy_personaggio_context(),
            value_string={f"adjustment.{key}": value for key, value in adjustment_formulas.items()},
        )
    except (CalculationExpressionError, SyntaxError, TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
        raise ApiError(
            "management.variables.formula_invalid",
            f"Formula contributo caratteristiche: {exc}",
            "adjustment.livello",
        ) from exc

    final.update(calculate_characteristic_modifiers(final))
    for key in PRE_FORMULA_BASE_STATS:
        final[key] = base.get(key, 0)

    for target in DERIVED_STAT_ORDER:
        formula = formulas.get(target)
        if not formula:
            final[target] = base.get(target, 0)
            continue
        contexts = {
            "base": base,
            "pre": pre,
            "final": final,
            "personaggio": _dummy_personaggio_context(),
        }
        try:
            value = evaluate_number(formula, contexts)
        except (
            CalculationExpressionError,
            SyntaxError,
            TypeError,
            ValueError,
            ZeroDivisionError,
            OverflowError,
        ) as exc:
            raise ApiError(
                "management.variables.formula_invalid",
                f"Formula {target}: {exc}",
                f"formula.{target}",
            ) from exc
        if not math.isfinite(value):
            raise ApiError(
                "management.variables.formula_invalid",
                (
                    f"Formula {target}: il risultato di prova "
                    "non è un numero finito."
                ),
                f"formula.{target}",
            )
        final[target] = normalize_number(value)


def _current_profile_data(
    profile: GlobalModifiers | None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    value_float = dict(FORMULE_BASE_VALUE_FLOAT)
    value_string: dict[str, Any] = {}
    notes = ""
    if profile is not None:
        if isinstance(profile.value_float, dict):
            value_float.update(profile.value_float)
        if isinstance(profile.value_string, dict):
            value_string.update(profile.value_string)
        notes = profile.rule_notes
    return value_float, value_string, notes


def _normalized_submission(
    submitted: Any,
    profile: GlobalModifiers | None,
) -> dict[str, Any]:
    if not isinstance(submitted, Mapping):
        raise ApiError(
            "management.variables.invalid_payload",
            "Le variabili devono essere inviate come un oggetto.",
            "values",
        )
    fields = game_variable_field_map(profile)
    unknown = sorted(set(submitted) - set(fields))
    if unknown:
        raise ApiError(
            "management.variables.unknown",
            f"Variabile sconosciuta: {unknown[0]}.",
            unknown[0],
        )

    normalized: dict[str, Any] = {}
    for field_id, raw in submitted.items():
        field = fields[field_id]
        value_type = field["valueType"]
        if value_type in {"number", "integer"}:
            normalized[field_id] = _validate_number(raw, field)
        elif value_type == "formula":
            value = str(raw or "").strip()
            if len(value) > 500:
                raise ApiError(
                    "management.variables.formula_too_long",
                    (
                        f"{field['label']}: la formula può contenere "
                        "al massimo 500 caratteri."
                    ),
                    field_id,
                )
            normalized[field_id] = value
        elif value_type == "multi_select":
            if not isinstance(raw, list):
                raise ApiError(
                    "management.variables.selection_required",
                    f"{field['label']}: la selezione non è valida.",
                    field_id,
                )
            values = list(dict.fromkeys(str(value) for value in raw))
            invalid = [
                value for value in values
                if value not in ALLOWED_QUICK_TARGETS
            ]
            if invalid:
                raise ApiError(
                    "management.variables.selection_invalid",
                    (
                        f"{field['label']}: {invalid[0]} "
                        "non è una statistica valida."
                    ),
                    field_id,
                )
            normalized[field_id] = sorted(values)
        elif value_type == "text":
            value = str(raw or "").strip()
            if len(value) > 4000:
                raise ApiError(
                    "management.variables.text_too_long",
                    (
                        f"{field['label']}: il testo può contenere "
                        "al massimo 4000 caratteri."
                    ),
                    field_id,
                )
            normalized[field_id] = value
        else:
            raise ApiError(
                "management.variables.type_unsupported",
                f"{field['label']}: tipo di dato non supportato.",
                field_id,
            )
    return normalized


def _prepared_profile(
    normalized: Mapping[str, Any],
    profile: GlobalModifiers | None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    value_float, value_string, notes = _current_profile_data(profile)
    stored_formulas = value_string.get("formulas", {})
    formulas = {
        **FORMULE_BASE_FORMULAS,
        **{
            key: value
            for key, value in (
                stored_formulas.items()
                if isinstance(stored_formulas, Mapping)
                else []
            )
            if key in PERSONAGGIO_TOT_KEYS
        },
    }
    for field_id, value in normalized.items():
        if field_id.startswith("base."):
            key = field_id.removeprefix("base.")
            if (
                key not in FORMULE_BASE_VALUE_FLOAT
                or key in NON_EDITABLE_BASE_KEYS
            ):
                raise ApiError(
                    "management.variables.base_not_editable",
                    f"Il valore base {key} non è modificabile.",
                    field_id,
                )
            value_float[key] = value
        elif field_id.startswith("formula."):
            key = field_id.removeprefix("formula.")
            if key not in editable_formula_targets(value_string):
                raise ApiError(
                    "management.variables.formula_not_editable",
                    (
                        f"La formula {key} non è modificabile "
                        "da questa pagina."
                    ),
                    field_id,
                )
            if value:
                formulas[key] = str(value)
            else:
                formulas.pop(key, None)
        elif field_id == PROFILE_NOTES_FIELD_ID:
            notes = str(value)

    adjustment_formulas = {
        key: str(value_string.get(f"adjustment.{key}", CHARACTERISTIC_ADJUSTMENT_DEFAULTS[key]))
        for key in CHARACTERISTIC_ADJUSTMENT_DEFAULTS
    }
    for key, field_id in ADJUSTMENT_FIELD_IDS.items():
        if field_id in normalized:
            adjustment_formulas[key] = str(normalized[field_id])
        value_string[field_id] = adjustment_formulas[key]

    stored_quick = value_string.get(
        QUICK_STAT_ADJUSTMENT_CONFIG_KEY,
        {},
    )
    quick = dict(stored_quick) if isinstance(stored_quick, Mapping) else {}
    for key, field_id in QUICK_FIELD_IDS.items():
        if field_id in normalized:
            quick[key] = normalized[field_id]
    if quick:
        value_string[QUICK_STAT_ADJUSTMENT_CONFIG_KEY] = quick

    stored_pricing = value_string.get(SKILL_PRICING_CONFIG_KEY, {})
    pricing = (
        dict(stored_pricing)
        if isinstance(stored_pricing, Mapping)
        else {}
    )
    for key, field_id in SKILL_FIELD_IDS.items():
        if field_id in normalized:
            pricing[key] = normalized[field_id]
    if pricing:
        modifier_base = float(pricing.get("modifier_base", 0) or 0)
        modifier_max = float(pricing.get("modifier_max", 0) or 0)
        if modifier_max < modifier_base:
            raise ApiError(
                "management.variables.skill_modifier_order",
                (
                    "Il divisore massimo del rincaro non può essere "
                    "inferiore al divisore base."
                ),
                SKILL_FIELD_IDS["modifier_max"],
            )
        value_string[SKILL_PRICING_CONFIG_KEY] = pricing

    value_string["formulas"] = formulas
    _validate_formula_pipeline(value_float, formulas, adjustment_formulas)
    return value_float, value_string, notes


def _display_value(value: Any) -> str:
    if isinstance(value, list):
        labels = dict(QUICK_STAT_ADJUSTMENT_TARGET_CHOICES)
        return ", ".join(
            labels.get(item, item) for item in value
        ) or "Nessuna"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value) if value not in (None, "") else "Vuoto"


def _digest(normalized: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_game_variables(
    user,
    giocatore: Giocatore,
    submitted: Any,
) -> dict[str, Any]:
    require_game_variable_admin(user, giocatore)
    profile = get_game_variable_profile()
    fields = game_variable_field_map(profile)
    normalized = _normalized_submission(submitted, profile)
    _prepared_profile(normalized, profile)
    changes = []
    for field_id, after in normalized.items():
        before = fields[field_id]["value"]
        if before == after:
            continue
        changes.append({
            "fieldId": field_id,
            "label": fields[field_id]["label"],
            "before": _display_value(before),
            "after": _display_value(after),
            "section": fields[field_id]["section"],
        })
    warnings = []
    if normalized.get(QUICK_FIELD_IDS["targets"]) == []:
        warnings.append(
            "Nessuna statistica riceverà l'effetto di "
            "Stanchezza o Modificatore generale."
        )
    token = signing.dumps(
        {
            "revision": game_variable_revision(profile),
            "digest": _digest(normalized),
        },
        salt=VARIABLE_PREVIEW_SALT,
        compress=True,
    )
    return {
        "valid": True,
        "previewToken": token,
        "changedCount": len(changes),
        "changes": changes,
        "warnings": warnings,
        "message": (
            f"Validazione completata: {len(changes)} modifiche pronte."
            if changes
            else "Validazione completata: nessuna modifica rilevata."
        ),
    }


@transaction.atomic
def save_game_variables(
    user,
    giocatore: Giocatore,
    submitted: Any,
    preview_token: Any,
) -> dict[str, Any]:
    require_game_variable_admin(user, giocatore)
    if not preview_token:
        raise ApiError(
            "management.variables.validation_required",
            "Valida le modifiche prima di salvarle.",
            "previewToken",
        )
    try:
        preview = signing.loads(
            str(preview_token),
            salt=VARIABLE_PREVIEW_SALT,
            max_age=VARIABLE_PREVIEW_MAX_AGE_SECONDS,
        )
    except signing.SignatureExpired as exc:
        raise ApiError(
            "management.variables.validation_expired",
            (
                "La validazione è scaduta. "
                "Controlla nuovamente le modifiche."
            ),
            "previewToken",
            409,
        ) from exc
    except signing.BadSignature as exc:
        raise ApiError(
            "management.variables.validation_invalid",
            "La validazione non è valida. Ripeti il controllo.",
            "previewToken",
            409,
        ) from exc

    profile = GlobalModifiers.objects.select_for_update().filter(
        name="Formule_base",
        archived_at__isnull=True,
    ).first()
    normalized = _normalized_submission(submitted, profile)
    if (
        not isinstance(preview, Mapping)
        or preview.get("digest") != _digest(normalized)
    ):
        raise ApiError(
            "management.variables.changed_after_validation",
            (
                "I valori sono cambiati dopo la validazione. "
                "Controllali di nuovo."
            ),
            "previewToken",
            409,
        )
    if preview.get("revision", "") != game_variable_revision(profile):
        raise ApiError(
            "management.variables.stale",
            (
                "Il profilo è stato aggiornato da un'altra operazione. "
                "Ricarica e valida nuovamente."
            ),
            "previewToken",
            409,
        )

    value_float, value_string, notes = _prepared_profile(
        normalized,
        profile,
    )
    if profile is None:
        profile = GlobalModifiers(name="Formule_base")
    profile.value_float = value_float
    profile.value_string = value_string
    profile.rule_notes = notes
    profile.save()
    # A global-rule change must be visible immediately on every existing sheet.
    for character_id in Personaggio.objects.values_list("pk", flat=True):
        refresh_personaggio(character_id)
    return game_variables_payload(profile)
