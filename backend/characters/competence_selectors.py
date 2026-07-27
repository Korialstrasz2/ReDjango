from __future__ import annotations

import re
from typing import Any, Mapping

from django.templatetags.static import static
from django.utils.text import slugify

from backend.core.competence_defaults import COMPETENCE_DEFINITION_BY_KEY
from backend.core.models import Competenze, DatiCampagna

from .models import Personaggio, TiroCompetenza
from .services.refresh_personaggio import (
    apply_operations,
    build_personaggio_context,
    collect_calculation_effects,
    collect_personaggio_effect_payloads,
    condition_matches,
    evaluate_number,
)


THRESHOLD_RE = re.compile(r"\((?P<score>-?\d+)\)\s*(?P<text>.*?)(?=\s*\(-?\d+\)|$)", re.DOTALL)
RANK_MIN = 0
RANK_MAX = 7
EXTRA_MIN = -99
EXTRA_MAX = 99


MASTERY_FEATURES = (
    {"rank": 1, "key": "focus", "title": "Impulso", "description": "Spendi 3 Energia per aggiungere +1 al tiro."},
    {"rank": 2, "key": "d8", "title": "Dado d8", "description": "Il dado della competenza diventa un d8."},
    {"rank": 3, "key": "amplify", "title": "Impulso maggiore", "description": "Spendi 6 Energia per aggiungere +2 al tiro."},
    {"rank": 4, "key": "d10", "title": "Dado d10", "description": "Il dado della competenza diventa un d10."},
    {"rank": 5, "key": "discount", "title": "Controllo dell'Energia", "description": "Le tecniche della competenza costano 1 Energia in meno."},
    {"rank": 6, "key": "d12", "title": "Dado d12", "description": "Il dado della competenza diventa un d12."},
    {"rank": 7, "key": "rerolls", "title": "Fato domato", "description": "Due rilanci gratuiti sullo stesso tiro, una volta al giorno."},
)


def competence_key(competence: Competenze) -> str:
    metadata = competence.metadata if isinstance(competence.metadata, dict) else {}
    return str(metadata.get("key") or slugify(competence.nome).replace("-", "_")).strip()


def competence_records():
    return Competenze.objects.filter(archived_at__isnull=True).order_by("ordine", "nome")


def get_competence_record(key: str) -> Competenze:
    normalized = str(key or "").strip().lower()
    for competence in competence_records():
        if competence_key(competence) == normalized:
            return competence
    raise Competenze.DoesNotExist


def bounded_integer(raw: Any, minimum: int, maximum: int, fallback: int = 0) -> int:
    if isinstance(raw, bool):
        return fallback
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, value))


def normalized_competence_state(personaggio: Personaggio, key: str) -> dict[str, int]:
    state = personaggio.competenze if isinstance(personaggio.competenze, dict) else {}
    raw = state.get(key) if isinstance(state.get(key), Mapping) else {}
    return {
        "barra1": bounded_integer(raw.get("barra1"), RANK_MIN, RANK_MAX),
        "barra2": bounded_integer(raw.get("barra2"), RANK_MIN, RANK_MAX),
        "extra": bounded_integer(raw.get("extra"), EXTRA_MIN, EXTRA_MAX),
    }


def rank_xp(rank: int) -> int:
    normalized = bounded_integer(rank, RANK_MIN, RANK_MAX)
    return normalized * (normalized + 1) // 2


def upgrade_cost(current: int, target: int) -> int:
    current_rank = bounded_integer(current, RANK_MIN, RANK_MAX)
    target_rank = bounded_integer(target, RANK_MIN, RANK_MAX)
    return max(0, rank_xp(target_rank) - rank_xp(current_rank))


def die_sides_for_mastery(rank: int) -> int:
    normalized = bounded_integer(rank, RANK_MIN, RANK_MAX)
    if normalized >= 6:
        return 12
    if normalized >= 4:
        return 10
    if normalized >= 2:
        return 8
    return 6


def daily_marker() -> str:
    campaign = DatiCampagna.objects.filter(attiva=True, archived_at__isnull=True).order_by("id").first()
    if campaign is not None:
        return f"campaign:{campaign.id}:{campaign.giorni_da_inizio}"
    from django.utils import timezone

    return f"calendar:{timezone.localdate().isoformat()}"


def description_thresholds(description: str) -> tuple[str, list[dict[str, Any]]]:
    text = str(description or "").strip()
    matches = list(THRESHOLD_RE.finditer(text))
    if not matches:
        return text, []
    intro = text[: matches[0].start()].strip(" .")
    thresholds = [
        {
            "score": int(match.group("score")),
            "text": re.sub(r"\s+", " ", match.group("text")).strip(" ."),
        }
        for match in matches
    ]
    return intro, thresholds


def _calculation_contexts(personaggio: Personaggio) -> dict[str, Mapping[str, Any]]:
    totals = personaggio.tot if isinstance(personaggio.tot, dict) else {}
    return {
        "base": totals,
        "pre": totals,
        "final": totals,
        "personaggio": build_personaggio_context(personaggio),
    }


def _source_kind(source: str) -> str:
    lowered = source.lower()
    if lowered.startswith("equip."):
        return "equipment"
    if "abilità" in lowered or "abilita" in lowered:
        return "skill"
    return "effect"


