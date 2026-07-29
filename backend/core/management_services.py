from __future__ import annotations

from typing import Any

from django.db import models, transaction

from backend.characters.models import Personaggio
from backend.characters.services.refresh_personaggio import refresh_personaggio
from backend.core.api import ApiError
from backend.core.models import DatiCampagna, Effetto, Giocatore, Oggetto
from backend.core.security import effective_role, has_minimum_role
from backend.media_library.models import UploadedImage

from .management_selectors import (
    ORPHAN_SOURCES,
    PROFILE_FIELDS,
    READ_ONLY_PROFILE_KEYS,
    RELATION_CONFIG,
    RELATION_FIELDS,
    character_management_detail,
    deletion_preview_token,
    orphan_queryset,
)


PROFILE_SPEC_BY_KEY = {field["key"]: field for field in PROFILE_FIELDS}


def require_game_manager(user, giocatore: Giocatore) -> None:
    if not has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER):
        raise ApiError(
            "management.forbidden",
            "Solo master e amministratori possono usare gli strumenti di gestione.",
            status=403,
        )


def _integer_value(raw: Any, *, nullable: bool, field: str) -> int | None:
    if raw in (None, "") and nullable:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ApiError("management.integer_required", "Inserisci un numero intero valido.", field) from exc


def _related_instance(model, raw: Any, field: str, missing_message: str):
    if raw in (None, "", 0, "0"):
        return None
    try:
        return model.objects.get(pk=int(raw))
    except (TypeError, ValueError, model.DoesNotExist) as exc:
        raise ApiError("management.related_not_found", missing_message, field, 404) from exc


