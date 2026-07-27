from __future__ import annotations

import ast
import copy
import math
import operator
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from django.db import transaction
from django.db.models.fields.related import ForeignKey

from backend.characters.models import PERSONAGGIO_TOT_KEYS, Personaggio, default_personaggio_tot
from backend.characters.race_rules import automatic_race_effects
from backend.core.defaults import (
    CHARACTERISTIC_ADJUSTMENT_DEFAULTS,
    QUICK_STAT_ADJUSTMENT_CONFIG_KEY,
    QUICK_STAT_ADJUSTMENT_DEFAULTS,
    V2_GLOBAL_MODIFIERS_DEFAULTS,
)
from backend.core.models import Effetto, GlobalModifiers, Oggetto


DEFAULT_PROFILE_NAME = "Formule_base"

CHARACTERISTICS = (
    "forza",
    "resistenza",
    "velocita",
    "agilita",
    "intelligenza",
    "concentrazione",
    "personalita",
    "saggezza",
    "fortuna",
)

PRE_FORMULA_BASE_STATS = ("stanchezza", "modificatore_generale")

MODIFIER_BY_CHARACTERISTIC = {stat: f"mod_{stat}" for stat in CHARACTERISTICS}
CHARACTERISTIC_MODIFIER_KEYS = set(MODIFIER_BY_CHARACTERISTIC.values())

DERIVED_STAT_ORDER = tuple(
    key
    for key in PERSONAGGIO_TOT_KEYS
    if key not in CHARACTERISTICS
    and key not in PRE_FORMULA_BASE_STATS
    and key not in CHARACTERISTIC_MODIFIER_KEYS
    and key != "malus_carico"
) + ("malus_carico",)

SAFE_FUNCTIONS = {
    "floor": math.floor,
    "ceil": math.ceil,
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
}

BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}

UNARY_OPS = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

COMPARE_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}

OPERATION_ALIASES = {
    "+": "add",
    "add": "add",
    "plus": "add",
    "flat_add": "add",
    "increase": "add",
    "-": "subtract",
    "sub": "subtract",
    "subtract": "subtract",
    "minus": "subtract",
    "flat_subtract": "subtract",
    "flat_sub": "subtract",
    "decrease": "subtract",
    "*": "multiply",
    "mul": "multiply",
    "multiply": "multiply",
    "multiplier": "multiply",
    "x": "multiply",
    "%": "percent",
    "percent": "percent",
    "percentage": "percent",
    "percentage_change": "percent",
    "percent_change": "percent",
    "min": "min",
    "minimum": "min",
    "floor_value": "min",
    "max": "max",
    "maximum": "max",
    "cap": "cap",
    "set": "set",
    "=": "set",
    "override": "set",
    "strong_set": "strong_set",
    "strong-set": "strong_set",
    "final_set": "strong_set",
}

OPERATION_ORDER = ("add", "subtract", "multiply", "percent", "min", "max", "cap", "set")
SUPPORTED_CALCULATION_OPERATIONS = (*OPERATION_ORDER, "strong_set")

OPERATION_LIST_KEYS = (
    "operations",
    "modifiers",
    "effects",
    "calculation_effects",
    "calculationEffects",
    "rules",
)

FORMULA_OVERRIDE_KEYS = (
    "formula_overrides",
    "formulaOverrides",
    "formula_override",
    "formulaOverride",
)

LEGACY_EFFECT_RE = re.compile(r"^(?:personaggio\.)?([\w_]+)\s*([+\-*=])\s*(.+)$", re.IGNORECASE)


class CalculationExpressionError(ValueError):
    pass


@dataclass(frozen=True)
class CalculationOperation:
    target: str
    operation: str
    value: Any
    order: int
    source: str = ""
    condition: Any = None
    phase: str = ""


@dataclass(frozen=True)
class FormulaOverride:
    target: str
    formula: str
    order: int
    source: str = ""


@dataclass
class CollectedEffects:
    operations: list[CalculationOperation] = field(default_factory=list)
    formula_overrides: list[FormulaOverride] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class CalculationResult:
    totals: dict[str, Any]
    breakdown: dict[str, Any]


class SafeExpressionEvaluator(ast.NodeVisitor):
    def __init__(self, contexts: Mapping[str, Mapping[str, Any]]):
        self.contexts = contexts

    def visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, (int, float, bool)):
            return node.value
        raise CalculationExpressionError("Only numeric and boolean constants are allowed.")

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        op = BIN_OPS.get(type(node.op))
        if op is None:
            raise CalculationExpressionError(f"Unsupported operator: {type(node.op).__name__}.")
        return op(self.visit(node.left), self.visit(node.right))

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        op = UNARY_OPS.get(type(node.op))
        if op is None:
            raise CalculationExpressionError(f"Unsupported unary operator: {type(node.op).__name__}.")
        return op(self.visit(node.operand))

    def visit_Call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name) or node.func.id not in SAFE_FUNCTIONS:
            raise CalculationExpressionError("Only whitelisted functions can be called.")
        if node.keywords:
            raise CalculationExpressionError("Keyword arguments are not supported.")
        return SAFE_FUNCTIONS[node.func.id](*(self.visit(arg) for arg in node.args))

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id in {"True", "False"}:
            return node.id == "True"
        raise CalculationExpressionError(
            f"Use explicit context variables such as base.{node.id}, pre.{node.id}, final.{node.id}, or personaggio.{node.id}."
        )

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        if node.attr.startswith("_"):
            raise CalculationExpressionError("Private attributes are not readable.")
        if not isinstance(node.value, ast.Name):
            raise CalculationExpressionError("Only one-level context attributes are supported.")
        context_name = node.value.id
        if context_name not in self.contexts:
            raise CalculationExpressionError(f"Unknown context: {context_name}.")
        context = self.contexts[context_name]
        if node.attr not in context:
            raise CalculationExpressionError(f"Unknown variable: {context_name}.{node.attr}.")
        return context[node.attr]

    def visit_Compare(self, node: ast.Compare) -> bool:
        left = self.visit(node.left)
        for op_node, comparator in zip(node.ops, node.comparators):
            op = COMPARE_OPS.get(type(op_node))
            if op is None:
                raise CalculationExpressionError(f"Unsupported comparison: {type(op_node).__name__}.")
            right = self.visit(comparator)
            if not op(left, right):
                return False
            left = right
        return True

    def visit_BoolOp(self, node: ast.BoolOp) -> bool:
        if isinstance(node.op, ast.And):
            return all(bool(self.visit(value)) for value in node.values)
        if isinstance(node.op, ast.Or):
            return any(bool(self.visit(value)) for value in node.values)
        raise CalculationExpressionError(f"Unsupported boolean operator: {type(node.op).__name__}.")

    def generic_visit(self, node: ast.AST) -> Any:
        raise CalculationExpressionError(f"Unsupported expression: {type(node).__name__}.")


