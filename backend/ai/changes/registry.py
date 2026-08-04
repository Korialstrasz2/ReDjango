from __future__ import annotations

from backend.core.api import ApiError

from .handlers import ItemChangeHandler, SkillChangeHandler, SpellChangeHandler, ThemeChangeHandler


ENTITY_HANDLERS = {
    "item": ItemChangeHandler(),
    "skill": SkillChangeHandler(),
    "spell": SpellChangeHandler(),
    "theme": ThemeChangeHandler(),
}


def get_change_handler(entity_type: str):
    key = str(entity_type or "").strip().lower()
    handler = ENTITY_HANDLERS.get(key)
    if handler is None:
        raise ApiError(
            "ai.change_entity_unsupported",
            f"Il tipo di entità «{key or '—'}» non è supportato.",
            "entityType",
        )
    return handler


def change_entity_catalog(user, giocatore) -> list[dict]:
    result = []
    for handler in ENTITY_HANDLERS.values():
        try:
            handler.require_access(user, giocatore, "create")
        except ApiError:
            continue
        result.append(
            {
                "type": handler.entity_type,
                "label": handler.label,
                "minimumRole": handler.minimum_role,
                "actions": sorted(handler.supported_actions),
                "fields": handler.field_schema(user, giocatore, action="create"),
            }
        )
    return result
