from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from typing import Any

from backend.characters.models import Personaggio, SkillPersonaggio
from backend.core.defaults import SKILL_PRICING_CONFIG_KEY, SKILL_PRICING_DEFAULTS
from backend.core.models import GlobalModifiers, Skill


def _decimal(value: Any, fallback: float | int) -> Decimal:
    if value in (None, ""):
        value = fallback
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(str(fallback))


def skill_pricing_config() -> dict[str, Decimal]:
    configured: dict[str, Any] = {}
    profile = GlobalModifiers.objects.filter(name="Formule_base", archived_at__isnull=True).first()
    if profile and isinstance(profile.value_string, dict):
        candidate = profile.value_string.get(SKILL_PRICING_CONFIG_KEY, {})
        if isinstance(candidate, dict):
            configured = candidate
    result = {
        key: _decimal(configured.get(key), fallback)
        for key, fallback in SKILL_PRICING_DEFAULTS.items()
    }
    if result["modifier_base"] <= 0:
        result["modifier_base"] = _decimal(SKILL_PRICING_DEFAULTS["modifier_base"], 3)
    if result["modifier_max"] < result["modifier_base"]:
        result["modifier_max"] = result["modifier_base"]
    if result["scaling_divisor"] <= 0:
        result["scaling_divisor"] = _decimal(SKILL_PRICING_DEFAULTS["scaling_divisor"], 1.5)
    if result["spent_xp_discount_cap"] <= 0:
        result["spent_xp_discount_cap"] = _decimal(
            SKILL_PRICING_DEFAULTS["spent_xp_discount_cap"],
            100,
        )
    return result


def spent_xp_in_skill_category(
    character: Personaggio | None,
    skill: Skill,
    *,
    lock: bool = False,
) -> int:
    if character is None or skill.tipo_pe == "all":
        return 0
    pool = skill.tipo_pe if skill.tipo_pe in {"general", "red", "green", "blue"} else "general"
    ownerships = SkillPersonaggio.objects.filter(
        personaggio=character,
        archived_at__isnull=True,
        skill__archived_at__isnull=True,
    )
    if lock:
        ownerships = ownerships.select_for_update()
    total = 0
    for spend in ownerships.values_list("spesa_pe", flat=True):
        if isinstance(spend, dict):
            try:
                total += max(0, int(spend.get(pool, 0) or 0))
            except (TypeError, ValueError):
                continue
    return total


def skill_price(
    skill: Skill,
    character: Personaggio | None,
    *,
    lock_ownerships: bool = False,
) -> dict[str, Any]:
    base_cost = max(0, int(skill.costo_pe or 0))
    spent_xp = spent_xp_in_skill_category(character, skill, lock=lock_ownerships)
    if character is None or base_cost == 0:
        return {
            "baseCost": base_cost,
            "calculatedCost": base_cost,
            "calculatedBeforeOwnedSkillDiscount": base_cost,
            "levelSurcharge": 0,
            "spentXpInCategory": spent_xp,
            "surchargeDiscountPercent": 0,
            "ownedSkillDiscount": 0,
            "ownedSkillDiscountSources": [],
        }

    config = skill_pricing_config()
    base = Decimal(base_cost)
    level = Decimal(max(0, int(character.livello or 0)))
    modifier = min(config["modifier_base"] + base, config["modifier_max"])
    scaled_level = (level * config["scaling_factor"]) / config["scaling_divisor"]
    before_discount = (base + (base / modifier) * scaled_level).to_integral_value(rounding=ROUND_FLOOR)
    raw_surcharge = max(Decimal(0), before_discount - base)
    cap = config["spent_xp_discount_cap"]
    remaining_ratio = max(Decimal(0), Decimal(1) - (Decimal(spent_xp) / cap))
    # The legacy curve first floors the level-adjusted cost.  Its discounted
    # result must follow the same player-facing rule: fractional PE never round
    # up (4.2 and 4.8 both cost 4 PE).
    before_owned_skill_discount = (base + raw_surcharge * remaining_ratio).to_integral_value(rounding=ROUND_FLOOR)
    owned_skill_discount = 0
    owned_skill_discount_sources: list[str] = []
    ownerships = SkillPersonaggio.objects.filter(
        personaggio=character,
        archived_at__isnull=True,
        skill__archived_at__isnull=True,
    ).select_related("skill")
    if lock_ownerships:
        ownerships = ownerships.select_for_update()
    for ownership in ownerships:
        metadata = ownership.skill.metadata if isinstance(ownership.skill.metadata, dict) else {}
        rule = metadata.get("pricingModifier", {})
        if not isinstance(rule, dict) or rule.get("type") != "owned_skill_flat_discount":
            continue
        try:
            amount = max(0, int(rule.get("amount", 0) or 0))
            minimum_base_cost = max(0, int(rule.get("minimumBaseCost", 0) or 0))
        except (TypeError, ValueError):
            continue
        xp_types = rule.get("xpTypes", [])
        if not isinstance(xp_types, list) or skill.tipo_pe not in {str(value) for value in xp_types}:
            continue
        if base_cost < minimum_base_cost or amount <= 0:
            continue
        owned_skill_discount += amount
        owned_skill_discount_sources.append(ownership.skill.nome)
    final_cost = max(Decimal(0), before_owned_skill_discount - Decimal(owned_skill_discount))
    discount_percent = (Decimal(1) - remaining_ratio) * Decimal(100)
    return {
        "baseCost": base_cost,
        "calculatedCost": int(final_cost),
        "calculatedBeforeOwnedSkillDiscount": int(before_owned_skill_discount),
        "levelSurcharge": int(before_owned_skill_discount) - base_cost,
        "spentXpInCategory": spent_xp,
        "surchargeDiscountPercent": float(discount_percent.quantize(Decimal("0.01"))),
        "ownedSkillDiscount": int(before_owned_skill_discount - final_cost),
        "ownedSkillDiscountSources": owned_skill_discount_sources,
    }
