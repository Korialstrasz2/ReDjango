from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from typing import Any

from backend.characters.models import Personaggio
from backend.core.api import ApiError
from backend.core.models import Skill, SpellDefinition


TIER_ALIASES = {
    "base": SpellDefinition.TIER_BASE,
    "novizio": SpellDefinition.TIER_BASE,
    "apprendista": SpellDefinition.TIER_APPRENTICE,
    "apprentice": SpellDefinition.TIER_APPRENTICE,
    "maestro": SpellDefinition.TIER_MASTER,
    "master": SpellDefinition.TIER_MASTER,
}
ROUNDING_VALUES = {value for value, _label in SpellDefinition.ROUNDING_CHOICES}


def _decimal_field(
    values: Mapping[str, Any],
    key: str,
    *,
    minimum: Decimal = Decimal("0"),
    strictly_positive: bool = False,
) -> Decimal:
    try:
        value = Decimal(str(values.get(key, 0) or 0))
    except Exception as exc:
        raise ApiError("spells.number_required", "Inserisci un numero valido.", f"spell.{key}") from exc
    if value < minimum or (strictly_positive and value <= 0):
        comparator = "maggiore di zero" if strictly_positive else f"almeno {minimum}"
        raise ApiError("spells.number_out_of_range", f"Il valore deve essere {comparator}.", f"spell.{key}")
    return value


