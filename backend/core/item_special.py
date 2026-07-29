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
        "hint": "Uno o più degli otto effetti Elder conservati sono testo libero che non è stato tradotto in un effetto strutturato: aggiungi l'effetto strutturato equivalente oppure svuota il testo residuo.",
    },
    "tipo_1_vuoto": {
        "label": "Tipo 1 non impostato",
        "hint": "Assegna un Tipo 1 valido nella scheda Classificazione.",
    },
}


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
    if any(
        (raw := clean_legacy_value(getattr(item, f"effetto_{index}"))) and convert_effect(raw) is None
        for index in range(1, 9)
    ):
        reasons.append("effetti_descrittivi")
    if not item.tipo_1:
        reasons.append("tipo_1_vuoto")
    return reasons


def special_reason_entries(item: Oggetto) -> list[dict[str, Any]]:
    return [
        {"code": code, **SPECIAL_REASON_LABELS.get(code, {"label": code, "hint": ""})}
        for code in compute_special_reasons(item)
    ]