def linked_extra_for(personaggio: Personaggio, key: str, manual_extra: int) -> dict[str, Any]:
    target = f"competenza.{key}"
    collected = collect_calculation_effects(collect_personaggio_effect_payloads(personaggio))
    contexts = _calculation_contexts(personaggio)
    effective, applied = apply_operations(target, manual_extra, collected.operations, contexts)

    strong_operations = [
        operation
        for operation in collected.operations
        if operation.target == target and operation.operation == "strong_set"
    ]
    for operation in sorted(strong_operations, key=lambda item: item.order):
        if not condition_matches(operation.condition, contexts):
            continue
        before = effective
        effective = evaluate_number(operation.value, contexts)
        applied.append({
            "target": target,
            "operation": "strong_set",
            "value": effective,
            "before": before,
            "after": effective,
            "source": operation.source,
            "order": operation.order,
        })

    effective_integer = int(round(effective))
    breakdown = []
    for operation in applied:
        source = str(operation.get("source") or "Effetto collegato")
        breakdown.append({
            "source": source,
            "sourceType": _source_kind(source),
            "operation": str(operation.get("operation") or "add"),
            "value": operation.get("value", 0),
            "delta": int(round(float(operation.get("after", 0)) - float(operation.get("before", 0)))),
        })
    return {
        "effective": effective_integer,
        "linked": effective_integer - manual_extra,
        "breakdown": breakdown,
    }


def _daily_reroll_claim(personaggio: Personaggio, key: str) -> TiroCompetenza | None:
    return (
        TiroCompetenza.objects.filter(
            personaggio=personaggio,
            competence_key=key,
            daily_marker=daily_marker(),
            rerolls_used__gt=0,
            archived_at__isnull=True,
        )
        .order_by("-created_at", "-id")
        .first()
    )


def serialize_competence_roll(roll: TiroCompetenza, *, current_marker: str | None = None) -> dict[str, Any]:
    marker = current_marker or daily_marker()
    current_state = normalized_competence_state(roll.personaggio, roll.competence_key)
    claim = _daily_reroll_claim(roll.personaggio, roll.competence_key)
    can_reroll = (
        current_state["barra2"] >= 7
        and roll.daily_marker == marker
        and roll.rerolls_used < 2
        and (claim is None or claim.id == roll.id)
    )
    return {
        "id": roll.id,
        "competenceKey": roll.competence_key,
        "competenceName": roll.competenza.nome,
        "technique": roll.technique,
        "dieSides": roll.die_sides,
        "baseRank": roll.base_rank,
        "manualExtra": roll.manual_extra,
        "linkedExtra": roll.linked_extra,
        "modifier": roll.modifier,
        "focusBonus": roll.focus_bonus,
        "multiplier": roll.multiplier,
        "energySpent": roll.energy_spent,
        "rolls": list(roll.rolls or []),
        "total": roll.total,
        "rerollsUsed": roll.rerolls_used,
        "rerollsRemaining": max(0, 2 - roll.rerolls_used) if can_reroll else 0,
        "canReroll": can_reroll,
        "rolledAt": roll.created_at.isoformat() if roll.created_at else None,
    }


def competence_catalog_payload(personaggio: Personaggio) -> dict[str, Any]:
    marker = daily_marker()
    entries = []
    spent_xp = 0
    for competence in competence_records():
        key = competence_key(competence)
        state = normalized_competence_state(personaggio, key)
        extras = linked_extra_for(personaggio, key, state["extra"])
        definition = COMPETENCE_DEFINITION_BY_KEY.get(key, {})
        metadata = competence.metadata if isinstance(competence.metadata, dict) else {}
        attribute = str(metadata.get("attribute") or definition.get("attribute") or "")
        intro, thresholds = description_thresholds(competence.descrizione)
        spent_xp += rank_xp(state["barra1"]) + rank_xp(state["barra2"])
        claim = _daily_reroll_claim(personaggio, key) if state["barra2"] >= 7 else None
        rerolls_remaining = 0 if state["barra2"] < 7 else max(0, 2 - (claim.rerolls_used if claim else 0))
        entries.append({
            "id": competence.id,
            "key": key,
            "name": competence.nome,
            "description": competence.descrizione,
            "descriptionIntro": intro,
            "thresholds": thresholds,
            "attribute": attribute,
            "category": competence.categoria,
            "iconUrl": static(f"frontend/images/competencies/icons/{key}.png"),
            "baseRank": state["barra1"],
            "masteryRank": state["barra2"],
            "manualExtra": state["extra"],
            "linkedExtra": extras["linked"],
            "effectiveExtra": extras["effective"],
            "sourceBreakdown": extras["breakdown"],
            "rollModifier": state["barra1"] + extras["effective"],
            "dieSides": die_sides_for_mastery(state["barra2"]),
            "nextBaseCost": state["barra1"] + 1 if state["barra1"] < RANK_MAX else None,
            "nextMasteryCost": state["barra2"] + 1 if state["barra2"] < RANK_MAX else None,
            "masteryFeatures": [
                {**feature, "unlocked": state["barra2"] >= feature["rank"]}
                for feature in MASTERY_FEATURES
            ],
            "dailyRerollsRemaining": rerolls_remaining,
        })

    energy_max = int(float((personaggio.tot or {}).get("energia", 0) or 0))
    recent_rolls = list(
        TiroCompetenza.objects.filter(personaggio=personaggio, archived_at__isnull=True)
        .select_related("personaggio", "competenza")
        .order_by("-created_at", "-id")[:10]
    )
    return {
        "character": {
            "id": personaggio.id,
            "name": personaggio.nome,
            "level": personaggio.livello,
            "xpAvailable": int(personaggio.pe_abilita or 0),
            "xpSpent": spent_xp,
            "energyCurrent": max(0, energy_max - int(personaggio.energia_spesa or 0)),
            "energyMaximum": energy_max,
        },
        "competencies": entries,
        "masteryFeatures": list(MASTERY_FEATURES),
        "recentRolls": [serialize_competence_roll(roll, current_marker=marker) for roll in recent_rolls],
        "backgrounds": [
            static(f"frontend/images/competencies/backgrounds/{index}.jpg")
            for index in range(1, 22)
        ],
        "effectTargetPrefix": "competenza.",
    }
