from __future__ import annotations

from copy import copy
from typing import Any

from django.db.models import Q
from django.utils.text import slugify

from backend.core.api import ApiError
from backend.core.models import Giocatore, Theme
from backend.core.theme_selectors import THEME_COLOR_FIELDS, THEME_COLOR_FIELD_NAMES, serialize_managed_theme
from backend.core.theme_services import (
    _apply_payload,
    _clean_backgrounds,
    archive_theme,
    create_theme,
    require_theme_admin,
    save_theme,
)
from backend.core.theme_surfaces import THEME_SURFACES

from ..contracts import PreparedChange
from .base import canonical_digest, json_safe


class ThemeChangeHandler:
    entity_type = "theme"
    label = "Tema"
    minimum_role = Giocatore.ROLE_ADMIN
    supported_actions = frozenset({"create", "update", "archive"})
    BASE_FIELDS = frozenset(
        {
            "name",
            "description",
            "order",
            "isActive",
            "overlayOpacity",
            "panelOpacity",
            "backgroundPosition",
            "backgroundBlur",
            "backgrounds",
        }
    )
    EDITABLE_FIELDS = BASE_FIELDS | frozenset(THEME_COLOR_FIELD_NAMES)

    def require_access(self, user, giocatore, action: str) -> None:
        if action not in self.supported_actions:
            raise ApiError("ai.change_action_unsupported", "Azione proposta non supportata.", "action")
        require_theme_admin(user, giocatore)

    @staticmethod
    def _field(
        name: str,
        label: str,
        kind: str,
        group: str,
        *,
        required: bool = False,
        nullable: bool = False,
        help: str = "",
        ui: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "label": label,
            "kind": kind,
            "group": group,
            "required": required,
            "nullable": nullable,
            "readOnly": False,
            "help": help,
            "choices": [],
            "ui": {"widget": kind, "width": "full" if kind in {"longText", "structured"} else "half", **(ui or {})},
        }

    def field_schema(self, user, giocatore, *, action: str, instance=None) -> list[dict[str, Any]]:
        self.require_access(user, giocatore, action)
        fields = [
            self._field("name", "Nome", "text", "Identità", required=True),
            self._field("description", "Descrizione", "longText", "Identità"),
            self._field("order", "Ordine", "integer", "Identità", ui={"minimum": 0}),
            self._field("isActive", "Attivo", "boolean", "Stato"),
        ]
        fields.extend(
            self._field(entry["field"], entry["label"], "color", "Colori", nullable=bool(entry["fallbackSetting"]))
            for entry in THEME_COLOR_FIELDS
        )
        fields.extend(
            [
                self._field("overlayOpacity", "Opacità velo", "number", "Aspetto", ui={"minimum": 0, "maximum": 1, "step": 0.01}),
                self._field("panelOpacity", "Opacità pannelli", "number", "Aspetto", ui={"minimum": 0, "maximum": 1, "step": 0.01}),
                self._field("backgroundPosition", "Posizione sfondo", "text", "Aspetto"),
                self._field("backgroundBlur", "Sfocatura sfondo", "integer", "Aspetto", ui={"minimum": 0, "maximum": 20}),
                self._field(
                    "backgrounds",
                    "Sfondi per superficie",
                    "structured",
                    "Sfondi",
                    ui={
                        "widget": "themeBackgrounds",
                        "surfaces": [
                            {"key": surface["key"], "label": surface["label"], "section": surface["section"]}
                            for surface in THEME_SURFACES
                        ],
                    },
                ),
            ]
        )
        return fields

    def _queryset(self, *, for_update: bool = False):
        queryset = Theme.objects.prefetch_related("backgrounds__image")
        if for_update:
            queryset = queryset.select_for_update()
        return queryset

    def _load(self, object_id: int, *, for_update: bool = False) -> Theme:
        try:
            return self._queryset(for_update=for_update).get(pk=int(object_id))
        except (TypeError, ValueError, Theme.DoesNotExist) as exc:
            raise ApiError("management.themes.not_found", "Il tema richiesto non esiste.", status=404) from exc

    def _values_for(self, theme: Theme) -> dict[str, Any]:
        serialized = serialize_managed_theme(theme)
        return {
            "name": serialized["name"],
            "description": serialized["description"],
            "order": serialized["order"],
            "isActive": serialized["isActive"],
            **serialized["colors"],
            "overlayOpacity": serialized["overlayOpacity"],
            "panelOpacity": serialized["panelOpacity"],
            "backgroundPosition": serialized["backgroundPosition"],
            "backgroundBlur": serialized["backgroundBlur"],
            "backgrounds": {
                key: value.get("id") if isinstance(value, dict) else None
                for key, value in serialized["backgrounds"].items()
            },
        }

    def _snapshot_for(self, theme: Theme) -> dict[str, Any]:
        values = json_safe(self._values_for(theme))
        digest = canonical_digest({"id": theme.id, "entityType": self.entity_type, "values": values})
        return {
            "id": theme.id,
            "entityType": self.entity_type,
            "label": theme.name,
            "updatedAt": theme.updated_at.isoformat() if theme.updated_at else None,
            "values": values,
            "display": {"active": theme.is_active, "default": theme.is_default, "seeded": (theme.metadata or {}).get("seed_kind") == "theme"},
            "digest": digest,
        }

    def snapshot(self, user, giocatore, object_id: int, *, for_update: bool = False) -> dict[str, Any]:
        self.require_access(user, giocatore, "update")
        return self._snapshot_for(self._load(object_id, for_update=for_update))

    def search(self, user, giocatore, query: str, limit: int) -> list[dict[str, Any]]:
        self.require_access(user, giocatore, "update")
        text = str(query or "").strip()[:160]
        cap = max(1, min(int(limit or 10), 25))
        queryset = self._queryset().filter(archived_at__isnull=True)
        if text:
            queryset = queryset.filter(Q(name__icontains=text) | Q(description__icontains=text))
        return [
            {
                "id": theme.id,
                "label": theme.name,
                "description": theme.description[:280],
                "meta": {"active": theme.is_active, "default": theme.is_default},
            }
            for theme in queryset.order_by("order", "name")[:cap]
        ]

    def _default_values(self) -> dict[str, Any]:
        theme = Theme()
        return {
            "name": "",
            "description": "",
            "order": 0,
            "isActive": True,
            **{field_name: getattr(theme, field_name) for field_name in THEME_COLOR_FIELD_NAMES},
            "overlayOpacity": float(theme.overlay_opacity),
            "panelOpacity": float(theme.panel_opacity),
            "backgroundPosition": theme.background_position,
            "backgroundBlur": theme.background_blur,
            "backgrounds": {},
        }

    def _filter_values(self, values: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(values, dict):
            raise ApiError("ai.change_values_invalid", "I valori proposti devono essere un oggetto JSON.", "values")
        unknown = sorted(set(values) - self.EDITABLE_FIELDS)
        if unknown:
            raise ApiError("ai.change_field_unknown", f"Campi non modificabili: {', '.join(unknown)}.", "values")
        return dict(values)

    def _service_payload(self, values: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": values["name"],
            "description": values["description"],
            "order": values["order"],
            "isActive": values["isActive"],
            "colors": {field_name: values[field_name] for field_name in THEME_COLOR_FIELD_NAMES},
            "overlayOpacity": values["overlayOpacity"],
            "panelOpacity": values["panelOpacity"],
            "backgroundPosition": values["backgroundPosition"],
            "backgroundBlur": values["backgroundBlur"],
            "backgrounds": values.get("backgrounds") or {},
        }

    def _validate_values(self, values: dict[str, Any], *, instance: Theme | None) -> dict[str, Any]:
        filtered = self._filter_values(values)
        candidate = copy(instance) if instance is not None else Theme(metadata={"seed_kind": "theme_custom"})
        candidate.is_default = False
        payload = self._service_payload(filtered)
        cleaned_backgrounds = _clean_backgrounds(payload)
        _apply_payload(candidate, payload, partial=False)
        candidate.is_active = bool(payload.get("isActive", True))
        candidate.slug = candidate.slug or (slugify(candidate.name)[:80] or "tema")
        candidate.full_clean(exclude=["slug"])
        normalized = {
            "name": candidate.name,
            "description": candidate.description,
            "order": candidate.order,
            "isActive": candidate.is_active,
            **{field_name: getattr(candidate, field_name) for field_name in THEME_COLOR_FIELD_NAMES},
            "overlayOpacity": candidate.overlay_opacity,
            "panelOpacity": candidate.panel_opacity,
            "backgroundPosition": candidate.background_position,
            "backgroundBlur": candidate.background_blur,
            "backgrounds": {key: image.id if image is not None else None for key, image in cleaned_backgrounds.items()},
        }
        return json_safe(normalized)

    def prepare_create(self, user, giocatore, values: dict[str, Any], source_id: int | None = None) -> PreparedChange:
        self.require_access(user, giocatore, "create")
        original: dict[str, Any] = {}
        base_updated_at = None
        base_digest = ""
        materialized = self._default_values()
        if source_id is not None:
            source = self._load(source_id)
            original = self._snapshot_for(source)
            materialized.update(original["values"])
            materialized["name"] = ""
            base_updated_at = source.updated_at
            base_digest = original["digest"]
        materialized.update(self._filter_values(values))
        normalized = self._validate_values(materialized, instance=None)
        return PreparedChange(
            values=normalized,
            original_snapshot=original,
            field_schema=self.field_schema(user, giocatore, action="create"),
            display_label=normalized["name"],
            base_updated_at=base_updated_at,
            base_digest=base_digest,
        )

    def prepare_update(
        self,
        user,
        giocatore,
        object_id: int,
        values: dict[str, Any],
        *,
        for_update: bool = False,
    ) -> PreparedChange:
        self.require_access(user, giocatore, "update")
        theme = self._load(object_id, for_update=for_update)
        original = self._snapshot_for(theme)
        materialized = {**original["values"], **self._filter_values(values)}
        normalized = self._validate_values(materialized, instance=theme)
        return PreparedChange(
            values=normalized,
            original_snapshot=original,
            field_schema=self.field_schema(user, giocatore, action="update", instance=theme),
            display_label=normalized["name"],
            base_updated_at=theme.updated_at,
            base_digest=original["digest"],
        )

    def prepare_archive(
        self,
        user,
        giocatore,
        object_id: int,
        *,
        for_update: bool = False,
    ) -> PreparedChange:
        self.require_access(user, giocatore, "archive")
        theme = self._load(object_id, for_update=for_update)
        if theme.archived_at:
            raise ApiError("management.themes.already_archived", "Il tema è già archiviato.", status=409)
        if theme.is_default:
            raise ApiError("management.themes.default_not_archivable", "Non puoi archiviare il tema predefinito.", status=409)
        if (theme.metadata or {}).get("seed_kind") == "theme":
            raise ApiError("management.themes.seeded_not_archivable", "I temi di serie non possono essere archiviati.", status=409)
        original = self._snapshot_for(theme)
        return PreparedChange(
            values=original["values"],
            original_snapshot=original,
            field_schema=[],
            display_label=theme.name,
            base_updated_at=theme.updated_at,
            base_digest=original["digest"],
        )

    def apply_create(self, user, giocatore, values: dict[str, Any]) -> dict[str, Any]:
        result = create_theme(user, giocatore, self._service_payload(values))
        theme = result["theme"]
        return {"id": theme["id"], "label": theme["name"], "action": "create", "entityType": self.entity_type}

    def apply_update(self, user, giocatore, object_id: int, values: dict[str, Any]) -> dict[str, Any]:
        result = save_theme(user, giocatore, object_id, self._service_payload(values))
        theme = result["theme"]
        return {"id": theme["id"], "label": theme["name"], "action": "update", "entityType": self.entity_type}

    def apply_archive(self, user, giocatore, object_id: int) -> dict[str, Any]:
        theme = self._load(object_id)
        label = theme.name
        archive_theme(user, giocatore, object_id)
        return {"id": theme.id, "label": label, "action": "archive", "entityType": self.entity_type}
