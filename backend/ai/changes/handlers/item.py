from __future__ import annotations

from typing import Any

from django.db.models import Q

from backend.core.api import ApiError
from backend.core.item_services import (
    clean_item_values,
    create_item,
    archive_item,
    require_item_author,
    update_item,
)
from backend.core.models import Giocatore, Oggetto, OpzioneTipoOggetto, TipoArma
from backend.media_library.models import UploadedImage
from backend.media_library.selectors import get_uploaded_image_for_user, list_uploaded_images_for_user

from ..contracts import PreparedChange
from .base import canonical_digest, json_safe


class ItemChangeHandler:
    entity_type = "item"
    label = "Oggetto"
    minimum_role = Giocatore.ROLE_MASTER
    supported_actions = frozenset({"create", "update", "archive"})

    SCALAR_FIELDS = (
        "nome",
        "modello",
        "temporaneo",
        "speciale",
        "numero_ordine",
        "icona",
        "tipo_1",
        "tipo_2",
        "tipo_3",
        "tipo_4",
        "descrizione",
        "valore",
        "peso",
        "rarita",
        "lv_loot",
        "regione_loot",
        "peso_regione",
        "pa_per_attacco",
        "effetto_1",
        "effetto_2",
        "effetto_3",
        "effetto_4",
        "effetto_5",
        "effetto_6",
        "effetto_7",
        "effetto_8",
        "regole_speciali",
        "effects",
    )
    RELATION_FIELDS = ("tipoArmaId", "mediaId")
    EDITABLE_FIELDS = frozenset((*SCALAR_FIELDS, *RELATION_FIELDS))

    def require_access(self, user, giocatore, action: str) -> None:
        if action not in self.supported_actions:
            raise ApiError(
                "ai.change_action_unsupported",
                f"L'azione «{action}» non è supportata per gli oggetti.",
                "action",
            )
        require_item_author(user, giocatore)

    def _type_choices(self) -> dict[int, list[dict[str, str]]]:
        choices: dict[int, list[dict[str, str]]] = {}
        queryset = OpzioneTipoOggetto.objects.filter(
            attiva=True,
            archived_at__isnull=True,
        ).order_by("posizione", "ordine", "etichetta", "valore")
        for option in queryset:
            choices.setdefault(option.posizione, []).append(
                {"value": option.valore, "label": option.label}
            )
        return choices

    @staticmethod
    def _field(
        name: str,
        label: str,
        kind: str,
        group: str,
        *,
        required: bool = False,
        nullable: bool = False,
        help_text: str = "",
        choices: list[dict[str, Any]] | None = None,
        widget: str | None = None,
        width: str = "half",
    ) -> dict[str, Any]:
        ui: dict[str, Any] = {"width": width}
        if widget:
            ui["widget"] = widget
        elif kind == "choice":
            ui["widget"] = "select"
        return {
            "name": name,
            "label": label,
            "kind": kind,
            "group": group,
            "required": required,
            "nullable": nullable,
            "readOnly": False,
            "help": help_text,
            "choices": choices or [],
            "ui": ui,
        }

    def field_schema(self, user, giocatore, *, action: str, instance=None) -> list[dict[str, Any]]:
        self.require_access(user, giocatore, action)
        if action == "archive":
            return []
        type_choices = self._type_choices()
        weapon_choices = [
            {"value": weapon.id, "label": weapon.nome}
            for weapon in TipoArma.objects.filter(archived_at__isnull=True).order_by("nome")
        ]
        image_choices = [
            {"value": image.id, "label": image.title}
            for image in list_uploaded_images_for_user(user)[:200]
        ]
        rarity_choices = [
            {"value": value, "label": label}
            for value, label in Oggetto.Rarita.choices
        ]
        fields = [
            self._field("nome", "Nome", "text", "Identità", required=True, width="full"),
            self._field("icona", "Icona", "text", "Identità"),
            self._field("numero_ordine", "Numero d'ordine", "integer", "Identità", nullable=True),
            self._field("modello", "Modello", "boolean", "Identità"),
            self._field("temporaneo", "Temporaneo", "boolean", "Identità"),
            self._field("speciale", "Speciale", "boolean", "Identità"),
            self._field("descrizione", "Descrizione", "longText", "Identità", width="full"),
            self._field("mediaId", "Immagine", "image", "Identità", nullable=True, choices=image_choices, widget="imagePicker", width="full"),
            self._field("tipo_1", "Tipo 1", "choice", "Classificazione", nullable=True, choices=type_choices.get(1, [])),
            self._field("tipo_2", "Tipo 2", "choice", "Classificazione", nullable=True, choices=type_choices.get(2, [])),
            self._field("tipo_3", "Tipo 3", "choice", "Classificazione", nullable=True, choices=type_choices.get(3, [])),
            self._field("tipo_4", "Tipo 4", "choice", "Classificazione", nullable=True, choices=type_choices.get(4, [])),
            self._field("tipoArmaId", "Tipo arma", "relation", "Classificazione", nullable=True, choices=weapon_choices, widget="select"),
            self._field("valore", "Valore", "integer", "Economia e loot", nullable=True),
            self._field("peso", "Peso", "number", "Economia e loot", nullable=True),
            self._field("rarita", "Rarità", "choice", "Economia e loot", nullable=True, choices=rarity_choices),
            self._field("lv_loot", "Livello loot", "text", "Economia e loot", nullable=True),
            self._field("regione_loot", "Regione loot", "text", "Economia e loot", nullable=True),
            self._field("peso_regione", "Peso regione", "number", "Economia e loot", nullable=True),
            self._field("pa_per_attacco", "PA per attacco", "integer", "Economia e loot", nullable=True),
        ]
        fields.extend(
            self._field(
                f"effetto_{index}",
                f"Effetto Elder {index}",
                "text",
                "Effetti e regole",
                nullable=True,
                help_text="Massimo 255 caratteri.",
                width="full",
            )
            for index in range(1, 9)
        )
        fields.extend(
            [
                self._field("regole_speciali", "Regole speciali", "longText", "Effetti e regole", nullable=True, width="full"),
                self._field("effects", "Effetti strutturati", "structured", "Effetti e regole", widget="itemEffects", width="full"),
            ]
        )
        return fields

    def _queryset(self, *, for_update: bool = False):
        queryset = Oggetto.objects.select_related("tipo_arma", "media")
        if for_update:
            queryset = queryset.select_for_update()
        return queryset

    def _load(self, object_id: int, *, for_update: bool = False) -> Oggetto:
        try:
            return self._queryset(for_update=for_update).get(pk=int(object_id))
        except (TypeError, ValueError, Oggetto.DoesNotExist) as exc:
            raise ApiError("items.not_found", "L'oggetto richiesto non esiste.", status=404) from exc

    def _values_for(self, item: Oggetto) -> dict[str, Any]:
        values = {field: json_safe(getattr(item, field)) for field in self.SCALAR_FIELDS}
        values["tipoArmaId"] = item.tipo_arma_id
        values["mediaId"] = item.media_id
        return values

    def _snapshot_for(self, item: Oggetto) -> dict[str, Any]:
        updated_at = item.updated_at.isoformat() if item.updated_at else None
        values = self._values_for(item)
        snapshot = {
            "id": item.id,
            "entityType": self.entity_type,
            "label": item.nome,
            "updatedAt": updated_at,
            "values": values,
            "display": {
                "name": item.nome,
                "archived": bool(item.archiviato or item.archived_at),
                "weaponType": item.tipo_arma.nome if item.tipo_arma_id else "",
                "image": item.media.title if item.media_id else "",
            },
        }
        snapshot["digest"] = canonical_digest(
            {
                "id": snapshot["id"],
                "entityType": snapshot["entityType"],
                "updatedAt": snapshot["updatedAt"],
                "values": snapshot["values"],
            }
        )
        return snapshot

    def snapshot(self, user, giocatore, object_id: int, *, for_update: bool = False) -> dict[str, Any]:
        self.require_access(user, giocatore, "update")
        return self._snapshot_for(self._load(object_id, for_update=for_update))

    def search(self, user, giocatore, query: str, limit: int) -> list[dict[str, Any]]:
        self.require_access(user, giocatore, "update")
        text = str(query or "").strip()[:160]
        cap = max(1, min(int(limit or 10), 25))
        queryset = Oggetto.objects.filter(archiviato=False, archived_at__isnull=True)
        if text:
            queryset = queryset.filter(
                Q(nome__icontains=text)
                | Q(descrizione__icontains=text)
                | Q(tipo_1__icontains=text)
                | Q(tipo_2__icontains=text)
                | Q(tipo_3__icontains=text)
            )
        return [
            {
                "id": item.id,
                "entityType": self.entity_type,
                "label": item.nome,
                "summary": item.descrizione[:180],
                "updatedAt": item.updated_at.isoformat() if item.updated_at else None,
            }
            for item in queryset.order_by("nome")[:cap]
        ]

    def _default_values(self) -> dict[str, Any]:
        item = Oggetto()
        values = {field: json_safe(getattr(item, field)) for field in self.SCALAR_FIELDS}
        values["tipoArmaId"] = None
        values["mediaId"] = None
        return values

    def _filter_values(self, values: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(values, dict):
            raise ApiError("ai.change_values_invalid", "I valori proposti devono essere un oggetto JSON.", "values")
        aliases = {"tipo_arma_id": "tipoArmaId", "media_id": "mediaId"}
        normalized: dict[str, Any] = {}
        unknown: list[str] = []
        for raw_name, value in values.items():
            name = aliases.get(str(raw_name), str(raw_name))
            if name not in self.EDITABLE_FIELDS:
                unknown.append(str(raw_name))
                continue
            normalized[name] = value
        if unknown:
            raise ApiError(
                "ai.change_field_unknown",
                f"Campi non modificabili: {', '.join(sorted(unknown))}.",
                "values",
            )
        return normalized

    def _validate_relations(self, user, values: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(values)
        raw_weapon = normalized.get("tipoArmaId")
        if raw_weapon in (None, ""):
            normalized["tipoArmaId"] = None
        else:
            try:
                weapon_id = int(raw_weapon)
                TipoArma.objects.get(pk=weapon_id)
            except (TypeError, ValueError, TipoArma.DoesNotExist) as exc:
                raise ApiError("items.weapon_type_invalid", "Il tipo arma selezionato non esiste.", "tipoArmaId") from exc
            normalized["tipoArmaId"] = weapon_id

        raw_media = normalized.get("mediaId")
        if raw_media in (None, ""):
            normalized["mediaId"] = None
        else:
            try:
                media_id = int(raw_media)
                get_uploaded_image_for_user(user, media_id)
            except (TypeError, ValueError, UploadedImage.DoesNotExist) as exc:
                raise ApiError("items.media_invalid", "L'immagine selezionata non è disponibile.", "mediaId") from exc
            normalized["mediaId"] = media_id
        return normalized

    def _validate_values(self, user, values: dict[str, Any], *, instance: Oggetto | None) -> dict[str, Any]:
        filtered = self._filter_values(values)
        scalar_payload = {name: filtered.get(name) for name in self.SCALAR_FIELDS if name in filtered}
        cleaned = clean_item_values(scalar_payload, partial=False)
        normalized = {**self._default_values(), **cleaned}
        normalized.update({name: filtered.get(name) for name in self.RELATION_FIELDS if name in filtered})
        normalized = self._validate_relations(user, normalized)

        duplicates = Oggetto.objects.filter(nome__iexact=normalized["nome"])
        if instance is not None:
            duplicates = duplicates.exclude(pk=instance.pk)
        if duplicates.exists():
            raise ApiError("items.duplicate_name", "Esiste già un oggetto con questo nome.", "nome", 409)
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
            source_values = dict(original["values"])
            source_values.pop("nome", None)
            materialized.update(source_values)
            materialized["nome"] = ""
            base_updated_at = source.updated_at
            base_digest = original["digest"]
        materialized.update(self._filter_values(values))
        normalized = self._validate_values(user, materialized, instance=None)
        return PreparedChange(
            values=normalized,
            original_snapshot=original,
            field_schema=self.field_schema(user, giocatore, action="create"),
            display_label=normalized["nome"],
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
        item = self._load(object_id, for_update=for_update)
        original = self._snapshot_for(item)
        materialized = {**original["values"], **self._filter_values(values)}
        normalized = self._validate_values(user, materialized, instance=item)
        return PreparedChange(
            values=normalized,
            original_snapshot=original,
            field_schema=self.field_schema(user, giocatore, action="update", instance=item),
            display_label=normalized["nome"],
            base_updated_at=item.updated_at,
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
        item = self._load(object_id, for_update=for_update)
        if item.archiviato or item.archived_at:
            raise ApiError("items.already_archived", "L'oggetto è già archiviato.", status=409)
        original = self._snapshot_for(item)
        return PreparedChange(
            values=original["values"],
            original_snapshot=original,
            field_schema=[],
            display_label=item.nome,
            base_updated_at=item.updated_at,
            base_digest=original["digest"],
        )

    def apply_create(self, user, giocatore, values: dict[str, Any]) -> dict[str, Any]:
        item = create_item(user, giocatore, values)
        return {"id": item.id, "label": item.nome, "action": "create"}

    def apply_update(self, user, giocatore, object_id: int, values: dict[str, Any]) -> dict[str, Any]:
        item = update_item(user, giocatore, object_id, values)
        return {"id": item.id, "label": item.nome, "action": "update"}

    def apply_archive(self, user, giocatore, object_id: int) -> dict[str, Any]:
        item = archive_item(user, giocatore, object_id)
        return {"id": item.id, "label": item.nome, "action": "archive"}
