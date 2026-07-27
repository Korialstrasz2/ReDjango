from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify

from backend.core.api import ApiError
from backend.core.legacy_skill_import import SOURCE_PROJECT, build_import_run
from backend.core.management_services import require_game_manager
from backend.core.models import (
    FamigliaSkill,
    Giocatore,
    GruppoFamiglieSkill,
    Skill,
    SkillMigrationReview,
)
from backend.media_library.models import UploadedImage

from .skill_services import upsert_imported_skill


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


def default_legacy_skill_source() -> Path:
    return Path(settings.BASE_DIR).parent / "firstDjango" / "the_elder_django" / "db.sqlite3"


@transaction.atomic
def reconcile_legacy_skill_reviews(run) -> dict[str, int]:
    # The common icon fallback is expected for most legacy rows and would bury
    # the records that genuinely need a decision. Warnings remain attached to
    # blocked candidates, while the persistent queue contains only candidates
    # that were not safe to auto-import (including changed live sources).
    relevant = [candidate for candidate in run.candidates if candidate["decision"] != "auto_import"]
    source_ids = [candidate["sourceId"] for candidate in relevant]
    live_by_source = {
        int(skill.metadata["sourceId"]): skill
        for skill in Skill.objects.filter(metadata__sourceProject=SOURCE_PROJECT)
        if isinstance(skill.metadata, dict) and str(skill.metadata.get("sourceId", "")).isdigit()
    }
    created = 0
    reopened = 0
    for candidate in relevant:
        values = candidate["values"]
        suggested_hash = values.get("metadata", {}).get("sourceHash")
        review = SkillMigrationReview.objects.select_for_update().filter(
            source_project=SOURCE_PROJECT,
            source_id=candidate["sourceId"],
        ).first()
        previous_hash = None
        if review and isinstance(review.suggested_values, dict):
            previous_hash = review.suggested_values.get("metadata", {}).get("sourceHash")
        source_changed = bool(previous_hash and previous_hash != suggested_hash)
        if review is None:
            review = SkillMigrationReview(
                source_project=SOURCE_PROJECT,
                source_id=candidate["sourceId"],
                working_values=values,
            )
            created += 1
        elif source_changed:
            review.working_values = values
            review.edited = False
            review.status = SkillMigrationReview.STATUS_OPEN
            review.resolution_notes = ""
            reopened += 1
        elif not review.edited:
            review.working_values = values
        review.nome = candidate["name"]
        review.severity = (
            SkillMigrationReview.SEVERITY_BLOCKED
            if candidate["decision"] != "auto_import"
            else SkillMigrationReview.SEVERITY_WARNING
        )
        review.decision = candidate["decision"]
        review.blockers = candidate["blockers"]
        review.warnings = candidate["warnings"]
        review.suggested_values = values
        review.source_snapshot = candidate["source"]
        review.resolved_skill = live_by_source.get(candidate["sourceId"])
        review.archived_at = None
        review.save()
    stale_reviews = SkillMigrationReview.objects.filter(
        source_project=SOURCE_PROJECT,
        archived_at__isnull=True,
    ).exclude(source_id__in=source_ids)
    stale_reviews.filter(status=SkillMigrationReview.STATUS_OPEN, edited=False).delete()
    stale_reviews.exclude(status=SkillMigrationReview.STATUS_OPEN, edited=False).update(archived_at=timezone.now())
    return {
        "sourceSkills": run.summary["sourceSkillCount"],
        "queued": len(relevant),
        "blocked": sum(1 for candidate in relevant if candidate["decision"] != "auto_import"),
        "warnings": sum(1 for candidate in relevant if candidate["decision"] == "auto_import"),
        "created": created,
        "reopened": reopened,
    }


@transaction.atomic
def sync_legacy_skill_reviews(user, giocatore: Giocatore) -> dict[str, int]:
    require_game_manager(user, giocatore)
    source_path = default_legacy_skill_source()
    if not source_path.is_file():
        raise ApiError(
            "management.skills.legacy_source_missing",
            f"Database Elder non trovato: {source_path}",
            status=404,
        )
    return reconcile_legacy_skill_reviews(build_import_run(source_path))


def _review(review_id: int, *, lock: bool = False) -> SkillMigrationReview:
    queryset = SkillMigrationReview.objects.select_related("resolved_skill")
    if lock:
        queryset = queryset.select_for_update()
    try:
        return queryset.get(pk=review_id, archived_at__isnull=True)
    except SkillMigrationReview.DoesNotExist as exc:
        raise ApiError("management.skills.review_not_found", "Revisione non trovata.", status=404) from exc


def _review_values(review: SkillMigrationReview, values: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(values)
    proposed_metadata = review.suggested_values.get("metadata", {}) if isinstance(review.suggested_values, dict) else {}
    metadata = dict(result.get("metadata") or {}) if isinstance(result.get("metadata"), Mapping) else {}
    metadata.update({
        "sourceProject": review.source_project,
        "sourceId": review.source_id,
        "sourceHash": proposed_metadata.get("sourceHash"),
        "manualReview": True,
        "orderChaosCollapsed": True,
    })
    result["metadata"] = metadata
    return result


@transaction.atomic
def save_legacy_skill_review(user, giocatore: Giocatore, review_id: int, values: Any, notes: str = "") -> SkillMigrationReview:
    require_game_manager(user, giocatore)
    if not isinstance(values, Mapping):
        raise ApiError("management.skills.review_values_invalid", "La correzione deve essere un oggetto.", "values")
    review = _review(review_id, lock=True)
    review.working_values = _review_values(review, values)
    review.resolution_notes = str(notes or "").strip()[:4000]
    review.edited = True
    review.status = SkillMigrationReview.STATUS_OPEN
    review.save(update_fields=["working_values", "resolution_notes", "edited", "status", "updated_at"])
    return review


@transaction.atomic
def import_legacy_skill_review(user, giocatore: Giocatore, review_id: int) -> tuple[SkillMigrationReview, Skill]:
    require_game_manager(user, giocatore)
    review = _review(review_id, lock=True)
    values = _review_values(review, review.working_values if isinstance(review.working_values, dict) else {})
    try:
        skill = upsert_imported_skill(values)
    except IntegrityError as exc:
        raise ApiError("management.skills.review_conflict", "La correzione collide con una skill esistente.", status=409) from exc
    if skill.archived_at is not None:
        skill.archived_at = None
        skill.save(update_fields=["archived_at", "updated_at"])
    review.working_values = values
    review.resolved_skill = skill
    review.status = SkillMigrationReview.STATUS_IMPORTED
    review.edited = True
    review.save(update_fields=["working_values", "resolved_skill", "status", "edited", "updated_at"])
    return review, skill


@transaction.atomic
def set_legacy_skill_review_status(user, giocatore: Giocatore, review_id: int, status: str) -> SkillMigrationReview:
    require_game_manager(user, giocatore)
    if status not in {SkillMigrationReview.STATUS_OPEN, SkillMigrationReview.STATUS_IGNORED}:
        raise ApiError("management.skills.review_status_invalid", "Stato di revisione non valido.", "status")
    review = _review(review_id, lock=True)
    review.status = status
    review.save(update_fields=["status", "updated_at"])
    return review
