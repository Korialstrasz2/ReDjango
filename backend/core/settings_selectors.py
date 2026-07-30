from django.db.models import Q

from backend.characters.models import Personaggio

from .backup_defaults import BACKUP_SETTING_KEYS
from .models import CharacterAssignmentRequest, Giocatore, SettingDefinition, SettingOverride, Theme
from .security import effective_role, has_minimum_role, security_payload


SERIALIZED_VALUE_TYPES = {
    SettingDefinition.TYPE_BOOL: "boolean",
    SettingDefinition.TYPE_INT: "integer",
}

# These definitions are global game rules. They remain editable in Django Admin,
# but are intentionally absent from per-player/per-master preference screens.
ADMIN_MANAGED_SETTING_KEYS = frozenset({
    "combat.base_movement_ap",
    "security.game_master_access_code",
    "security.game_admin_access_code",
    "mercato.locations",
    "mercato.shop_types",
    "mercato.generator_rules",
    *BACKUP_SETTING_KEYS,
})
GLOBAL_EDITABLE_SETTING_KEYS = frozenset({
    "security.access_mode",
})


def setting_base_value(setting: SettingDefinition):
    return setting.default_value if setting.value is None else setting.value


def can_edit_setting(role: str, setting: SettingDefinition) -> bool:
    if not has_minimum_role(role, setting.minimum_role):
        return False
    if role == Giocatore.ROLE_ADMIN:
        return True
    if role == Giocatore.ROLE_MASTER:
        return setting.master_customizable or setting.user_customizable
    return setting.minimum_role == Giocatore.ROLE_USER and setting.user_customizable


def global_setting_value(key: str, fallback=None):
    setting = SettingDefinition.objects.filter(key=key, active=True, archived_at__isnull=True).first()
    return setting_base_value(setting) if setting else fallback


def _image_url(image) -> str:
    return image.file.url if image and image.file else ""


def serialize_theme(theme: Theme) -> dict:
    return {
        "slug": theme.slug,
        "name": theme.name,
        "description": theme.description,
        "colors": {
            "background": theme.background_color,
            "panel": theme.panel_color,
            "panelStrong": theme.panel_strong_color,
            "text": theme.text_color,
            "mutedText": theme.muted_text_color,
            "line": theme.line_color,
            "accent": theme.accent_color,
            "accentStrong": theme.accent_strong_color,
            "gold": theme.gold_color,
            "sidebar": theme.sidebar_color,
            "health": theme.health_color,
            "mana": theme.mana_color,
            "energy": theme.energy_color,
            "power": theme.power_color,
            "validSlot": theme.valid_slot_color,
            "invalidSlot": theme.invalid_slot_color,
        },
        "overlayOpacity": float(theme.overlay_opacity),
        "panelOpacity": float(theme.panel_opacity),
        "backgroundPosition": theme.background_position,
        "backgroundBlur": theme.background_blur,
        "backgrounds": {
            "dashboard": _image_url(theme.dashboard_background),
            "characters": _image_url(theme.characters_background),
            "personaggio": _image_url(theme.personaggio_background),
            "media": _image_url(theme.media_background),
            "guide": _image_url(theme.guide_background),
            "settings": _image_url(theme.settings_background),
            "dice": _image_url(theme.dice_background),
            "journal": _image_url(theme.journal_background),
            "lore": _image_url(theme.lore_background),
            "market": _image_url(theme.market_background),
        },
    }


def active_themes() -> list[Theme]:
    return list(
        Theme.objects.filter(is_active=True, archived_at__isnull=True)
        .select_related(
            "dashboard_background",
            "characters_background",
            "personaggio_background",
            "media_background",
            "guide_background",
            "settings_background",
            "dice_background",
            "journal_background",
            "lore_background",
            "market_background",
        )
        .order_by("order", "name")
    )


