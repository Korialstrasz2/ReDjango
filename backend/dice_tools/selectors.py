from .models import DiceSet, DiceTexture


def serialize_dice_texture(texture: DiceTexture) -> dict:
    metadata = texture.image.metadata if isinstance(texture.image.metadata, dict) else {}
    return {
        "sides": texture.sides,
        "imageId": texture.image_id,
        "imageUrl": texture.image.file.url if texture.image.file else "",
        "imageName": metadata.get("originalName") or texture.image.title,
        "offsetX": texture.offset_x,
        "offsetY": texture.offset_y,
        "scale": texture.scale,
        "rotation": texture.rotation,
    }


def serialize_dice_set(dice_set: DiceSet) -> dict:
    return {
        "id": dice_set.id,
        "slug": dice_set.slug,
        "name": dice_set.name,
        "description": dice_set.description,
        "dice": sorted({int(side) for side in dice_set.dice}),
        "surfaceColor": dice_set.surface_color,
        "accentColor": dice_set.accent_color,
        "textColor": dice_set.text_color,
        "textures": [serialize_dice_texture(texture) for texture in dice_set.textures.all()],
        "isActive": dice_set.is_active and dice_set.archived_at is None,
        "isDefault": dice_set.is_default,
        "order": dice_set.order,
        "createdAt": dice_set.created_at.isoformat() if dice_set.created_at else None,
        "updatedAt": dice_set.updated_at.isoformat() if dice_set.updated_at else None,
    }


def dice_set_queryset(*, include_inactive: bool = False):
    queryset = DiceSet.objects.filter(archived_at__isnull=True).prefetch_related("textures__image")
    if not include_inactive:
        queryset = queryset.filter(is_active=True)
    return queryset.order_by("order", "name")


def dice_sets_payload(*, include_inactive: bool = False) -> dict:
    sets = list(dice_set_queryset(include_inactive=include_inactive))
    selected_default = next((entry for entry in sets if entry.is_default and entry.is_active), None)
    if selected_default is None:
        selected_default = next((entry for entry in sets if entry.is_active), None)
    return {
        "diceSets": [serialize_dice_set(entry) for entry in sets],
        "defaultDiceSetId": selected_default.id if selected_default else None,
    }
