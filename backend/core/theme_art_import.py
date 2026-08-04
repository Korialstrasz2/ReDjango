"""Importa gli sfondi dei temi preparati fuori dal progetto.

Le sorgenti sono PNG in Downloads, una per superficie, con nomi
«{theme-slug}-{surface-key}.png». Entrano convertite in WebP al 70%,
senza ridimensionamento: ogni superficie conserva la propria proporzione
(pagine 16:9, strumenti rapidi 3:4). Ogni file diventa un UploadedImage
dell'Archivio e viene agganciato al tema come riga ThemeBackground.

Reimportare aggiorna le righe esistenti (chiave naturale nel metadata) e
sostituisce il file: non duplica. Gli sfondi di serie restano intatti.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import transaction
from PIL import Image, UnidentifiedImageError

from backend.media_library.models import ImageCategory, UploadedImage

from .models import Theme, ThemeBackground
from .theme_surfaces import THEME_SURFACES


WEBP_QUALITY = 70

# Le superfici importabili: le pagine 16:9 e gli strumenti rapidi 3:4, cioè i
# file che compaiono in Downloads come «{slug}-{surface}.png». Le modali non
# hanno ancora immagini dedicate.
IMPORTABLE_SURFACES = [
    "dashboard",
    "personaggio",
    "skills",
    "competencies",
    "creation",
    "combat",
    "travel",
    "market",
    "lore",
    "media",
    "guide",
    "settings",
    "journal",
    "dice",
    "ai",
    "audio",
    "theft",
]

SURFACE_LABELS = {entry["key"]: entry["label"] for entry in THEME_SURFACES}


class ThemeArtImportError(RuntimeError):
    pass


@dataclass(frozen=True)
class ThemeArtReport:
    imported: int = 0
    updated: int = 0
    missing: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "imported": self.imported,
            "updated": self.updated,
            "missing": list(self.missing),
        }


def _to_webp(path: Path) -> bytes:
    """PNG → WebP q70 senza ridimensionare: la proporzione della superficie è voluta."""
    try:
        with Image.open(path) as image:
            image.load()
            frame = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
            buffer = io.BytesIO()
            frame.save(buffer, "WEBP", quality=WEBP_QUALITY, method=6)
            return buffer.getvalue()
    except (UnidentifiedImageError, OSError) as exc:
        raise ThemeArtImportError(f"Immagine illeggibile: {path.name} ({exc})") from exc


def _theme_category() -> ImageCategory | None:
    # SQLite non supporta il lookup JSON «contains»: filtra in Python.
    return next(
        (
            category
            for category in ImageCategory.objects.filter(
                is_active=True, archived_at__isnull=True
            ).order_by("order", "name")
            if "theme_background" in (category.usage_types or [])
        ),
        None,
    )


def _seed_key(theme_slug: str, surface_key: str) -> str:
    return f"theme-art:{theme_slug}:{surface_key}"


def _surface_sources(source: Path, theme_slug: str) -> dict[str, Path]:
    """superficie → file PNG in Downloads, per il tema dato."""
    found: dict[str, Path] = {}
    for surface_key in IMPORTABLE_SURFACES:
        candidate = source / f"{theme_slug}-{surface_key}.png"
        if candidate.is_file():
            found[surface_key] = candidate
    return found


def _store_asset(
    theme: Theme, surface_key: str, path: Path, category: ImageCategory | None
) -> UploadedImage:
    content = _to_webp(path)
    seed_key = _seed_key(theme.slug, surface_key)
    label = SURFACE_LABELS.get(surface_key, surface_key)
    title = f"Tema {theme.name} · {label}"

    asset = UploadedImage.objects.filter(
        metadata__seed_key=seed_key, archived_at__isnull=True
    ).first() or UploadedImage(
        title=title,
        usage_type="theme_background",
        group="Temi",
        folder=f"themes/{theme.slug}",
        source="user_art",
        prompt="Sfondo del tema importato dagli sfondi preparati a parte per ReDjango.",
        metadata={
            "seed_kind": "theme_art",
            "seed_key": seed_key,
            "theme": theme.slug,
            "surface": surface_key,
            "convertedTo": f"webp q{WEBP_QUALITY}",
        },
    )
    is_new = asset.pk is None
    asset.category = asset.category or category
    asset.metadata = {
        **(asset.metadata if isinstance(asset.metadata, dict) else {}),
        "seed_kind": "theme_art",
        "seed_key": seed_key,
        "theme": theme.slug,
        "surface": surface_key,
        "convertedTo": f"webp q{WEBP_QUALITY}",
        "sourceFile": path.name,
    }
    if asset.pk and asset.file:
        asset.file.delete(save=False)
    asset.file.save(f"{theme.slug}-{surface_key}.webp", ContentFile(content), save=False)
    asset.save()
    return asset, is_new


@transaction.atomic
def import_theme_art(source: Path, themes: tuple[str, ...]) -> ThemeArtReport:
    if not source.is_dir():
        raise ThemeArtImportError(f"Cartella sorgente non trovata: {source}")

    category = _theme_category()
    imported = 0
    updated = 0
    missing: list[str] = []

    for theme_slug in themes:
        try:
            theme = Theme.objects.get(slug=theme_slug, archived_at__isnull=True)
        except Theme.DoesNotExist as exc:
            raise ThemeArtImportError(f"Tema sconosciuto: {theme_slug}") from exc

        sources = _surface_sources(source, theme_slug)
        for surface_key in IMPORTABLE_SURFACES:
            path = sources.get(surface_key)
            if path is None:
                missing.append(f"{theme_slug}-{surface_key}")
                continue
            asset, is_new = _store_asset(theme, surface_key, path, category)
            ThemeBackground.objects.update_or_create(
                theme=theme,
                surface_key=surface_key,
                defaults={"image": asset},
            )
            if is_new:
                imported += 1
            else:
                updated += 1

    return ThemeArtReport(imported=imported, updated=updated, missing=tuple(dict.fromkeys(missing)))
