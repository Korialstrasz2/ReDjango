from __future__ import annotations

import re
import sqlite3
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.db import transaction
from django.db.models import ForeignKey, Q

from backend.characters.models import Equip, Faretra, Personaggio, Zaino
from backend.characters.services.custom_effects import effect_target_values
from backend.characters.services.refresh_personaggio import normalize_stat_key, refresh_personaggio
from backend.core.competence_defaults import COMPETENCE_DEFINITIONS
from backend.core.models import Oggetto, OpzioneTipoOggetto, TipoArma


SOURCE_PROJECT = "the_elder_django"
SOURCE_TABLE = "django_slim_oggetto"
EMPTY_VALUES = {"", "vuoto"}
PLACEHOLDER_RE = re.compile(r"^(?:vuoto|no\s|nessun[oa]?\s)", re.IGNORECASE)
NUMERIC_EFFECT_RE = re.compile(
    r"^(?:Personaggio\.)?([\w]+)\s*([+\-])\s*([+\-]?\d+(?:[.,]\d+)?)\s*$",
    re.IGNORECASE,
)
LEVEL_FORMULA_EFFECT_RE = re.compile(
    r"^(?:Personaggio\.)?(?P<target>[\w]+)\s*(?P<operation>[+\-])\s*"
    r"\(f\)\s*Personaggio\.livello\s*(?P<offset>[+\-]\s*\d+(?:[.,]\d+)?)?\s*$",
    re.IGNORECASE,
)
SIMPLE_BONUS_RE = re.compile(r"^(.+?)\s*([+\-])\s*([+\-]?\d+(?:[.,]\d+)?)\s*$")

# ReDjango intentionally merged the legacy Ordine/Caos ratios into one value.
# Item effects must apply that same mapping; otherwise valid bonuses
# remain inert only because they still use their historical target name.
# en_per_mana/pa_per_mana are not listed: Elder dropped their formulas in
# migration 0118 and nothing reads them, so those bonuses are simply skipped.
LEGACY_TARGET_ALIASES = {
    "ogni_en_x_mana_ordine": "ogni_en_x_mana",
    "ogni_en_x_mana_caos": "ogni_en_x_mana",
    "ogni_pa_x_mana_ordine": "ogni_pa_x_mana",
    "ogni_pa_x_mana_caos": "ogni_pa_x_mana",
}

# Current POC records have no Elder identity. These choices preserve the same
# practical category and, where possible, material/tier. They are intentionally
# explicit so the dry-run report is auditable and repeatable.
ASSIGNMENT_REPLACEMENTS = {
    "Lama corta da prova": 177,          # Spada lunga (ferro)
    "Martello della Guardia": 9,         # Martello (ferro)
    "Arco di betulla": 464,              # Arco corto (legno)
    "Armatura di cuoio rinforzato": 550, # Armatura (pelle)
    "Scudo tondo del confine": 565,      # Scudo (pelle)
    "Mantello dell'esploratore": 5853,   # Mantello da viaggio
    "Anello del sangue calmo": 644,      # Anello + pf lv. 1
    "Amuleto del focus chiaro": 3649,    # Amuleto + mana lv. 1
    "Cintura robusta": 4238,             # Cintura + pf lv. 1
    "Stivali leggeri": 595,              # Veste principiante (Al)
    "Faretra capiente": 5027,            # Faretra media
    "Pozione di cura minore": 4836,      # Pozione cura lv. 1
    "Sali di luna": 5041,                # Reagente Blu lv. 1
    "Kit da scasso": 5780,               # Set scassinamento base
    "Libro degli appunti": 5496,         # Libro principiante, alterazione
    "Tonico di energia": 5013,           # Pozione energia lv. 1
    "Pergamena di gelo": 5406,           # Pergamena distruzione minore lv. 1
    "Moneta antica": 5816,               # Monete
    "Freccia normale": 5049,
    "Sacca media": 5075,
}


