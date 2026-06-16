from .models import UserMediaAsset


def serialize_media_asset(asset: UserMediaAsset) -> dict:
    url = asset.file.url if asset.file else ""
    return {
        "id": asset.id,
        "title": asset.title,
        "originalName": asset.original_name,
        "url": url,
        "mimeType": asset.mime_type,
        "sizeBytes": asset.size_bytes,
        "sha256": asset.sha256,
        "notes": asset.notes,
        "createdAt": asset.created_at.isoformat() if asset.created_at else None,
    }


def list_media_assets_for_user(user):
    return UserMediaAsset.objects.filter(owner=user)


def get_media_asset_for_user(user, asset_id: int) -> UserMediaAsset:
    return UserMediaAsset.objects.get(owner=user, id=asset_id)


def media_list_payload(user) -> dict:
    return {"assets": [serialize_media_asset(asset) for asset in list_media_assets_for_user(user)]}


def media_detail_payload(asset: UserMediaAsset) -> dict:
    return {"asset": serialize_media_asset(asset)}