def _clean_profile_values(values: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, raw in values.items():
        spec = PROFILE_SPEC_BY_KEY.get(key)
        if spec is None or key in READ_ONLY_PROFILE_KEYS:
            continue
        field_type = spec["type"]
        if field_type == "campaign":
            cleaned[key] = _related_instance(DatiCampagna, raw, key, "Campagna non trovata.")
            continue
        if field_type == "image":
            cleaned[key] = _related_instance(UploadedImage, raw, key, "Immagine non trovata.")
            continue
        if field_type == "integer":
            value = _integer_value(raw, nullable=bool(spec.get("nullable")), field=key)
            if value is not None and spec.get("minimum") is not None and value < spec["minimum"]:
                raise ApiError(
                    "management.minimum_value",
                    f"{spec['label']} non può essere inferiore a {spec['minimum']}.",
                    key,
                )
        elif field_type == "json":
            if not isinstance(raw, dict):
                raise ApiError(
                    "management.object_required",
                    f"{spec['label']} deve essere un oggetto JSON.",
                    key,
                )
            value = raw
        else:
            value = str(raw or "").strip()
        cleaned[key] = value
    if "nome" in cleaned and not cleaned["nome"]:
        raise ApiError("management.name_required", "Il nome del personaggio è obbligatorio.", "nome")
    if "nome_interno" in cleaned and not cleaned["nome_interno"]:
        raise ApiError(
            "management.internal_name_required",
            "Il nome interno del personaggio è obbligatorio.",
            "nome_interno",
        )
    return cleaned


def _relation_value(spec: dict[str, Any], raw: Any, field_path: str):
    field_type = spec["type"]
    if field_type == "integer":
        return _integer_value(raw, nullable=bool(spec.get("nullable")), field=field_path)
    if field_type == "json":
        if not isinstance(raw, dict):
            raise ApiError(
                "management.object_required",
                f"{spec['label']} deve essere un oggetto JSON.",
                field_path,
            )
        return raw
    if field_type == "boolean":
        if not isinstance(raw, bool):
            raise ApiError("management.boolean_required", "Scegli Sì oppure No.", field_path)
        return raw
    if field_type == "item":
        if raw in (None, ""):
            return None
        try:
            return Oggetto.objects.get(pk=int(raw))
        except (TypeError, ValueError, Oggetto.DoesNotExist) as exc:
            raise ApiError("management.item_not_found", "Oggetto non trovato.", field_path, 404) from exc
    if field_type == "effect":
        if raw in (None, ""):
            return None
        try:
            return Effetto.objects.get(pk=int(raw))
        except (TypeError, ValueError, Effetto.DoesNotExist) as exc:
            raise ApiError("management.effect_not_found", "Effetto non trovato.", field_path, 404) from exc
    return str(raw or "")


def _update_relation(character: Personaggio, kind: str, payload: dict[str, Any]) -> None:
    if kind not in RELATION_CONFIG:
        return
    instance = getattr(character, kind)
    if instance is None:
        if payload:
            raise ApiError(
                "management.related_record_missing",
                f"Il record {RELATION_CONFIG[kind]['label']} non è collegato. Collegalo prima di modificarlo.",
                kind,
                409,
            )
        return
    specs = {spec["key"]: spec for spec in RELATION_FIELDS[kind]}
    for key, raw in payload.items():
        spec = specs.get(key)
        if spec is None:
            continue
        setattr(instance, key, _relation_value(spec, raw, f"{kind}.{key}"))
    try:
        instance.full_clean()
    except Exception as exc:
        raise ApiError(
            "management.related_invalid",
            f"Controlla i dati di {RELATION_CONFIG[kind]['label']}.",
            kind,
        ) from exc
    instance.save()


@transaction.atomic
def update_managed_character(
    user,
    giocatore: Giocatore,
    character_id: int,
    profile: dict[str, Any],
    relations: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    require_game_manager(user, giocatore)
    try:
        character = (
            Personaggio.objects.select_for_update()
            .select_related(*RELATION_CONFIG.keys())
            .get(pk=character_id)
        )
    except Personaggio.DoesNotExist as exc:
        raise ApiError("management.character_not_found", "Personaggio non trovato.", status=404) from exc

    for key, value in _clean_profile_values(profile).items():
        setattr(character, key, value)
    try:
        character.full_clean()
    except Exception as exc:
        raise ApiError(
            "management.character_invalid",
            "Controlla i dati del personaggio: il nome interno deve essere univoco.",
        ) from exc
    character.save()

    for kind, values in relations.items():
        if isinstance(values, dict):
            _update_relation(character, kind, values)

    refresh_personaggio(character.pk)
    return character_management_detail(character.pk)


@transaction.atomic
def attach_orphan_record(
    user,
    giocatore: Giocatore,
    character_id: int,
    kind: str,
    record_id: int,
) -> dict[str, Any]:
    require_game_manager(user, giocatore)
    config = RELATION_CONFIG.get(kind)
    if config is None:
        raise ApiError("management.relation_unknown", "Tipo di record non riconosciuto.", "kind")
    try:
        character = Personaggio.objects.select_for_update().get(pk=character_id)
        record = config["model"].objects.select_for_update().get(pk=record_id)
    except (Personaggio.DoesNotExist, config["model"].DoesNotExist) as exc:
        raise ApiError("management.resource_not_found", "Record o personaggio non trovato.", status=404) from exc
    if getattr(character, f"{kind}_id") is not None:
        raise ApiError(
            "management.relation_already_present",
            f"{character.nome} ha già un record {config['label']}.",
            "characterId",
            409,
        )
    if record.personaggi.exists():
        raise ApiError("management.relation_not_orphan", "Il record è già collegato a un personaggio.", status=409)
    setattr(character, kind, record)
    character.save(update_fields=[kind, "updated_at"])
    refresh_personaggio(character.pk)
    return character_management_detail(character.pk)


@transaction.atomic
def delete_orphan_record(user, giocatore: Giocatore, kind: str, record_id: int) -> dict[str, Any]:
    """Delete one leftover record that no character points at any more.

    Migrations and half-finished edits leave behind Zaino, Equip, Faretra, Note,
    effect blocks and combat buttons that belong to nobody. They are invisible in
    the game and only grow, so the Orfani tab has to be able to remove them.

    Two guarantees make that safe. The ownership check is repeated here under a
    row lock, so a record attached to a character between listing and clicking is
    refused rather than deleted. And only the container itself is removed: its
    slots reference Oggetto and Effetto with SET_NULL, so the catalogue and the
    Skill list cannot be reached from this operation at all.
    """
    require_game_manager(user, giocatore)
    source = ORPHAN_SOURCES.get(kind)
    if source is None:
        raise ApiError("management.relation_unknown", "Tipo di record non riconosciuto.", "kind")
    try:
        record = source["model"].objects.select_for_update().get(pk=record_id)
    except source["model"].DoesNotExist as exc:
        raise ApiError("management.resource_not_found", "Record non trovato.", status=404) from exc

    if kind == "bottoni_combat":
        owner = record.personaggio.nome if record.personaggio_id else ""
    else:
        owner = next((character.nome for character in record.personaggi.all()), "")
    if owner:
        raise ApiError(
            "management.relation_not_orphan",
            f"Il record è collegato a {owner}: non è un orfano e non viene eliminato.",
            status=409,
        )

    label = str(record)
    record.delete()
    return {"kind": kind, "label": source["label"], "name": label}


@transaction.atomic
def delete_managed_character(
    user,
    giocatore: Giocatore,
    character_id: int,
    preview_token: str,
) -> str:
    require_game_manager(user, giocatore)
    try:
        character = (
            Personaggio.objects.select_for_update()
            .select_related(*RELATION_CONFIG.keys())
            .prefetch_related("effetti_personalizzati")
            .get(pk=character_id)
        )
    except Personaggio.DoesNotExist as exc:
        raise ApiError("management.character_not_found", "Personaggio non trovato.", status=404) from exc
    if preview_token != deletion_preview_token(character):
        raise ApiError(
            "management.preview_stale",
            "I record collegati sono cambiati. Riapri l'anteprima prima di eliminare.",
            "previewToken",
            409,
        )

    character_name = character.nome
    metadata = character.metadata if isinstance(character.metadata, dict) else {}
    cloned_item_ids = [int(value) for value in metadata.get("combat_cloned_item_ids", []) if str(value).isdigit()]
    cloned_effect_ids = [int(value) for value in metadata.get("combat_cloned_effect_ids", []) if str(value).isdigit()]
    related_records: list[models.Model] = [
        record
        for kind in RELATION_CONFIG
        if (record := getattr(character, kind)) is not None
    ]
    for player in Giocatore.objects.select_for_update().all():
        character_ids = [entry for entry in player.character_ids if entry != character.id]
        if character_ids != player.character_ids:
            player.character_ids = character_ids
            player.save(update_fields=["character_ids", "updated_at"])

    character.delete()
    for record in related_records:
        if not record.personaggi.exists():
            record.delete()
    Oggetto.objects.filter(id__in=cloned_item_ids).delete()
    Effetto.objects.filter(id__in=cloned_effect_ids).delete()
    return character_name
