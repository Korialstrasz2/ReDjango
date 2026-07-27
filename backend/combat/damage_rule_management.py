from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core import signing
from django.db import transaction

from backend.core.api import ApiError
from backend.core.game_variable_selectors import (
    game_variable_revision,
    get_game_variable_profile,
)
from backend.core.game_variable_services import require_game_variable_admin
from backend.core.models import GlobalModifiers

from .damage_rules import (
    ATTACK_DIFFERENCE_MAXIMUM,
    ATTACK_DIFFERENCE_MINIMUM,
    D20_MAXIMUM,
    D20_MINIMUM,
    DAMAGE_RULES_CONFIG_KEY,
    PROFILE_NAME,
    RESISTANCE_LEVEL_MAXIMUM,
    RESISTANCE_LEVEL_MINIMUM,
    TIER_MAXIMUM,
    TIER_MINIMUM,
    configured_damage_rules,
    default_damage_rules,
)


DAMAGE_RULES_PREVIEW_SALT = "redjango.damage-rules.preview.v1"
DAMAGE_RULES_PREVIEW_MAX_AGE_SECONDS = 15 * 60
DICE_FORMULA_PATTERN = re.compile(
    r"^\s*(?:\d{1,3}d\d{1,4}|\d{1,6})"
    r"(?:\s*[+-]\s*(?:\d{1,3}d\d{1,4}|\d{1,6}))*\s*$",
    re.IGNORECASE,
)


def damage_rules_payload(profile=None) -> dict[str, Any]:
    profile = profile if profile is not None else get_game_variable_profile()
    return {
        "profile": {
            "name": PROFILE_NAME,
            "revision": game_variable_revision(profile),
            "updatedAt": (
                profile.updated_at.isoformat()
                if profile and profile.updated_at
                else None
            ),
        },
        "rules": configured_damage_rules(profile),
        "defaults": default_damage_rules(),
        "counts": {
            "resistanceLevels": (
                RESISTANCE_LEVEL_MAXIMUM - RESISTANCE_LEVEL_MINIMUM + 1
            ),
            "damageTiers": TIER_MAXIMUM - TIER_MINIMUM + 1,
            "d20Rows": D20_MAXIMUM - D20_MINIMUM + 1,
            "attackDifferenceColumns": (
                ATTACK_DIFFERENCE_MAXIMUM
                - ATTACK_DIFFERENCE_MINIMUM
                + 1
            ),
        },
        "behaviour": {
            "resistanceOutsideRange": (
                "I livelli sotto -4 usano -4; i livelli sopra 9 usano 9."
            ),
            "tierOutsideRange": (
                "Un Tier senza formula non infligge danno automatico."
            ),
            "gridLookup": (
                "La riga è il d20 naturale; la colonna è la differenza "
                "Attacco − Difesa già limitata tra -25 e 45."
            ),
        },
    }


