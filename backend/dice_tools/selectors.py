from datetime import timedelta

from django.utils import timezone

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
        # Sides without a texture fall back to a flat colour with nothing in the
        # interface saying so, which is why most sets looked half-finished.
        "untexturedDice": sorted(
            {int(side) for side in dice_set.dice}
            - {texture.sides for texture in dice_set.textures.all()}
        ),
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


def dice_history_payload(
    user,
    giocatore: Giocatore,
    *,
    player: str = "",
    character_id: int | None = None,
    source: str = "",
    since_days: int = 0,
    limit: int = 100,
    offset: int = 0,
    include_statistics: bool = False,
) -> dict:
    if not has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER):
        raise ApiError(
            "dice_history.forbidden",
            "Solo Master e Amministratori possono vedere i tiri del gruppo.",
            status=403,
        )
    records = DiceRollRecord.objects.filter(archived_at__isnull=True).select_related("giocatore", "personaggio")
    if player:
        records = records.filter(player_name__icontains=player)
    if character_id:
        records = records.filter(personaggio_id=character_id)
    if source in dict(DiceRollRecord.SOURCE_CHOICES):
        records = records.filter(source=source)
    if since_days > 0:
        records = records.filter(created_at__gte=timezone.now() - timedelta(days=since_days))
    total = records.count()
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    page = list(records.order_by("-created_at", "-id")[offset:offset + limit])
    payload = {
        "rolls": [serialize_dice_roll_record(record) for record in page],
        "total": total,
        "limit": limit,
        "offset": offset,
        "hasMore": offset + len(page) < total,
        "sources": [{"value": value, "label": label} for value, label in DiceRollRecord.SOURCE_CHOICES],
        # order_by() clears the model's default ordering: leaving it in place
        # puts created_at into the SELECT and defeats distinct().
        "players": sorted(
            value for value in
            DiceRollRecord.objects.filter(archived_at__isnull=True)
            .exclude(player_name="")
            .order_by()
            .values_list("player_name", flat=True)
            .distinct()
        ),
    }
    if include_statistics:
        payload["statistics"] = dice_statistics(records)
    return payload


def dice_statistics(records) -> dict:
    """Aggregate the filtered rolls per player and per die set.

    Every value is already stored on the record, so this is the cheap half of
    "was that d20 really that unlucky" - it does not re-roll or re-derive
    anything, it only counts what was saved.
    """
    per_player: dict[str, dict] = {}
    per_set: dict[str, dict] = {}
    face_counts: dict[int, int] = {}
    # values() also drops the select_related the caller's queryset carries,
    # which would otherwise clash with a deferred-field query.
    for record in records.values("player_name", "dice_set_name", "rolls", "total"):
        faces = [int(value) for value in (record["rolls"] or [])]
        for bucket, key in ((per_player, record["player_name"] or "—"), (per_set, record["dice_set_name"] or "—")):
            entry = bucket.setdefault(key, {"name": key, "rolls": 0, "dice": 0, "totalSum": 0, "faceSum": 0})
            entry["rolls"] += 1
            entry["dice"] += len(faces)
            entry["totalSum"] += record["total"]
            entry["faceSum"] += sum(faces)
        for face in faces:
            face_counts[face] = face_counts.get(face, 0) + 1

    def _finish(bucket: dict) -> list[dict]:
        rows = []
        for entry in bucket.values():
            rows.append({
                "name": entry["name"],
                "rolls": entry["rolls"],
                "dice": entry["dice"],
                "averageTotal": round(entry["totalSum"] / entry["rolls"], 2) if entry["rolls"] else 0,
                "averageDie": round(entry["faceSum"] / entry["dice"], 2) if entry["dice"] else 0,
            })
        return sorted(rows, key=lambda row: (-row["rolls"], row["name"]))

    return {
        "byPlayer": _finish(per_player),
        "byDiceSet": _finish(per_set),
        "faceDistribution": [
            {"face": face, "count": face_counts[face]}
            for face in sorted(face_counts)
        ],
    }