def _setting_payload(setting: SettingDefinition, role: str, override: SettingOverride | None) -> dict:
    base_value = setting_base_value(setting)
    if setting.key in GLOBAL_EDITABLE_SETTING_KEYS:
        override = None
    value = override.value if override is not None else base_value
    metadata = setting.metadata if isinstance(setting.metadata, dict) else {}
    choices = setting.choices if isinstance(setting.choices, list) else []
    if setting.key == "appearance.theme":
        theme_choices = [
            {"value": theme.slug, "label": theme.name}
            for theme in Theme.objects.filter(is_active=True, archived_at__isnull=True).order_by("order", "name")
        ]
        choices = theme_choices or choices
    elif setting.key == "dice.default_set":
        from backend.dice_tools.models import DiceSet

        dice_choices = [
            {"value": dice_set.slug, "label": dice_set.name}
            for dice_set in DiceSet.objects.filter(is_active=True, archived_at__isnull=True).order_by("order", "name")
        ]
        choices = dice_choices or choices
    return {
        "key": setting.key,
        "label": setting.label,
        "category": setting.category,
        "description": setting.description,
        "minimumRole": setting.minimum_role,
        "valueType": SERIALIZED_VALUE_TYPES.get(setting.value_type, setting.value_type),
        "value": value,
        "baseValue": base_value,
        "isOverride": override is not None,
        "choices": choices,
        "constraints": {
            key: metadata[key]
            for key in ("minimum", "maximum", "step")
            if key in metadata
        },
        "editable": can_edit_setting(role, setting),
        "uiToken": setting.ui_token,
        "order": setting.order,
    }


def settings_payload(user, giocatore: Giocatore) -> dict:
    from .access import runtime_access_payload

    role = effective_role(user, giocatore)
    definitions = list(
        SettingDefinition.objects.filter(active=True, archived_at__isnull=True).order_by("category", "order", "key")
    )
    overrides = {
        override.setting_id: override
        for override in SettingOverride.objects.filter(giocatore=giocatore, setting__in=definitions).select_related("setting")
    }

    visible_settings = []
    ui_values = {}
    for setting in definitions:
        if setting.key in ADMIN_MANAGED_SETTING_KEYS:
            continue
        role_can_see = has_minimum_role(role, setting.minimum_role)
        override = overrides.get(setting.id) if role_can_see else None
        serialized = _setting_payload(setting, role, override)
        if role_can_see:
            visible_settings.append(serialized)
        if setting.ui_token and (
            role_can_see
            or setting.minimum_role == Giocatore.ROLE_ADMIN
        ):
            ui_values[setting.key] = serialized["value"]

    capabilities = security_payload(user, giocatore)
    capabilities["showAdminLink"] = bool(
        capabilities["showAdminLink"]
        and global_setting_value("navigation.admin_link_enabled", True)
    )
    themes = active_themes()
    selected_slug = ui_values.get("appearance.theme")
    selected_theme = next((theme for theme in themes if theme.slug == selected_slug), None)
    if selected_theme is None:
        selected_theme = next((theme for theme in themes if theme.is_default), themes[0] if themes else None)
        if selected_theme is not None:
            ui_values["appearance.theme"] = selected_theme.slug

    assigned_ids = {
        int(value)
        for value in (giocatore.character_ids if isinstance(giocatore.character_ids, list) else [])
        if str(value).isdigit()
    }
    requests = {
        assignment.personaggio_id: assignment
        for assignment in CharacterAssignmentRequest.objects.filter(
            giocatore=giocatore,
            archived_at__isnull=True,
        ).select_related("personaggio")
    }
    available_characters = Personaggio.objects.filter(archived_at__isnull=True).filter(
        Q(metadata__seed_kind__isnull=True)
        | ~Q(metadata__seed_kind="empty_personaggio_template")
    ).order_by("nome", "id")

    return {
        "giocatore": {
            "id": giocatore.id,
            "name": giocatore.nome,
            "displayName": giocatore.display_name or giocatore.nome,
        },
        "player": {
            "alias": giocatore.display_name or giocatore.nome,
            "characters": [
                {
                    "id": character.id,
                    "name": character.nome,
                    "assigned": character.id in assigned_ids,
                    "requestStatus": requests[character.id].status if character.id in requests else "",
                }
                for character in available_characters
            ],
        },
        "security": capabilities,
        "runtime": runtime_access_payload(),
        "settings": visible_settings,
        "ui": ui_values,
        "themes": [serialize_theme(theme) for theme in themes],
        "theme": serialize_theme(selected_theme) if selected_theme else None,
    }
