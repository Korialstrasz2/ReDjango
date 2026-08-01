"""Filter-and-transform batch editing for the item catalogue.

This is the ReDjango replacement for Elder Django's floating "Bulk edit
Oggetti" modal. The idea is the same — describe a set of rows with filters,
describe a transformation with actions, look at a preview, then commit — but
three things changed on purpose:

* every field, operator and choice list is declared here and served to the
  client, so the browser cannot ask for a column that is not editable in bulk;
* every computed row is validated by `clean_item_values`, the same function the
  single-item editor uses, so a batch cannot write a value the form would
  refuse;
* applying requires the token returned by the matching preview, so nobody
  commits a transformation they have not seen, and a catalogue that moved under
  the operator invalidates the run instead of silently editing different rows.

Structured columns (`effects`, the weapon/alchemy/crafting profiles, `media`,
`metadata`) are deliberately absent: they are nested documents, and a
find-and-replace over them would corrupt more than it fixes.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from backend.core.api import ApiError
from backend.core.item_services import (
    clean_item_values,
    refresh_characters_using_items,
    require_item_author,
    sync_special_rules_review,
)
from backend.core.models import Giocatore, Oggetto, OpzioneTipoOggetto, TipoArma


# Preview walks the whole match set so the operator sees a real "how many rows
# actually change" count rather than a count of rows that merely matched. The
# cap keeps an unfiltered run from evaluating the entire catalogue twice.
PREVIEW_SCAN_CAP = 3000
PREVIEW_SAMPLE_CAP = 200
ISSUE_CAP = 25


@dataclass(frozen=True)
class BulkField:
    name: str
    label: str
    kind: str
    group: str
    hint: str = ""
    type_position: int | None = None

    @property
    def column(self) -> str:
        return "tipo_arma_id" if self.name == "tipo_arma" else self.name

    @property
    def nullable(self) -> bool:
        """True when the column stores NULL for "no value", False when it stores ""."""
        return self.kind in {"integer", "number", "rarity", "weaponType"}


BULK_FIELDS: tuple[BulkField, ...] = (
    BulkField("nome", "Nome", "text", "Identità", "Deve restare unico: la modifica si ferma se due oggetti finiscono con lo stesso nome."),
    BulkField("icona", "Icona", "text", "Identità"),
    BulkField("numero_ordine", "Numero d'ordine", "integer", "Identità"),
    BulkField("modello", "Modello", "boolean", "Identità"),
    BulkField("temporaneo", "Temporaneo", "boolean", "Identità"),
    BulkField("archiviato", "Archiviato", "boolean", "Identità", "Allinea anche la data di archiviazione, come la casella dell'editor."),
    BulkField("speciale", "Speciale", "boolean", "Identità", "Il flag esclude l'oggetto da ogni negozio."),
    BulkField("descrizione", "Descrizione", "longText", "Identità"),
    BulkField("tipo_1", "Tipo 1", "itemType", "Classificazione", type_position=1),
    BulkField("tipo_2", "Tipo 2", "itemType", "Classificazione", type_position=2),
    BulkField("tipo_3", "Tipo 3", "itemType", "Classificazione", type_position=3),
    BulkField("tipo_4", "Tipo 4", "itemType", "Classificazione", type_position=4),
    BulkField("tipo_arma", "Tipo arma", "weaponType", "Classificazione"),
    BulkField("valore", "Valore", "integer", "Economia e loot"),
    BulkField("peso", "Peso", "number", "Economia e loot"),
    BulkField("rarita", "Rarità", "rarity", "Economia e loot"),
    BulkField("lv_loot", "Livello loot", "text", "Economia e loot"),
    BulkField("regione_loot", "Regione loot", "text", "Economia e loot"),
    BulkField("peso_regione", "Peso regione", "number", "Economia e loot"),
    BulkField("pa_per_attacco", "PA per attacco", "integer", "Economia e loot"),
    *(
        BulkField(f"effetto_{index}", f"Effetto Elder {index}", "text", "Effetti Elder e regole", "Massimo 255 caratteri.")
        for index in range(1, 9)
    ),
    BulkField("regole_speciali", "Regole speciali", "longText", "Effetti Elder e regole", "Scriverle dichiara riviste le voci Elder descrittive presenti in quel momento."),
    BulkField("notes", "Note", "longText", "Effetti Elder e regole"),
)

FIELDS_BY_NAME = {field.name: field for field in BULK_FIELDS}

TEXT_KINDS = {"text", "longText"}
NUMERIC_KINDS = {"integer", "number"}

FILTER_OPERATORS: dict[str, tuple[str, ...]] = {
    "text": ("eq", "ne", "icontains", "istartswith", "iendswith", "in", "empty", "notempty", "regex"),
    "longText": ("eq", "ne", "icontains", "istartswith", "iendswith", "in", "empty", "notempty", "regex"),
    "integer": ("eq", "ne", "lt", "lte", "gt", "gte", "in", "empty", "notempty"),
    "number": ("eq", "ne", "lt", "lte", "gt", "gte", "in", "empty", "notempty"),
    "boolean": ("eq",),
    "rarity": ("eq", "ne", "in", "empty", "notempty"),
    "itemType": ("eq", "ne", "icontains", "in", "empty", "notempty"),
    "weaponType": ("eq", "ne", "in", "empty", "notempty"),
}

OPERATOR_LABELS: dict[str, str] = {
    "eq": "è uguale a",
    "ne": "è diverso da",
    "lt": "è minore di",
    "lte": "è minore o uguale a",
    "gt": "è maggiore di",
    "gte": "è maggiore o uguale a",
    "icontains": "contiene",
    "istartswith": "inizia con",
    "iendswith": "finisce con",
    "in": "è uno di",
    "empty": "è vuoto",
    "notempty": "non è vuoto",
    "regex": "corrisponde alla regex",
}

VALUELESS_FILTER_OPERATORS = {"empty", "notempty"}

_LOOKUPS = {"eq": "", "lt": "__lt", "lte": "__lte", "gt": "__gt", "gte": "__gte", "icontains": "__icontains", "istartswith": "__istartswith", "iendswith": "__iendswith", "regex": "__regex"}

ACTION_OPERATORS: dict[str, tuple[str, ...]] = {
    "text": ("set", "append", "prepend", "replace", "regexReplace", "strip", "upper", "lower", "capitalize", "clear"),
    "longText": ("set", "append", "prepend", "replace", "regexReplace", "strip", "upper", "lower", "capitalize", "clear"),
    "integer": ("set", "inc", "dec", "mul", "div", "clear"),
    "number": ("set", "inc", "dec", "mul", "div", "clear"),
    "boolean": ("set", "toggle"),
    "rarity": ("set", "clear"),
    "itemType": ("set", "clear"),
    "weaponType": ("set", "clear"),
}

ACTION_LABELS: dict[str, str] = {
    "set": "imposta a",
    "append": "aggiungi in coda",
    "prepend": "aggiungi in testa",
    "replace": "sostituisci il testo",
    "regexReplace": "sostituisci con regex",
    "strip": "togli gli spazi ai lati",
    "upper": "rendi maiuscolo",
    "lower": "rendi minuscolo",
    "capitalize": "iniziale maiuscola",
    "clear": "svuota",
    "inc": "somma",
    "dec": "sottrai",
    "mul": "moltiplica per",
    "div": "dividi per",
    "toggle": "inverti",
}

VALUELESS_ACTION_OPERATORS = {"strip", "upper", "lower", "capitalize", "clear", "toggle"}
REPLACEMENT_ACTION_OPERATORS = {"replace", "regexReplace"}

ROUNDING_MODES: tuple[tuple[str, str], ...] = (
    ("keep", "Nessun arrotondamento"),
    ("round", "Arrotonda"),
    ("ceil", "Arrotonda per eccesso"),
    ("floor", "Arrotonda per difetto"),
    ("trunc", "Tronca"),
)


def _fail(code: str, message: str, field: str | None = None, status: int = 400) -> ApiError:
    return ApiError(code, message, field, status)


# ---------------------------------------------------------------- catalogue --


def bulk_field_catalog() -> dict[str, Any]:
    """Everything the browser needs to build the rows without hard-coding the schema."""
    type_options: dict[int, list[dict[str, str]]] = {}
    for option in OpzioneTipoOggetto.objects.filter(attiva=True, archived_at__isnull=True).order_by("posizione", "ordine", "etichetta", "valore"):
        type_options.setdefault(option.posizione, []).append({"value": option.valore, "label": option.label})
    weapon_choices = [{"value": str(weapon.id), "label": weapon.nome} for weapon in TipoArma.objects.filter(archived_at__isnull=True).order_by("nome")]
    rarity_choices = [{"value": str(value), "label": label} for value, label in Oggetto.Rarita.choices]

    def choices_for(field: BulkField) -> list[dict[str, str]]:
        if field.kind == "itemType":
            return type_options.get(field.type_position or 0, [])
        if field.kind == "weaponType":
            return weapon_choices
        if field.kind == "rarity":
            return rarity_choices
        if field.kind == "boolean":
            return [{"value": "true", "label": "Sì"}, {"value": "false", "label": "No"}]
        return []

    return {
        "fields": [
            {
                "name": field.name,
                "label": field.label,
                "kind": field.kind,
                "group": field.group,
                "hint": field.hint,
                "nullable": field.nullable,
                "choices": choices_for(field),
                "filterOperators": [{"value": operator, "label": OPERATOR_LABELS[operator]} for operator in FILTER_OPERATORS[field.kind]],
                "actionOperators": [{"value": operator, "label": ACTION_LABELS[operator]} for operator in ACTION_OPERATORS[field.kind]],
            }
            for field in BULK_FIELDS
        ],
        "valuelessFilterOperators": sorted(VALUELESS_FILTER_OPERATORS),
        "valuelessActionOperators": sorted(VALUELESS_ACTION_OPERATORS),
        "replacementActionOperators": sorted(REPLACEMENT_ACTION_OPERATORS),
        "roundingModes": [{"value": value, "label": label} for value, label in ROUNDING_MODES],
        "previewScanCap": PREVIEW_SCAN_CAP,
    }


# --------------------------------------------------------------- normalising --


def _normalise_filters(raw_filters: list[dict[str, Any]]) -> list[dict[str, str]]:
    filters: list[dict[str, str]] = []
    for index, entry in enumerate(raw_filters or []):
        name = str(entry.get("field") or "").strip()
        field = FIELDS_BY_NAME.get(name)
        if field is None:
            raise _fail("items.bulk_field_unknown", f"Il campo «{name or '—'}» non è modificabile in blocco.", f"filters.{index}.field")
        operator = str(entry.get("operator") or "").strip()
        if operator not in FILTER_OPERATORS[field.kind]:
            raise _fail("items.bulk_operator_unknown", f"«{OPERATOR_LABELS.get(operator, operator or '—')}» non è un confronto valido per {field.label}.", f"filters.{index}.operator")
        value = "" if operator in VALUELESS_FILTER_OPERATORS else str(entry.get("value") if entry.get("value") is not None else "")
        if operator not in VALUELESS_FILTER_OPERATORS and not value.strip() and field.kind not in TEXT_KINDS:
            raise _fail("items.bulk_filter_value_required", f"Il filtro su {field.label} ha bisogno di un valore.", f"filters.{index}.value")
        filters.append({"field": field.name, "operator": operator, "value": value})
    return filters


def _normalise_actions(raw_actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw_actions or []):
        name = str(entry.get("field") or "").strip()
        field = FIELDS_BY_NAME.get(name)
        if field is None:
            raise _fail("items.bulk_field_unknown", f"Il campo «{name or '—'}» non è modificabile in blocco.", f"actions.{index}.field")
        if field.name in seen:
            raise _fail("items.bulk_action_duplicated", f"{field.label} compare in due modifiche: tienine una sola, altrimenti l'ordine deciderebbe il risultato.", f"actions.{index}.field")
        seen.add(field.name)
        operator = str(entry.get("operator") or "").strip()
        if operator not in ACTION_OPERATORS[field.kind]:
            raise _fail("items.bulk_operator_unknown", f"«{ACTION_LABELS.get(operator, operator or '—')}» non è una modifica valida per {field.label}.", f"actions.{index}.operator")
        value = "" if operator in VALUELESS_ACTION_OPERATORS else str(entry.get("value") if entry.get("value") is not None else "")
        if operator in {"inc", "dec", "mul", "div"}:
            # The operand is the same for every row, so a bad one is a mistake
            # in the recipe: catching it here reports it once against the
            # offending row of the form instead of once per catalogue item.
            if not value.strip():
                raise _fail("items.bulk_action_value_required", f"«{ACTION_LABELS[operator]}» su {field.label} ha bisogno di un numero.", f"actions.{index}.value")
            try:
                operand = float(value.strip())
            except ValueError as exc:
                raise _fail("items.bulk_action_value_invalid", f"«{ACTION_LABELS[operator]}» su {field.label} vuole un numero, non «{value}».", f"actions.{index}.value") from exc
            if operator == "div" and operand == 0:
                raise _fail("items.bulk_division_by_zero", f"Non posso dividere {field.label} per zero.", f"actions.{index}.value")
        if operator in REPLACEMENT_ACTION_OPERATORS and not value:
            raise _fail("items.bulk_action_value_required", f"Indica cosa cercare in {field.label}.", f"actions.{index}.value")
        replacement = str(entry.get("replacement") or "") if operator in REPLACEMENT_ACTION_OPERATORS else ""
        rounding = str(entry.get("rounding") or "keep").strip() or "keep"
        if rounding not in {mode for mode, _ in ROUNDING_MODES}:
            raise _fail("items.bulk_rounding_unknown", f"Arrotondamento «{rounding}» sconosciuto.", f"actions.{index}.rounding")
        try:
            decimals = max(0, min(6, int(entry.get("decimals") or 0)))
        except (TypeError, ValueError) as exc:
            raise _fail("items.bulk_rounding_invalid", "I decimali devono essere un numero intero.", f"actions.{index}.decimals") from exc
        if field.kind != "number":
            # Integer columns always land on a whole number and text columns
            # have nothing to round, so the option is dropped rather than kept
            # in the signed token where it would look meaningful.
            decimals = 0
        if operator == "regexReplace":
            try:
                re.compile(value)
            except re.error as exc:
                raise _fail("items.bulk_regex_invalid", f"Espressione regolare non valida: {exc}.", f"actions.{index}.value") from exc
        actions.append({
            "field": field.name,
            "operator": operator,
            "value": value,
            "replacement": replacement,
            "rounding": rounding,
            "decimals": decimals,
        })
    if not actions:
        raise _fail("items.bulk_actions_required", "Aggiungi almeno una modifica da applicare.", "actions")
    return actions


# ------------------------------------------------------------------ filtering --


def _filter_scalar(field: BulkField, raw: str) -> Any:
    text = raw.strip()
    if field.kind == "boolean":
        return text.casefold() in {"true", "1", "sì", "si", "yes"}
    if field.kind == "integer" or field.kind == "rarity" or field.kind == "weaponType":
        try:
            return int(float(text))
        except (TypeError, ValueError) as exc:
            raise _fail("items.bulk_filter_value_invalid", f"Il filtro su {field.label} vuole un numero intero, non «{text}».", "filters") from exc
    if field.kind == "number":
        try:
            return float(text)
        except (TypeError, ValueError) as exc:
            raise _fail("items.bulk_filter_value_invalid", f"Il filtro su {field.label} vuole un numero, non «{text}».", "filters") from exc
    return raw


def _empty_q(field: BulkField) -> Q:
    if field.nullable:
        return Q(**{f"{field.column}__isnull": True})
    return Q(**{field.column: ""})


def _filter_q(entry: dict[str, str]) -> Q:
    field = FIELDS_BY_NAME[entry["field"]]
    operator = entry["operator"]
    if operator == "empty":
        return _empty_q(field)
    if operator == "notempty":
        return ~_empty_q(field)
    if operator == "in":
        parts = [part.strip() for part in entry["value"].split(",")]
        values = [_filter_scalar(field, part) for part in parts if part]
        if not values:
            raise _fail("items.bulk_filter_value_required", f"L'elenco per {field.label} è vuoto.", "filters")
        return Q(**{f"{field.column}__in": values})
    value = _filter_scalar(field, entry["value"])
    if operator == "ne":
        return ~Q(**{field.column: value})
    return Q(**{f"{field.column}{_LOOKUPS[operator]}": value})


def _matching_queryset(filters: list[dict[str, str]]):
    query = Q()
    for entry in filters:
        query &= _filter_q(entry)
    return Oggetto.objects.filter(query).order_by("id")


# ---------------------------------------------------------------- transforming --


def _as_number(field: BulkField, raw: str) -> float:
    try:
        return float(raw.strip())
    except (TypeError, ValueError) as exc:
        raise _fail("items.bulk_action_value_invalid", f"La modifica su {field.label} vuole un numero, non «{raw}».", "actions") from exc


def _round(value: float, mode: str, decimals: int) -> float:
    factor = 10 ** decimals
    if mode == "ceil":
        return math.ceil(value * factor) / factor
    if mode == "floor":
        return math.floor(value * factor) / factor
    if mode == "trunc":
        return math.trunc(value * factor) / factor
    if mode == "round":
        # Half away from zero, not Python's banker's rounding: a price of 12.5
        # becoming 12 is the kind of surprise a batch edit must not produce.
        return math.floor(value * factor + .5) / factor if value >= 0 else -(math.floor(-value * factor + .5) / factor)
    return value


def _numeric_result(field: BulkField, action: dict[str, Any], current: Any) -> Any:
    operator = action["operator"]
    if operator == "clear":
        return None
    if operator == "set":
        if not action["value"].strip():
            return None
        result = _as_number(field, action["value"])
    else:
        base = float(current) if current is not None else 0.
        amount = _as_number(field, action["value"])
        if operator == "inc":
            result = base + amount
        elif operator == "dec":
            result = base - amount
        elif operator == "mul":
            result = base * amount
        else:
            if amount == 0:
                raise _fail("items.bulk_division_by_zero", f"Non posso dividere {field.label} per zero.", "actions")
            result = base / amount
    rounding = action["rounding"]
    if field.kind == "integer":
        # The column only stores whole numbers, so "nessun arrotondamento" has
        # to mean something: it means the same as "arrotonda".
        return int(_round(result, "round" if rounding == "keep" else rounding, 0))
    return _round(result, rounding, action["decimals"])


def _text_result(field: BulkField, action: dict[str, Any], current: Any) -> str:
    operator = action["operator"]
    text = "" if current is None else str(current)
    if operator == "clear":
        return ""
    if operator == "set":
        return action["value"]
    if operator == "append":
        return text + action["value"]
    if operator == "prepend":
        return action["value"] + text
    if operator == "replace":
        return text.replace(action["value"], action["replacement"])
    if operator == "regexReplace":
        try:
            return re.sub(action["value"], action["replacement"], text)
        except re.error as exc:
            raise _fail("items.bulk_regex_invalid", f"Espressione regolare non valida: {exc}.", "actions") from exc
    if operator == "strip":
        return text.strip()
    if operator == "upper":
        return text.upper()
    if operator == "lower":
        return text.lower()
    return text[:1].upper() + text[1:] if text else text


def _choice_result(field: BulkField, action: dict[str, Any]) -> Any:
    if action["operator"] == "clear" or not action["value"].strip():
        return None if field.nullable else ""
    if field.kind == "itemType":
        return action["value"].strip()
    return _filter_scalar(field, action["value"])


def _row_value(field: BulkField, action: dict[str, Any], item: Oggetto) -> Any:
    current = getattr(item, field.column)
    if field.kind == "boolean":
        return not bool(current)  # only `toggle` reaches here; `set` is constant
    if field.kind in NUMERIC_KINDS:
        return _numeric_result(field, action, current)
    return _text_result(field, action, current)


def _display(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if value is True:
        return "Sì"
    if value is False:
        return "No"
    return str(value)


# `set` and `clear` produce the same value for every row, so they are resolved
# and validated once instead of once per row. That matters: validating an item
# type hits `OpzioneTipoOggetto`, and doing it per row would mean one query per
# row per type field on a scan of thousands.
CONSTANT_OPERATORS = {"set", "clear"}


@dataclass
class CompiledPlan:
    """A recipe validated as far as it can be before any row is read."""

    constants: dict[str, Any]
    constant_weapon_type: int | None
    weapon_type_touched: bool
    dynamic: list[dict[str, Any]]


def compile_actions(actions: list[dict[str, Any]]) -> CompiledPlan:
    constants: dict[str, Any] = {}
    constant_weapon_type: int | None = None
    weapon_type_touched = False
    dynamic: list[dict[str, Any]] = []

    for action in actions:
        field = FIELDS_BY_NAME[action["field"]]
        if action["operator"] not in CONSTANT_OPERATORS:
            dynamic.append(action)
            continue
        if field.kind == "boolean":
            value: Any = action["value"].strip().casefold() in {"true", "1", "sì", "si", "yes"}
        elif field.kind in NUMERIC_KINDS:
            value = _numeric_result(field, action, None)
        elif field.kind in TEXT_KINDS:
            value = _text_result(field, action, None)
        else:
            value = _choice_result(field, action)
        if field.name == "tipo_arma":
            constant_weapon_type = value
            weapon_type_touched = True
        else:
            constants[field.name] = value

    # `clean_item_values` is the single-item editor's validator. Running the
    # constants through it here is what stops a batch from writing an item type
    # that is not configured, a rarity outside 0–5 or a negative weight, and it
    # normalises the value exactly as a form save would.
    constants = clean_item_values(constants, partial=True)
    if weapon_type_touched and constant_weapon_type is not None and not TipoArma.objects.filter(pk=constant_weapon_type).exists():
        raise _fail("items.bulk_weapon_type_unknown", f"Il tipo arma #{constant_weapon_type} non esiste.", "actions")
    return CompiledPlan(constants, constant_weapon_type, weapon_type_touched, dynamic)


@dataclass
class RowPlan:
    item: Oggetto
    changes: list[dict[str, Any]]
    values: dict[str, Any]
    weapon_type_id: int | None
    weapon_type_touched: bool


def _plan_row(item: Oggetto, plan: CompiledPlan) -> RowPlan:
    """Work out what this one row would become, and validate it like a form save."""
    computed = {action["field"]: _row_value(FIELDS_BY_NAME[action["field"]], action, item) for action in plan.dynamic}
    # Dynamic operators never apply to a choice field — those only offer `set`
    # and `clear` — so this pass validates lengths, numbers and the non-empty
    # name rule without touching the database.
    values = {**plan.constants, **clean_item_values(computed, partial=True)}

    changes = [
        {"field": name, "label": FIELDS_BY_NAME[name].label, "before": _display(getattr(item, name)), "after": _display(value)}
        for name, value in values.items()
        if getattr(item, name) != value
    ]
    if plan.weapon_type_touched and item.tipo_arma_id != plan.constant_weapon_type:
        changes.append({"field": "tipo_arma", "label": "Tipo arma", "before": _display(item.tipo_arma_id), "after": _display(plan.constant_weapon_type)})
    return RowPlan(item, changes, values, plan.constant_weapon_type, plan.weapon_type_touched)


def _operation_token(filters: list[dict[str, str]], actions: list[dict[str, Any]], total: int) -> str:
    raw = json.dumps({"filters": filters, "actions": actions, "total": total}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------- preview --

# Every column a plan reads. Preview never saves, so loading only these keeps
# the JSON blobs (`effects`, the three profiles) out of a several-thousand-row
# scan. Apply must not use it: `save()` skips deferred columns, and `updated_at`
# would stop moving.
_PLAN_COLUMNS = (
    "id", "nome", "icona", "numero_ordine", "modello", "temporaneo", "archiviato", "speciale",
    "descrizione", "tipo_1", "tipo_2", "tipo_3", "tipo_4", "tipo_arma_id", "valore", "peso", "rarita",
    "lv_loot", "regione_loot", "peso_regione", "pa_per_attacco",
    *(f"effetto_{index}" for index in range(1, 9)),
    "regole_speciali", "notes",
)


def _name_collisions(proposed: dict[str, list[int]]) -> list[str]:
    """Names that two edited rows would share, or that an untouched row already holds.

    Rows inside the batch are compared case-insensitively, because a `rendi
    minuscolo` on `nome` is exactly the kind of action that collapses two
    distinct names into one. The check against the rest of the catalogue stays
    an exact match: that is what `nome`'s unique constraint enforces, and an
    `iexact` sweep would need one clause per renamed row.
    """
    grouped: dict[str, tuple[str, list[int]]] = {}
    for name, ids in proposed.items():
        label, seen = grouped.get(name.casefold(), (name, []))
        grouped[name.casefold()] = (label, seen + ids)
    clashing = sorted(label for label, ids in grouped.values() if len(ids) > 1)
    if clashing:
        return clashing
    touched = [item_id for _, ids in grouped.values() for item_id in ids]
    return sorted(
        Oggetto.objects.exclude(id__in=touched)
        .filter(nome__in=list(proposed))
        .values_list("nome", flat=True)
    )


def preview_bulk_items(
    user,
    giocatore: Giocatore,
    raw_filters: list[dict[str, Any]],
    raw_actions: list[dict[str, Any]],
    *,
    limit: int = 25,
) -> dict[str, Any]:
    require_item_author(user, giocatore)
    filters = _normalise_filters(raw_filters)
    actions = _normalise_actions(raw_actions)
    compiled = compile_actions(actions)
    sample_size = max(1, min(int(limit or 25), PREVIEW_SAMPLE_CAP))

    queryset = _matching_queryset(filters)
    total = queryset.count()
    scanned = changed = 0
    sample: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    renamed: dict[str, list[int]] = {}

    for item in queryset.only(*_PLAN_COLUMNS)[:PREVIEW_SCAN_CAP].iterator(chunk_size=200):
        scanned += 1
        try:
            row = _plan_row(item, compiled)
        except ApiError as error:
            if len(issues) < ISSUE_CAP:
                issues.append({"id": item.id, "name": item.nome, "field": error.field or "", "message": error.message})
            continue
        if not row.changes:
            continue
        changed += 1
        if "nome" in row.values:
            renamed.setdefault(row.values["nome"], []).append(item.id)
        if len(sample) < sample_size:
            sample.append({"id": item.id, "name": item.nome, "changes": row.changes})

    for name in _name_collisions(renamed)[:ISSUE_CAP]:
        issues.append({"id": None, "name": name, "field": "nome", "message": f"Il nome «{name}» finirebbe su più di un oggetto."})

    return {
        "total": total,
        "scanned": scanned,
        # Beyond the cap nobody has seen the rows, but Apply re-plans and
        # validates the whole match set in one transaction, so the worst a
        # truncated preview can produce is a clean refusal, never a half-write.
        "truncated": scanned < total,
        "changed": changed,
        "sample": sample,
        "issues": issues,
        "filters": filters,
        "actions": actions,
        # A run with nothing to change, or with a problem in it, gets no token:
        # Apply stays unreachable until the operator fixes the recipe.
        "token": _operation_token(filters, actions, total) if changed and not issues else "",
    }


# ----------------------------------------------------------------------- apply --


@transaction.atomic
def apply_bulk_items(
    user,
    giocatore: Giocatore,
    raw_filters: list[dict[str, Any]],
    raw_actions: list[dict[str, Any]],
    token: str,
) -> dict[str, Any]:
    """Commit the transformation the matching preview described, or nothing at all.

    The whole run is one transaction and one validation pass: if a single row
    would fail, everything rolls back. A batch is not a place to discover that
    row 1400 was invalid after 1399 rows were already written.
    """
    require_item_author(user, giocatore)
    filters = _normalise_filters(raw_filters)
    actions = _normalise_actions(raw_actions)
    compiled = compile_actions(actions)

    # Counting on the plain queryset and locking only the row read: several
    # backends reject `SELECT COUNT(*) … FOR UPDATE`.
    queryset = _matching_queryset(filters)
    matched = queryset.count()
    if not token or token != _operation_token(filters, actions, matched):
        raise _fail(
            "items.bulk_token_stale",
            "L'anteprima non corrisponde più a questa modifica: i filtri sono cambiati oppure il catalogo si è mosso. Rilancia l'anteprima e riprova.",
            "token",
            409,
        )

    rows: list[RowPlan] = []
    renamed: dict[str, list[int]] = {}
    for item in queryset.select_for_update():
        row = _plan_row(item, compiled)
        if not row.changes:
            continue
        rows.append(row)
        if "nome" in row.values:
            renamed.setdefault(row.values["nome"], []).append(item.id)

    clashing = _name_collisions(renamed)
    if clashing:
        raise _fail(
            "items.duplicate_name",
            f"La modifica creerebbe nomi duplicati ({', '.join(clashing[:3])}). Nessun oggetto è stato toccato.",
            "nome",
            409,
        )

    for row in rows:
        item = row.item
        for name, value in row.values.items():
            setattr(item, name, value)
        if row.weapon_type_touched:
            item.tipo_arma_id = row.weapon_type_id
        # Both mirror `update_item`: the catalogue flag and the soft-delete
        # timestamp have to move together, and the rules text is what declares
        # the current Elder effects reviewed.
        if "archiviato" in row.values:
            item.archived_at = (item.archived_at or timezone.now()) if row.values["archiviato"] else None
        if "regole_speciali" in row.values:
            sync_special_rules_review(item)
        item.save()

    refreshed = refresh_characters_using_items(sorted(row.item.id for row in rows))
    return {"matched": matched, "updated": len(rows), "unchanged": matched - len(rows), "refreshedCharacters": refreshed}