def evaluate_expression(expression: Any, contexts: Mapping[str, Mapping[str, Any]]) -> Any:
    if isinstance(expression, (int, float, bool)):
        return expression
    if expression is None:
        return 0
    if not isinstance(expression, str):
        raise CalculationExpressionError(f"Unsupported expression type: {type(expression).__name__}.")
    cleaned = expression.strip()
    if cleaned.startswith("(f)"):
        cleaned = cleaned[3:].strip()
    if cleaned.endswith("%"):
        cleaned = cleaned[:-1].strip()
    tree = ast.parse(cleaned, mode="eval")
    return SafeExpressionEvaluator(contexts).visit(tree.body)


def evaluate_number(expression: Any, contexts: Mapping[str, Mapping[str, Any]]) -> float:
    value = evaluate_expression(expression, contexts)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalculationExpressionError("Expression must resolve to a number.")
    return float(value)


def normalize_number(value: Any) -> Any:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _normalized_calculation_number(value: Any) -> int | float:
    try:
        return normalize_number(round(float(value or 0), 6))
    except (TypeError, ValueError):
        return 0


def build_calculation_source_breakdown(
    base_totals: Mapping[str, Any],
    item_totals: Mapping[str, Any],
    final_totals: Mapping[str, Any],
) -> dict[str, dict[str, int | float]]:
    """Project every total as the baseline plus item and active-effect changes."""
    keys = set(PERSONAGGIO_TOT_KEYS) | set(base_totals) | set(item_totals) | set(final_totals)
    breakdown: dict[str, dict[str, int | float]] = {}
    for key in sorted(keys):
        base_value = _normalized_calculation_number(base_totals.get(key, 0))
        item_value = _normalized_calculation_number(item_totals.get(key, 0))
        final_value = _normalized_calculation_number(final_totals.get(key, 0))
        breakdown[key] = {
            "base": base_value,
            "items": _normalized_calculation_number(item_value - base_value),
            "effects": _normalized_calculation_number(final_value - item_value),
        }
    return breakdown


