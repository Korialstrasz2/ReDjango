"""Creazione di un personaggio giocabile.

Un PG nuovo nasce al livello 1, con le caratteristiche al valore base del
profilo attivo, zero PE in ogni riserva e nessuna moneta: la creazione decide
solo identità, razza, sottorazza e caratteristica preferita. I bonus razziali
non vengono scritti qui perché ``refresh_personaggio`` li ricava già da
``razza_1``/``razza_2`` tramite ``automatic_race_effects``; crearli a mano li
raddoppierebbe.
"""

from __future__ import annotations

from typing import Any, Mapping
from uuid import uuid4

from django.db import transaction
from django.utils.text import slugify

from backend.core.api import ApiError
from backend.core.defaults import (
    CHARACTERISTIC_KEYS,
    CHARACTERISTIC_LABELS,
    PREFERRED_CHARACTERISTIC_EFFECT_NAME,
    PREFERRED_CHARACTERISTIC_FORMULA,
)
from backend.core.models import Giocatore

from ..models import (
    EffettiPersonaggio,
    EffettoPersonalizzato,
    Equip,
    Faretra,
    Note,
    OperazioneEffettoPersonalizzato,
    Personaggio,
    Zaino,
)
from ..race_rules import RACE_CATALOG, race_configuration_payload, subraces_for
from .refresh_personaggio import refresh_personaggio


# La rotta è raggiungibile da qualunque giocatore: senza un tetto un account
# potrebbe riempire la campagna di schede. Master e amministratori ne sono
# esenti perché creano personaggi anche per il tavolo.
MAX_PLAYABLE_CHARACTERS_PER_PLAYER = 5

MIN_AGE = 1
MAX_AGE = 999
SEX_CHOICES = (("maschio", "Maschio"), ("femmina", "Femmina"), ("altro", "Altro"))
CREATION_EFFECT_ORIGIN = "Creazione personaggio"


def _text(values: Mapping[str, Any], key: str, limit: int) -> str:
    return str(values.get(key) or "").strip()[:limit]


def _unique_nome_interno(nome: str) -> str:
    base = slugify(nome)[:120] or "personaggio"
    for _attempt in range(10):
        candidate = f"{base}-{uuid4().hex[:10]}"
        if not Personaggio.objects.filter(nome_interno=candidate).exists():
            return candidate
    raise ApiError(
        "characters.internal_name_unavailable",
        "Non è stato possibile generare un identificativo univoco. Riprova.",
        status=409,
    )


def validate_creation_values(values: Mapping[str, Any]) -> dict[str, Any]:
    nome = _text(values, "nome", 180)
    if not nome:
        raise ApiError("characters.name_required", "Il personaggio deve avere un nome.", "nome")

    razza = _text(values, "razza", 120)
    if razza not in RACE_CATALOG:
        raise ApiError("characters.race_invalid", "Scegli una razza fra quelle disponibili.", "razza")

    sottorazza = _text(values, "sottorazza", 120)
    available = subraces_for(razza)
    if sottorazza and sottorazza not in available:
        raise ApiError(
            "characters.subrace_invalid",
            f"«{sottorazza}» non è una sottorazza di {razza}.",
            "sottorazza",
        )
    if available and not sottorazza:
        raise ApiError(
            "characters.subrace_required",
            f"{razza} richiede una sottorazza.",
            "sottorazza",
        )

    preferita = _text(values, "caratteristicaPreferita", 32).lower()
    if preferita not in CHARACTERISTIC_KEYS:
        raise ApiError(
            "characters.preferred_characteristic_invalid",
            "Scegli una caratteristica preferita fra le nove disponibili.",
            "caratteristicaPreferita",
        )

    raw_age = values.get("eta")
    eta: int | None = None
    if raw_age not in (None, ""):
        try:
            eta = int(raw_age)
        except (TypeError, ValueError) as exc:
            raise ApiError("characters.age_invalid", "L'età deve essere un numero.", "eta") from exc
        if not MIN_AGE <= eta <= MAX_AGE:
            raise ApiError(
                "characters.age_invalid",
                f"L'età deve essere compresa fra {MIN_AGE} e {MAX_AGE}.",
                "eta",
            )

    sesso = _text(values, "sesso", 80)
    valid_sexes = {key for key, _label in SEX_CHOICES}
    if sesso and sesso.lower() not in valid_sexes:
        raise ApiError("characters.sex_invalid", "Sesso non valido.", "sesso")

    return {
        "nome": nome,
        "razza": razza,
        "sottorazza": sottorazza,
        "caratteristica_preferita": preferita,
        "eta": eta,
        "sesso": dict(SEX_CHOICES).get(sesso.lower(), "") if sesso else "",
        "dettagli_personaggio": _text(values, "dettagliPersonaggio", 4000),
        "background": _text(values, "background", 8000),
    }


