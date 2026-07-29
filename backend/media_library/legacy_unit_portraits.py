from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.core.files import File
from django.db import transaction
from django.utils.text import slugify
from PIL import Image, UnidentifiedImageError

from backend.core.models import Unit

from .models import ImageCategory, UploadedImage


LEGACY_PROJECT = "the_elder_django"
LEGACY_UNIT_TABLE = "django_slim_unit"
ASSET_SOURCE = "elder_django"
IMPORT_KIND = "unit_portrait"
IMPORT_VERSION = 1
PORTRAIT_USAGE_TYPE = "character_portrait"
PORTRAIT_CATEGORY_SLUG = "personaggi"
PORTRAIT_GROUP = "Unit e NPC"
SUPPORTED_SOURCE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


class PortraitImportError(RuntimeError):
    pass


@dataclass(frozen=True)
class PortraitCandidate:
    unit_id: int
    unit_name: str
    source_ids: tuple[int, ...]
    source_path: Path | None
    match_strategy: str
    blockers: tuple[str, ...] = ()

    @property
    def import_key(self) -> str:
        source_key = ",".join(str(source_id) for source_id in self.source_ids)
        return f"{LEGACY_PROJECT}:{LEGACY_UNIT_TABLE}:{source_key}:portrait"


def normalize_portrait_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(character for character in text if not unicodedata.combining(character))
    return " ".join(text.replace("’", "'").split())


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_names_by_id(database: Path, source_ids: Iterable[int]) -> dict[int, str]:
    resolved = database.resolve(strict=True)
    connection = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)
    try:
        placeholders = ",".join("?" for _source_id in source_ids)
        if not placeholders:
            return {}
        return {
            int(source_id): str(name or "").strip()
            for source_id, name in connection.execute(
                f"SELECT id, nome FROM {LEGACY_UNIT_TABLE} WHERE id IN ({placeholders})",
                tuple(source_ids),
            )
        }
    finally:
        connection.close()


def discover_portrait_candidates(
    source_directory: Path,
    legacy_database: Path,
    *,
    expected_count: int = 131,
) -> list[PortraitCandidate]:
    if not source_directory.is_dir():
        raise PortraitImportError(f"Cartella ritratti Elder non trovata: {source_directory}")
    if not legacy_database.is_file():
        raise PortraitImportError(f"Database Elder non trovato: {legacy_database}")

    units = list(
        Unit.objects.filter(
            archived_at__isnull=True,
            metadata__sourceProject=LEGACY_PROJECT,
        ).order_by("id")
    )
    if len(units) != expected_count:
        raise PortraitImportError(
            f"Attese {expected_count} Unit Elder canoniche, trovate {len(units)}."
        )

    all_source_ids: list[int] = []
    unit_source_ids: dict[int, tuple[int, ...]] = {}
    duplicate_links: dict[int, list[int]] = defaultdict(list)
    for unit in units:
        metadata = unit.metadata if isinstance(unit.metadata, dict) else {}
        raw_source_ids = metadata.get("sourceIds")
        if not isinstance(raw_source_ids, list) or not raw_source_ids:
            raise PortraitImportError(f"Unit #{unit.id} {unit.nome} priva di metadata.sourceIds.")
        try:
            source_ids = tuple(sorted({int(source_id) for source_id in raw_source_ids}))
        except (TypeError, ValueError) as error:
            raise PortraitImportError(
                f"Unit #{unit.id} {unit.nome} contiene sourceIds non validi."
            ) from error
        unit_source_ids[unit.id] = source_ids
        all_source_ids.extend(source_ids)
        for source_id in source_ids:
            duplicate_links[source_id].append(unit.id)
    duplicated = {
        source_id: linked_units
        for source_id, linked_units in duplicate_links.items()
        if len(linked_units) > 1
    }
    if duplicated:
        raise PortraitImportError(f"Source ID Elder collegati a più Unit: {duplicated}")

    source_names = _source_names_by_id(legacy_database, all_source_ids)
    missing_source_rows = sorted(set(all_source_ids) - set(source_names))
    if missing_source_rows:
        raise PortraitImportError(
            "Righe Unit Elder mancanti nel database sorgente: "
            + ", ".join(str(source_id) for source_id in missing_source_rows)
        )

    source_files = [
        path
        for path in source_directory.iterdir()
        if path.is_file() and path.suffix.casefold() in SUPPORTED_SOURCE_SUFFIXES
    ]
    exact_files: dict[str, list[Path]] = defaultdict(list)
    normalized_files: dict[str, list[Path]] = defaultdict(list)
    for path in source_files:
        exact_files[path.stem].append(path)
        normalized_files[normalize_portrait_name(path.stem)].append(path)

    candidates: list[PortraitCandidate] = []
    for unit in units:
        source_ids = unit_source_ids[unit.id]
        legacy_names = list(
            dict.fromkeys(source_names[source_id] for source_id in source_ids if source_names[source_id])
        )
        strategies = (
            ("legacy-name-exact", legacy_names, exact_files),
            ("unit-name-exact", [unit.nome], exact_files),
            ("legacy-name-normalized", legacy_names, normalized_files),
            ("unit-name-normalized", [unit.nome], normalized_files),
        )
        matched: list[Path] = []
        strategy = ""
        for strategy_name, names, index in strategies:
            matches = {
                path
                for name in names
                for path in index.get(
                    name if strategy_name.endswith("exact") else normalize_portrait_name(name),
                    [],
                )
            }
            if matches:
                matched = sorted(matches, key=lambda path: path.name.casefold())
                strategy = strategy_name
                break
        blockers = []
        if not matched:
            blockers.append("source_portrait_missing")
        elif len(matched) > 1:
            blockers.append("source_portrait_ambiguous")
        candidates.append(
            PortraitCandidate(
                unit_id=unit.id,
                unit_name=unit.nome,
                source_ids=source_ids,
                source_path=matched[0] if len(matched) == 1 else None,
                match_strategy=strategy or "unmatched",
                blockers=tuple(blockers),
            )
        )
    return candidates


