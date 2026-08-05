from __future__ import annotations

import json
from typing import Any

from backend.core.api import ApiError

from .registry import get_change_handler

ALLOWED_CONTEXT_KEYS = frozenset({"entityType", "targetId", "sourceId", "sourceSurface"})
ALLOWED_SOURCE_SURFACES = frozenset(
    {
        "item-management",
        "skill-management",
        "theme-management",
        "unit-management",
        "management-hub",
        "master-ai",
    }
)
MAX_CONTEXT_BYTES = 4096


def _optional_identifier(value: Any, field: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        identifier = int(value)
    except (TypeError, ValueError) as exc:
        raise ApiError("ai.change_context_id_invalid", "L'identificatore del contesto non è valido.", field) from exc
    if identifier <= 0:
        raise ApiError("ai.change_context_id_invalid", "L'identificatore del contesto deve essere positivo.", field)
    return identifier


def validate_change_context(user, giocatore, context: dict[str, Any] | None) -> dict[str, Any]:
    """Return a permission-checked, size-capped context hint for proposer runs.

    Context never grants access and never replaces the model's search/read tools.
    Loading target/source snapshots here only proves that the current user may
    resolve the hinted records through the explicit entity handler.
    """

    if context in (None, {}):
        return {}
    if not isinstance(context, dict):
        raise ApiError("ai.change_context_invalid", "Il contesto deve essere un oggetto JSON.", "context")
    unknown = set(context) - ALLOWED_CONTEXT_KEYS
    if unknown:
        raise ApiError(
            "ai.change_context_field_unknown",
            f"Campi contesto non riconosciuti: {', '.join(sorted(unknown))}.",
            "context",
        )

    entity_type = str(context.get("entityType") or "").strip().lower()
    target_id = _optional_identifier(context.get("targetId"), "context.targetId")
    source_id = _optional_identifier(context.get("sourceId"), "context.sourceId")
    source_surface = str(context.get("sourceSurface") or "").strip().lower()

    if target_id is not None and source_id is not None:
        raise ApiError(
            "ai.change_context_target_source_conflict",
            "Il contesto può indicare una destinazione oppure una sorgente, non entrambe.",
            "context",
        )
    if (target_id is not None or source_id is not None) and not entity_type:
        raise ApiError(
            "ai.change_context_entity_required",
            "Il tipo di entità è obbligatorio quando il contesto indica un record.",
            "context.entityType",
        )
    if source_surface and source_surface not in ALLOWED_SOURCE_SURFACES:
        raise ApiError(
            "ai.change_context_surface_invalid",
            "La superficie di provenienza non è supportata.",
            "context.sourceSurface",
        )

    sanitized: dict[str, Any] = {}
    if entity_type:
        handler = get_change_handler(entity_type)
        handler.require_access(user, giocatore, "update" if target_id is not None else "create")
        sanitized["entityType"] = handler.entity_type
        if target_id is not None:
            handler.snapshot(user, giocatore, target_id)
            sanitized["targetId"] = target_id
        if source_id is not None:
            handler.snapshot(user, giocatore, source_id)
            sanitized["sourceId"] = source_id
    if source_surface:
        sanitized["sourceSurface"] = source_surface

    encoded = json.dumps(sanitized, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_CONTEXT_BYTES:
        raise ApiError("ai.change_context_too_large", "Il contesto supera la dimensione consentita.", "context")
    return sanitized
