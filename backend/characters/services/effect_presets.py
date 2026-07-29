"""Preset effetto: modelli riutilizzabili che precompilano l'editor degli effetti.

Un preset non è un effetto applicato. Viene copiato nel modulo "Nuovo effetto"
così che possa essere ritoccato prima di diventare un ``EffettoPersonalizzato``,
esattamente come faceva Elder Django.
"""

from __future__ import annotations

from typing import Any, Mapping

from backend.core.api import ApiError

from ..effect_preset_defaults import EFFECT_PRESET_CATEGORIES
from ..models import EffettoPreset
from .custom_effects import (
    EFFECT_ICONS,
    _effect_icon_image_url,
    _normalize_description,
    validate_effect_values,
)


def validate_preset_values(values: Mapping[str, Any]) -> dict[str, Any]:
    """Riusa la validazione degli effetti così un preset rotto non è salvabile.

    I preset accettano zero operazioni: molte condizioni ereditate esistono solo
    come descrizione arbitrata al tavolo. La descrizione viene salvata senza il
    marcatore ``(t)``, che torna quando il preset diventa un effetto applicato.
    """
    validated = validate_effect_values(values, allow_empty_operations=True)
    category = str(values.get("category") or "").strip()
    if category and category not in EFFECT_PRESET_CATEGORIES:
        raise ApiError(
            "presets.category_invalid",
            "La categoria del preset non è disponibile.",
            "category",
        )
    return {
        "nome": validated["nome"],
        "descrizione": _normalize_description(validated["descrizione"], False),
        "origine": validated["origine"] or "Preset",
        "icona": validated["icona"],
        "temporaneo": validated["temporaneo"],
        "categoria": category,
        "operazioni": [
            {
                "target": operation["bersaglio"],
                "operation": operation["operazione"],
                "value": operation["valore"],
                "condition": operation["condizione"],
            }
            for operation in validated["operazioni"]
        ],
    }


def _preset_operations(preset: EffettoPreset) -> list[dict[str, str]]:
    raw = preset.operazioni if isinstance(preset.operazioni, list) else []
    return [
        {
            "target": str(entry.get("target") or ""),
            "operation": str(entry.get("operation") or "add"),
            "value": str(entry.get("value") or ""),
            "condition": str(entry.get("condition") or ""),
        }
        for entry in raw
        if isinstance(entry, Mapping)
    ]


def effect_preset_payload() -> list[dict[str, Any]]:
    """Elenco dei preset per l'editor, con l'URL dell'icona già risolto."""
    icon_labels = {value: label for value, label, _category, _keywords in EFFECT_ICONS}
    return [
        {
            "id": preset.id,
            "name": preset.nome,
            "description": preset.descrizione,
            "origin": preset.origine,
            "icon": preset.icona,
            "iconUrl": _effect_icon_image_url(
                preset.icona,
                icon_labels.get(preset.icona, preset.icona.replace("_", " ").title()),
            ),
            "temporary": preset.temporaneo,
            "category": preset.categoria,
            "operations": _preset_operations(preset),
        }
        for preset in EffettoPreset.objects.all()
    ]
