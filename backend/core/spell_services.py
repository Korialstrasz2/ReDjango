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
# Risorse che un incantesimo può richiedere in modo fisso, oltre al Mana.
FIXED_COST_RESOURCES = ("pf", "energia", "potere", "pa", "stanchezza")
SPELL_ECONOMY_KEYS = {
    "manaDiscountPerPower": "sconto_mana_per_potere",
    "actionPointDiscountPerPower": "sconto_pa_per_potere",
    "manaPerEnergy": "ogni_en_x_mana",
    "manaPerActionPoint": "ogni_pa_x_mana",
}


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
    raw_fixed_costs = raw.get("fixedCosts") or {}
    if not isinstance(raw_fixed_costs, Mapping):
        raise ApiError(
            "spells.fixed_costs_invalid",
            "I costi fissi devono essere un oggetto.",
            "spell.fixedCosts",
        )
    fixed_costs = {
        resource: float(amount)
        for resource in FIXED_COST_RESOURCES
        if (amount := _decimal_field(raw_fixed_costs, resource)) > 0
    }
    return {
        "tier": tier,
        "range_text": str(raw.get("range") or "").strip()[:160],
        "effect_unit": str(raw.get("effectUnit") or "Effetto").strip()[:120] or "Effetto",
        "base_mana": _decimal_field(raw, "baseMana"),
        "effect_per_mana": _decimal_field(raw, "effectPerMana", strictly_positive=True),
        "minimum_mana": _decimal_field(raw, "minimumMana"),
        "fixed_costs": fixed_costs,
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


def spell_fixed_costs(definition: SpellDefinition) -> dict[str, int]:
    """Fixed non-mana cost of one cast, normalised to the combat resource keys."""
    stored = definition.fixed_costs if isinstance(definition.fixed_costs, dict) else {}
    costs: dict[str, int] = {}
    for resource in FIXED_COST_RESOURCES:
        try:
            amount = Decimal(str(stored.get(resource, 0) or 0))
        except Exception:
            continue
        if amount > 0:
            costs[resource] = int(amount.to_integral_value(rounding=ROUND_CEILING))
    return costs


def _readable(value: Decimal) -> str:
    """Cut the long tail that dividing by a stored ratio produces (6,999999… → 7)."""
    normalized = Decimal(value).quantize(Decimal("0.0001")).normalize()
    return format(normalized, "f")


def spell_cost_summary(definition: SpellDefinition) -> str:
    """One readable line separating the fixed part of the cost from the variable one."""
    mana_per_effect = _readable(Decimal(1) / Decimal(definition.effect_per_mana))
    variable = f"{mana_per_effect} Mana per {definition.effect_unit.lower()}"
    parts = (
        [f"{_readable(definition.base_mana)} Mana fissi più {variable}"]
        if definition.base_mana
        else [variable]
    )
    if definition.minimum_mana:
        parts.append(f"minimo {_readable(definition.minimum_mana)} Mana")
    fixed = spell_fixed_costs(definition)
    if fixed:
        parts.append(
            "costi fissi " + ", ".join(f"{amount} {resource.upper()}" for resource, amount in fixed.items())
        )
    return " · ".join(parts)


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
        "fixedCosts": spell_fixed_costs(definition),
        "rounding": definition.rounding,
        "roundingLabel": definition.get_rounding_display(),
        "legacyFormula": definition.legacy_formula,
        "costNotes": definition.cost_notes,
        "formula": (
            f"{definition.effect_unit} = max(0, (Mana - {definition.base_mana:g}) "
            f"× {definition.effect_per_mana:g})"
        ),
        "costSummary": spell_cost_summary(definition),
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


def character_spell_economy(character: Personaggio) -> dict[str, Decimal]:
    return {name: _tot_value(character, key) for name, key in SPELL_ECONOMY_KEYS.items()}


def _ceil(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def spell_cast_breakdown(
    definition: SpellDefinition,
    effect: Decimal,
    *,
    economy: Mapping[str, Decimal],
    power_used: Decimal = Decimal("0"),
    free_power: Decimal = Decimal("0"),
) -> dict[str, Any]:
    """Price one cast, keeping the fixed and per-effect halves visible.

    Follows the original rules: the fixed Mana and the Mana bought with the effect
    slider are summed first, Energia and PA are converted from that total before any
    discount, the whole Potere (spent plus free) discounts Mana and PA, and only the
    spent Potere is actually paid. Fixed costs in other resources are added on top and
    are never converted.
    """
    # I campi decimali possono arrivare come int quando l'oggetto non è stato riletto
    # dal database, quindi vengono normalizzati prima di qualunque calcolo.
    fixed_mana = max(Decimal("0"), Decimal(definition.base_mana))
    variable_mana = max(Decimal("0"), Decimal(effect)) / Decimal(definition.effect_per_mana)
    required_mana = max(Decimal(definition.minimum_mana), fixed_mana + variable_mana)
    total_power = max(Decimal("0"), Decimal(power_used)) + max(Decimal("0"), Decimal(free_power))
    spent_power = max(Decimal("0"), Decimal(power_used))

    mana_discount = total_power * Decimal(economy.get("manaDiscountPerPower", 0))
    action_discount = total_power * Decimal(economy.get("actionPointDiscountPerPower", 0))
    energy_rate = Decimal(economy.get("manaPerEnergy", 0))
    action_rate = Decimal(economy.get("manaPerActionPoint", 0))

    converted_energy = _ceil(required_mana / energy_rate) if energy_rate > 0 else 0
    converted_action = (
        _ceil(max(Decimal("0"), required_mana / action_rate - action_discount)) if action_rate > 0 else 0
    )
    fixed_costs = spell_fixed_costs(definition)
    costs = {
        "pf": fixed_costs.get("pf", 0),
        "mana": _ceil(max(Decimal("0"), required_mana - mana_discount)),
        "energia": converted_energy + fixed_costs.get("energia", 0),
        "potere": int(spent_power) + fixed_costs.get("potere", 0),
        "pa": converted_action + fixed_costs.get("pa", 0),
        "stanchezza": fixed_costs.get("stanchezza", 0),
    }
    return {
        "fixedMana": float(fixed_mana),
        "variableMana": float(variable_mana),
        "requiredMana": _ceil(required_mana),
        "minimumApplied": required_mana > fixed_mana + variable_mana,
        "manaDiscount": float(mana_discount),
        "actionPointDiscount": float(action_discount),
        "convertedEnergy": converted_energy,
        "convertedActionPoints": converted_action,
        "fixedCosts": fixed_costs,
        "costs": costs,
        "projectedEffect": float(
            _round_effect(
                max(
                    Decimal("0"),
                    (Decimal(_ceil(required_mana)) - fixed_mana) * Decimal(definition.effect_per_mana),
                ),
                definition.rounding,
            )
        ),
    }


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
    breakdown = spell_cast_breakdown(
        definition, effect, economy=character_spell_economy(character), power_used=power
    )
    return {
        "skillId": skill.id,
        "skillName": skill.nome,
        "tier": definition.tier,
        "tierLabel": definition.get_tier_display(),
        "requestedEffect": float(effect),
        "projectedEffect": breakdown["projectedEffect"],
        "effectUnit": definition.effect_unit,
        "fixedMana": breakdown["fixedMana"],
        "variableMana": breakdown["variableMana"],
        "requiredManaBeforeDiscounts": breakdown["requiredMana"],
        "powerConsidered": float(power),
        "fixedCosts": breakdown["fixedCosts"],
        "resourceOptions": {
            "mana": breakdown["costs"]["mana"],
            "energy": breakdown["costs"]["energia"],
            "actionPoints": breakdown["costs"]["pa"],
        },
        "costs": breakdown["costs"],
        "costSummary": spell_cost_summary(definition),
        "spendsResources": False,
        "combatReady": False,
        "note": (
            "Anteprima soltanto: in combattimento Mana, Energia e PA si pagano insieme, "
            "il Potere usato riduce Mana e PA e i costi fissi si sommano a parte."
        ),
    }
