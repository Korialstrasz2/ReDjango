from .models import Character


def serialize_character(character: Character) -> dict:
    return {
        "id": character.id,
        "name": character.name,
        "ancestry": character.ancestry,
        "archetype": character.archetype,
        "level": character.level,
        "stats": character.stats,
        "resources": character.resources,
        "notes": character.notes,
        "portrait": character.portrait.to_dict() if character.portrait_id else None,
        "createdAt": character.created_at.isoformat() if character.created_at else None,
        "updatedAt": character.updated_at.isoformat() if character.updated_at else None,
    }


def list_characters_for_user(user):
    return Character.objects.filter(owner=user).select_related("portrait")


def get_character_for_user(user, character_id: int) -> Character:
    return Character.objects.select_related("portrait").get(owner=user, id=character_id)


def character_list_payload(user) -> dict:
    return {"characters": [serialize_character(character) for character in list_characters_for_user(user)]}


def character_detail_payload(character: Character) -> dict:
    return {"character": serialize_character(character)}
