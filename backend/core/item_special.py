from __future__ import annotations

from typing import Any

from .legacy_item_import import clean_legacy_value, convert_effect
from .models import Oggetto


# Mirrors the reason codes `legacy_item_import.read_plan` assigns at import time
# (see `backend/core/legacy_item_import.py`), so a live recheck and the original
# import agree on what "speciale" means.
SPECIAL_REASON_LABELS: dict[str, dict[str, str]] = {
    "non_modello": {
        "label": "Non è un modello",
        "hint": "Attiva “Modello riutilizzabile” in Identità se l'oggetto deve comparire nel catalogo normale.",
    },
    "temporaneo": {
        "label": "Segnato come temporaneo",
        "hint": "Disattiva “Temporaneo” in Identità se non è più una prova provvisoria.",
    },
    "effetti_descrittivi": {
        "label": "Effetti Elder non convertiti",
        "hint": (
            "Uno o più degli otto effetti Elder conservati sono testo libero che non è stato tradotto "
            "in un effetto strutturato: aggiungi l'effetto strutturato equivalente, oppure riscrivi la "
            "regola in “Regole speciali” per dichiararla rivista, oppure svuota il testo residuo."
        ),
    },
    "tipo_1_vuoto": {
        "label": "Tipo 1 non impostato",
        "hint": "Assegna un Tipo 1 valido nella scheda Classificazione.",
    },
}

# Key under `Oggetto.metadata` listing the Elder texts that `regole_speciali`
# already covers. It is written by the item editor, never by hand: see
# `item_services.sync_special_rules_review`.
REVIEWED_EFFECTS_KEY = "descriptiveEffectsReviewed"


def _comparable(text: str) -> str:
    return " ".join(str(text or "").split()).casefold()


def descriptive_effects(item: Oggetto) -> list[str]:
    """Elder texts that `convert_effect` cannot turn into a structured operation."""
    return [
        raw
        for index in range(1, 9)
        if (raw := clean_legacy_value(getattr(item, f"effetto_{index}"))) and convert_effect(raw) is None
    ]


def reviewed_descriptive_effects(item: Oggetto) -> set[str]:
    metadata = item.metadata if isinstance(item.metadata, dict) else {}
    stored = metadata.get(REVIEWED_EFFECTS_KEY)
    return {_comparable(entry) for entry in stored} if isinstance(stored, list) else set()


def unreviewed_descriptive_effects(item: Oggetto) -> list[str]:
    """Descriptive texts nobody has curated into `regole_speciali` yet.

    Only these keep an item in the review queue. The review is recorded per
    text rather than as a single flag, so editing an `effetto_N` afterwards
    brings the item back for review instead of inheriting the old verdict.
    """
    reviewed = reviewed_descriptive_effects(item)
    return [raw for raw in descriptive_effects(item) if _comparable(raw) not in reviewed]


def compute_special_reasons(item: Oggetto) -> list[str]:
    """Recompute why `item` would be flagged `speciale`, from its *current* field values.

    Uses the same reason codes as the legacy import, but reads live fields
    instead of the frozen snapshot in `metadata["specialReasons"]`, so a reason
    disappears the moment the underlying data is fixed rather than staying
    stuck at whatever the import saw.
    """
    reasons: list[str] = []
    if not item.modello:
        reasons.append("non_modello")
    if item.temporaneo:
        reasons.append("temporaneo")
    if unreviewed_descriptive_effects(item):
        reasons.append("effetti_descrittivi")
    if not item.tipo_1:
        reasons.append("tipo_1_vuoto")
    return reasons


def special_reason_entries(item: Oggetto) -> list[dict[str, Any]]:
    return [
        {"code": code, **SPECIAL_REASON_LABELS.get(code, {"label": code, "hint": ""})}
        for code in compute_special_reasons(item)
    ]
