from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from backend.core.api import ApiError
from backend.core.management_services import require_game_manager
from backend.core.models import (
    FamigliaSkill,
    Giocatore,
    GruppoFamiglieSkill,
    Skill,
)
from backend.media_library.models import UploadedImage


def _text(values: Mapping[str, Any], key: str, maximum: int | None = None) -> str:
    value = str(values.get(key) or "").strip()
    return value[:maximum] if maximum else value


def _integer(values: Mapping[str, Any], key: str, *, minimum: int = 0) -> int:
    try:
        value = int(values.get(key, 0) or 0)
    except (TypeError, ValueError) as exc:
        raise ApiError("management.skills.integer_required", "Inserisci un numero intero valido.", key) from exc
    if value < minimum:
        raise ApiError("management.skills.minimum", f"Il valore non può essere inferiore a {minimum}.", key)
    return value


def _unique_slug(model, raw_slug: str, name: str, instance=None) -> str:
    candidate = slugify(raw_slug or name)
    if not candidate:
        raise ApiError("management.skills.slug_required", "Inserisci un nome o uno slug valido.", "slug")
    duplicates = model.objects.filter(slug=candidate)
    if instance and instance.pk:
        duplicates = duplicates.exclude(pk=instance.pk)
    if duplicates.exists():
        raise ApiError("management.skills.slug_duplicate", "Questo slug è già in uso.", "slug", 409)
    return candidate


@transaction.atomic
def save_skill_group(user, giocatore: Giocatore, values: Mapping[str, Any], group_id: int | None = None) -> GruppoFamiglieSkill:
    require_game_manager(user, giocatore)
    group = GruppoFamiglieSkill.objects.select_for_update().filter(pk=group_id).first() if group_id else GruppoFamiglieSkill()
    if group_id and not group.pk:
        raise ApiError("management.skills.group_not_found", "Gruppo non trovato.", status=404)
    name = _text(values, "name", 80)
    if not name:
        raise ApiError("management.skills.group_name_required", "Il nome del gruppo è obbligatorio.", "name")
    duplicate = GruppoFamiglieSkill.objects.filter(nome__iexact=name)
    if group.pk:
        duplicate = duplicate.exclude(pk=group.pk)
    if duplicate.exists():
        raise ApiError("management.skills.group_name_duplicate", "Esiste già un gruppo con questo nome.", "name", 409)
    group.nome = name
    group.slug = _unique_slug(GruppoFamiglieSkill, _text(values, "slug", 100), name, group)
    group.ordine = _integer(values, "order")
    group.note = _text(values, "notes")
    group.archived_at = None
    group.save()
    return group


@transaction.atomic
def set_skill_group_archived(user, giocatore: Giocatore, group_id: int, archived: bool) -> GruppoFamiglieSkill:
    require_game_manager(user, giocatore)
    try:
        group = GruppoFamiglieSkill.objects.select_for_update().get(pk=group_id)
    except GruppoFamiglieSkill.DoesNotExist as exc:
        raise ApiError("management.skills.group_not_found", "Gruppo non trovato.", status=404) from exc
    if archived and group.famiglie.filter(archived_at__isnull=True).exists():
        raise ApiError(
            "management.skills.group_not_empty",
            "Sposta o archivia prima tutte le famiglie attive del gruppo.",
            status=409,
        )
    group.archived_at = timezone.now() if archived else None
    group.save(update_fields=["archived_at", "updated_at"])
    return group


def _image(raw_id: Any) -> UploadedImage | None:
    if raw_id in (None, ""):
        return None
    try:
        return UploadedImage.objects.get(pk=int(raw_id))
    except (TypeError, ValueError, UploadedImage.DoesNotExist) as exc:
        raise ApiError("management.skills.image_not_found", "Immagine non trovata.", "imageId", 404) from exc


