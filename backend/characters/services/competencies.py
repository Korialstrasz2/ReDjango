from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from backend.core.api import ApiError
from backend.core.models import Competenze
from backend.dice_tools.services import roll_dice

from ..competence_selectors import (
    EXTRA_MAX,
    EXTRA_MIN,
    RANK_MAX,
    RANK_MIN,
    competence_catalog_payload,
    competence_key,
    daily_marker,
    die_sides_for_mastery,
    get_competence_record,
    linked_extra_for,
    normalized_competence_state,
    rank_xp,
    serialize_competence_roll,
    upgrade_cost,
)
from ..models import Personaggio, TiroCompetenza
from .resources import spend_energy


def _locked_character(character_id: int) -> Personaggio:
    try:
        return (
            Personaggio.objects.select_for_update()
            .select_related("equip", "effetti")
            .prefetch_related("effetti_personalizzati__operazioni")
            .get(pk=character_id)
        )
    except Personaggio.DoesNotExist as exc:
        raise ApiError("character.not_found", "Personaggio non trovato.", status=404) from exc


def _competence(key: str) -> Competenze:
    try:
        return get_competence_record(key)
    except Competenze.DoesNotExist as exc:
        raise ApiError("competencies.not_found", "Competenza non trovata.", "competenceKey", 404) from exc


def _persist_state(personaggio: Personaggio, key: str, state: dict[str, int]) -> None:
    all_state = dict(personaggio.competenze) if isinstance(personaggio.competenze, dict) else {}
    all_state[key] = {
        "barra1": int(state["barra1"]),
        "barra2": int(state["barra2"]),
        "extra": int(state["extra"]),
    }
    personaggio.competenze = all_state
    personaggio.save(update_fields=["competenze", "updated_at"])


@transaction.atomic
def upgrade_competence(character_id: int, key: str, track: str, target_rank: int) -> Personaggio:
    personaggio = _locked_character(character_id)
    competence = _competence(key)
    normalized_key = competence_key(competence)
    state = normalized_competence_state(personaggio, normalized_key)
    field = "barra1" if track == "base" else "barra2" if track == "mastery" else ""
    if not field:
        raise ApiError("competencies.track_invalid", "Scegli la barra da migliorare.", "track")
    try:
        target = int(target_rank)
    except (TypeError, ValueError) as exc:
        raise ApiError("competencies.rank_invalid", "Il grado deve essere un numero intero.", "targetRank") from exc
    current = state[field]
    if target == current or not RANK_MIN <= target <= RANK_MAX:
        raise ApiError(
            "competencies.rank_invalid",
            f"Il nuovo grado deve essere diverso da {current} e compreso tra {RANK_MIN} e {RANK_MAX}.",
            "targetRank",
        )
    available = int(personaggio.pe_abilita or 0)
    if target > current:
        cost = upgrade_cost(current, target)
        if cost > available:
            raise ApiError(
                "competencies.xp_insufficient",
                f"Servono {cost} PE competenze, ma ne restano {available}.",
                "targetRank",
                409,
            )
        new_balance = available - cost
    else:
        refund = rank_xp(current) - rank_xp(target)
        new_balance = available + refund
        # Deliberately no per-character counter is enforced here: the “massimo 3 volte”
        # warning is advisory scare copy only, as requested, and must not block refunds.
    state[field] = target
    personaggio.pe_abilita = new_balance
    all_state = dict(personaggio.competenze) if isinstance(personaggio.competenze, dict) else {}
    all_state[normalized_key] = state
    personaggio.competenze = all_state
    personaggio.save(update_fields=["competenze", "pe_abilita", "updated_at"])
    return personaggio


@transaction.atomic
def update_competence_extra(character_id: int, key: str, extra: int) -> Personaggio:
    personaggio = _locked_character(character_id)
    competence = _competence(key)
    normalized_key = competence_key(competence)
    try:
        value = int(extra)
    except (TypeError, ValueError) as exc:
        raise ApiError("competencies.extra_invalid", "L'extra deve essere un numero intero.", "extra") from exc
    if not EXTRA_MIN <= value <= EXTRA_MAX:
        raise ApiError(
            "competencies.extra_out_of_range",
            f"L'extra deve essere compreso tra {EXTRA_MIN} e {EXTRA_MAX}.",
            "extra",
        )
    state = normalized_competence_state(personaggio, normalized_key)
    state["extra"] = value
    _persist_state(personaggio, normalized_key, state)
    return personaggio


