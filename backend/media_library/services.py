import hashlib
from pathlib import Path

from django.db import transaction
from django.db.models.deletion import ProtectedError, RestrictedError

from backend.core.api import ApiError

from .defaults import DEFAULT_IMAGE_GROUPS
from .models import ImageCategory, UploadedImage
from .selectors import USER_IMAGE_FOLDER


MAXIMUM_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {
    ".avif": {"image/avif"},
    ".bmp": {"image/bmp"},
    ".gif": {"image/gif"},
    ".jpeg": {"image/jpeg"},
    ".jpg": {"image/jpeg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
}


def _checksum(uploaded_file) -> str:
    hasher = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        hasher.update(chunk)
    uploaded_file.seek(0)
    return hasher.hexdigest()


def _category_for_upload(payload: dict, usage_type: str) -> ImageCategory:
    category_id = payload.get("categoryId")
    if category_id not in (None, ""):
        try:
            return ImageCategory.objects.get(pk=int(category_id), is_active=True, archived_at__isnull=True)
        except (TypeError, ValueError, ImageCategory.DoesNotExist) as exc:
            raise ApiError("media.category_not_found", "Scegli una categoria immagine valida.", "categoryId") from exc

    categories = ImageCategory.objects.filter(is_active=True, archived_at__isnull=True).order_by("order", "name")
    category = next(
        (entry for entry in categories if usage_type in (entry.usage_types or [])),
        None,
    )
    if category is None:
        category = next(
            (entry for entry in categories if "generic" in (entry.usage_types or [])),
            None,
        )
    if category is None:
        raise ApiError(
            "media.category_required",
            "Configura almeno una categoria immagine attiva dall'amministrazione Django.",
            "categoryId",
            409,
        )
    return category


@transaction.atomic
def create_uploaded_image(owner, uploaded_file, payload: dict) -> UploadedImage:
    if not uploaded_file:
        raise ApiError("media.file_required", "Seleziona un'immagine da caricare.", "file")

    mime_type = (uploaded_file.content_type or "").lower()
    extension = Path(uploaded_file.name).suffix.casefold()
    if mime_type not in ALLOWED_IMAGE_TYPES.get(extension, set()):
        raise ApiError("media.image_required", "L'archivio multimediale accetta soltanto file immagine.", "file")
    if uploaded_file.size > MAXIMUM_IMAGE_BYTES:
        raise ApiError(
            "media.image_too_large",
            "L'immagine non può superare 10 MB.",
            "file",
        )

    title = str(payload.get("title") or uploaded_file.name).strip()[:180] or uploaded_file.name[:180]
    usage_type = str(payload.get("usageType") or "generic")[:80]
    category = _category_for_upload(payload, usage_type)
    group = str(payload.get("group") or DEFAULT_IMAGE_GROUPS.get(usage_type) or "Senza gruppo").strip()[:160] or "Senza gruppo"
    asset = UploadedImage(
        title=title,
        folder=USER_IMAGE_FOLDER,
        usage_type=usage_type,
        category=category,
        group=group,
        visibilita_limitata=bool(payload.get("limitedVisibility", False)),
        source="local_upload",
        metadata={
            "ownerUserId": owner.id,
            "originalName": str(payload.get("originalName") or uploaded_file.name)[:255],
            "originalMimeType": str(payload.get("originalMimeType") or mime_type)[:120],
            "originalSizeBytes": int(payload.get("originalSizeBytes") or uploaded_file.size or 0),
            "mimeType": mime_type[:120],
            "sizeBytes": uploaded_file.size or 0,
            "sha256": _checksum(uploaded_file),
            "notes": str(payload.get("notes") or ""),
            "convertedToWebp": bool(payload.get("convertedToWebp")),
            "webpQuality": payload.get("webpQuality"),
        },
    )
    asset.file = uploaded_file
    asset.save()
    return asset


@transaction.atomic
def move_uploaded_image(asset: UploadedImage, payload: dict) -> UploadedImage:
    category_id = payload.get("categoryId")
    try:
        category = ImageCategory.objects.get(
            pk=int(category_id),
            is_active=True,
            archived_at__isnull=True,
        )
    except (TypeError, ValueError, ImageCategory.DoesNotExist) as exc:
        raise ApiError("media.category_not_found", "Scegli una categoria immagine valida.", "categoryId") from exc

    group = str(payload.get("group") or "").strip()[:160]
    if not group:
        raise ApiError("media.group_required", "Inserisci il gruppo di destinazione.", "group")

    asset.category = category
    asset.group = group
    asset.save(update_fields=["category", "group", "updated_at"])
    return asset


@transaction.atomic
def set_uploaded_image_limited_visibility(asset: UploadedImage, limited: object) -> UploadedImage:
    asset.visibilita_limitata = bool(limited)
    asset.save(update_fields=["visibilita_limitata", "updated_at"])
    return asset


@transaction.atomic
def delete_uploaded_image(asset: UploadedImage) -> None:
    thumbnail = asset.thumbnail
    original = asset.file
    try:
        asset.delete()
    except (ProtectedError, RestrictedError) as exc:
        raise ApiError(
            "media.delete_protected",
            "L'immagine è collegata a un record che deve essere modificato prima dell'eliminazione.",
            status=409,
        ) from exc
    if thumbnail:
        thumbnail.delete(save=False)
    if original:
        original.delete(save=False)