@transaction.atomic
def save_skill_family(user, giocatore: Giocatore, values: Mapping[str, Any], family_id: int | None = None) -> FamigliaSkill:
    require_game_manager(user, giocatore)
    family = FamigliaSkill.objects.select_for_update().filter(pk=family_id).first() if family_id else FamigliaSkill()
    if family_id and not family.pk:
        raise ApiError("management.skills.family_not_found", "Famiglia non trovata.", status=404)
    name = _text(values, "name", 160)
    if not name:
        raise ApiError("management.skills.family_name_required", "Il nome della famiglia è obbligatorio.", "name")
    duplicate = FamigliaSkill.objects.filter(nome__iexact=name)
    if family.pk:
        duplicate = duplicate.exclude(pk=family.pk)
    if duplicate.exists():
        raise ApiError("management.skills.family_name_duplicate", "Esiste già una famiglia con questo nome.", "name", 409)
    try:
        group = GruppoFamiglieSkill.objects.get(pk=int(values.get("groupId")), archived_at__isnull=True)
    except (TypeError, ValueError, GruppoFamiglieSkill.DoesNotExist) as exc:
        raise ApiError("management.skills.group_not_found", "Gruppo attivo non trovato.", "groupId", 404) from exc
    family.nome = name
    family.gruppo = group
    family.ordine = _integer(values, "order")
    family.is_classe = bool(values.get("isClass"))
    family.is_religione = bool(values.get("isReligion"))
    family.is_perk = bool(values.get("isPerk"))
    family.note = _text(values, "notes")
    family.note_addizionali = _text(values, "additionalNotes")
    family.immagine = _image(values.get("imageId"))
    family.archived_at = None
    family.save()
    return family


@transaction.atomic
def set_skill_family_archived(user, giocatore: Giocatore, family_id: int, archived: bool) -> FamigliaSkill:
    require_game_manager(user, giocatore)
    try:
        family = FamigliaSkill.objects.select_for_update().select_related("gruppo").get(pk=family_id)
    except FamigliaSkill.DoesNotExist as exc:
        raise ApiError("management.skills.family_not_found", "Famiglia non trovata.", status=404) from exc
    if archived and family.skills.filter(archived_at__isnull=True).exists():
        raise ApiError(
            "management.skills.family_not_empty",
            "Sposta o archivia prima tutte le skill attive della famiglia.",
            status=409,
        )
    if not archived and family.gruppo.archived_at is not None:
        raise ApiError(
            "management.skills.group_archived",
            "Ripristina prima il gruppo della famiglia.",
            status=409,
        )
    family.archived_at = timezone.now() if archived else None
    family.save(update_fields=["archived_at", "updated_at"])
    return family


@transaction.atomic
def set_managed_skill_archived(user, giocatore: Giocatore, skill_id: int, archived: bool) -> Skill:
    require_game_manager(user, giocatore)
    try:
        skill = Skill.objects.select_for_update().select_related("famiglia", "famiglia__gruppo").get(pk=skill_id)
    except Skill.DoesNotExist as exc:
        raise ApiError("skills.not_found", "Abilità non trovata.", status=404) from exc
    if not archived and (
        skill.famiglia.archived_at is not None
        or skill.famiglia.gruppo.archived_at is not None
    ):
        raise ApiError(
            "management.skills.structure_archived",
            "Ripristina prima il gruppo e la famiglia della skill.",
            status=409,
        )
    skill.archived_at = timezone.now() if archived else None
    skill.save(update_fields=["archived_at", "updated_at"])
    return skill


@transaction.atomic
def reorder_skill_structure(user, giocatore: Giocatore, groups: Any = None, families: Any = None) -> dict[str, int]:
    """Renumber groups and families in one call.

    `ordine` used to be typed one record at a time across 15 groups and 99
    families, which is why the numbering drifted. The structure editor now sends
    the whole list in its new order and the positions are rewritten together.
    """
    require_game_manager(user, giocatore)
    touched = {"groups": 0, "families": 0}
    for model, entries, key in ((GruppoFamiglieSkill, groups, "groups"), (FamigliaSkill, families, "families")):
        if not entries:
            continue
        if not isinstance(entries, list):
            raise ApiError("management.skills.order_invalid", "L'ordine deve essere una lista di identificativi.", key)
        identifiers = []
        for raw in entries:
            try:
                identifiers.append(int(raw))
            except (TypeError, ValueError) as exc:
                raise ApiError("management.skills.order_invalid", "Identificativo non valido nell'ordine.", key) from exc
        found = model.objects.select_for_update().filter(pk__in=identifiers)
        if found.count() != len(set(identifiers)):
            raise ApiError("management.skills.order_unknown", "Un record dell'ordine non esiste più.", key, 409)
        by_id = {record.pk: record for record in found}
        updates = []
        for position, identifier in enumerate(identifiers, start=1):
            record = by_id[identifier]
            if record.ordine != position:
                record.ordine = position
                updates.append(record)
        if updates:
            model.objects.bulk_update(updates, ["ordine"])
        touched[key] = len(updates)
    return touched
