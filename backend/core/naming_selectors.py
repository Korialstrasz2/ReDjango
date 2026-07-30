"""Letture del catalogo nomi: razze, culture e consistenza dei bacini."""

from __future__ import annotations

from django.utils.text import slugify

from backend.characters.race_rules import RACE_NAMES

from .models import NomiRazzeInfo
from .naming_rules import GENDER_CHOICES


def _culture_payload(culture: NomiRazzeInfo) -> dict:
    male = len(culture.names_male or [])
    female = len(culture.names_female or [])
    return {
        "id": culture.id,
        "name": culture.name,
        "slug": slugify(culture.name),
        "race": culture.race,
        "description": culture.description,
        "maleCount": male,
        "femaleCount": female,
        "surnameCount": len(culture.surnames or []),
        # Un bacino unisex (Argoniani) è legittimo: conta avere almeno un nome.
        "usable": bool(male or female),
    }


def name_catalog_payload() -> dict:
    """Razze in ordine, ognuna con le proprie culture.

    Le razze presenti anche in `RACE_CATALOG` vengono prima e sono marcate come
    giocabili; quelle solo narrative (Ayleid, Dwemer, Maormer, Nedic, Tsaesci)
    restano disponibili perché servono a nominare PNG, non personaggi.
    """

    cultures = NomiRazzeInfo.objects.filter(archived_at__isnull=True).order_by("race", "name")
    grouped: dict[str, list[dict]] = {}
    for culture in cultures:
        payload = _culture_payload(culture)
        if not payload["usable"]:
            continue
        grouped.setdefault(culture.race or "Senza razza", []).append(payload)

    playable = set(RACE_NAMES)
    races = [
        {
            "race": race,
            "slug": slugify(race),
            "playable": race in playable,
            # La cultura omonima della razza è il bacino «semplice»: è quella che
            # la modalità rapida usa senza chiedere nulla in più.
            "defaultCulture": next((entry["name"] for entry in entries if entry["name"] == race), entries[0]["name"]),
            "cultures": entries,
        }
        for race, entries in grouped.items()
    ]
    races.sort(key=lambda entry: (not entry["playable"], entry["race"].lower()))
    return {
        "races": races,
        "genders": [dict(entry) for entry in GENDER_CHOICES],
        "cultureCount": sum(len(entry["cultures"]) for entry in races),
    }