def _integer(
    raw: Any,
    *,
    field: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(raw, bool) or raw in (None, ""):
        raise ApiError(
            "management.damage_rules.integer_required",
            "Inserisci un numero intero.",
            field,
        )
    try:
        number = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ApiError(
            "management.damage_rules.integer_required",
            "Inserisci un numero intero valido.",
            field,
        ) from exc
    if not number.is_finite() or number != number.to_integral_value():
        raise ApiError(
            "management.damage_rules.integer_required",
            "Inserisci un numero intero finito.",
            field,
        )
    value = int(number)
    if value < minimum or value > maximum:
        raise ApiError(
            "management.damage_rules.out_of_range",
            f"Il valore deve essere compreso tra {minimum} e {maximum}.",
            field,
        )
    return value


def _validate_dice_formula(raw: Any, tier: int) -> str:
    formula = str(raw or "").strip().lower().replace(" ", "")
    field = f"tierDamageFormulas.{tier}"
    if not formula or not DICE_FORMULA_PATTERN.fullmatch(formula):
        raise ApiError(
            "management.damage_rules.formula_invalid",
            (
                f"Tier {tier}: usa una formula come 2d6, "
                "1d8+1d10 oppure 2d6+3."
            ),
            field,
        )
    for count, sides in re.findall(r"(\d{1,3})d(\d{1,4})", formula):
        if int(count) > 100 or not 2 <= int(sides) <= 1_000:
            raise ApiError(
                "management.damage_rules.formula_unsafe",
                (
                    f"Tier {tier}: ogni termine può tirare al massimo "
                    "100 dadi con 2–1000 facce."
                ),
                field,
            )
    return formula


def normalize_damage_rules(submitted: Any) -> dict[str, Any]:
    if not isinstance(submitted, Mapping):
        raise ApiError(
            "management.damage_rules.invalid_payload",
            "Le regole del danno devono essere un oggetto.",
            "rules",
        )

    resistance_source = submitted.get("resistancePercentages")
    tier_source = submitted.get("tierDamageFormulas")
    grid_source = submitted.get("damageMultipliers")
    if not isinstance(resistance_source, Mapping):
        raise ApiError(
            "management.damage_rules.resistances_required",
            "La tabella delle resistenze non è valida.",
            "resistancePercentages",
        )
    if not isinstance(tier_source, Mapping):
        raise ApiError(
            "management.damage_rules.tiers_required",
            "La tabella dei Tier non è valida.",
            "tierDamageFormulas",
        )
    if not isinstance(grid_source, Mapping):
        raise ApiError(
            "management.damage_rules.grid_required",
            "La griglia dei moltiplicatori non è valida.",
            "damageMultipliers",
        )

    expected_resistances = {
        str(level)
        for level in range(
            RESISTANCE_LEVEL_MINIMUM,
            RESISTANCE_LEVEL_MAXIMUM + 1,
        )
    }
    if set(map(str, resistance_source)) != expected_resistances:
        raise ApiError(
            "management.damage_rules.resistance_levels_incomplete",
            "La tabella deve contenere tutti i livelli da -4 a 9.",
            "resistancePercentages",
        )
    resistances = {
        level: _integer(
            resistance_source[level],
            field=f"resistancePercentages.{level}",
            minimum=-500,
            maximum=100,
        )
        for level in sorted(expected_resistances, key=int)
    }

    expected_tiers = {
        str(tier)
        for tier in range(TIER_MINIMUM, TIER_MAXIMUM + 1)
    }
    if set(map(str, tier_source)) != expected_tiers:
        raise ApiError(
            "management.damage_rules.tiers_incomplete",
            "La tabella deve contenere tutti i Tier da -5 a 30.",
            "tierDamageFormulas",
        )
    tiers = {
        tier: _validate_dice_formula(tier_source[tier], int(tier))
        for tier in sorted(expected_tiers, key=int)
    }

    expected_rolls = {
        str(roll)
        for roll in range(D20_MINIMUM, D20_MAXIMUM + 1)
    }
    if set(map(str, grid_source)) != expected_rolls:
        raise ApiError(
            "management.damage_rules.grid_rows_incomplete",
            "La griglia deve contenere tutte le righe d20 da 1 a 20.",
            "damageMultipliers",
        )
    column_count = (
        ATTACK_DIFFERENCE_MAXIMUM - ATTACK_DIFFERENCE_MINIMUM + 1
    )
    grid: dict[str, list[int]] = {}
    for roll in sorted(expected_rolls, key=int):
        row = grid_source[roll]
        if not isinstance(row, list) or len(row) != column_count:
            raise ApiError(
                "management.damage_rules.grid_columns_incomplete",
                (
                    f"La riga d20 {roll} deve contenere "
                    f"{column_count} colonne."
                ),
                f"damageMultipliers.{roll}",
            )
        grid[roll] = [
            _integer(
                value,
                field=(
                    f"damageMultipliers.{roll}."
                    f"{ATTACK_DIFFERENCE_MINIMUM + index}"
                ),
                minimum=0,
                maximum=1_000,
            )
            for index, value in enumerate(row)
        ]

    return {
        "version": 1,
        "bounds": default_damage_rules()["bounds"],
        "resistancePercentages": resistances,
        "tierDamageFormulas": tiers,
        "damageMultipliers": grid,
    }


def _digest(rules: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        rules,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _change_counts(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, int]:
    resistances = sum(
        before["resistancePercentages"].get(key)
        != after["resistancePercentages"].get(key)
        for key in after["resistancePercentages"]
    )
    tiers = sum(
        before["tierDamageFormulas"].get(key)
        != after["tierDamageFormulas"].get(key)
        for key in after["tierDamageFormulas"]
    )
    multipliers = sum(
        previous != current
        for roll, row in after["damageMultipliers"].items()
        for previous, current in zip(
            before["damageMultipliers"].get(roll, []),
            row,
            strict=False,
        )
    )
    return {
        "resistances": resistances,
        "tiers": tiers,
        "multipliers": multipliers,
        "total": resistances + tiers + multipliers,
    }


def validate_damage_rules(user, giocatore, submitted: Any) -> dict[str, Any]:
    require_game_variable_admin(user, giocatore)
    profile = get_game_variable_profile()
    normalized = normalize_damage_rules(submitted)
    counts = _change_counts(configured_damage_rules(profile), normalized)
    warnings = []
    if all(value == 0 for value in normalized["damageMultipliers"]["20"]):
        warnings.append("La riga del 20 naturale non infligge mai danno.")
    if any(
        not math.isfinite(float(value))
        for value in normalized["resistancePercentages"].values()
    ):
        # Defensive: normalize_damage_rules already rejects this.
        raise ApiError(
            "management.damage_rules.non_finite",
            "Le percentuali devono essere finite.",
            "resistancePercentages",
        )
    token = signing.dumps(
        {
            "revision": game_variable_revision(profile),
            "digest": _digest(normalized),
        },
        salt=DAMAGE_RULES_PREVIEW_SALT,
        compress=True,
    )
    return {
        "valid": True,
        "previewToken": token,
        "changedCount": counts["total"],
        "changeCounts": counts,
        "warnings": warnings,
        "message": (
            f"Validazione completata: {counts['total']} valori pronti."
            if counts["total"]
            else "Validazione completata: nessuna modifica rilevata."
        ),
    }


@transaction.atomic
def save_damage_rules(
    user,
    giocatore,
    submitted: Any,
    preview_token: Any,
) -> dict[str, Any]:
    require_game_variable_admin(user, giocatore)
    if not preview_token:
        raise ApiError(
            "management.damage_rules.validation_required",
            "Valida le regole prima di salvarle.",
            "previewToken",
        )
    try:
        preview = signing.loads(
            str(preview_token),
            salt=DAMAGE_RULES_PREVIEW_SALT,
            max_age=DAMAGE_RULES_PREVIEW_MAX_AGE_SECONDS,
        )
    except signing.SignatureExpired as exc:
        raise ApiError(
            "management.damage_rules.validation_expired",
            "La validazione è scaduta. Ripeti il controllo.",
            "previewToken",
            409,
        ) from exc
    except signing.BadSignature as exc:
        raise ApiError(
            "management.damage_rules.validation_invalid",
            "La validazione non è valida. Ripeti il controllo.",
            "previewToken",
            409,
        ) from exc

    profile = GlobalModifiers.objects.select_for_update().filter(
        name=PROFILE_NAME,
        archived_at__isnull=True,
    ).first()
    normalized = normalize_damage_rules(submitted)
    if (
        not isinstance(preview, Mapping)
        or preview.get("digest") != _digest(normalized)
    ):
        raise ApiError(
            "management.damage_rules.changed_after_validation",
            "Le regole sono cambiate dopo la validazione.",
            "previewToken",
            409,
        )
    if preview.get("revision", "") != game_variable_revision(profile):
        raise ApiError(
            "management.damage_rules.stale",
            "Il profilo è stato aggiornato. Ricarica e valida nuovamente.",
            "previewToken",
            409,
        )
    if profile is None:
        profile = GlobalModifiers(name=PROFILE_NAME)
    value_string = (
        dict(profile.value_string)
        if isinstance(profile.value_string, Mapping)
        else {}
    )
    value_string[DAMAGE_RULES_CONFIG_KEY] = normalized
    profile.value_string = value_string
    profile.save()
    return damage_rules_payload(profile)