def _webp_mode(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    ):
        return image.convert("RGBA")
    if image.mode not in {"RGB", "RGBA"}:
        return image.convert("RGB")
    return image


def stage_portrait_candidates(
    candidates: list[PortraitCandidate],
    staging_directory: Path,
    *,
    quality: int = 70,
) -> dict[str, Any]:
    source_stage = staging_directory / "source"
    converted_stage = staging_directory / "converted"
    source_stage.mkdir(parents=True, exist_ok=True)
    converted_stage.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, Any]] = []
    content_groups: dict[str, list[int]] = defaultdict(list)
    for candidate in candidates:
        entry: dict[str, Any] = {
            "unitId": candidate.unit_id,
            "unitName": candidate.unit_name,
            "sourceIds": list(candidate.source_ids),
            "importKey": candidate.import_key,
            "matchStrategy": candidate.match_strategy,
            "sourcePath": str(candidate.source_path) if candidate.source_path else "",
            "blockers": list(candidate.blockers),
            "conversion": {"format": "WEBP", "quality": quality},
        }
        if candidate.source_path is None:
            entries.append(entry)
            continue

        safe_stem = slugify(candidate.unit_name, allow_unicode=True) or f"unit-{candidate.unit_id}"
        staged_source = source_stage / f"{candidate.unit_id}-{candidate.source_path.name}"
        converted = converted_stage / f"{candidate.unit_id}-{safe_stem}.webp"
        try:
            shutil.copy2(candidate.source_path, staged_source)
            source_checksum = file_sha256(staged_source)
            with Image.open(staged_source) as opened:
                opened.load()
                original_size = opened.size
                converted_image = _webp_mode(opened)
                converted_image.save(converted, format="WEBP", quality=quality, method=6)
            with Image.open(converted) as verified:
                verified.load()
                if verified.format != "WEBP" or verified.size != original_size:
                    raise PortraitImportError("La verifica WebP non conserva formato e dimensioni.")
                converted_mode = verified.mode
            converted_checksum = file_sha256(converted)
            content_groups[converted_checksum].append(candidate.unit_id)
            entry.update(
                {
                    "stagedSourcePath": str(staged_source),
                    "convertedPath": str(converted),
                    "sourceSha256": source_checksum,
                    "convertedSha256": converted_checksum,
                    "width": original_size[0],
                    "height": original_size[1],
                    "convertedMode": converted_mode,
                    "sourceBytes": staged_source.stat().st_size,
                    "convertedBytes": converted.stat().st_size,
                    "conversionStatus": "validated",
                }
            )
        except (OSError, UnidentifiedImageError, PortraitImportError) as error:
            entry["blockers"].append("conversion_failed")
            entry["conversionStatus"] = "failed"
            entry["conversionError"] = str(error)
        entries.append(entry)

    duplicate_content = [
        {"convertedSha256": checksum, "unitIds": unit_ids}
        for checksum, unit_ids in sorted(content_groups.items())
        if len(unit_ids) > 1
    ]
    manifest = {
        "version": IMPORT_VERSION,
        "sourceProject": LEGACY_PROJECT,
        "importKind": IMPORT_KIND,
        "quality": quality,
        "entries": entries,
        "duplicateContent": duplicate_content,
        "summary": {
            "units": len(entries),
            "matched": sum(bool(entry["sourcePath"]) for entry in entries),
            "validated": sum(entry.get("conversionStatus") == "validated" for entry in entries),
            "blocked": sum(bool(entry["blockers"]) for entry in entries),
            "duplicateContentGroups": len(duplicate_content),
        },
    }
    manifest_path = staging_directory / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    manifest["manifestPath"] = str(manifest_path)
    return manifest


