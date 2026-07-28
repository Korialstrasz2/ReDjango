from __future__ import annotations

from backend.core.models import DatiCampagna, Giocatore, TimelineEvent
from backend.core.security import effective_role, has_minimum_role

from .models import (
    REPUTATION_MAX,
    REPUTATION_MIN,
    EventoReputazione,
    Fazione,
    PersonaggioLore,
    RelazioneFazione,
    clamp_reputation,
)

# Narrative bands for a reputation score. They are reading aids only: the
# numeric value stays the single source of truth for every rule.
REPUTATION_TIERS = [
    (-70, "ostilita_aperta", "Ostilità aperta"),
    (-40, "ostile", "Ostile"),
    (-15, "diffidente", "Diffidente"),
    (15, "neutrale", "Neutrale"),
    (40, "cordiale", "Cordiale"),
    (70, "amichevole", "Amichevole"),
    (REPUTATION_MAX, "alleato", "Alleati fidati"),
]


def reputation_tier(value: int) -> dict:
    for threshold, key, label in REPUTATION_TIERS:
        if value <= threshold:
            return {"key": key, "label": label}
    return {"key": "alleato", "label": "Alleati fidati"}


def _image_url(image) -> str:
    return image.file.url if image and image.file else ""


def can_manage_lore(user, giocatore: Giocatore) -> bool:
    return has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)


def resolve_campaign(giocatore: Giocatore) -> DatiCampagna | None:
    if giocatore.active_campaign_id:
        campaign = DatiCampagna.objects.filter(
            pk=giocatore.active_campaign_id,
            archived_at__isnull=True,
        ).first()
        if campaign:
            return campaign
    return DatiCampagna.objects.filter(archived_at__isnull=True, attiva=True).first()


def replay_reputations(factions: list[Fazione], events: list[EventoReputazione]) -> tuple[dict[int, int], dict[int, dict[int, dict[str, int]]]]:
    """Rebuild every current score from the base values and the event log.

    Nothing is written back: the current reputation is always derived, so
    deleting or re-dating an event genuinely rewrites the present. ``set``
    events act as absolute anchors, which is why they never propagate.

    Returns the current score per faction, plus, for each event, the previous
    and resulting value of every faction it touched.
    """
    scores = {faction.id: clamp_reputation(faction.reputazione_base) for faction in factions}
    timeline: dict[int, dict[int, dict[str, int]]] = {}
    for event in events:
        resolved: dict[int, dict[str, int]] = {}
        for effect in event.effetti.all():
            if effect.fazione_id not in scores:
                continue
            previous = scores[effect.fazione_id]
            if event.modalita == EventoReputazione.MODE_SET and effect.valore_assoluto is not None:
                current = clamp_reputation(effect.valore_assoluto)
            else:
                current = clamp_reputation(previous + effect.delta)
            scores[effect.fazione_id] = current
            resolved[effect.id] = {"previous": previous, "resulting": current}
        timeline[event.id] = resolved
    return scores, timeline


def _faction_payload(faction: Fazione, score: int, *, can_manage: bool, relations: dict[int, float], npc_counts: dict[int, int]) -> dict:
    payload = {
        "id": faction.id,
        "name": faction.nome,
        "description": faction.descrizione,
        "emblemId": faction.emblema_id,
        "emblemUrl": _image_url(faction.emblema),
        "reputation": score,
        "tier": reputation_tier(score),
        "order": faction.ordine,
        "characterCount": npc_counts.get(faction.id, 0),
    }
    if can_manage:
        # The reaction grid and the untouched starting value are master tools:
        # players read the standing, never the machinery behind it.
        payload["baseReputation"] = clamp_reputation(faction.reputazione_base)
        payload["relations"] = [
            {"targetId": target_id, "coefficient": coefficient}
            for target_id, coefficient in sorted(relations.items())
        ]
    return payload


def _event_payload(event: EventoReputazione, resolved: dict[int, dict[str, int]], names: dict[int, str], *, can_manage: bool) -> dict:
    effects = []
    for effect in event.effetti.all():
        if effect.fazione_id not in names:
            continue
        values = resolved.get(effect.id, {"previous": 0, "resulting": 0})
        effects.append({
            "id": effect.id,
            "factionId": effect.fazione_id,
            "factionName": names[effect.fazione_id],
            "delta": effect.delta,
            "absoluteValue": effect.valore_assoluto,
            "propagated": effect.propagato,
            "previous": values["previous"],
            "resulting": values["resulting"],
        })
    payload = {
        "id": event.id,
        "title": event.titolo,
        "reason": event.motivo,
        "mode": event.modalita,
        "campaignDay": event.giorno_campagna,
        "campaignTime": event.ora_campagna,
        "recordedBy": event.registrato_da,
        "createdAt": event.created_at.isoformat(),
        "effects": effects,
    }
    if can_manage:
        payload["visibleToPlayers"] = event.visibile_ai_giocatori
    return payload


