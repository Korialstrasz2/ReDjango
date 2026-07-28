"""Storage for per-item ("speciali") icons uploaded from the item editor.

The browser crops the upload to a square, scales it to 128x128 and encodes it
as WebP before sending, so this module only validates and writes the file.
Icons live next to the shared category icons under the static tree, named
after the item so `serialize_item` can find them without a database lookup.
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings

from backend.core.api import ApiError
from backend.core.models import Oggetto

from ..selectors import ITEM_ICON_SPECIAL_DIRECTORY, item_special_icon_path

MAXIMUM_ICON_BYTES = 512 * 1024
_WEBP_MAGIC = (b"RIFF", b"WEBP")


def special_icon_directory() -> Path:
    return Path(settings.BASE_DIR) / "frontend" / "static" / ITEM_ICON_SPECIAL_DIRECTORY


def _validate(uploaded_file) -> bytes:
    if not uploaded_file:
        raise ApiError("item.icon_file_required", "Seleziona un'immagine da caricare.", "file")
    if uploaded_file.size > MAXIMUM_ICON_BYTES:
        raise ApiError("item.icon_too_large", "L'icona supera il limite di 512 KB.", "file")

    content = uploaded_file.read()
    if content[:4] != _WEBP_MAGIC[0] or content[8:12] != _WEBP_MAGIC[1]:
        raise ApiError("item.icon_invalid_format", "L'icona deve essere in formato WebP.", "file")
    return content


def store_special_item_icon(item: Oggetto, uploaded_file) -> str:
    """Write the icon for `item` and return the static path it was saved to."""
    content = _validate(uploaded_file)
    relative_path = item_special_icon_path(item.nome)
    if not relative_path:
        raise ApiError("item.icon_name_required", "L'oggetto deve avere un nome per usare un'icona dedicata.", "nome")

    directory = special_icon_directory()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / Path(relative_path).name).write_bytes(content)
    return relative_path


def delete_special_item_icon(item: Oggetto) -> bool:
    """Remove the dedicated icon for `item`; returns True when one existed."""
    relative_path = item_special_icon_path(item.nome)
    if not relative_path:
        return False
    target = special_icon_directory() / Path(relative_path).name
    if not target.is_file():
        return False
    target.unlink()
    return True
