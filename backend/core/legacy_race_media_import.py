"""Importa ritratti e clip del generatore nomi Elder.

Le sorgenti sono PNG 1024x1024 da circa 1,8 MB l'uno: scaricarne uno a ogni
passaggio del mouse sarebbe inaccettabile, quindi entrano convertiti in WebP con
il lato lungo limitato. Le clip restano mp4 e vanno in `VideoClip`, non
nell'Archivio immagini, che renderizza ogni riga come `<img>`.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.text import slugify
from PIL import Image, UnidentifiedImageError

from backend.media_library.models import ImageCategory, UploadedImage, VideoClip

from .legacy_names_import import RACE_ALIASES, normalized_culture_name
from .models import NomiRazzeInfo


LEGACY_PROJECT = "the_elder_django"
ASSET_SOURCE = "elder_django"
RACE_USAGE_TYPE = "race_portrait"
RACE_GROUP = "Razze"
CULTURE_GROUP = "Culture"
CLIP_USAGE_TYPE = "race_clip"
CATEGORY_SLUG = "personaggi"

# 640 px bastano al pannello laterale e portano un PNG da 1,8 MB sotto i 100 KB.
MAXIMUM_EDGE = 640
WEBP_QUALITY = 70

SEX_SUFFIXES = {"maschile": "m", "femminile": "f"}


class RaceMediaImportError(RuntimeError):
    pass


@dataclass(frozen=True)
class MediaReport:
    races: int = 0
    culture_images: int = 0
    clips: int = 0
    linked: int = 0
    missing: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "races": self.races,
            "cultureImages": self.culture_images,
            "clips": self.clips,
            "linked": self.linked,
            "missing": list(self.missing),
        }


def _asset_root(source: Path) -> Path:
    root = source / "static" / "media" / "images" / "razze"
    if not root.is_dir():
        raise RaceMediaImportError(f"Cartella immagini Elder non trovata: {root}")
    return root


def _find(directory: Path, *candidates: str) -> Path | None:
    """Cerca ignorando le maiuscole: i file Elder mescolano «Altmer-f» e «nord-gen»."""

    if not directory.is_dir():
        return None
    available = {entry.name.casefold(): entry for entry in directory.iterdir() if entry.is_file()}
    for candidate in candidates:
        found = available.get(candidate.casefold())
        if found is not None:
            return found
    return None


def to_webp(path: Path) -> bytes:
    try:
        with Image.open(path) as image:
            image.load()
            frame = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
            frame.thumbnail((MAXIMUM_EDGE, MAXIMUM_EDGE), Image.LANCZOS)
            buffer = io.BytesIO()
            frame.save(buffer, "WEBP", quality=WEBP_QUALITY, method=6)
            return buffer.getvalue()
    except (UnidentifiedImageError, OSError) as exc:
        raise RaceMediaImportError(f"Immagine illeggibile: {path.name} ({exc})") from exc


def _category() -> ImageCategory | None:
    return ImageCategory.objects.filter(slug=CATEGORY_SLUG, is_active=True, archived_at__isnull=True).first()


def _store_image(title: str, group: str, path: Path, category: ImageCategory | None) -> UploadedImage:
    """`title` è la chiave naturale: reimportare aggiorna, non duplica."""

    content = to_webp(path)
    asset = UploadedImage.objects.filter(
        title=title, usage_type=RACE_USAGE_TYPE, group=group, archived_at__isnull=True
    ).first() or UploadedImage(title=title, usage_type=RACE_USAGE_TYPE, group=group)
    asset.category = asset.category or category
    asset.folder = group
    asset.source = ASSET_SOURCE
    asset.metadata = {
        **(asset.metadata if isinstance(asset.metadata, dict) else {}),
        "sourceProject": LEGACY_PROJECT,
        "sourceFile": path.name,
        "convertedTo": f"webp q{WEBP_QUALITY}",
        "maximumEdge": MAXIMUM_EDGE,
    }
    if asset.pk and asset.file:
        asset.file.delete(save=False)
    asset.file.save(f"{slugify(title) or 'razza'}.webp", ContentFile(content), save=False)
    asset.save()
    return asset


def _store_clip(title: str, path: Path) -> VideoClip:
    clip = VideoClip.objects.filter(
        title=title, usage_type=CLIP_USAGE_TYPE, archived_at__isnull=True
    ).first() or VideoClip(title=title, usage_type=CLIP_USAGE_TYPE)
    clip.source = ASSET_SOURCE
    clip.metadata = {
        **(clip.metadata if isinstance(clip.metadata, dict) else {}),
        "sourceProject": LEGACY_PROJECT,
        "sourceFile": path.name,
    }
    if clip.pk and clip.file:
        clip.file.delete(save=False)
    clip.file.save(path.name, ContentFile(path.read_bytes()), save=False)
    clip.save()
    return clip


def _race_source_names(race: str) -> tuple[str, ...]:
    """Elder salvava i ritratti col nome della razza di allora («orco-gen.png»)."""

    legacy = {alias for alias, current in RACE_ALIASES.items() if current == race}
    names = []
    for candidate in (race, *legacy):
        slug = slugify(candidate)
        names.extend([f"{slug}-gen.png", f"{candidate}-gen.png", f"{slug}.png", f"{candidate}.png"])
    return tuple(dict.fromkeys(names))


def plan_race_media(source: Path) -> dict[str, dict]:
    """Che cosa esiste per ogni cultura, senza toccare il database."""

    root = _asset_root(source)
    groups = root / "gruppi"
    videos = groups / "video"
    plan: dict[str, dict] = {}
    for culture in NomiRazzeInfo.objects.filter(archived_at__isnull=True).order_by("race", "name"):
        legacy_name = str((culture.metadata or {}).get("legacyName") or culture.name)
        entry: dict = {"race": culture.race, "racePortrait": _find(root, *_race_source_names(culture.race))}
        for gender, suffix in SEX_SUFFIXES.items():
            names = []
            for candidate in dict.fromkeys([culture.name, legacy_name, normalized_culture_name(legacy_name)]):
                slug = slugify(candidate)
                names.extend([f"{slug}-{suffix}.png", f"{candidate}-{suffix}.png"])
            entry[f"image_{suffix}"] = _find(groups, *names)
            entry[f"clip_{suffix}"] = _find(videos, *[f"{name[:-4]}-1.mp4" for name in names])
        plan[culture.name] = entry
    return plan


@transaction.atomic
def import_race_media(source: Path) -> MediaReport:
    plan = plan_race_media(source)
    category = _category()
    race_assets: dict[str, UploadedImage] = {}
    culture_images = 0
    clips = 0
    linked = 0
    missing: list[str] = []

    for culture in NomiRazzeInfo.objects.filter(archived_at__isnull=True).order_by("race", "name"):
        entry = plan.get(culture.name)
        if entry is None:
            continue
        fields: list[str] = []

        race_portrait = entry["racePortrait"]
        if race_portrait is not None:
            if culture.race not in race_assets:
                race_assets[culture.race] = _store_image(culture.race, RACE_GROUP, race_portrait, category)
            culture.immagine_razza = race_assets[culture.race]
            fields.append("immagine_razza")
        elif culture.race:
            missing.append(f"ritratto razza {culture.race}")

        for gender, suffix in SEX_SUFFIXES.items():
            image_path = entry[f"image_{suffix}"]
            if image_path is not None:
                title = f"{culture.name} · {gender.capitalize()}"
                setattr(culture, f"immagine_{gender}", _store_image(title, CULTURE_GROUP, image_path, category))
                fields.append(f"immagine_{gender}")
                culture_images += 1
            else:
                missing.append(f"{culture.name} {gender}")

            clip_path = entry[f"clip_{suffix}"]
            if clip_path is not None:
                clip = _store_clip(f"{culture.name} · {gender.capitalize()}", clip_path)
                clip.poster = getattr(culture, f"immagine_{gender}", None)
                clip.save(update_fields=["poster", "updated_at"])
                setattr(culture, f"clip_{gender}", clip)
                fields.append(f"clip_{gender}")
                clips += 1

        if fields:
            culture.save(update_fields=[*dict.fromkeys(fields), "updated_at"])
            linked += 1

    return MediaReport(
        races=len(race_assets),
        culture_images=culture_images,
        clips=clips,
        linked=linked,
        missing=tuple(dict.fromkeys(missing)),
    )