def _technique_values(mastery_rank: int, technique: str) -> tuple[int, int, int]:
    discount = 1 if mastery_rank >= 5 else 0
    if technique == "standard":
        return 0, 0, 1
    if technique == "focus":
        if mastery_rank < 1:
            raise ApiError("competencies.technique_locked", "Impulso richiede Maestria 1.", "technique", 409)
        return max(0, 3 - discount), 1, 1
    if technique == "amplify":
        if mastery_rank < 3:
            raise ApiError("competencies.technique_locked", "Impulso maggiore richiede Maestria 3.", "technique", 409)
        return max(0, 6 - discount), 2, 1
    raise ApiError("competencies.technique_invalid", "Tecnica del tiro non valida.", "technique")


@transaction.atomic
def roll_competence(
    character_id: int,
    key: str,
    technique: str = "standard",
    dice_set_id: int | None = None,
) -> tuple[Personaggio, TiroCompetenza]:
    personaggio = _locked_character(character_id)
    competence = _competence(key)
    normalized_key = competence_key(competence)
    state = normalized_competence_state(personaggio, normalized_key)
    extras = linked_extra_for(personaggio, normalized_key, state["extra"])
    energy_cost, focus_bonus, multiplier = _technique_values(state["barra2"], technique)
    sides = die_sides_for_mastery(state["barra2"])
    dice_payload: dict[str, Any] = {"sides": sides, "count": 1, "modifier": 0}
    if dice_set_id:
        dice_payload["diceSetId"] = dice_set_id
    raw_roll = roll_dice(dice_payload)
    die_value = int(raw_roll["rolls"][0])
    modifier = state["barra1"] + int(extras["effective"])
    total = (die_value + modifier + focus_bonus) * multiplier
    if energy_cost:
        spend_energy(personaggio, energy_cost)
    roll = TiroCompetenza.objects.create(
        personaggio=personaggio,
        competenza=competence,
        competence_key=normalized_key,
        technique=technique,
        die_sides=sides,
        base_rank=state["barra1"],
        manual_extra=state["extra"],
        linked_extra=int(extras["linked"]),
        modifier=modifier,
        focus_bonus=focus_bonus,
        multiplier=multiplier,
        energy_spent=energy_cost,
        rolls=[{"value": die_value, "total": total, "rolledAt": timezone.now().isoformat()}],
        total=total,
        daily_marker=daily_marker(),
    )
    return personaggio, roll


@transaction.atomic
def reroll_competence(character_id: int, roll_id: int) -> TiroCompetenza:
    personaggio = _locked_character(character_id)
    try:
        roll = (
            TiroCompetenza.objects.select_for_update()
            .select_related("personaggio", "competenza")
            .get(pk=roll_id, personaggio=personaggio, archived_at__isnull=True)
        )
    except TiroCompetenza.DoesNotExist as exc:
        raise ApiError("competencies.roll_not_found", "Tiro competenza non trovato.", "rollId", 404) from exc
    state = normalized_competence_state(personaggio, roll.competence_key)
    marker = daily_marker()
    if state["barra2"] < 7:
        raise ApiError("competencies.reroll_locked", "I rilanci gratuiti richiedono Maestria 7.", "rollId", 409)
    if roll.daily_marker != marker:
        raise ApiError("competencies.reroll_expired", "Questo tiro appartiene a un giorno precedente.", "rollId", 409)
    if roll.rerolls_used >= 2:
        raise ApiError("competencies.rerolls_exhausted", "Hai già usato entrambi i rilanci su questo tiro.", "rollId", 409)
    other_claim = TiroCompetenza.objects.filter(
        personaggio=personaggio,
        competence_key=roll.competence_key,
        daily_marker=marker,
        rerolls_used__gt=0,
        archived_at__isnull=True,
    ).exclude(pk=roll.pk).exists()
    if other_claim:
        raise ApiError(
            "competencies.reroll_daily_used",
            "I rilanci gratuiti di oggi sono già legati a un altro tiro di questa competenza.",
            "rollId",
            409,
        )
    raw_roll = roll_dice({"sides": roll.die_sides, "count": 1, "modifier": 0})
    die_value = int(raw_roll["rolls"][0])
    total = (die_value + roll.modifier + roll.focus_bonus) * roll.multiplier
    roll.rolls = [
        *list(roll.rolls or []),
        {"value": die_value, "total": total, "rolledAt": timezone.now().isoformat()},
    ]
    roll.total = total
    roll.rerolls_used += 1
    roll.save(update_fields=["rolls", "total", "rerolls_used", "updated_at"])
    return roll


def updated_competence_payload(personaggio: Personaggio) -> dict[str, Any]:
    personaggio.refresh_from_db()
    return competence_catalog_payload(personaggio)


def serialized_roll(roll: TiroCompetenza) -> dict[str, Any]:
    return serialize_competence_roll(roll)
