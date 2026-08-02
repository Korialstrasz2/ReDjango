from __future__ import annotations

import hashlib
import json
import math
import shutil
import tempfile
import threading
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageOps

from .models import DatiMappa, UploadedImage


TILE_SIZE = 512
TILE_QUALITY = 92
_BUILD_LOCK = threading.Lock()


def image_revision(asset: UploadedImage) -> str:
    """Return a stable revision without changing the uploaded image record."""

    metadata = asset.metadata if isinstance(asset.metadata, dict) else {}
    checksum = str(metadata.get("sha256") or "").lower()
    if len(checksum) == 64 and all(character in "0123456789abcdef" for character in checksum):
        return checksum
    candidate = Path(asset.file.path)
    stat = candidate.stat()
    identity = f"{asset.file.name}:{stat.st_size}:{stat.st_mtime_ns}".encode("utf-8")
    return hashlib.sha256(identity).hexdigest()


def _tiles_root() -> Path:
    root = Path(settings.MEDIA_ROOT) / ".derived" / "travel_tiles"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _revision_directory(travel_map: DatiMappa, revision: str) -> Path:
    return _tiles_root() / str(travel_map.pk) / revision


def _read_manifest(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    required = {"width", "height", "tileSize", "maxLevel", "revision", "baseUrl"}
    return data if isinstance(data, dict) and required.issubset(data) else None


def _build_pyramid(travel_map: DatiMappa, revision: str, destination: Path) -> dict:
    source_path = Path(travel_map.image.file.path)
    with Image.open(source_path) as opened:
        source = ImageOps.exif_transpose(opened)
        source.load()
        width, height = source.size
        max_level = max(0, math.ceil(math.log2(max(width, height) / TILE_SIZE)))
        total_bytes = 0

        for level in range(max_level + 1):
            divisor = 2 ** (max_level - level)
            level_width = max(1, math.ceil(width / divisor))
            level_height = max(1, math.ceil(height / divisor))
            level_image = source if divisor == 1 else source.resize(
                (level_width, level_height),
                Image.Resampling.LANCZOS,
            )
            level_directory = destination / str(level)
            level_directory.mkdir(parents=True, exist_ok=True)
            columns = math.ceil(level_width / TILE_SIZE)
            rows = math.ceil(level_height / TILE_SIZE)
            for row in range(rows):
                for column in range(columns):
                    left = column * TILE_SIZE
                    top = row * TILE_SIZE
                    tile = level_image.crop(
                        (
                            left,
                            top,
                            min(left + TILE_SIZE, level_width),
                            min(top + TILE_SIZE, level_height),
                        )
                    )
                    if tile.mode not in {"RGB", "RGBA"}:
                        tile = tile.convert("RGB")
                    tile_path = level_directory / f"{column}-{row}.webp"
                    tile.save(tile_path, format="WEBP", quality=TILE_QUALITY, method=4)
                    total_bytes += tile_path.stat().st_size
            if level_image is not source:
                level_image.close()

    return {
        "width": width,
        "height": height,
        "tileSize": TILE_SIZE,
        "maxLevel": max_level,
        "revision": revision,
        "baseUrl": f"/media/travel-tiles/{travel_map.pk}/{revision}",
        "format": "webp",
        "byteSize": total_bytes,
    }


def ensure_travel_tiles(travel_map: DatiMappa) -> dict:
    """Build an immutable full-resolution pyramid once and return its manifest."""

    revision = image_revision(travel_map.image)
    destination = _revision_directory(travel_map, revision)
    manifest_path = destination / "manifest.json"
    manifest = _read_manifest(manifest_path)
    if manifest is not None and manifest.get("revision") == revision:
        return manifest

    with _BUILD_LOCK:
        manifest = _read_manifest(manifest_path)
        if manifest is not None and manifest.get("revision") == revision:
            return manifest

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".{revision[:12]}-", dir=destination.parent))
        try:
            manifest = _build_pyramid(travel_map, revision, temporary)
            (temporary / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            # A previous interrupted build may have left an incomplete derived
            # directory. It is safe to replace: originals live elsewhere and the
            # directory is fully reproducible from the source image.
            if destination.exists() and _read_manifest(manifest_path) is None:
                shutil.rmtree(destination, ignore_errors=True)
            try:
                temporary.replace(destination)
            except FileExistsError:
                existing = _read_manifest(manifest_path)
                if existing is None:
                    raise
                manifest = existing
        finally:
            if temporary.exists():
                shutil.rmtree(temporary, ignore_errors=True)
        return manifest


def travel_tile_path(travel_map: DatiMappa, revision: str, level: int, column: int, row: int) -> Path | None:
    if revision != image_revision(travel_map.image):
        return None
    manifest = ensure_travel_tiles(travel_map)
    if level < 0 or level > int(manifest["maxLevel"]) or column < 0 or row < 0:
        return None
    candidate = _revision_directory(travel_map, revision) / str(level) / f"{column}-{row}.webp"
    return candidate if candidate.is_file() else None