def _npc_payload(npc: PersonaggioLore, names: dict[int, str], *, can_manage: bool) -> dict:
    payload = {
        "id": npc.id,
        "name": npc.nome,
        "role": npc.ruolo,
        "description": npc.descrizione,
        "portraitId": npc.ritratto_id,
        "portraitUrl": _image_url(npc.ritratto),
        "factionId": npc.fazione_id,
        "factionName": names.get(npc.fazione_id, "") if npc.fazione_id else "",
        "order": npc.ordine,
    }
    if can_manage:
        payload["visibleToPlayers"] = npc.visibile_ai_giocatori
    return payload


def _timeline_event_payload(event: TimelineEvent, *, can_manage: bool) -> dict:
    return {
        "id": event.id,
        "title": event.nome,
        "dateLabel": event.data_evento or str(event.ordine_cronologico),
        "year": event.ordine_cronologico,
        "description": event.descrizione,
        "imageId": event.immagine_id,
        "imageUrl": _image_url(event.immagine),
        "tags": event.tags if isinstance(event.tags, list) else [],
        "createdAt": event.created_at.isoformat(),
        "updatedAt": event.updated_at.isoformat(),
        "canEdit": can_manage,
    }


def lore_payload(user, giocatore: Giocatore) -> dict:
    can_manage = can_manage_lore(user, giocatore)
    campaign = resolve_campaign(giocatore)
    if campaign is None:
        return {
            "campaign": None,
            "permissions": {"canManage": can_manage},
            "factions": [],
            "npcs": [],
            "events": [],
            "timelineEvents": [],
            "limits": {"min": REPUTATION_MIN, "max": REPUTATION_MAX},
        }

    factions = list(
        Fazione.objects.filter(campagna=campaign, archived_at__isnull=True)
        .select_related("emblema")
        .order_by("ordine", "nome")
    )
    faction_names = {faction.id: faction.nome for faction in factions}

    # Every event is replayed, including the ones a player may not read, so a
    # hidden event still moves the standing everybody can see.
    events = list(
        EventoReputazione.objects.filter(campagna=campaign, archived_at__isnull=True)
        .prefetch_related("effetti")
        .order_by("giorno_campagna", "created_at", "id")
    )
    scores, timeline = replay_reputations(factions, events)

    relations: dict[int, dict[int, float]] = {}
    if can_manage:
        for relation in RelazioneFazione.objects.filter(origine__in=factions, destinazione__in=factions):
            relations.setdefault(relation.origine_id, {})[relation.destinazione_id] = relation.coefficiente

    npcs = list(
        PersonaggioLore.objects.filter(campagna=campaign, archived_at__isnull=True)
        .select_related("ritratto")
        .order_by("ordine", "nome")
    )
    npc_counts: dict[int, int] = {}
    for npc in npcs:
        if npc.fazione_id:
            npc_counts[npc.fazione_id] = npc_counts.get(npc.fazione_id, 0) + 1

    visible_events = events if can_manage else [event for event in events if event.visibile_ai_giocatori]
    visible_npcs = npcs if can_manage else [npc for npc in npcs if npc.visibile_ai_giocatori]
    timeline_events = list(
        TimelineEvent.objects.filter(
            campagna=campaign,
            archived_at__isnull=True,
        )
        .select_related("immagine")
        .order_by("ordine_cronologico", "created_at", "id")
    )

    return {
        "campaign": {
            "id": campaign.id,
            "name": campaign.nome,
            "currentDay": campaign.giorni_da_inizio,
            "currentTime": campaign.ora_corrente,
        },
        "permissions": {"canManage": can_manage},
        "factions": [
            _faction_payload(
                faction,
                scores.get(faction.id, 0),
                can_manage=can_manage,
                relations=relations.get(faction.id, {}),
                npc_counts=npc_counts,
            )
            for faction in factions
        ],
        "npcs": [_npc_payload(npc, faction_names, can_manage=can_manage) for npc in visible_npcs],
        "events": [
            _event_payload(event, timeline.get(event.id, {}), faction_names, can_manage=can_manage)
            for event in reversed(visible_events)
        ],
        "timelineEvents": [
            _timeline_event_payload(event, can_manage=can_manage)
            for event in timeline_events
        ],
        "limits": {"min": REPUTATION_MIN, "max": REPUTATION_MAX},
    }


__all__ = [
    "can_manage_lore",
    "lore_payload",
    "replay_reputations",
    "reputation_tier",
    "resolve_campaign",
]