def _normalized_label(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    return " ".join("".join(ch for ch in value if not unicodedata.combining(ch)).split())


COMPETENCE_TARGETS = {
    _normalized_label(str(definition["name"])): f"competenza.{definition['key']}"
    for definition in COMPETENCE_DEFINITIONS
}

# Elder consistently doubles the m in Camuffare — in the effect text and in the
# `+skillcammuffare` type tag alike. Without this spelling, the 20th of the 21
# competences is the only one whose item bonuses never import.
COMPETENCE_TARGETS["cammuffare"] = "competenza.camuffare"


def clean_legacy_value(value: Any) -> str:
    cleaned = str(value or "").strip()
    return "" if cleaned.casefold() in EMPTY_VALUES else cleaned


def _number(value: str) -> int | float:
    parsed = float(value.replace(",", "."))
    return int(parsed) if parsed.is_integer() else parsed


def _target(raw_target: str) -> str:
    return LEGACY_TARGET_ALIASES.get(normalize_stat_key(raw_target), normalize_stat_key(raw_target))


def convert_effect(raw: Any) -> dict[str, Any] | None:
    """Convert only effects with exact, calculable semantics.

    Descriptive/timed/boolean Elder rules remain in effetto_N for human review;
    guessing would silently alter game behaviour.
    """
    text = clean_legacy_value(raw)
    if not text:
        return None
    match = NUMERIC_EFFECT_RE.fullmatch(text)
    if match:
        raw_target, sign, raw_value = match.groups()
        target = _target(raw_target)
        if target in effect_target_values():
            value = _number(raw_value)
            if value < 0:
                sign = "+" if sign == "-" else "-"
                value = abs(value)
            return {
                "target": target,
                "operation": "add" if sign == "+" else "subtract",
                "value": value,
                "source": "elder_import",
            }
    match = LEVEL_FORMULA_EFFECT_RE.fullmatch(text)
    if match:
        target = _target(match.group("target"))
        if target in effect_target_values():
            offset = (match.group("offset") or "").replace(",", ".")
            expression = "personaggio.livello" + (
                f" {offset.strip()[0]} {offset.strip()[1:].strip()}" if offset else ""
            )
            return {
                "target": target,
                "operation": "add" if match.group("operation") == "+" else "subtract",
                "value": expression,
                "source": "elder_import",
            }
    match = SIMPLE_BONUS_RE.fullmatch(text)
    if match:
        raw_label, sign, raw_value = match.groups()
        target = COMPETENCE_TARGETS.get(_normalized_label(raw_label))
        if target:
            value = _number(raw_value)
            if value < 0:
                sign = "+" if sign == "-" else "-"
                value = abs(value)
            return {
                "target": target,
                "operation": "add" if sign == "+" else "subtract",
                "value": value,
                "source": "elder_import",
            }
    return None


@dataclass
class ImportPlan:
    rows: list[dict[str, Any]]
    skipped: list[dict[str, Any]]
    type_options: dict[int, list[str]]
    source_names: dict[int, str]
    converted_effects: int
    retained_effects: int
    special_items: int
    assignments: list[dict[str, Any]]


def read_plan(source_db: Path) -> ImportPlan:
    source_db = source_db.resolve(strict=True)
    connection = sqlite3.connect(f"file:{source_db.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        source_rows = [dict(row) for row in connection.execute(f"SELECT * FROM {SOURCE_TABLE} ORDER BY id")]
        source_weapon_names = {
            int(row["id"]): str(row["nome"]).strip()
            for row in connection.execute("SELECT id, nome FROM django_slim_tipo_arma")
        }
    finally:
        connection.close()

    skipped = [row for row in source_rows if PLACEHOLDER_RE.match(str(row.get("nome") or "").strip())]
    rows = [row for row in source_rows if row not in skipped]
    source_names = {int(row["id"]): str(row["nome"]).strip() for row in rows}
    for old_name, source_id in ASSIGNMENT_REPLACEMENTS.items():
        if source_id not in source_names:
            raise ValueError(f"Replacement {source_id} for {old_name!r} is missing from Elder data.")

    # Merge only case variants. The title-cased spelling wins for Extra/extra;
    # otherwise the most frequent original spelling is retained.
    canonical: dict[tuple[int, str], str] = {}
    type_options: dict[int, list[str]] = {}
    for position in range(1, 5):
        values = [clean_legacy_value(row.get(f"tipo_{position}")) for row in rows]
        counts = Counter(value for value in values if value)
        grouped: dict[str, list[str]] = {}
        for value in counts:
            grouped.setdefault(value.casefold(), []).append(value)
        chosen = []
        for folded, spellings in grouped.items():
            value = "Extra" if folded == "extra" else max(spellings, key=lambda entry: (counts[entry], entry))
            canonical[(position, folded)] = value
            chosen.append(value)
        type_options[position] = sorted(chosen, key=lambda entry: entry.casefold())

    weapon_types = {entry.nome.casefold(): entry for entry in TipoArma.objects.all()}
    converted_total = retained_total = special_total = 0
    prepared: list[dict[str, Any]] = []
    for row in rows:
        raw_effects = [clean_legacy_value(row.get(f"effetto_{index}")) for index in range(1, 9)]
        structured = [converted for raw in raw_effects if (converted := convert_effect(raw))]
        retained = [raw for raw in raw_effects if raw and convert_effect(raw) is None]
        converted_total += len(structured)
        retained_total += len(retained)
        types = []
        for position in range(1, 5):
            value = clean_legacy_value(row.get(f"tipo_{position}"))
            types.append(canonical.get((position, value.casefold()), value) if value else "")
        reasons = []
        if not bool(row.get("modello")):
            reasons.append("non_modello")
        if bool(row.get("temporaneo")):
            reasons.append("temporaneo")
        if retained:
            reasons.append("effetti_descrittivi")
        if not types[0]:
            reasons.append("tipo_1_vuoto")
        speciale = bool(reasons)
        special_total += int(speciale)
        source_weapon_name = source_weapon_names.get(int(row.get("tipo_arma_id") or 0), "")
        weapon_type = weapon_types.get(source_weapon_name.casefold())
        values = {
            "nome": str(row["nome"]).strip(),
            "modello": bool(row.get("modello")),
            "temporaneo": bool(row.get("temporaneo")),
            "archiviato": bool(row.get("archiviato")),
            "speciale": speciale,
            "numero_ordine": row.get("numero_ordine"),
            "icona": clean_legacy_value(row.get("icona")),
            **{f"tipo_{index}": types[index - 1] for index in range(1, 5)},
            "descrizione": clean_legacy_value(row.get("descrizione")),
            "valore": row.get("valore"),
            "peso": row.get("peso"),
            "rarita": None if row.get("rarita") is None else int(row["rarita"]),
            "lv_loot": clean_legacy_value(row.get("lv_loot")),
            "regione_loot": clean_legacy_value(row.get("regione")),
            "peso_regione": row.get("peso_regione"),
            "tipo_arma": weapon_type,
            "pa_per_attacco": row.get("pa_per_attacco"),
            **{f"effetto_{index}": raw_effects[index - 1] for index in range(1, 9)},
            "effects": structured,
            "metadata": {
                "sourceProject": SOURCE_PROJECT,
                "sourceTable": SOURCE_TABLE,
                "sourceId": int(row["id"]),
                "effectConversion": {
                    "converted": len(structured),
                    "retainedForReview": len(retained),
                },
                "specialReasons": reasons,
            },
        }
        prepared.append(values)

    assignments = snapshot_assignments()
    missing = sorted({
        entry["oldName"] for entry in assignments
        if entry.get("sourceId") is None and entry["oldName"] not in ASSIGNMENT_REPLACEMENTS
    })
    if missing:
        raise ValueError(f"No deterministic Elder replacement for assigned items: {', '.join(missing)}")
    return ImportPlan(prepared, skipped, type_options, source_names, converted_total, retained_total, special_total, assignments)


def _item_fields(model) -> list[ForeignKey]:
    return [
        field for field in model._meta.fields
        if isinstance(field, ForeignKey) and field.remote_field.model is Oggetto
    ]


def snapshot_assignments() -> list[dict[str, Any]]:
    result = []
    for model in (Equip, Zaino, Faretra):
        fields = _item_fields(model)
        for record in model.objects.all():
            for field in fields:
                item = getattr(record, field.name)
                if item is not None:
                    metadata = item.metadata if isinstance(item.metadata, dict) else {}
                    source_id = (
                        int(metadata["sourceId"])
                        if metadata.get("sourceProject") == SOURCE_PROJECT and metadata.get("sourceId") is not None
                        else None
                    )
                    result.append({
                        "model": model,
                        "recordId": record.pk,
                        "field": field.name,
                        "oldName": item.nome,
                        "sourceId": source_id,
                    })
    return result


def repair_imported_item_effects(*, apply: bool = False) -> dict[str, int]:
    """Backfill only safely convertible legacy effects into existing imported items.

    This deliberately adds missing structured effects rather than replacing the
    catalogue or removing existing effects. It is therefore safe for an already
    edited ReDjango database.
    """
    scanned = needing_repair = effects_to_add = 0
    changed_item_ids: list[int] = []
    imported_items = Oggetto.objects.filter(
        metadata__sourceProject=SOURCE_PROJECT,
        metadata__sourceTable=SOURCE_TABLE,
    )
    for item in imported_items:
        scanned += 1
        raw_effects = [clean_legacy_value(getattr(item, f"effetto_{index}")) for index in range(1, 9)]
        converted = [effect for raw in raw_effects if (effect := convert_effect(raw))]
        retained = [raw for raw in raw_effects if raw and convert_effect(raw) is None]
        existing = item.effects if isinstance(item.effects, list) else []
        missing = [effect for effect in converted if effect not in existing]
        if not missing:
            continue
        needing_repair += 1
        effects_to_add += len(missing)
        if not apply:
            continue
        metadata = dict(item.metadata) if isinstance(item.metadata, dict) else {}
        conversion = dict(metadata.get("effectConversion") or {})
        conversion.update(converted=len(converted), retainedForReview=len(retained))
        metadata["effectConversion"] = conversion
        # Imported at module scope this would be circular: `item_special` reads
        # `convert_effect` from here to keep one definition of "convertible".
        from backend.core.item_special import unreviewed_descriptive_effects

        reasons = [reason for reason in metadata.get("specialReasons", []) if reason != "effetti_descrittivi"]
        if unreviewed_descriptive_effects(item):
            reasons.append("effetti_descrittivi")
        metadata["specialReasons"] = reasons
        item.effects = [*existing, *missing]
        item.metadata = metadata
        item.speciale = bool(reasons)
        item.save(update_fields=["effects", "metadata", "speciale"])
        changed_item_ids.append(item.pk)

    refreshed = 0
    if apply and changed_item_ids:
        equipment_fields = _item_fields(Equip)
        equipped_items = Q()
        for field in equipment_fields:
            equipped_items |= Q(**{f"equip__{field.name}_id__in": changed_item_ids})
        character_ids = Personaggio.objects.filter(equipped_items).values_list("pk", flat=True).distinct()
        for character_id in character_ids:
            refresh_personaggio(character_id)
            refreshed += 1
    return {
        "scanned": scanned,
        "itemsNeedingRepair": needing_repair,
        "effectsToAdd": effects_to_add,
        "updated": needing_repair if apply else 0,
        "refreshedCharacters": refreshed,
    }


@transaction.atomic
def apply_plan(plan: ImportPlan) -> dict[str, int]:
    Oggetto.objects.all().delete()
    OpzioneTipoOggetto.objects.all().delete()
    options = []
    for position, values in plan.type_options.items():
        options.extend(
            OpzioneTipoOggetto(posizione=position, valore=value, etichetta=value, ordine=order)
            for order, value in enumerate(values, start=1)
        )
    OpzioneTipoOggetto.objects.bulk_create(options)
    Oggetto.objects.bulk_create([Oggetto(**values) for values in plan.rows], batch_size=500)
    imported_by_source = {
        int(item.metadata["sourceId"]): item
        for item in Oggetto.objects.filter(metadata__sourceProject=SOURCE_PROJECT)
    }
    for assignment in plan.assignments:
        source_id = assignment.get("sourceId") or ASSIGNMENT_REPLACEMENTS[assignment["oldName"]]
        assignment["model"].objects.filter(pk=assignment["recordId"]).update(
            **{f"{assignment['field']}_id": imported_by_source[source_id].id}
        )
    for character_id in Personaggio.objects.values_list("id", flat=True):
        refresh_personaggio(character_id)
    return {
        "imported": len(plan.rows),
        "skippedPlaceholders": len(plan.skipped),
        "typeOptions": sum(map(len, plan.type_options.values())),
        "convertedEffects": plan.converted_effects,
        "retainedEffects": plan.retained_effects,
        "specialItems": plan.special_items,
        "remappedAssignments": len(plan.assignments),
    }
