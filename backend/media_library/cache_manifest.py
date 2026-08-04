from __future__ import annotations

import hashlib
import math
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.db.models import Q
from PIL import UnidentifiedImageError

from backend.core.campaigns import selected_campaign_id
from backend.core.models import DatiCampagna, Giocatore

from .models import AudioFile, DatiMappa, UploadedImage, VideoClip
from .travel_tiles import ensure_travel_tiles, travel_tile_path


STATIC_MEDIA_DIRECTORIES = ("images", "audio", "video", "fonts")
STATIC_MEDIA_SUFFIXES = {
    ".avif", ".flac", ".gif", ".ico", ".jpeg", ".jpg", ".m4a", ".mov",
    ".mp3", ".mp4", ".oga", ".ogg", ".otf", ".png", ".svg", ".ttf",
    ".wav", ".webm", ".webp", ".woff", ".woff2",
}


def _file_size(field) -> int:
    if not field:
        return 0
    try:
        return int(field.size)
    except (OSError, TypeError, ValueError):
        return 0


def _revision(record, field, *, metadata_sha: bool = False) -> str:
    metadata = record.metadata if isinstance(record.metadata, dict) else {}
    digest = str(metadata.get("sha256") or "").casefold() if metadata_sha else ""
    if len(digest) == 64 and all(character in "0123456789abcdef" for character in digest):
        return digest
    identity = ":".join(
        (
            str(field.name if field else ""),
            str(_file_size(field)),
            record.updated_at.isoformat() if record.updated_at else "",
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _entry(*, url: str, revision: str, size: int, kind: str, label: str, cache_key: str | None = None) -> dict:
    return {
        "url": url,
        "cacheKey": cache_key or url,
        "revision": revision,
        "size": max(0, int(size)),
        "kind": kind,
        "label": label,
    }


@lru_cache(maxsize=4096)
def _content_digest(path_string: str, size: int, modified_ns: int) -> str:
    del size, modified_ns  # They intentionally form part of the cache key.
    digest = hashlib.sha256()
    with Path(path_string).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _static_media_entries() -> list[dict]:
    static_root = Path(settings.BASE_DIR) / "frontend" / "static" / "frontend"
    entries: list[dict] = []
    for directory_name in STATIC_MEDIA_DIRECTORIES:
        directory = static_root / directory_name
        if not directory.is_dir():
            continue
        for candidate in sorted(directory.rglob("*")):
            if not candidate.is_file() or candidate.suffix.casefold() not in STATIC_MEDIA_SUFFIXES:
                continue
            stat = candidate.stat()
            relative = candidate.relative_to(static_root).as_posix()
            static_name = f"frontend/{relative}"
            try:
                static_url = staticfiles_storage.url(static_name)
            except ValueError:
                # Online startup runs collectstatic before serving requests. The
                # fallback keeps management/tests diagnostic-friendly if the
                # manifest has not been collected yet.
                static_url = f"/static/{quote(static_name, safe='/')}"
            entries.append(_entry(
                url=static_url,
                revision=_content_digest(str(candidate), stat.st_size, stat.st_mtime_ns),
                size=stat.st_size,
                kind="static_media",
                label=f"Risorsa integrata · {relative}",
                cache_key=f"static:frontend/{relative}",
            ))
    return entries


def _tile_entries(travel_map: DatiMappa) -> list[dict]:
    try:
        manifest = ensure_travel_tiles(travel_map)
    except (OSError, UnidentifiedImageError):
        return []
    width = int(manifest["width"])
    height = int(manifest["height"])
    tile_size = int(manifest["tileSize"])
    max_level = int(manifest["maxLevel"])
    revision = str(manifest["revision"])
    base_url = str(manifest["baseUrl"]).rstrip("/")
    entries: list[dict] = []
    for level in range(max_level + 1):
        divisor = 2 ** (max_level - level)
        level_width = max(1, math.ceil(width / divisor))
        level_height = max(1, math.ceil(height / divisor))
        columns = math.ceil(level_width / tile_size)
        rows = math.ceil(level_height / tile_size)
        for row in range(rows):
            for column in range(columns):
                candidate = travel_tile_path(travel_map, revision, level, column, row)
                if candidate is None:
                    continue
                entries.append(
                    _entry(
                        url=f"{base_url}/{level}/{column}/{row}.webp",
                        revision=f"{revision}:{level}:{column}:{row}",
                        size=candidate.stat().st_size,
                        kind="map_tile",
                        label=f"{travel_map.nome} · dettaglio {level + 1}/{max_level + 1}",
                    )
                )
    return entries


def media_cache_manifest(user, giocatore: Giocatore) -> dict:
    """Describe immutable, non-restricted media for this player and campaign."""

    campaign_id = selected_campaign_id(giocatore)
    campaign = (
        DatiCampagna.objects.filter(pk=campaign_id, archived_at__isnull=True).first()
        if campaign_id
        else None
    )
    maps = list(
        DatiMappa.objects.select_related("image").filter(
            campagna_id=campaign_id,
            archived_at__isnull=True,
        ).exclude(image__visibilita_limitata=True)
    ) if campaign_id else []
    map_image_ids = {travel_map.image_id for travel_map in maps}
    image_filter = Q(campagna__isnull=True)
    if campaign_id:
        image_filter |= Q(campagna_id=campaign_id) | Q(pk__in=map_image_ids)

    entries_by_url: dict[str, dict] = {}

    def add(entry: dict) -> None:
        if entry["url"]:
            entries_by_url.setdefault(entry["url"], entry)

    images = UploadedImage.objects.filter(
        image_filter,
        archived_at__isnull=True,
        visibilita_limitata=False,
    ).order_by("id")
    for image in images:
        if image.file:
            add(_entry(
                url=image.file.url,
                revision=_revision(image, image.file, metadata_sha=True),
                size=_file_size(image.file),
                kind="image",
                label=image.title,
            ))
        if image.thumbnail:
            add(_entry(
                url=image.thumbnail.url,
                revision=_revision(image, image.thumbnail),
                size=_file_size(image.thumbnail),
                kind="thumbnail",
                label=f"{image.title} · miniatura",
            ))

    for track in AudioFile.objects.filter(archived_at__isnull=True).order_by("id"):
        if track.file:
            add(_entry(
                url=track.file.url,
                revision=_revision(track, track.file, metadata_sha=True),
                size=_file_size(track.file),
                kind="audio",
                label=track.title,
            ))

    for clip in VideoClip.objects.filter(archived_at__isnull=True).order_by("id"):
        if clip.file:
            add(_entry(
                url=clip.file.url,
                revision=_revision(clip, clip.file, metadata_sha=True),
                size=_file_size(clip.file),
                kind="video",
                label=clip.title,
            ))

    for travel_map in maps:
        if travel_map.tipo == "globale":
            for entry in _tile_entries(travel_map):
                add(entry)

    for entry in _static_media_entries():
        add(entry)

    entries = list(entries_by_url.values())
    return {
        "scope": f"user-{user.pk}-campaign-{campaign_id or 0}",
        "campaign": {"id": campaign.pk, "name": campaign.nome} if campaign else None,
        "entries": entries,
        "totalBytes": sum(entry["size"] for entry in entries),
    }