def _existing_assets_by_import_key() -> dict[str, UploadedImage]:
    assets: dict[str, UploadedImage] = {}
    duplicates = []
    for asset in UploadedImage.objects.filter(source=ASSET_SOURCE).order_by("id"):
        metadata = asset.metadata if isinstance(asset.metadata, dict) else {}
        if metadata.get("importKind") != IMPORT_KIND:
            continue
        import_key = str(metadata.get("importKey") or "")
        if not import_key:
            continue
        if import_key in assets:
            duplicates.append(import_key)
        assets[import_key] = asset
    if duplicates:
        raise PortraitImportError(
            "UploadedImage duplicate per importKey: " + ", ".join(sorted(set(duplicates)))
        )
    return assets


@transaction.atomic
def apply_staged_portraits(
    manifest: dict[str, Any],
    *,
    allow_partial: bool = False,
) -> dict[str, int]:
    blocked = [entry for entry in manifest["entries"] if entry.get("blockers")]
    if blocked and not allow_partial:
        names = ", ".join(entry["unitName"] for entry in blocked)
        raise PortraitImportError(
            f"Importazione annullata: {len(blocked)} ritratti bloccati ({names})."
        )
    importable_entries = [
        entry for entry in manifest["entries"] if not entry.get("blockers")
    ]
    if not importable_entries:
        raise PortraitImportError("Nessun ritratto valido disponibile per l'importazione.")

    try:
        category = ImageCategory.objects.get(
            slug=PORTRAIT_CATEGORY_SLUG,
            is_active=True,
            archived_at__isnull=True,
        )
    except ImageCategory.DoesNotExist as error:
        raise PortraitImportError(
            "Categoria immagini attiva 'personaggi' non trovata."
        ) from error

    existing_assets = _existing_assets_by_import_key()
    created_files: list[tuple[Any, str]] = []
    old_files_to_delete: list[tuple[Any, str]] = []
    counts = {
        "created": 0,
        "updated": 0,
        "reused": 0,
        "linked": 0,
        "skipped": len(blocked),
    }
    try:
        for entry in importable_entries:
            unit = Unit.objects.select_for_update().get(
                pk=entry["unitId"],
                archived_at__isnull=True,
                metadata__sourceProject=LEGACY_PROJECT,
            )
            import_key = entry["importKey"]
            asset = existing_assets.get(import_key)
            is_new = asset is None
            if is_new:
                asset = UploadedImage(source=ASSET_SOURCE)

            current_metadata = asset.metadata if isinstance(asset.metadata, dict) else {}
            next_metadata = {
                **current_metadata,
                "sourceProject": LEGACY_PROJECT,
                "sourceTable": LEGACY_UNIT_TABLE,
                "sourceIds": entry["sourceIds"],
                "sourcePath": entry["sourcePath"],
                "sourceSha256": entry["sourceSha256"],
                "convertedSha256": entry["convertedSha256"],
                "conversion": entry["conversion"],
                "width": entry["width"],
                "height": entry["height"],
                "importKind": IMPORT_KIND,
                "importKey": import_key,
                "importVersion": IMPORT_VERSION,
            }
            changed = (
                is_new
                or current_metadata.get("convertedSha256") != entry["convertedSha256"]
                or asset.title != unit.nome
                or asset.category_id != category.id
                or asset.usage_type != PORTRAIT_USAGE_TYPE
                or asset.group != PORTRAIT_GROUP
                or asset.visibilita_limitata
            )
            old_file_name = asset.file.name if asset.file else ""
            asset.title = unit.nome
            asset.folder = PORTRAIT_CATEGORY_SLUG
            asset.usage_type = PORTRAIT_USAGE_TYPE
            asset.category = category
            asset.group = PORTRAIT_GROUP
            asset.visibilita_limitata = False
            asset.metadata = next_metadata
            if is_new or current_metadata.get("convertedSha256") != entry["convertedSha256"]:
                converted_path = Path(entry["convertedPath"])
                with converted_path.open("rb") as converted_file:
                    asset.file.save(converted_path.name, File(converted_file), save=False)
                created_files.append((asset.file.storage, asset.file.name))
            asset.full_clean()
            asset.save()
            existing_assets[import_key] = asset
            if old_file_name and old_file_name != asset.file.name:
                old_files_to_delete.append((asset.file.storage, old_file_name))
            if is_new:
                counts["created"] += 1
            elif changed:
                counts["updated"] += 1
            else:
                counts["reused"] += 1
            if unit.lore_image_id != asset.id:
                unit.lore_image = asset
                unit.save(update_fields=["lore_image", "updated_at"])
                counts["linked"] += 1
        for storage, old_name in old_files_to_delete:
            transaction.on_commit(lambda storage=storage, old_name=old_name: storage.delete(old_name))
    except Exception:
        for storage, created_name in created_files:
            storage.delete(created_name)
        raise
    return counts