def normalize_stat_key(key: Any) -> str:
    normalized = str(key or "").strip().lower()
    normalized = normalized.replace("personaggio.", "")
    normalized = normalized.replace(" ", "_").replace("-", "_")
    for suffix in ("_tot", "_base", "_extra", "_item", "_bonus", "_temp"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
    if normalized.startswith("modificatore_") and normalized != "modificatore_generale":
        normalized = normalized.replace("modificatore_", "mod_", 1)
    mana_aliases = {
    }
    return mana_aliases.get(normalized, normalized)


def build_personaggio_context(personaggio: Any | None) -> dict[str, Any]:
    allowed_fields = (
        "id",
        "pk",
        "nome",
        "nome_interno",
        "tipologia",
        "razza_1",
        "razza_2",
        "razza_3",
        "livello",
        "eta",
        "sesso",
        "monete",
        "danno",
        "mana_speso",
        "energia_spesa",
        "potere_speso",
        "stanchezza_accumulata",
        "mana_in_sifone",
        "pe_generali",
        "pe_rossi",
        "pe_verdi",
        "pe_blu",
        "pe_abilita",
    )
    if personaggio is None:
        return {"livello": 1}
    if isinstance(personaggio, Mapping):
        return {field: personaggio[field] for field in allowed_fields if field in personaggio}
    context = {}
    for field_name in allowed_fields:
        if hasattr(personaggio, field_name):
            context[field_name] = getattr(personaggio, field_name)
    context.setdefault("livello", 1)
    return context


def build_base_values(global_values: Mapping[str, Any]) -> dict[str, float]:
    base = {key: 0.0 for key in PERSONAGGIO_TOT_KEYS}
    for raw_key, raw_value in (global_values or {}).items():
        key = normalize_stat_key(raw_key)
        if key not in base:
            continue
        try:
            base[key] = float(raw_value or 0)
        except (TypeError, ValueError):
            base[key] = 0.0
    return base


def calculate_characteristic_modifiers(values: Mapping[str, Any]) -> dict[str, int]:
    return {
        modifier_key: math.floor((float(values.get(stat, 0)) - 10) / 2)
        for stat, modifier_key in MODIFIER_BY_CHARACTERISTIC.items()
    }


def build_pre_snapshot(base: Mapping[str, Any]) -> dict[str, Any]:
    pre = dict(base)
    pre.update(calculate_characteristic_modifiers(base))
    return {key: normalize_number(value) for key, value in pre.items()}


def extract_formula_map(value_string: Mapping[str, Any] | None) -> dict[str, str]:
    formula_map: dict[str, str] = {}
    if not isinstance(value_string, Mapping):
        return formula_map

    nested = value_string.get("formulas") or value_string.get("formulae") or {}
    if isinstance(nested, Mapping):
        for key, formula in nested.items():
            if formula not in (None, ""):
                formula_map[normalize_stat_key(key)] = str(formula)

    for key, formula in value_string.items():
        normalized_key = str(key)
        if normalized_key.startswith("formula."):
            formula_map[normalize_stat_key(normalized_key.removeprefix("formula."))] = str(formula)
        elif normalized_key.startswith("formula_"):
            formula_map[normalize_stat_key(normalized_key.removeprefix("formula_"))] = str(formula)

    return formula_map


def extract_characteristic_adjustments(
    value_string: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Return the optional global adjustments applied to characteristics.

    The formulas are deliberately stored as the historical flat keys so existing
    Formule_base profiles retain their configuration. A profile that predates
    these keys receives no adjustment until it is explicitly configured.
    """
    if not isinstance(value_string, Mapping):
        return {}
    adjustments = {}
    for key in CHARACTERISTIC_ADJUSTMENT_DEFAULTS:
        value = value_string.get(f"adjustment.{key}")
        if value not in (None, ""):
            adjustments[key] = str(value)
    return adjustments


def apply_characteristic_adjustments(
    final: dict[str, Any],
    *,
    base: Mapping[str, Any],
    pre: Mapping[str, Any],
    personaggio_context: Mapping[str, Any],
    value_string: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Apply level first, then the Fortuna adjustment to non-Fortuna traits."""
    adjustments = extract_characteristic_adjustments(value_string)
    applied: dict[str, Any] = {}
    for key, targets in (
        ("livello", CHARACTERISTICS),
        ("fortuna", tuple(stat for stat in CHARACTERISTICS if stat != "fortuna")),
    ):
        formula = adjustments.get(key)
        if not formula:
            continue
        contexts = {
            "base": base,
            "pre": pre,
            "final": final,
            "personaggio": personaggio_context,
        }
        value = evaluate_number(formula, contexts)
        for stat in targets:
            final[stat] = _normalized_calculation_number(
                float(final.get(stat, 0) or 0) + value
            )
        applied[key] = {
            "formula": formula,
            "value": _normalized_calculation_number(value),
            "targets": list(targets),
        }
    return applied


def extract_quick_stat_adjustment(value_string: Mapping[str, Any] | None) -> dict[str, Any]:
    configured = (
        value_string.get(QUICK_STAT_ADJUSTMENT_CONFIG_KEY, {})
        if isinstance(value_string, Mapping)
        else {}
    )
    if not isinstance(configured, Mapping):
        configured = {}

    def number(key: str) -> float:
        try:
            return float(configured.get(key, QUICK_STAT_ADJUSTMENT_DEFAULTS[key]))
        except (TypeError, ValueError):
            return float(QUICK_STAT_ADJUSTMENT_DEFAULTS[key])

    raw_targets = configured.get("targets", QUICK_STAT_ADJUSTMENT_DEFAULTS["targets"])
    targets = {
        normalize_stat_key(target)
        for target in raw_targets
        if isinstance(target, str)
    } if isinstance(raw_targets, Iterable) and not isinstance(raw_targets, (str, bytes, Mapping)) else set()
    return {
        "fatigue_percent_per_point": number("fatigue_percent_per_point"),
        "fatigue_fixed_per_point": number("fatigue_fixed_per_point"),
        "general_modifier_percent_per_point": number("general_modifier_percent_per_point"),
        "general_modifier_fixed_per_point": number("general_modifier_fixed_per_point"),
        "targets": targets,
    }


def apply_quick_stat_adjustment(
    totals: Mapping[str, Any],
    value_string: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply fatigue/general modifier once, after every other calculation phase."""
    config = extract_quick_stat_adjustment(value_string)
    updated = dict(totals)
    fatigue_value = float(updated.get("stanchezza", 0) or 0)
    general_modifier_value = float(updated.get("modificatore_generale", 0) or 0)
    fatigue_percent = fatigue_value * config["fatigue_percent_per_point"]
    general_modifier_percent = general_modifier_value * config["general_modifier_percent_per_point"]
    fatigue_fixed = fatigue_value * config["fatigue_fixed_per_point"]
    general_modifier_fixed = (
        general_modifier_value * config["general_modifier_fixed_per_point"]
    )
    total_percent = general_modifier_percent - fatigue_percent
    multiplier = max(0.0, 1 + (total_percent / 100))
    applied: dict[str, dict[str, Any]] = {}

    for stat in sorted(config["targets"]):
        before = float(updated.get(stat, 0) or 0)
        fatigue_delta = -(before * fatigue_percent / 100)
        general_modifier_delta = before * general_modifier_percent / 100
        fatigue_fixed_delta = -fatigue_fixed
        general_modifier_fixed_delta = general_modifier_fixed
        after = math.floor(
            before * multiplier
            + fatigue_fixed_delta
            + general_modifier_fixed_delta
        )
        rounding_delta = (
            after
            - before
            - fatigue_delta
            - general_modifier_delta
            - fatigue_fixed_delta
            - general_modifier_fixed_delta
        )
        updated[stat] = normalize_number(after)
        applied[stat] = {
            "before": _normalized_calculation_number(before),
            "after": _normalized_calculation_number(after),
            "fatigue": _normalized_calculation_number(fatigue_delta),
            "fatigue_fixed": _normalized_calculation_number(fatigue_fixed_delta),
            "general_modifier": _normalized_calculation_number(general_modifier_delta),
            "general_modifier_fixed": _normalized_calculation_number(
                general_modifier_fixed_delta
            ),
            "rounding": _normalized_calculation_number(rounding_delta),
        }

    report = {
        "fatigue_value": _normalized_calculation_number(fatigue_value),
        "general_modifier_value": _normalized_calculation_number(general_modifier_value),
        "fatigue_percent_per_point": _normalized_calculation_number(
            config["fatigue_percent_per_point"]
        ),
        "fatigue_fixed_per_point": _normalized_calculation_number(
            config["fatigue_fixed_per_point"]
        ),
        "general_modifier_percent_per_point": _normalized_calculation_number(
            config["general_modifier_percent_per_point"]
        ),
        "general_modifier_fixed_per_point": _normalized_calculation_number(
            config["general_modifier_fixed_per_point"]
        ),
        "fatigue_percent": _normalized_calculation_number(fatigue_percent),
        "fatigue_fixed": _normalized_calculation_number(fatigue_fixed),
        "general_modifier_percent": _normalized_calculation_number(general_modifier_percent),
        "general_modifier_fixed": _normalized_calculation_number(
            general_modifier_fixed
        ),
        "total_percent": _normalized_calculation_number(total_percent),
        "multiplier": _normalized_calculation_number(multiplier),
        "targets": sorted(config["targets"]),
        "applied": applied,
    }
    return updated, report


def apply_action_point_minimum(totals: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Enforce Elder's absolute minimum of four action points.

    This is deliberately a terminal rule: fatigue, encumbrance, effects, and
    final overrides may reduce PA, but none of them can leave a character below
    the playable minimum.
    """
    updated = dict(totals)
    before = float(updated.get("pa", 0) or 0)
    after = max(4, before)
    updated["pa"] = normalize_number(after)
    return updated, {
        "minimum": 4,
        "before": _normalized_calculation_number(before),
        "after": after,
        "applied": before < 4,
    }


def normalize_operation_name(raw_operation: Any) -> str:
    operation = str(raw_operation or "").strip().lower()
    return OPERATION_ALIASES.get(operation, operation)


def _operation_from_dict(payload: Mapping[str, Any], order: int, source: str) -> CalculationOperation | None:
    target = payload.get("target") or payload.get("stat") or payload.get("name") or payload.get("field")
    raw_operation = payload.get("operation") or payload.get("op") or payload.get("type")
    if target is None or raw_operation is None:
        return None
    operation = normalize_operation_name(raw_operation)
    if operation not in SUPPORTED_CALCULATION_OPERATIONS:
        return None
    value = payload.get("value", payload.get("amount", payload.get("formula", 0)))
    return CalculationOperation(
        target=normalize_stat_key(target),
        operation=operation,
        value=value,
        order=order,
        source=str(payload.get("source") or payload.get("origine") or source),
        condition=payload.get("condition") or payload.get("conditions") or payload.get("when"),
        phase=str(payload.get("phase") or ""),
    )


def _operation_from_legacy_string(payload: str, order: int, source: str) -> CalculationOperation | None:
    cleaned = payload.strip()
    if cleaned.startswith("Personaggio."):
        cleaned = cleaned.replace("Personaggio.", "personaggio.", 1)
    match = LEGACY_EFFECT_RE.match(cleaned)
    if not match:
        return None
    target, raw_operation, value = match.groups()
    return CalculationOperation(
        target=normalize_stat_key(target),
        operation=normalize_operation_name(raw_operation),
        value=value.strip(),
        order=order,
        source=source,
    )


def _append_formula_override(collected: CollectedEffects, target: Any, formula: Any, order: int, source: str) -> None:
    if target in (None, "") or formula in (None, ""):
        return
    collected.formula_overrides.append(
        FormulaOverride(
            target=normalize_stat_key(target),
            formula=str(formula),
            order=order,
            source=source,
        )
    )


def collect_calculation_effects(effect_payloads: Iterable[Any]) -> CollectedEffects:
    collected = CollectedEffects()
    counter = 0

    def next_order() -> int:
        nonlocal counter
        counter += 1
        return counter

    def ingest(payload: Any, source: str = "") -> None:
        if payload in (None, ""):
            return
        if isinstance(payload, str):
            operation = _operation_from_legacy_string(payload, next_order(), source)
            if operation is not None:
                collected.operations.append(operation)
            return
        if isinstance(payload, Iterable) and not isinstance(payload, Mapping):
            for index, item in enumerate(payload):
                ingest(item, f"{source}[{index}]" if source else str(index))
            return
        if not isinstance(payload, Mapping):
            collected.warnings.append(f"Unsupported effect payload from {source or 'unknown'}.")
            return

        payload_source = str(payload.get("source") or payload.get("origine") or payload.get("name") or source)

        for nested_key in OPERATION_LIST_KEYS:
            if nested_key in payload:
                ingest(payload[nested_key], payload_source or nested_key)

        if "effect_payload" in payload:
            ingest(payload["effect_payload"], payload_source or "effect_payload")
        if "payload" in payload:
            ingest(payload["payload"], payload_source or "payload")

        operation = _operation_from_dict(payload, next_order(), payload_source)
        if operation is not None:
            collected.operations.append(operation)

        for override_key in FORMULA_OVERRIDE_KEYS:
            if override_key not in payload:
                continue
            override_payload = payload[override_key]
            if isinstance(override_payload, Mapping):
                if "target" in override_payload and "formula" in override_payload:
                    _append_formula_override(
                        collected,
                        override_payload.get("target"),
                        override_payload.get("formula"),
                        next_order(),
                        payload_source,
                    )
                else:
                    for target, formula in override_payload.items():
                        _append_formula_override(collected, target, formula, next_order(), payload_source)
            elif isinstance(override_payload, Iterable) and not isinstance(override_payload, (str, bytes)):
                for override in override_payload:
                    if isinstance(override, Mapping):
                        _append_formula_override(
                            collected,
                            override.get("target") or override.get("stat"),
                            override.get("formula") or override.get("value"),
                            next_order(),
                            str(override.get("source") or payload_source),
                        )

        if normalize_operation_name(payload.get("operation") or payload.get("op")) in {
            "formula_override",
            "override_formula",
        }:
            _append_formula_override(
                collected,
                payload.get("target") or payload.get("stat"),
                payload.get("formula") or payload.get("value"),
                next_order(),
                payload_source,
            )

    if isinstance(effect_payloads, Mapping):
        ingest(effect_payloads, "effects")
    else:
        ingest(list(effect_payloads or []), "effects")
    collected.operations.sort(key=lambda item: item.order)
    collected.formula_overrides.sort(key=lambda item: item.order)
    return collected


def condition_matches(condition: Any, contexts: Mapping[str, Mapping[str, Any]]) -> bool:
    if condition in (None, "", {}, []):
        return True
    if isinstance(condition, str):
        return bool(evaluate_expression(condition, contexts))
    if isinstance(condition, Iterable) and not isinstance(condition, Mapping):
        return all(condition_matches(item, contexts) for item in condition)
    if isinstance(condition, Mapping):
        if "expression" in condition:
            return bool(evaluate_expression(condition["expression"], contexts))
        left_expression = condition.get("field") or condition.get("left")
        raw_operation = str(condition.get("operation") or condition.get("op") or "==").strip()
        right_expression = condition["value"] if "value" in condition else condition.get("right")
        left = evaluate_expression(left_expression, contexts)
        right = evaluate_expression(right_expression, contexts)
        operation = {
            "==": operator.eq,
            "eq": operator.eq,
            "!=": operator.ne,
            "ne": operator.ne,
            ">": operator.gt,
            "gt": operator.gt,
            ">=": operator.ge,
            "gte": operator.ge,
            "<": operator.lt,
            "lt": operator.lt,
            "<=": operator.le,
            "lte": operator.le,
        }.get(raw_operation)
        if operation is None:
            raise CalculationExpressionError(f"Unsupported condition operator: {raw_operation}.")
        return bool(operation(left, right))
    return bool(condition)


def apply_operations(
    target: str,
    starting_value: float,
    operations: Iterable[CalculationOperation],
    contexts: Mapping[str, Mapping[str, Any]],
) -> tuple[float, list[dict[str, Any]]]:
    current = float(starting_value or 0)
    target_key = normalize_stat_key(target)
    target_operations = [operation for operation in operations if operation.target == target_key]
    applied: list[dict[str, Any]] = []

    for operation_name in OPERATION_ORDER:
        for operation in [item for item in target_operations if item.operation == operation_name]:
            if not condition_matches(operation.condition, contexts):
                continue
            value = evaluate_number(operation.value, contexts)
            before = current
            if operation_name == "add":
                current += value
            elif operation_name == "subtract":
                current -= value
            elif operation_name == "multiply":
                current *= value
            elif operation_name == "percent":
                current *= 1 + (value / 100)
            elif operation_name == "min":
                current = max(current, value)
            elif operation_name in {"max", "cap"}:
                current = min(current, value)
            elif operation_name == "set":
                current = value
            applied.append(
                {
                    "target": target_key,
                    "operation": operation_name,
                    "value": normalize_number(value),
                    "before": normalize_number(before),
                    "after": normalize_number(current),
                    "source": operation.source,
                    "order": operation.order,
                }
            )

    return current, applied


def apply_strong_set_operations(
    totals: Mapping[str, Any],
    operations: Iterable[CalculationOperation],
    *,
    base: Mapping[str, Any] | None = None,
    pre: Mapping[str, Any] | None = None,
    personaggio: Any | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply terminal overrides after fatigue, general modifiers and final rounding."""
    updated = dict(totals)
    personaggio_context = build_personaggio_context(personaggio)
    applied: dict[str, list[dict[str, Any]]] = {}

    for operation in sorted(
        (item for item in operations if item.operation == "strong_set"),
        key=lambda item: item.order,
    ):
        contexts = {
            "base": base or updated,
            "pre": pre or updated,
            "final": updated,
            "personaggio": personaggio_context,
        }
        if not condition_matches(operation.condition, contexts):
            continue
        before = float(updated.get(operation.target, 0) or 0)
        value = evaluate_number(operation.value, contexts)
        updated[operation.target] = normalize_number(value)
        applied.setdefault(operation.target, []).append(
            {
                "target": operation.target,
                "operation": "strong_set",
                "value": normalize_number(value),
                "before": normalize_number(before),
                "after": normalize_number(value),
                "source": operation.source,
                "order": operation.order,
            }
        )

    return updated, {"applied": applied}


def merge_strong_set_report(
    breakdown: dict[str, Any],
    report: Mapping[str, Any],
) -> None:
    """Expose terminal overrides alongside normal operations and modified-stat reports."""
    breakdown["strong_set_adjustment"] = dict(report)
    applied = report.get("applied") if isinstance(report, Mapping) else {}
    if not isinstance(applied, Mapping):
        return
    operation_report = breakdown.setdefault("applied_operations", {})
    modified_report = breakdown.setdefault("modified_stats", {})
    for target, operations in applied.items():
        if not isinstance(operations, list) or not operations:
            continue
        operation_report.setdefault(target, []).extend(operations)
        modified_report.setdefault(target, []).extend(
            {"kind": "operation", **operation}
            for operation in operations
        )


def resolve_formula_override_records(overrides: Iterable[FormulaOverride]) -> dict[str, FormulaOverride]:
    resolved: dict[str, FormulaOverride] = {}
    for override in sorted(overrides, key=lambda item: item.order):
        resolved[override.target] = override
    return resolved


def resolve_formula_overrides(overrides: Iterable[FormulaOverride]) -> dict[str, str]:
    return {
        target: override.formula
        for target, override in resolve_formula_override_records(overrides).items()
    }


def build_modified_stats_report(
    applied_operations: Mapping[str, list[dict[str, Any]]],
    resolved_formula_overrides: Mapping[str, FormulaOverride],
) -> dict[str, list[dict[str, Any]]]:
    modified: dict[str, list[dict[str, Any]]] = {}

    for stat, operations in applied_operations.items():
        if not operations:
            continue
        modified.setdefault(stat, []).extend(
            {
                "kind": "operation",
                **operation,
            }
            for operation in operations
        )

    for stat, override in resolved_formula_overrides.items():
        modified.setdefault(stat, []).append(
            {
                "kind": "formula_override",
                "target": stat,
                "formula": override.formula,
                "source": override.source,
                "order": override.order,
            }
        )

    return {stat: modified[stat] for stat in sorted(modified)}


def calculate_personaggio_totals(
    *,
    global_values: Mapping[str, Any],
    global_strings: Mapping[str, Any] | None = None,
    personaggio: Any | None = None,
    effect_payloads: Iterable[Any] | None = None,
    apply_quick_stats: bool = True,
) -> CalculationResult:
    base = build_base_values(global_values)
    pre = build_pre_snapshot(base)
    personaggio_context = build_personaggio_context(personaggio)
    collected = collect_calculation_effects(effect_payloads or [])
    formulas = extract_formula_map(global_strings or {})
    resolved_formula_overrides = resolve_formula_override_records(collected.formula_overrides)
    custom_overrides = {
        target: override.formula
        for target, override in resolved_formula_overrides.items()
    }
    formulas.update(custom_overrides)

    totals = default_personaggio_tot()
    final: dict[str, Any] = {}
    applied_operations: dict[str, list[dict[str, Any]]] = {}

    char_contexts = {"base": base, "pre": pre, "final": {}, "personaggio": personaggio_context}
    for stat in CHARACTERISTICS:
        value, applied = apply_operations(stat, base.get(stat, 0), collected.operations, char_contexts)
        totals[stat] = normalize_number(value)
        final[stat] = totals[stat]
        if applied:
            applied_operations[stat] = applied

    characteristic_adjustments = apply_characteristic_adjustments(
        final,
        base=base,
        pre=pre,
        personaggio_context=personaggio_context,
        value_string=global_strings,
    )
    characteristic_rounding: dict[str, dict[str, int | float]] = {}
    for stat in CHARACTERISTICS:
        before_rounding = float(final.get(stat, 0) or 0)
        rounded = math.floor(before_rounding)
        final[stat] = rounded
        totals[stat] = rounded
        characteristic_rounding[stat] = {
            "before": _normalized_calculation_number(before_rounding),
            "after": rounded,
        }

    final.update(calculate_characteristic_modifiers(final))
    for modifier_key in calculate_characteristic_modifiers(final):
        totals[modifier_key] = final[modifier_key]

    pre_formula_contexts = {"base": base, "pre": pre, "final": final, "personaggio": personaggio_context}
    for stat in PRE_FORMULA_BASE_STATS:
        value, applied = apply_operations(stat, base.get(stat, 0), collected.operations, pre_formula_contexts)
        totals[stat] = normalize_number(value)
        final[stat] = totals[stat]
        if applied:
            applied_operations[stat] = applied

    for stat in DERIVED_STAT_ORDER:
        formula = formulas.get(stat)
        contexts = {"base": base, "pre": pre, "final": final, "personaggio": personaggio_context}
        if formula:
            value = evaluate_number(formula, contexts)
        else:
            value = base.get(stat, 0)
        value, applied = apply_operations(stat, value, collected.operations, contexts)
        totals[stat] = normalize_number(value)
        final[stat] = totals[stat]
        if applied:
            applied_operations[stat] = applied

    quick_stat_report: dict[str, Any] = {}
    strong_set_report: dict[str, Any] = {"applied": {}}
    if apply_quick_stats:
        totals, quick_stat_report = apply_quick_stat_adjustment(totals, global_strings)

        totals, strong_set_report = apply_strong_set_operations(
            totals,
            collected.operations,
            base=base,
            pre=pre,
            personaggio=personaggio,
        )
        for target, operations in strong_set_report["applied"].items():
            applied_operations.setdefault(target, []).extend(operations)

        totals, action_point_minimum_report = apply_action_point_minimum(totals)
    else:
        action_point_minimum_report = {}

    return CalculationResult(
        totals=totals,
        breakdown={
            "profile": DEFAULT_PROFILE_NAME,
            "base": {key: normalize_number(value) for key, value in base.items()},
            "pre": pre,
            "formulas": formulas,
            "formula_overrides": [
                {
                    "target": override.target,
                    "formula": override.formula,
                    "source": override.source,
                    "order": override.order,
                    "active": resolved_formula_overrides.get(override.target) == override,
                }
                for override in collected.formula_overrides
            ],
            "resolved_formula_overrides": {
                target: {
                    "target": target,
                    "formula": override.formula,
                    "source": override.source,
                    "order": override.order,
                }
                for target, override in sorted(resolved_formula_overrides.items())
            },
            "custom_overrides": custom_overrides,
            "applied_operations": applied_operations,
            "characteristic_adjustments": characteristic_adjustments,
            "characteristic_rounding": characteristic_rounding,
            "quick_stat_adjustment": quick_stat_report,
            "strong_set_adjustment": strong_set_report,
            "action_point_minimum": action_point_minimum_report,
            "modified_stats": build_modified_stats_report(applied_operations, resolved_formula_overrides),
            "warnings": collected.warnings,
        },
    )


def _default_profile_values(profile_name: str) -> dict[str, Any]:
    for profile in V2_GLOBAL_MODIFIERS_DEFAULTS:
        if profile["name"] == profile_name:
            return copy.deepcopy(profile)
    return {
        "name": profile_name,
        "value_float": {},
        "value_string": {},
        "rule_notes": "",
    }


def _has_placeholder_base_values(value_float: Mapping[str, Any]) -> bool:
    sentinel_keys = ("forza", "resistenza", "pf", "mana", "attacco", "difesa", "mod_carico")
    for key in sentinel_keys:
        try:
            if float(value_float.get(key, 0) or 0) != 0:
                return False
        except (TypeError, ValueError):
            return False
    return True


def get_or_create_global_profile(profile_name: str = DEFAULT_PROFILE_NAME) -> GlobalModifiers:
    defaults = _default_profile_values(profile_name)
    profile, created = GlobalModifiers.objects.get_or_create(
        name=profile_name,
        defaults={
            "value_float": defaults.get("value_float", {}),
            "value_string": defaults.get("value_string", {}),
            "rule_notes": defaults.get("rule_notes", ""),
        },
    )
    if created:
        return profile

    changed = False
    value_float = profile.value_float if isinstance(profile.value_float, dict) else {}
    value_string = profile.value_string if isinstance(profile.value_string, dict) else {}
    if profile_name == DEFAULT_PROFILE_NAME and _has_placeholder_base_values(value_float):
        value_float = copy.deepcopy(defaults.get("value_float", {}))
        changed = True
    for key, value in defaults.get("value_float", {}).items():
        if key not in value_float:
            value_float[key] = value
            changed = True
    for key, value in defaults.get("value_string", {}).items():
        if key not in value_string:
            value_string[key] = value
            changed = True
    if not profile.rule_notes and defaults.get("rule_notes"):
        profile.rule_notes = defaults["rule_notes"]
        changed = True
    if changed:
        profile.value_float = value_float
        profile.value_string = value_string
        profile.save(update_fields=["value_float", "value_string", "rule_notes", "updated_at"])
    return profile


def collect_personaggio_effect_payloads(personaggio: Personaggio) -> list[Any]:
    payloads: list[Any] = []

    has_imported_racial_abilities = any(
        isinstance(ownership.metadata, dict) and ownership.metadata.get("source") == "race.auto"
        for ownership in personaggio.skill_sbloccate.all()
    )
    if not has_imported_racial_abilities:
        for automatic_effect in automatic_race_effects(personaggio.razza_1, personaggio.razza_2):
            if automatic_effect["payload"]:
                payloads.append(
                    {
                        "source": f"effetti.automatici.{automatic_effect['key']}",
                        "effect_payload": automatic_effect["payload"],
                    }
                )

    equip = getattr(personaggio, "equip", None)
    if equip is not None:
        from .inventory_rules import active_weapon_slot, equipment_dual_wield

        dual_wield = equipment_dual_wield(equip)
        primary_slot = active_weapon_slot(equip)
        for field_info in equip._meta.get_fields():
            if not isinstance(field_info, ForeignKey) or field_info.related_model is not Oggetto:
                continue
            item = getattr(equip, field_info.name, None)
            if item is None:
                continue
            if dual_wield and field_info.name in {"arma", "scudo"} and field_info.name != primary_slot:
                continue
            effects = getattr(item, "effects", None)
            if effects:
                payloads.append({"source": f"equip.{field_info.name}:{item.nome}", "effects": effects})

    effetti = getattr(personaggio, "effetti", None)
    if effetti is not None:
        for field_info in effetti._meta.get_fields():
            if not isinstance(field_info, ForeignKey) or field_info.related_model is not Effetto:
                continue
            effetto = getattr(effetti, field_info.name, None)
            if effetto is None or not effetto.effect_payload:
                continue
            payloads.append(
                {
                    "source": f"effetti.{field_info.name}:{effetto.nome}",
                    "effect_payload": effetto.effect_payload,
                }
            )

    for custom_effect in personaggio.effetti_personalizzati.all():
        operations = []
        for custom_operation in custom_effect.operazioni.all():
            operation = {
                "target": custom_operation.bersaglio,
                "operation": custom_operation.operazione,
                "value": custom_operation.valore,
            }
            if custom_operation.condizione:
                operation["condition"] = custom_operation.condizione
            operations.append(operation)
        if operations:
            origin = f" ({custom_effect.origine})" if custom_effect.origine else ""
            payloads.append(
                {
                    "source": f"effetti.personalizzati.{custom_effect.id}:{custom_effect.nome}{origin}",
                    "effects": operations,
                }
            )
    return payloads


def _equipment_rule_key(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").casefold())
    normalized = "".join(character for character in normalized if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")


def _item_rule_values(item: Oggetto | None) -> set[str]:
    if item is None:
        return set()
    values = {
        _equipment_rule_key(value)
        for value in (
            item.tipo_1,
            item.tipo_2,
            item.tipo_3,
            item.tipo_4,
        )
        if value
    }
    weapon_type = getattr(item, "tipo_arma", None)
    if weapon_type is not None:
        values.update(
            _equipment_rule_key(value)
            for value in (
                weapon_type.nome,
                weapon_type.lunghezza,
                weapon_type.potenza,
                weapon_type.bonus_1,
                weapon_type.bonus_2,
            )
            if value
        )
        rules = weapon_type.rules if isinstance(weapon_type.rules, Mapping) else {}
        values.update(_equipment_rule_key(value) for value in rules.values() if isinstance(value, str))
    profile = item.weapon_profile if isinstance(item.weapon_profile, Mapping) else {}
    values.update(_equipment_rule_key(value) for value in profile.values() if isinstance(value, str))
    return {value for value in values if value}


def _real_equipped_item(item: Oggetto | None) -> Oggetto | None:
    return None if item is None or "placeholder" in _item_rule_values(item) else item


def apply_equipment_specializations(
    totals: Mapping[str, Any],
    personaggio: Personaggio,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply Elder's equipment-conditional skill totals to the active sheet values.

    The specialized totals stay visible for future combat consumers. The current
    equipped weapon, armor and shield also project them into Attacco, Difesa and
    Tier, so changing equipment immediately removes the old contribution.
    """

    updated = dict(totals)
    from .inventory_rules import active_equipped_weapon, item_is_weapon, item_weapon_profile

    equip = getattr(personaggio, "equip", None)
    weapon = _real_equipped_item(active_equipped_weapon(equip)) if equip else None
    armor = _real_equipped_item(getattr(equip, "armatura", None)) if equip else None
    shield_candidate = _real_equipped_item(getattr(equip, "scudo", None)) if equip else None
    shield = None if shield_candidate and item_is_weapon(shield_candidate) else shield_candidate
    weapon_values = _item_rule_values(weapon)
    armor_values = _item_rule_values(armor)

    attack_targets: list[str] = []
    tier_targets: list[str] = []
    if weapon is None or weapon_values & {"maninude", "mani_nude", "unarmed"}:
        attack_targets.append("atk_skill_maninude")
        tier_targets.append("tier_skill_maninude")
    else:
        profile = item_weapon_profile(weapon)
        length = _equipment_rule_key(
            profile.get("length") or getattr(getattr(weapon, "tipo_arma", None), "lunghezza", "")
        )
        power = _equipment_rule_key(
            profile.get("power") or getattr(getattr(weapon, "tipo_arma", None), "potenza", "")
        )
        length_target = {
            "corta": "atk_skill_corte",
            "corto": "atk_skill_corte",
            "short": "atk_skill_corte",
            "media": "atk_skill_medie1",
            "medio": "atk_skill_medie1",
            "lunga": "atk_skill_lunghe",
            "lungo": "atk_skill_lunghe",
            "long": "atk_skill_lunghe",
        }.get(length)
        if length_target:
            attack_targets.append(length_target)
        power_target = {
            "precisa": "atk_skill_precise",
            "preciso": "atk_skill_precise",
            "precisione": "atk_skill_precise",
            "media": "atk_skill_medie2",
            "medio": "atk_skill_medie2",
            "bilanciata": "atk_skill_medie2",
            "bilanciato": "atk_skill_medie2",
            "potente": "atk_skill_potenti",
            "alta": "atk_skill_potenti",
            "alto": "atk_skill_potenti",
            "pesante": "atk_skill_potenti",
        }.get(power)
        if power_target:
            attack_targets.append(power_target)
        damage = _equipment_rule_key(profile.get("damageType"))
        damage_target = {
            "perforante": "atk_skill_perforante",
            "taglio": "atk_skill_taglio",
            "contundente": "atk_skill_contundente",
        }.get(damage)
        if damage_target:
            attack_targets.append(damage_target)
        elif not damage:
            # Old items may have no structured damage type. Preserve support for
            # their exact legacy tags, but never let those tags override a saved
            # weapon profile.
            for trait, target in (
                ("taglio", "atk_skill_taglio"),
                ("contundente", "atk_skill_contundente"),
                ("perforante", "atk_skill_perforante"),
            ):
                if trait in weapon_values:
                    attack_targets.append(target)

        if not power:
            # A type-less legacy item can still declare its power as a plain
            # classification tag. Structured profile/type power wins whenever
            # it exists, so stale TipoArma data cannot add a second category.
            for trait, target in (
                ("precisa", "atk_skill_precise"),
                ("preciso", "atk_skill_precise"),
                ("bilanciata", "atk_skill_medie2"),
                ("bilanciato", "atk_skill_medie2"),
                ("potente", "atk_skill_potenti"),
            ):
                if trait in weapon_values:
                    attack_targets.append(target)

    defense_targets: list[str] = []
    if armor is None:
        defense_targets.append("def_skill_noarmatura")
    elif armor_values & {"leggera", "leggero", "light"}:
        defense_targets.append("def_skill_leggera")
    elif armor_values & {"pesante", "heavy"}:
        defense_targets.append("def_skill_pesante")
    if shield is not None:
        defense_targets.append("def_skill_scudo")

    attack_targets = list(dict.fromkeys(attack_targets))
    defense_targets = list(dict.fromkeys(defense_targets))
    tier_targets = list(dict.fromkeys(tier_targets))
    attack_bonus = sum(float(updated.get(target, 0) or 0) for target in attack_targets)
    defense_bonus = sum(float(updated.get(target, 0) or 0) for target in defense_targets)
    tier_bonus = sum(float(updated.get(target, 0) or 0) for target in tier_targets)
    updated["attacco"] = normalize_number(float(updated.get("attacco", 0) or 0) + attack_bonus)
    updated["difesa"] = normalize_number(float(updated.get("difesa", 0) or 0) + defense_bonus)
    updated["tier"] = normalize_number(float(updated.get("tier", 0) or 0) + tier_bonus)
    return updated, {
        "weapon": weapon.nome if weapon else "",
        "armor": armor.nome if armor else "",
        "shield": shield.nome if shield else "",
        "attackTargets": attack_targets,
        "defenseTargets": defense_targets,
        "tierTargets": tier_targets,
        "attackBonus": normalize_number(attack_bonus),
        "defenseBonus": normalize_number(defense_bonus),
        "tierBonus": normalize_number(tier_bonus),
    }


@transaction.atomic
def refresh_personaggio(
    personaggio: int | Personaggio,
    *,
    profile_name: str = DEFAULT_PROFILE_NAME,
) -> CalculationResult:
    personaggio_id = personaggio.pk if isinstance(personaggio, Personaggio) else personaggio
    locked_personaggio = (
        Personaggio.objects.select_for_update()
        .select_related("equip", "effetti")
        .prefetch_related("effetti_personalizzati__operazioni", "skill_sbloccate__skill")
        .get(pk=personaggio_id)
    )
    from backend.core.skill_services import sync_automatic_racial_skills

    if sync_automatic_racial_skills(locked_personaggio):
        locked_personaggio._prefetched_objects_cache.pop("effetti_personalizzati", None)
        locked_personaggio._prefetched_objects_cache.pop("skill_sbloccate", None)
    profile = get_or_create_global_profile(profile_name)
    profile_values = dict(profile.value_float or {})
    character_values = locked_personaggio.extra if isinstance(locked_personaggio.extra, dict) else {}
    for stat in PRE_FORMULA_BASE_STATS:
        if stat in character_values:
            profile_values[stat] = character_values[stat]
    try:
        fatigue_base = float(profile_values.get("stanchezza", 0) or 0)
    except (TypeError, ValueError):
        fatigue_base = 0
    profile_values["stanchezza"] = fatigue_base + int(locked_personaggio.stanchezza_accumulata or 0)
    effect_payloads = collect_personaggio_effect_payloads(locked_personaggio)
    item_payloads = [
        payload
        for payload in effect_payloads
        if isinstance(payload, Mapping) and str(payload.get("source") or "").startswith("equip.")
    ]
    base_result = calculate_personaggio_totals(
        global_values=profile_values,
        global_strings=profile.value_string or {},
        personaggio=locked_personaggio,
        effect_payloads=[],
        apply_quick_stats=False,
    )
    item_result = calculate_personaggio_totals(
        global_values=profile_values,
        global_strings=profile.value_string or {},
        personaggio=locked_personaggio,
        effect_payloads=item_payloads,
        apply_quick_stats=False,
    )
    result = calculate_personaggio_totals(
        global_values=profile_values,
        global_strings=profile.value_string or {},
        personaggio=locked_personaggio,
        effect_payloads=effect_payloads,
        apply_quick_stats=False,
    )
    from .inventory_rules import apply_encumbrance, calculate_weight_breakdown

    base_result.totals = apply_encumbrance(base_result.totals, {"penalty": 0})
    item_weight_breakdown = calculate_weight_breakdown(locked_personaggio, item_result.totals)
    item_result.totals = apply_encumbrance(item_result.totals, item_weight_breakdown)
    weight_breakdown = calculate_weight_breakdown(locked_personaggio, result.totals)
    result.totals = apply_encumbrance(result.totals, weight_breakdown)
    for calculation_result in (base_result, item_result, result):
        calculation_result.totals, specialization_report = apply_equipment_specializations(
            calculation_result.totals,
            locked_personaggio,
        )
        calculation_result.breakdown["equipment_specializations"] = specialization_report
    base_before_quick_stats = dict(base_result.totals)
    items_before_quick_stats = dict(item_result.totals)
    final_before_quick_stats = dict(result.totals)
    base_result.totals, base_result.breakdown["quick_stat_adjustment"] = apply_quick_stat_adjustment(
        base_result.totals,
        profile.value_string,
    )
    item_result.totals, item_result.breakdown["quick_stat_adjustment"] = apply_quick_stat_adjustment(
        item_result.totals,
        profile.value_string,
    )
    result.totals, result.breakdown["quick_stat_adjustment"] = apply_quick_stat_adjustment(
        result.totals,
        profile.value_string,
    )
    for calculation_result, payloads in (
        (base_result, []),
        (item_result, item_payloads),
        (result, effect_payloads),
    ):
        collected = collect_calculation_effects(payloads)
        calculation_result.totals, strong_set_report = apply_strong_set_operations(
            calculation_result.totals,
            collected.operations,
            base=calculation_result.breakdown.get("base"),
            pre=calculation_result.breakdown.get("pre"),
            personaggio=locked_personaggio,
        )
        merge_strong_set_report(calculation_result.breakdown, strong_set_report)
        (
            calculation_result.totals,
            calculation_result.breakdown["action_point_minimum"],
        ) = apply_action_point_minimum(calculation_result.totals)
    result.breakdown["profile"] = profile.name
    result.breakdown["inventory_weight"] = weight_breakdown
    result.breakdown["calculation_sources"] = build_calculation_source_breakdown(
        base_before_quick_stats,
        items_before_quick_stats,
        final_before_quick_stats,
    )
    locked_personaggio.tot = result.totals
    locked_personaggio.effetti_finali = result.breakdown
    locked_personaggio.custom_overrides = result.breakdown["custom_overrides"]
    locked_personaggio.save(update_fields=["tot", "effetti_finali", "custom_overrides", "updated_at"])
    return result