def _assert_quota(giocatore: Giocatore) -> None:
    if giocatore.role in {Giocatore.ROLE_MASTER, Giocatore.ROLE_ADMIN}:
        return
    owned = giocatore.character_ids if isinstance(giocatore.character_ids, list) else []
    playable = Personaggio.objects.filter(
        pk__in=[value for value in owned if isinstance(value, int)],
        tipologia="giocabile",
        archived_at__isnull=True,
    ).count()
    if playable >= MAX_PLAYABLE_CHARACTERS_PER_PLAYER:
        raise ApiError(
            "characters.quota_reached",
            f"Hai già {MAX_PLAYABLE_CHARACTERS_PER_PLAYER} personaggi giocabili. "
            "Chiedi al Master di archiviarne uno prima di crearne un altro.",
            status=409,
        )


def _create_preferred_characteristic_effect(personaggio: Personaggio, stat: str) -> EffettoPersonalizzato:
    label = CHARACTERISTIC_LABELS.get(stat, stat)
    effect = EffettoPersonalizzato.objects.create(
        personaggio=personaggio,
        nome=PREFERRED_CHARACTERISTIC_EFFECT_NAME,
        descrizione=f"Bonus progressivo su {label} legato al livello: {PREFERRED_CHARACTERISTIC_FORMULA}.",
        origine=CREATION_EFFECT_ORIGIN,
        icona="stella",
        temporaneo=False,
        ordine=1,
    )
    OperazioneEffettoPersonalizzato.objects.create(
        effetto=effect,
        ordine=1,
        bersaglio=stat,
        operazione="add",
        valore=PREFERRED_CHARACTERISTIC_FORMULA,
    )
    return effect


def _assign_to_player(giocatore: Giocatore, personaggio: Personaggio) -> None:
    owned = [
        value
        for value in (giocatore.character_ids if isinstance(giocatore.character_ids, list) else [])
        if isinstance(value, int)
    ]
    fields = []
    if personaggio.pk not in owned:
        giocatore.character_ids = [*owned, personaggio.pk]
        fields.append("character_ids")
    if giocatore.active_character_id is None:
        giocatore.active_character = personaggio
        fields.append("active_character")
    if fields:
        giocatore.save(update_fields=[*fields, "updated_at"])


@transaction.atomic
def create_personaggio(giocatore: Giocatore, values: Mapping[str, Any]) -> Personaggio:
    validated = validate_creation_values(values)
    _assert_quota(giocatore)

    nome = validated["nome"]
    equip = Equip.objects.create(nome=f"Equip - {nome}"[:160])
    zaino = Zaino.objects.create(nome=f"Zaino - {nome}"[:160])
    faretra = Faretra.objects.create(nome=f"Faretra - {nome}"[:160])
    effetti = EffettiPersonaggio.objects.create(nome=f"Effetti - {nome}"[:160])
    note = Note.objects.create(nome=f"Note - {nome}"[:160], background=validated["background"])

    personaggio = Personaggio.objects.create(
        nome=nome,
        nome_interno=_unique_nome_interno(nome),
        tipologia="giocabile",
        campagna=giocatore.active_campaign,
        razza_1=validated["razza"],
        razza_2=validated["sottorazza"],
        livello=1,
        eta=validated["eta"],
        sesso=validated["sesso"],
        caratteristica_preferita=validated["caratteristica_preferita"],
        dettagli_personaggio=validated["dettagli_personaggio"],
        monete=0,
        pe_generali=0,
        pe_rossi=0,
        pe_verdi=0,
        pe_blu=0,
        pe_abilita=0,
        equip=equip,
        zaino=zaino,
        faretra=faretra,
        note=note,
        effetti=effetti,
        metadata={"created_by": giocatore.nome, "created_via": "nuovo-pg"},
    )

    _create_preferred_characteristic_effect(personaggio, validated["caratteristica_preferita"])
    _assign_to_player(giocatore, personaggio)

    refresh_personaggio(personaggio)
    personaggio.refresh_from_db()
    return personaggio


def creation_options_payload(giocatore: Giocatore) -> dict[str, Any]:
    """Cataloghi che la procedura di creazione mostra, letti dal codice di gioco."""
    owned = [
        value
        for value in (giocatore.character_ids if isinstance(giocatore.character_ids, list) else [])
        if isinstance(value, int)
    ]
    playable = Personaggio.objects.filter(
        pk__in=owned,
        tipologia="giocabile",
        archived_at__isnull=True,
    ).count()
    unlimited = giocatore.role in {Giocatore.ROLE_MASTER, Giocatore.ROLE_ADMIN}
    return {
        **race_configuration_payload(),
        "characteristics": [
            {"value": key, "label": CHARACTERISTIC_LABELS[key]} for key in CHARACTERISTIC_KEYS
        ],
        "sexes": [{"value": key, "label": label} for key, label in SEX_CHOICES],
        "preferredCharacteristicFormula": PREFERRED_CHARACTERISTIC_FORMULA,
        "startingLevel": 1,
        "campaignName": giocatore.active_campaign.nome if giocatore.active_campaign_id else "",
        "quota": {
            "used": playable,
            "max": None if unlimited else MAX_PLAYABLE_CHARACTERS_PER_PLAYER,
            "canCreate": unlimited or playable < MAX_PLAYABLE_CHARACTERS_PER_PLAYER,
        },
    }
