"""Generazione di un nome da un bacino configurato.

Nessun fallback in codice: se una cultura non ha bacini utilizzabili l'errore lo
dice, invece di restituire silenziosamente un nome preso da un'altra parte.
"""

from __future__ import annotations

import random

from backend.characters.models import Personaggio
from backend.core.api import ApiError
from backend.lore.models import PersonaggioLore

from .campaigns import selected_campaign_id
from .models import Giocatore, NomiRazzeInfo
from .naming_rules import (
    GENDER_RANDOM,
    join_name,
    normalize_display,
    normalize_gender,
    pick,
    pool_for_gender,
    resolve_gender,
)


# Tentativi di riestrazione prima di arrendersi a un nome già usato: oltre questo
# numero il bacino è troppo piccolo perché l'unicità sia ottenibile, e il nome
# viene restituito comunque con l'avviso.
UNIQUENESS_ATTEMPTS = 8


def _usable(culture: NomiRazzeInfo) -> bool:
    return bool(culture.names_male or culture.names_female)


def _resolve_culture(payload: dict, *, rng: random.Random) -> NomiRazzeInfo:
    cultures = NomiRazzeInfo.objects.filter(archived_at__isnull=True)
    culture_id = payload.get("cultureId")
    if culture_id not in (None, ""):
        try:
            return cultures.get(pk=int(culture_id))
        except (TypeError, ValueError, NomiRazzeInfo.DoesNotExist) as exc:
            raise ApiError("names.culture_not_found", "Cultura non trovata.", "cultureId", 404) from exc

    race = str(payload.get("race") or "").strip()
    if not race:
        raise ApiError("names.race_required", "Scegli una razza.", "race")
    candidates = [entry for entry in cultures.filter(race__iexact=race).order_by("name") if _usable(entry)]
    if not candidates:
        raise ApiError(
            "names.pool_missing",
            f"Nessun bacino di nomi è configurato per «{race}». Importalo o aggiungilo da Django Admin.",
            "race",
            409,
        )
    # Chi clicca la razza e nient'altro sta chiedendo «sorprendimi»: la cultura
    # va tirata fra tutte quelle della razza, non fatta cadere sempre sulla stessa.
    if payload.get("randomCulture"):
        return rng.choice(candidates)
    # Altrimenti vince la cultura omonima della razza, il bacino «semplice».
    return next(
        (entry for entry in candidates if entry.name.casefold() == race.casefold()),
        candidates[0],
    )


def _taken_names(giocatore: Giocatore) -> set[str]:
    """Nomi già in uso nella campagna selezionata, per non generare un doppione."""

    campaign_id = selected_campaign_id(giocatore)
    if campaign_id is None:
        return set()
    lore_names = PersonaggioLore.objects.filter(
        campagna_id=campaign_id, archived_at__isnull=True
    ).values_list("nome", flat=True)
    character_names = Personaggio.objects.filter(
        campagna_id=campaign_id, archived_at__isnull=True
    ).values_list("nome", flat=True)
    return {str(name).strip().casefold() for name in [*lore_names, *character_names] if str(name).strip()}


def generate_name(giocatore: Giocatore, payload: dict) -> dict:
    """Un nome completo, pronto per il tavolo.

    Non scrive nulla: la generazione è una lettura del bacino più un tiro.
    """

    rng = random.Random()
    culture = _resolve_culture(payload, rng=rng)
    requested_gender = normalize_gender(payload.get("gender") or GENDER_RANDOM)
    if not requested_gender:
        raise ApiError("names.gender_invalid", "Genere non riconosciuto.", "gender")

    gender = resolve_gender(requested_gender, rng=rng)
    first_pool = pool_for_gender(culture.names_male or [], culture.names_female or [], gender)
    if not first_pool:
        raise ApiError(
            "names.pool_empty",
            f"La cultura «{culture.name}» non ha nomi configurati.",
            "cultureId",
            409,
        )

    taken = _taken_names(giocatore)
    surnames = culture.surnames or []
    full_name = ""
    first_name = ""
    surname = ""
    duplicate = True
    for _ in range(UNIQUENESS_ATTEMPTS):
        first_name = pick(first_pool, rng=rng)
        surname = pick(surnames, rng=rng) if surnames else ""
        full_name = join_name(first_name, surname, race=culture.race, gender=gender)
        if full_name.casefold() not in taken:
            duplicate = False
            break

    return {
        "name": full_name,
        "firstName": normalize_display(first_name),
        "surname": normalize_display(surname),
        "gender": gender,
        "requestedGender": requested_gender,
        "race": culture.race,
        "culture": culture.name,
        "cultureId": culture.id,
        "cultureDescription": culture.description,
        # Il tavolo deve sapere che cosa ha deciso il dado e che cosa ha deciso lui.
        "cultureWasRolled": bool(payload.get("randomCulture")) and payload.get("cultureId") in (None, ""),
        # Il tavolo deve sapere se sta per avere due Astrid, non scoprirlo dopo.
        "alreadyUsed": duplicate,
    }
