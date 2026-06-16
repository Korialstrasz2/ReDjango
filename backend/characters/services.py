from django.db import transaction

from backend.core.api import ApiError
from backend.media_library.models import UserMediaAsset
from backend.media_library.selectors import get_media_asset_for_user

from .models import DEFAULT_RESOURCES, DEFAULT_STATS, Character


ALLOWED_FIELDS = {"name", "ancestry", "archetype", "level", "stats", "resources", "notes", "portraitId"}


def _positive_int(value, fallback: int, field: str) -> int:
    try:
        parsed = int(value or fallback)
    except (TypeError, ValueError) as exc:
        raise ApiError(f"character.{field}_invalid", f"Character {field} must be a number.", field) from exc
    return max(1, parsed)


def apply_character_payload(character: Character, payload: dict, owner) -> None:
    clean = {key: value for key, value in payload.items() if key in ALLOWED_FIELDS}
    if "name" in clean:
        fallback = character.name or "New Character"
        character.name = str(clean["name"]).strip()[:120] or fallback
    if "ancestry" in clean:
        character.ancestry = str(clean["ancestry"]).strip()[:80]
    if "archetype" in clean:
        character.archetype = str(clean["archetype"]).strip()[:80]
    if "level" in clean:
        character.level = _positive_int(clean["level"], 1, "level")
    if "notes" in clean:
        character.notes = str(clean["notes"])
    if "stats" in clean and isinstance(clean["stats"], dict):
        character.stats = {**DEFAULT_STATS, **clean["stats"]}
    if "resources" in clean and isinstance(clean["resources"], dict):
        character.resources = {**DEFAULT_RESOURCES, **clean["resources"]}
    if "portraitId" in clean:
        portrait_id = clean.get("portraitId")
        try:
            character.portrait = get_media_asset_for_user(owner, portrait_id) if portrait_id else None
        except UserMediaAsset.DoesNotExist as exc:
            raise ApiError("character.portrait_not_found", "Selected portrait was not found.", "portraitId", 404) from exc


@transaction.atomic
def create_character(owner, payload: dict) -> Character:
    character = Character(owner=owner, name=str(payload.get("name") or "New Character")[:120])
    apply_character_payload(character, payload, owner)
    character.save()
    return character


@transaction.atomic
def update_character(character: Character, payload: dict, owner) -> Character:
    apply_character_payload(character, payload, owner)
    character.save()
    return character


@transaction.atomic
def delete_character(character: Character) -> None:
    character.delete()
