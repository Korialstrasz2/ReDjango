from pathlib import Path

from django.db import models

from backend.core.models import Giocatore
from backend.core.security import effective_role, get_or_create_giocatore_for_user, has_minimum_role

from .models import ImageCategory, UploadedImage


USER_IMAGE_FOLDER = "user_media"

USAGE_TYPE_LABELS = {
    "core.campaignloreentry": "Voce della storia",
    "core.daticampagna": "Campagna",
    "core.guida": "Guida",
    "core.halloffamecharacter": "Personaggio della Hall of Fame",
    "core.negozio": "Negozio",
    "core.oggetto": "Oggetto",
    "core.theme": "Tema",
    "core.timelineevent": "Evento della cronologia",
    "core.unit": "Unità",
    "dice_tools.dicetexture": "Texture dado",
    "media_library.datimappa": "Mappa",
    "media_library.uploadedimage": "Versione immagine",
}


def _metadata(asset: UploadedImage) -> dict:
    return asset.metadata if isinstance(asset.metadata, dict) else {}


def user_can_manage_all_images(user) -> bool:
    if not user:
        return False
    giocatore = get_or_create_giocatore_for_user(user)
    return has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_ADMIN)


def user_can_view_limited_images(user) -> bool:
    if not user:
        return False
    giocatore = get_or_create_giocatore_for_user(user)
    return has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)


def can_manage_uploaded_image(user, asset: UploadedImage, *, manage_all: bool | None = None) -> bool:
    if not user:
        return False
    if manage_all is None:
        manage_all = user_can_manage_all_images(user)
    return bool(manage_all)


def serialize_uploaded_image(asset: UploadedImage, user=None, *, manage_all: bool | None = None) -> dict:
    metadata = _metadata(asset)
    original_name = metadata.get("originalName") or Path(asset.file.name).name
    size_bytes = metadata.get("sizeBytes")
    if size_bytes is None and asset.file:
        try:
            size_bytes = asset.file.size
        except OSError:
            size_bytes = 0
    return {
        "id": asset.id,
        "title": asset.title,
        "originalName": original_name,
        "url": asset.file.url if asset.file else "",
        "thumbnailUrl": asset.thumbnail.url if asset.thumbnail else "",
        "mimeType": metadata.get("mimeType", "image/*"),
        "sizeBytes": size_bytes or 0,
        "notes": metadata.get("notes", ""),
        "folder": asset.folder,
        "usageType": asset.usage_type,
        "categoryId": asset.category_id,
        "category": asset.category.name if asset.category_id and asset.category else "Senza categoria",
        "categorySlug": asset.category.slug if asset.category_id and asset.category else "",
        "group": asset.group or "Senza gruppo",
        "source": asset.source,
        "limitedVisibility": asset.visibilita_limitata,
        "createdAt": asset.created_at.isoformat() if asset.created_at else None,
        "canDelete": can_manage_uploaded_image(user, asset, manage_all=manage_all),
        "canMove": can_manage_uploaded_image(user, asset, manage_all=manage_all),
        "canSetLimitedVisibility": can_manage_uploaded_image(user, asset, manage_all=manage_all),
    }


def list_uploaded_images_for_user(user):
    assets = UploadedImage.objects.select_related("category").filter(
        archived_at__isnull=True,
    )
    if not user_can_view_limited_images(user):
        assets = assets.filter(visibilita_limitata=False)
    return assets.order_by("category__order", "category__name", "group", "title")


def get_uploaded_image_for_user(user, asset_id: int) -> UploadedImage:
    assets = UploadedImage.objects.select_related("category").filter(id=asset_id, archived_at__isnull=True)
    if user_can_manage_all_images(user):
        return assets.get()
    if user_can_view_limited_images(user):
        return assets.get()
    return assets.get(folder=USER_IMAGE_FOLDER, metadata__ownerUserId=user.id)


def _usage_record_name(record, model_label: str) -> str:
    if model_label == "dice_tools.dicetexture":
        return f"{record.dice_set.name} · d{record.sides}"
    for field_name in ("nome", "name", "title", "slug"):
        value = getattr(record, field_name, None)
        if value:
            return str(value)
    return f"#{record.pk}"


def _deletion_behavior(field) -> str:
    on_delete = field.remote_field.on_delete
    if on_delete is models.CASCADE:
        return "cascade"
    if on_delete is models.SET_NULL:
        return "clear"
    if on_delete is models.PROTECT or on_delete is models.RESTRICT:
        return "protect"
    return "other"


def uploaded_image_usages(asset: UploadedImage) -> list[dict]:
    usages = []
    for relation in asset._meta.related_objects:
        field = relation.field
        related_model = relation.related_model
        model_label = related_model._meta.label_lower
        type_label = USAGE_TYPE_LABELS.get(model_label, str(related_model._meta.verbose_name).capitalize())
        records = related_model._default_manager.filter(**{field.name: asset})
        if model_label == "dice_tools.dicetexture":
            records = records.select_related("dice_set")
        for record in records:
            record_name = _usage_record_name(record, model_label)
            usages.append(
                {
                    "model": model_label,
                    "type": type_label,
                    "id": record.pk,
                    "name": record_name,
                    "label": f"{type_label}: {record_name}",
                    "field": str(field.verbose_name),
                    "deletionBehavior": _deletion_behavior(field),
                }
            )
    return sorted(usages, key=lambda entry: (entry["type"], entry["name"], entry["id"]))


def media_list_payload(user) -> dict:
    manage_all = user_can_manage_all_images(user)
    return {
        "assets": [
            serialize_uploaded_image(asset, user, manage_all=manage_all)
            for asset in list_uploaded_images_for_user(user)
        ],
        "categories": [
            {
                "id": category.id,
                "name": category.name,
                "slug": category.slug,
                "description": category.description,
                "usageTypes": category.usage_types if isinstance(category.usage_types, list) else [],
                "order": category.order,
            }
            for category in ImageCategory.objects.filter(
                is_active=True,
                archived_at__isnull=True,
            ).order_by("order", "name")
        ],
    }


def media_detail_payload(asset: UploadedImage, user=None) -> dict:
    usages = uploaded_image_usages(asset)
    return {
        "asset": serialize_uploaded_image(asset, user),
        "usages": usages,
        "usageCount": len(usages),
    }
