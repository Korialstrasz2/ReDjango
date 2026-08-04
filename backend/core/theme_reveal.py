"""Theme background reveal timing stored in Theme.metadata.

Keeping these values in metadata avoids a schema migration while preserving
per-theme configuration across devices and deployments.
"""

from __future__ import annotations

from typing import Any

from .api import ApiError

REVEAL_HOLD_KEY = "background_reveal_hold_seconds"
REVEAL_FADE_KEY = "background_reveal_fade_seconds"
DEFAULT_REVEAL_HOLD_SECONDS = 0.5
DEFAULT_REVEAL_FADE_SECONDS = 1.0
MIN_REVEAL_SECONDS = 0.0
MAX_REVEAL_SECONDS = 5.0


def _number(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not MIN_REVEAL_SECONDS <= number <= MAX_REVEAL_SECONDS:
        return default
    return round(number, 2)


def reveal_values(theme) -> dict[str, float]:
    metadata = theme.metadata if isinstance(theme.metadata, dict) else {}
    return {
        "revealHoldSeconds": _number(metadata.get(REVEAL_HOLD_KEY), DEFAULT_REVEAL_HOLD_SECONDS),
        "revealFadeSeconds": _number(metadata.get(REVEAL_FADE_KEY), DEFAULT_REVEAL_FADE_SECONDS),
    }


def _clean(field: str, raw_value: Any) -> float:
    try:
        value = round(float(raw_value), 2)
    except (TypeError, ValueError) as exc:
        raise ApiError(
            "management.themes.reveal_duration_invalid",
            "La durata della transizione deve essere un numero.",
            field,
        ) from exc
    if not MIN_REVEAL_SECONDS <= value <= MAX_REVEAL_SECONDS:
        raise ApiError(
            "management.themes.reveal_duration_range",
            "La durata della transizione deve essere compresa tra 0 e 5 secondi.",
            field,
        )
    return value


def apply_reveal_payload(theme, payload: dict) -> None:
    updates: dict[str, float] = {}
    if "revealHoldSeconds" in payload:
        updates[REVEAL_HOLD_KEY] = _clean("revealHoldSeconds", payload["revealHoldSeconds"])
    if "revealFadeSeconds" in payload:
        updates[REVEAL_FADE_KEY] = _clean("revealFadeSeconds", payload["revealFadeSeconds"])
    if not updates:
        return
    metadata = dict(theme.metadata) if isinstance(theme.metadata, dict) else {}
    metadata.update(updates)
    theme.metadata = metadata
