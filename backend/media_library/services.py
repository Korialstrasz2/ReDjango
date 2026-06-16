from django.db import transaction

from backend.core.api import ApiError

from .models import UserMediaAsset


@transaction.atomic
def create_media_asset(owner, uploaded_file, payload: dict) -> UserMediaAsset:
    if not uploaded_file:
        raise ApiError("media.file_required", "Missing file upload.", "file")

    title = str(payload.get("title") or uploaded_file.name).strip()[:160] or uploaded_file.name[:160]
    asset = UserMediaAsset(
        owner=owner,
        title=title,
        original_name=uploaded_file.name[:255],
        mime_type=(uploaded_file.content_type or "")[:120],
        size_bytes=uploaded_file.size or 0,
        notes=str(payload.get("notes") or ""),
    )
    asset.sha256 = UserMediaAsset.checksum(uploaded_file)
    asset.file = uploaded_file
    asset.save()
    return asset


@transaction.atomic
def delete_media_asset(asset: UserMediaAsset) -> None:
    if asset.file:
        asset.file.delete(save=False)
    asset.delete()
