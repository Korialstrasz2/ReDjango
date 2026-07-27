from django.db import transaction

from backend.core.api import ApiError
from backend.core.models import Giocatore
from backend.core.security import get_or_create_giocatore_for_user

from ..selectors import ordered_personaggi_for


@transaction.atomic
def select_personaggio_for_giocatore(
    giocatore: Giocatore,
    personaggio_id: int,
    *,
    include_all: bool = False,
) -> Giocatore:
    giocatore = Giocatore.objects.select_for_update().get(pk=giocatore.pk)
    allowed_ids = [
        personaggio.id
        for personaggio in ordered_personaggi_for(giocatore, include_all=include_all)
    ]
    if personaggio_id not in allowed_ids:
        raise ApiError(
            "personaggio.not_available",
            "Questo personaggio non è disponibile per il giocatore corrente.",
            status=404,
        )

    character_ids = giocatore.character_ids if isinstance(giocatore.character_ids, list) else []
    if personaggio_id not in character_ids:
        character_ids = [*character_ids, personaggio_id]

    giocatore.active_character_id = personaggio_id
    giocatore.character_ids = character_ids
    giocatore.save(update_fields=["active_character", "character_ids", "updated_at"])
    return giocatore
