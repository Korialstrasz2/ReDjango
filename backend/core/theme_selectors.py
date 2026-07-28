from .models import Theme
from .settings_selectors import active_themes, global_setting_value, serialize_theme


# Ogni campo colore del tema, con l'eventuale impostazione globale che ne fa da riserva.
THEME_COLOR_FIELDS = [
    {"field": "background_color", "key": "background", "label": "Sfondo", "fallbackSetting": ""},
    {"field": "panel_color", "key": "panel", "label": "Pannelli", "fallbackSetting": ""},
    {"field": "panel_strong_color", "key": "panelStrong", "label": "Pannelli in rilievo", "fallbackSetting": ""},
    {"field": "text_color", "key": "text", "label": "Testo", "fallbackSetting": ""},
    {"field": "muted_text_color", "key": "mutedText", "label": "Testo secondario", "fallbackSetting": ""},
    {"field": "line_color", "key": "line", "label": "Bordi", "fallbackSetting": ""},
    {"field": "accent_color", "key": "accent", "label": "Principale", "fallbackSetting": "appearance.accent_color"},
    {"field": "accent_strong_color", "key": "accentStrong", "label": "Principale intenso", "fallbackSetting": ""},
    {"field": "gold_color", "key": "gold", "label": "Dorato", "fallbackSetting": "appearance.gold_color"},
    {"field": "sidebar_color", "key": "sidebar", "label": "Menu laterale", "fallbackSetting": "appearance.sidebar_color"},
    {"field": "health_color", "key": "health", "label": "Punti ferita", "fallbackSetting": ""},
    {"field": "mana_color", "key": "mana", "label": "Mana", "fallbackSetting": ""},
    {"field": "energy_color", "key": "energy", "label": "Energia", "fallbackSetting": ""},
    {"field": "power_color", "key": "power", "label": "Potere", "fallbackSetting": ""},
    {"field": "valid_slot_color", "key": "validSlot", "label": "Slot compatibile", "fallbackSetting": ""},
    {"field": "invalid_slot_color", "key": "invalidSlot", "label": "Slot incompatibile", "fallbackSetting": ""},
]

# Le schermate che possono avere uno sfondo dedicato, nell'ordine in cui compaiono nel menu.
THEME_BACKGROUND_FIELDS = [
    {"field": "dashboard_background", "key": "dashboard", "label": "Sala principale"},
    {"field": "characters_background", "key": "characters", "label": "Selezione personaggi"},
    {"field": "personaggio_background", "key": "personaggio", "label": "Scheda personaggio"},
    {"field": "market_background", "key": "market", "label": "Mercato"},
    {"field": "lore_background", "key": "lore", "label": "Lore"},
    {"field": "media_background", "key": "media", "label": "Archivio immagini"},
    {"field": "guide_background", "key": "guide", "label": "Guide"},
    {"field": "settings_background", "key": "settings", "label": "Impostazioni"},
    {"field": "dice_background", "key": "dice", "label": "Area dadi"},
    {"field": "journal_background", "key": "journal", "label": "Diario"},
]

THEME_COLOR_FIELD_NAMES = [entry["field"] for entry in THEME_COLOR_FIELDS]
THEME_BACKGROUND_FIELD_NAMES = [entry["field"] for entry in THEME_BACKGROUND_FIELDS]
THEME_BLANKABLE_COLOR_FIELDS = frozenset(
    entry["field"] for entry in THEME_COLOR_FIELDS if entry["fallbackSetting"]
)


def _background_payload(theme: Theme, field_name: str) -> dict:
    image = getattr(theme, field_name)
    if image is None:
        return {"id": None, "title": "", "url": "", "thumbnailUrl": ""}
    return {
        "id": image.id,
        "title": image.title,
        "url": image.file.url if image.file else "",
        "thumbnailUrl": image.thumbnail.url if image.thumbnail else (image.file.url if image.file else ""),
    }


def serialize_managed_theme(theme: Theme) -> dict:
    return {
        "id": theme.id,
        "slug": theme.slug,
        "name": theme.name,
        "description": theme.description,
        "isActive": theme.is_active,
        "isDefault": theme.is_default,
        "order": theme.order,
        "colors": {entry["field"]: getattr(theme, entry["field"]) for entry in THEME_COLOR_FIELDS},
        "overlayOpacity": float(theme.overlay_opacity),
        "panelOpacity": float(theme.panel_opacity),
        "backgroundPosition": theme.background_position,
        "backgroundBlur": theme.background_blur,
        "backgrounds": {
            entry["field"]: _background_payload(theme, entry["field"])
            for entry in THEME_BACKGROUND_FIELDS
        },
        "isSeeded": (theme.metadata or {}).get("seed_kind") == "theme",
        "preview": serialize_theme(theme),
    }


def themes_management_payload() -> dict:
    themes = list(
        Theme.objects.filter(archived_at__isnull=True)
        .select_related(*THEME_BACKGROUND_FIELD_NAMES)
        .order_by("order", "name")
    )
    return {
        "themes": [serialize_managed_theme(theme) for theme in themes],
        "colorFields": THEME_COLOR_FIELDS,
        "backgroundFields": THEME_BACKGROUND_FIELDS,
        "fallbacks": {
            "appearance.accent_color": global_setting_value("appearance.accent_color", ""),
            "appearance.gold_color": global_setting_value("appearance.gold_color", ""),
            "appearance.sidebar_color": global_setting_value("appearance.sidebar_color", ""),
        },
        "activeCount": len(active_themes()),
    }
