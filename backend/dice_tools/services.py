from __future__ import annotations

import re
import secrets

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from backend.core.api import ApiError
from backend.core.models import Giocatore
from backend.core.security import effective_role, has_minimum_role
from backend.media_library.models import UploadedImage

from .models import ALLOWED_DICE_SIDES, DiceSet, DiceTexture


HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _require_admin(user, giocatore: Giocatore):
    if not has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_ADMIN):
        raise ApiError("dice_sets.forbidden", "Solo un amministratore può gestire i set di dadi.", status=403)


def _dice_set_or_error(dice_set_id: int, *, include_inactive: bool = True) -> DiceSet:
    queryset = DiceSet.objects.filter(pk=dice_set_id, archived_at__isnull=True)
    if not include_inactive:
        queryset = queryset.filter(is_active=True)
    dice_set = queryset.first()
    if dice_set is None:
        raise ApiError("dice_sets.not_found", "Set di dadi non trovato.", "diceSetId", 404)
    return dice_set


def _normalized_dice(raw) -> list[int]:
    if not isinstance(raw, list) or not raw:
        raise ApiError("dice_sets.dice_required", "Scegli almeno un dado.", "dice")
    values = []
    for item in raw:
        if isinstance(item, bool):
            raise ApiError("dice_sets.invalid_die", "Il set contiene un dado non supportato.", "dice")
        try:
            side = int(item)
        except (TypeError, ValueError) as exc:
            raise ApiError("dice_sets.invalid_die", "Il set contiene un dado non supportato.", "dice") from exc
        if side not in ALLOWED_DICE_SIDES:
            raise ApiError("dice_sets.invalid_die", f"d{side} non è supportato.", "dice")
        if side not in values:
            values.append(side)
    return sorted(values)


def _color(payload: dict, key: str, fallback: str) -> str:
    value = str(payload.get(key, fallback)).strip().lower()
    if not HEX_RE.fullmatch(value):
        raise ApiError("dice_sets.invalid_color", "Usa un colore esadecimale nel formato #RRGGBB.", key)
    return value


def _values(payload: dict, current: DiceSet | None = None) -> dict:
    name = str(payload.get("name", current.name if current else "")).strip()
    if not name:
        raise ApiError("dice_sets.name_required", "Inserisci un nome per il set.", "name")
    if len(name) > 120:
        raise ApiError("dice_sets.name_too_long", "Il nome del set è troppo lungo.", "name")
    description = str(payload.get("description", current.description if current else "")).strip()
    if len(description) > 1000:
        raise ApiError("dice_sets.description_too_long", "La descrizione è troppo lunga.", "description")
    dice = _normalized_dice(payload.get("dice", current.dice if current else list(ALLOWED_DICE_SIDES)))
    return {
        "name": name,
        "description": description,
        "dice": dice,
        "surface_color": _color(payload, "surfaceColor", current.surface_color if current else "#7f2434"),
        "accent_color": _color(payload, "accentColor", current.accent_color if current else "#d0a95b"),
        "text_color": _color(payload, "textColor", current.text_color if current else "#fff4d6"),
        "is_active": bool(payload.get("isActive", current.is_active if current else True)),
        "is_default": bool(payload.get("isDefault", current.is_default if current else False)),
        "order": max(0, int(payload.get("order", current.order if current else 0) or 0)),
    }


def _bounded_integer(raw, *, field: str, minimum: int, maximum: int, fallback: int) -> int:
    try:
        value = int(fallback if raw is None else raw)
    except (TypeError, ValueError) as exc:
        raise ApiError("dice_sets.invalid_texture_transform", "La trasformazione della texture non è valida.", field) from exc
    if not minimum <= value <= maximum:
        raise ApiError("dice_sets.invalid_texture_transform", "La trasformazione della texture è fuori dai limiti consentiti.", field)
    return value


def _normalized_textures(raw, included_dice: list[int]) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ApiError("dice_sets.invalid_textures", "Le texture dei dadi devono essere un elenco.", "textures")
    values = []
    used_sides = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ApiError("dice_sets.invalid_texture", "Una texture del set non è valida.", f"textures.{index}")
        try:
            sides = int(item.get("sides", 0))
            image_id = int(item.get("imageId", 0))
        except (TypeError, ValueError) as exc:
            raise ApiError("dice_sets.invalid_texture", "Una texture del set non è valida.", f"textures.{index}") from exc
        if sides not in included_dice:
            raise ApiError("dice_sets.texture_die_missing", f"Aggiungi d{sides} al set prima di assegnargli una texture.", "textures")
        if sides in used_sides:
            raise ApiError("dice_sets.texture_duplicate", f"Puoi usare una sola texture per d{sides}.", "textures")
        if image_id <= 0 or not UploadedImage.objects.filter(pk=image_id, archived_at__isnull=True).exists():
            raise ApiError("dice_sets.texture_image_missing", "L'immagine scelta per la texture non esiste più.", "textures", 404)
        used_sides.add(sides)
        values.append({
            "sides": sides,
            "image_id": image_id,
            "offset_x": _bounded_integer(item.get("offsetX"), field="offsetX", minimum=-100, maximum=100, fallback=0),
            "offset_y": _bounded_integer(item.get("offsetY"), field="offsetY", minimum=-100, maximum=100, fallback=0),
            "scale": _bounded_integer(item.get("scale"), field="scale", minimum=50, maximum=300, fallback=100),
            "rotation": _bounded_integer(item.get("rotation"), field="rotation", minimum=-180, maximum=180, fallback=0),
        })
    return values


