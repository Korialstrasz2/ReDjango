from backend.core.api import ApiError
from backend.core.models import Giocatore
from backend.core.security import effective_role, has_minimum_role

from .models import DiceRollRecord, DiceSet, DiceTexture


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


def serialize_dice_roll_record(record: DiceRollRecord) -> dict:
    metadata = record.metadata if isinstance(record.metadata, dict) else {}
    return {
        "id": record.id,
        "source": record.source,
        "sourceLabel": "Rilancio competenza" if metadata.get("reroll") else record.get_source_display(),
        "playerName": record.player_name,
        "characterId": record.personaggio_id,
        "characterName": record.character_name,
        "label": record.label,
        "notation": record.notation,
        "rolls": [int(value) for value in (record.rolls or [])],
        "modifier": record.modifier,
        "total": record.total,
        "diceSetName": record.dice_set_name,
        "rolledAt": record.created_at.isoformat(),
    }


def dice_history_payload(user, giocatore: Giocatore) -> dict:
    if not has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER):
        raise ApiError(
            "dice_history.forbidden",
            "Solo Master e Amministratori possono vedere i tiri del gruppo.",
            status=403,
        )
    records = (
        DiceRollRecord.objects.filter(archived_at__isnull=True)
        .select_related("giocatore", "personaggio")
        .order_by("-created_at", "-id")[:100]
    )
    return {
        "rolls": [serialize_dice_roll_record(record) for record in records],
        "limit": 100,
    }
