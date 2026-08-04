"""Install the theme reveal extension without widening the core theme modules."""

from __future__ import annotations

from functools import wraps

_installed = False


def install() -> None:
    global _installed
    if _installed:
        return
    _installed = True

    from . import settings_selectors, theme_selectors, theme_services
    from .theme_reveal import apply_reveal_payload, reveal_values

    original_serialize_theme = settings_selectors.serialize_theme

    @wraps(original_serialize_theme)
    def serialize_theme(theme):
        payload = original_serialize_theme(theme)
        payload.update(reveal_values(theme))
        return payload

    settings_selectors.serialize_theme = serialize_theme

    original_serialize_managed_theme = theme_selectors.serialize_managed_theme

    @wraps(original_serialize_managed_theme)
    def serialize_managed_theme(theme):
        payload = original_serialize_managed_theme(theme)
        values = reveal_values(theme)
        payload.update(values)
        if isinstance(payload.get("preview"), dict):
            payload["preview"].update(values)
        return payload

    theme_selectors.serialize_managed_theme = serialize_managed_theme
    theme_services.serialize_managed_theme = serialize_managed_theme

    original_apply_payload = theme_services._apply_payload

    @wraps(original_apply_payload)
    def apply_payload(theme, payload, *, partial):
        result = original_apply_payload(theme, payload, partial=partial)
        apply_reveal_payload(result, payload)
        return result

    theme_services._apply_payload = apply_payload