def _sync_textures(dice_set: DiceSet, textures: list[dict]):
    requested_sides = {entry["sides"] for entry in textures}
    dice_set.textures.exclude(sides__in=requested_sides).delete()
    for entry in textures:
        sides = entry["sides"]
        DiceTexture.objects.update_or_create(
            dice_set=dice_set,
            sides=sides,
            defaults={key: value for key, value in entry.items() if key != "sides"},
        )


def _unique_slug(name: str, current: DiceSet | None = None) -> str:
    base = slugify(name)[:70] or "set-dadi"
    slug = base
    suffix = 2
    queryset = DiceSet.objects.all()
    if current:
        queryset = queryset.exclude(pk=current.pk)
    while queryset.filter(slug=slug).exists():
        slug = f"{base[:66]}-{suffix}"
        suffix += 1
    return slug


def _validate_and_save(dice_set: DiceSet):
    if dice_set.is_default and not dice_set.is_active:
        raise ApiError("dice_sets.default_inactive", "Il set predefinito deve essere attivo.", "isDefault")
    try:
        dice_set.full_clean()
    except ValidationError as exc:
        raise ApiError("dice_sets.invalid", "; ".join(exc.messages)) from exc
    dice_set.save()
    if dice_set.is_default:
        DiceSet.objects.filter(archived_at__isnull=True).exclude(pk=dice_set.pk).update(is_default=False)
    return dice_set


@transaction.atomic
def create_dice_set(user, giocatore: Giocatore, payload: dict) -> DiceSet:
    _require_admin(user, giocatore)
    values = _values(payload)
    textures = _normalized_textures(payload.get("textures"), values["dice"])
    dice_set = DiceSet(slug=_unique_slug(values["name"]), **values)
    _validate_and_save(dice_set)
    _sync_textures(dice_set, textures)
    return dice_set


@transaction.atomic
def update_dice_set(user, giocatore: Giocatore, dice_set_id: int, payload: dict) -> DiceSet:
    _require_admin(user, giocatore)
    dice_set = _dice_set_or_error(dice_set_id)
    values = _values(payload, dice_set)
    textures = _normalized_textures(payload.get("textures"), values["dice"]) if "textures" in payload else None
    for field, value in values.items():
        setattr(dice_set, field, value)
    if payload.get("regenerateSlug"):
        dice_set.slug = _unique_slug(dice_set.name, dice_set)
    _validate_and_save(dice_set)
    if textures is not None:
        _sync_textures(dice_set, textures)
    else:
        dice_set.textures.exclude(sides__in=values["dice"]).delete()
    return dice_set


@transaction.atomic
def archive_dice_set(user, giocatore: Giocatore, dice_set_id: int) -> DiceSet:
    _require_admin(user, giocatore)
    dice_set = _dice_set_or_error(dice_set_id)
    if DiceSet.objects.filter(is_active=True, archived_at__isnull=True).exclude(pk=dice_set.pk).count() == 0:
        raise ApiError("dice_sets.last_active", "Mantieni almeno un set di dadi attivo.", status=409)
    dice_set.is_active = False
    dice_set.is_default = False
    dice_set.archived_at = timezone.now()
    dice_set.save(update_fields=["is_active", "is_default", "archived_at", "updated_at"])
    replacement = DiceSet.objects.filter(is_active=True, archived_at__isnull=True).order_by("order", "name").first()
    if replacement and not DiceSet.objects.filter(is_default=True, archived_at__isnull=True).exists():
        replacement.is_default = True
        replacement.save(update_fields=["is_default", "updated_at"])
    return dice_set


def roll_dice(payload: dict) -> dict:
    try:
        sides = int(payload.get("sides", 0))
        count = int(payload.get("count", 1))
        modifier = int(payload.get("modifier", 0))
    except (TypeError, ValueError) as exc:
        raise ApiError("dice.invalid_number", "Dado, quantità e modificatore devono essere numeri interi.") from exc
    if sides not in ALLOWED_DICE_SIDES:
        raise ApiError("dice.invalid_sides", "Questo tipo di dado non è supportato.", "sides")
    if not 1 <= count <= 10:
        raise ApiError("dice.invalid_count", "Puoi tirare da 1 a 10 dadi insieme.", "count")
    if not -100 <= modifier <= 100:
        raise ApiError("dice.invalid_modifier", "Il modificatore deve essere compreso tra -100 e 100.", "modifier")
    dice_set_id = payload.get("diceSetId")
    dice_set = _dice_set_or_error(int(dice_set_id), include_inactive=False) if dice_set_id else None
    if dice_set and sides not in [int(value) for value in dice_set.dice]:
        raise ApiError("dice.not_in_set", f"d{sides} non fa parte di {dice_set.name}.", "sides")
    rolls = [secrets.randbelow(sides) + 1 for _ in range(count)]
    subtotal = sum(rolls)
    return {
        "diceSetId": dice_set.id if dice_set else None,
        "diceSetName": dice_set.name if dice_set else "",
        "notation": f"{count}d{sides}{modifier:+d}" if modifier else f"{count}d{sides}",
        "sides": sides,
        "count": count,
        "rolls": rolls,
        "modifier": modifier,
        "subtotal": subtotal,
        "total": subtotal + modifier,
        "rolledAt": timezone.now().isoformat(),
    }