def validate_spell_values(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ApiError(
            "spells.definition_required",
            "Configura i dati dell'incantesimo.",
            "spell",
        )
    tier = TIER_ALIASES.get(str(raw.get("tier") or "base").strip().lower())
    if tier is None:
        raise ApiError("spells.tier_invalid", "Scegli un tier magico valido.", "spell.tier")
    rounding = str(raw.get("rounding") or SpellDefinition.ROUNDING_NONE).strip().lower()
    if rounding not in ROUNDING_VALUES:
        raise ApiError("spells.rounding_invalid", "Scegli un arrotondamento valido.", "spell.rounding")
    combat_configuration = raw.get("combatConfiguration") or {}
    if not isinstance(combat_configuration, Mapping):
        raise ApiError(
            "spells.combat_configuration_invalid",
            "La predisposizione al combattimento deve essere un oggetto.",
            "spell.combatConfiguration",
        )
    return {
        "tier": tier,
        "range_text": str(raw.get("range") or "").strip()[:160],
        "effect_unit": str(raw.get("effectUnit") or "Effetto").strip()[:120] or "Effetto",
        "base_mana": _decimal_field(raw, "baseMana"),
        "effect_per_mana": _decimal_field(raw, "effectPerMana", strictly_positive=True),
        "minimum_mana": _decimal_field(raw, "minimumMana"),
        "rounding": rounding,
        "legacy_formula": str(raw.get("legacyFormula") or "").strip()[:255],
        "cost_notes": str(raw.get("costNotes") or "").strip(),
        "combat_configuration": {
            **dict(combat_configuration),
            "prepared": True,
            "spendsResources": False,
        },
    }


def save_spell_definition(skill: Skill, raw: Any) -> SpellDefinition:
    fields = validate_spell_values(raw)
    definition, _created = SpellDefinition.objects.update_or_create(skill=skill, defaults=fields)
    return definition


def spell_for_skill(skill: Skill) -> SpellDefinition | None:
    try:
        return skill.spell_definition
    except SpellDefinition.DoesNotExist:
        return None


def serialize_spell(skill: Skill) -> dict[str, Any] | None:
    definition = spell_for_skill(skill)
    if definition is None:
        return None
    return {
        "id": definition.id,
        "tier": definition.tier,
        "tierLabel": definition.get_tier_display(),
        "range": definition.range_text,
        "effectUnit": definition.effect_unit,
        "baseMana": float(definition.base_mana),
        "effectPerMana": float(definition.effect_per_mana),
        "minimumMana": float(definition.minimum_mana),
        "rounding": definition.rounding,
        "roundingLabel": definition.get_rounding_display(),
        "legacyFormula": definition.legacy_formula,
        "costNotes": definition.cost_notes,
        "formula": (
            f"{definition.effect_unit} = max(0, (Mana - {definition.base_mana:g}) "
            f"× {definition.effect_per_mana:g})"
        ),
        "combatConfiguration": {
            **(
                definition.combat_configuration
                if isinstance(definition.combat_configuration, dict)
                else {}
            ),
            "prepared": True,
            "spendsResources": False,
        },
    }


def _round_effect(value: Decimal, rounding: str) -> Decimal:
    if rounding == SpellDefinition.ROUNDING_FLOOR:
        return value.to_integral_value(rounding=ROUND_FLOOR)
    if rounding == SpellDefinition.ROUNDING_CEIL:
        return value.to_integral_value(rounding=ROUND_CEILING)
    if rounding == SpellDefinition.ROUNDING_NEAREST:
        return value.to_integral_value(rounding=ROUND_HALF_UP)
    return value


def _tot_value(character: Personaggio, key: str) -> Decimal:
    totals = character.tot if isinstance(character.tot, dict) else {}
    try:
        return max(Decimal("0"), Decimal(str(totals.get(key, 0) or 0)))
    except Exception:
        return Decimal("0")


def preview_spell_cast(
    character: Personaggio,
    skill_id: int,
    raw_effect: Any,
    raw_power: Any = 0,
) -> dict[str, Any]:
    try:
        skill = Skill.objects.select_related("spell_definition", "famiglia").get(
            pk=skill_id,
            archived_at__isnull=True,
            spell_definition__archived_at__isnull=True,
        )
    except Skill.DoesNotExist as exc:
        raise ApiError("spells.not_found", "Incantesimo non trovato.", status=404) from exc
    definition = spell_for_skill(skill)
    if definition is None:
        raise ApiError("spells.not_found", "Questa Skill non è un incantesimo.", status=404)
    effect = _decimal_field({"effect": raw_effect}, "effect")
    power = _decimal_field({"power": raw_power}, "power")
    required_mana = max(
        definition.minimum_mana,
        definition.base_mana + (effect / definition.effect_per_mana),
    ).to_integral_value(rounding=ROUND_CEILING)
    mana_discount = power * _tot_value(character, "sconto_mana_per_potere")
    projected_mana = max(Decimal("0"), required_mana - mana_discount).to_integral_value(
        rounding=ROUND_CEILING
    )
    energy_rate = _tot_value(character, "ogni_en_x_mana")
    action_rate = _tot_value(character, "ogni_pa_x_mana")
    action_discount = power * _tot_value(character, "sconto_pa_per_potere")
    energy_cost = (
        (projected_mana / energy_rate).to_integral_value(rounding=ROUND_CEILING)
        if energy_rate > 0
        else None
    )
    action_cost = (
        max(Decimal("0"), (projected_mana / action_rate) - action_discount).to_integral_value(
            rounding=ROUND_CEILING
        )
        if action_rate > 0
        else None
    )
    projected_effect = _round_effect(
        max(Decimal("0"), (required_mana - definition.base_mana) * definition.effect_per_mana),
        definition.rounding,
    )
    return {
        "skillId": skill.id,
        "skillName": skill.nome,
        "tier": definition.tier,
        "tierLabel": definition.get_tier_display(),
        "requestedEffect": float(effect),
        "projectedEffect": float(projected_effect),
        "effectUnit": definition.effect_unit,
        "requiredManaBeforeDiscounts": int(required_mana),
        "powerConsidered": float(power),
        "resourceOptions": {
            "mana": int(projected_mana),
            "energy": int(energy_cost) if energy_cost is not None else None,
            "actionPoints": int(action_cost) if action_cost is not None else None,
        },
        "spendsResources": False,
        "combatReady": False,
        "note": (
            "Anteprima soltanto: il combattimento deciderà quale risorsa usare e quando applicare la spesa."
        ),
    }
