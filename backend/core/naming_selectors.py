"""Letture del catalogo nomi: razze, culture e consistenza dei bacini."""

from __future__ import annotations

from django.utils.text import slugify

from backend.characters.race_rules import RACE_NAMES

from .models import NomiRazzeInfo
from .naming_rules import GENDER_CHOICES


def _file_url(asset) -> str:
    return asset.file.url if asset is not None and asset.file else ""


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
        # Ritratti e clip per sesso: chiavi vuote quando l'asset non è stato importato,
        # così l'interfaccia sa mostrare il segnaposto invece di un'immagine rotta.
        "images": {
            "maschile": _file_url(culture.immagine_maschile),
            "femminile": _file_url(culture.immagine_femminile),
        },
        "clips": {
            "maschile": _file_url(culture.clip_maschile),
            "femminile": _file_url(culture.clip_femminile),
        },
    }


def name_catalog_payload() -> dict:
    """Razze in ordine, ognuna con le proprie culture.

    Le razze presenti anche in `RACE_CATALOG` vengono prima e sono marcate come
    giocabili; quelle solo narrative (Ayleid, Dwemer, Maormer, Nedic, Tsaesci)
    restano disponibili perché servono a nominare PNG, non personaggi.
    """

    cultures = NomiRazzeInfo.objects.filter(archived_at__isnull=True).select_related(
        "immagine_razza", "immagine_maschile", "immagine_femminile", "clip_maschile", "clip_femminile"
    ).order_by("race", "name")
    grouped: dict[str, list[dict]] = {}
    race_images: dict[str, str] = {}
    for culture in cultures:
        payload = _culture_payload(culture)
        if not payload["usable"]:
            continue
        race_key = culture.race or "Senza razza"
        grouped.setdefault(race_key, []).append(payload)
        # Il ritratto di razza è ripetuto su ogni cultura: basta la prima che ce l'ha.
        if race_key not in race_images:
            race_images[race_key] = _file_url(culture.immagine_razza)

    playable = set(RACE_NAMES)
    races = [
        {
            "race": race,
            "slug": slugify(race),
            "playable": race in playable,
            "image": race_images.get(race, ""),
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
