"""Auditable importer for reviewed Mercato shop-content plans.

The importer deliberately consumes JSON, never the Elder workbook directly.  Content
generation and review are separate from database mutation so a dry run can be
repeated, diffed and approved before it creates anything.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from django.db import transaction

from backend.core.api import ApiError
from backend.core.models import Giocatore, Negozio

from .config import get_generator_rules, get_shop_type_definitions, resolve_location
from .services import save_shop


ARTICLE_RE = re.compile(r"^(?:the|il|lo|la|l)\s+", re.IGNORECASE)


def normalized_name(value: object) -> str:
    """Comparison key shared by plan validation and idempotency checks."""
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return ARTICLE_RE.sub("", text).strip()


@dataclass
class PlanReport:
    created: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    invalid: list[dict[str, Any]] = field(default_factory=list)

    @property
    def errors(self) -> bool:
        return bool(self.conflicts or self.invalid)

    def payload(self) -> dict[str, Any]:
        return {
            "created": len(self.created), "skipped": len(self.skipped),
            "conflicts": self.conflicts, "invalid": self.invalid,
            "createPlanIds": [entry["planId"] for entry in self.created],
            "skipPlanIds": [entry["planId"] for entry in self.skipped],
        }


def load_plan(path: Path) -> list[dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Piano non leggibile: {exc}") from exc
    records = raw.get("records", raw) if isinstance(raw, (dict, list)) else None
    if not isinstance(records, list):
        raise ValueError("Il piano deve essere una lista JSON o un oggetto con records.")
    return records


def _record_error(record: object, message: str) -> dict[str, Any]:
    return {"planId": record.get("planId") if isinstance(record, dict) else None, "error": message}


def _existing(location_key: str, name: str) -> Negozio | None:
    target = normalized_name(name)
    for shop in Negozio.objects.filter(location_key=location_key, archived_at__isnull=True).only(
        "id", "nome", "proprietario", "categoria", "livello", "descrizione"
    ):
        if normalized_name(shop.nome) == target:
            return shop
    return None


def validate_plan(records: list[dict[str, Any]]) -> PlanReport:
    report = PlanReport()
    owner_ledger: set[str] = set()
    shop_ledger: set[tuple[str, str]] = set()
    category_keys = {entry["key"] for entry in get_shop_type_definitions()["types"] if entry["enabled"]}
    rules = get_generator_rules()
    for record in records:
        if not isinstance(record, dict):
            report.invalid.append(_record_error(record, "Il record deve essere un oggetto.")); continue
        if record.get("status") == "needs_review":
            continue
        required = ("planId", "locationKey", "categoryKey", "level", "name", "owner", "description", "seed", "status")
        missing = [key for key in required if record.get(key) in (None, "")]
        if missing:
            report.invalid.append(_record_error(record, f"Campi obbligatori mancanti: {', '.join(missing)}.")); continue
        if record["status"] != "approved":
            report.invalid.append(_record_error(record, "Solo i record con status approved possono essere importati.")); continue
        name, owner, description = str(record["name"]).strip(), str(record["owner"]).strip(), str(record["description"]).strip()
        if len(name) > 180 or len(owner) > 180 or not (20 <= len(description.split()) <= 45):
            report.invalid.append(_record_error(record, "Nome/proprietario oltre il limite o descrizione non compresa tra 20 e 45 parole.")); continue
        try:
            location = resolve_location(str(record["locationKey"]), selectable=True)
        except Exception as exc:
            report.invalid.append(_record_error(record, f"Località non valida: {exc}")); continue
        try:
            level = int(record["level"])
        except (TypeError, ValueError):
            report.invalid.append(_record_error(record, "Livello non valido.")); continue
        if record["categoryKey"] not in category_keys or not rules["minLevel"] <= level <= rules["maxLevel"]:
            report.invalid.append(_record_error(record, "Categoria non abilitata o livello fuori dai limiti.")); continue
        identity, owner_key = (location["key"], normalized_name(name)), normalized_name(owner)
        if identity in shop_ledger or owner_key in owner_ledger:
            report.invalid.append(_record_error(record, "Nome negozio locale o proprietario duplicato nel piano.")); continue
        shop_ledger.add(identity); owner_ledger.add(owner_key)
        existing = _existing(location["key"], name)
        if existing is None:
            report.created.append(record); continue
        same = (existing.proprietario == owner and existing.categoria == record["categoryKey"] and existing.livello == level and existing.descrizione == description)
        bucket = report.skipped if same else report.conflicts
        bucket.append({"planId": record["planId"], "shopId": existing.id, "name": existing.nome} if same else {"planId": record["planId"], "shopId": existing.id, "error": "Esiste già un negozio con stesso nome/località ma dati diversi."})
    return report


def apply_batch(user, giocatore: Giocatore, records: list[dict[str, Any]]) -> list[dict[str, int]]:
    """Create exactly one validated batch, rolling it back entirely on failure."""
    receipts: list[dict[str, int]] = []
    with transaction.atomic():
        for record in records:
            try:
                shop, created = save_shop(user, giocatore, {
                    "name": record["name"], "owner": record["owner"], "locationKey": record["locationKey"],
                    "categoryKey": record["categoryKey"], "level": record["level"], "description": record["description"],
                    "seed": record["seed"], "generateStock": True, "featured": False, "priceModifierPercent": 0,
                })
            except Exception as exc:
                raise RuntimeError(json.dumps(_record_error(record, str(exc)), ensure_ascii=False)) from exc
            if not created:
                raise RuntimeError(json.dumps(_record_error(record, "Il record non ha creato un negozio."), ensure_ascii=False))
            receipts.append({"planId": int(record["planId"]), "shopId": shop.id})
    return receipts
