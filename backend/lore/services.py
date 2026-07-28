from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from backend.core.api import ApiError
from backend.core.models import DatiCampagna, Giocatore, TimelineEvent
from backend.media_library.models import UploadedImage

from .models import (
    REPUTATION_MAX,
    REPUTATION_MIN,
    EffettoEventoReputazione,
    EventoReputazione,
    Fazione,
    PersonaggioLore,
    RelazioneFazione,
    clamp_reputation,
)
from .selectors import can_manage_lore, resolve_campaign

MAX_COEFFICIENT = 5.0


def require_lore_manager(user, giocatore: Giocatore) -> None:
    if not can_manage_lore(user, giocatore):
        raise ApiError(
            "lore.forbidden",
            "Solo master e amministratori possono modificare il lore della campagna.",
            status=403,
        )


def require_campaign(giocatore: Giocatore) -> DatiCampagna:
    campaign = resolve_campaign(giocatore)
    if campaign is None:
        raise ApiError("lore.campaign_missing", "Nessuna campagna attiva selezionata.", status=404)
    return campaign


def _text(raw, field: str, *, required: bool = False, limit: int = 2000) -> str:
    value = str(raw or "").strip()
    if required and not value:
        raise ApiError("lore.field_required", "Questo campo è obbligatorio.", field)
    return value[:limit]


def _reputation(raw, field: str) -> int:
    try:
        return clamp_reputation(int(raw))
    except (TypeError, ValueError) as exc:
        raise ApiError(
            "lore.value_invalid",
            f"Il valore deve essere un numero intero tra {REPUTATION_MIN} e {REPUTATION_MAX}.",
            field,
        ) from exc


def _image(raw, field: str) -> UploadedImage | None:
    if raw in (None, "", 0):
        return None
    image = UploadedImage.objects.filter(pk=raw, archived_at__isnull=True).first()
    if image is None:
        raise ApiError("lore.image_not_found", "Immagine non trovata nell'archivio.", field)
    return image


def _timeline_year(raw) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ApiError(
            "lore.timeline_year_invalid",
            "L'anno della Timeline deve essere un numero intero, anche negativo.",
            "year",
        ) from exc


def _timeline_tags(raw) -> list[str]:
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        raise ApiError(
            "lore.timeline_tags_invalid",
            "Le etichette della Timeline devono essere una lista.",
            "tags",
        )
    tags: list[str] = []
    seen: set[str] = set()
    for entry in raw:
        tag = str(entry or "").strip()
        if not tag:
            continue
        if len(tag) > 40:
            raise ApiError(
                "lore.timeline_tag_too_long",
                "Ogni etichetta può contenere al massimo 40 caratteri.",
                "tags",
            )
        key = tag.casefold()
        if key not in seen:
            seen.add(key)
            tags.append(tag)
    if len(tags) > 12:
        raise ApiError(
            "lore.timeline_tags_limit",
            "Un evento può avere al massimo 12 etichette.",
            "tags",
        )
    return tags


def _faction(campaign: DatiCampagna, raw, field: str = "factionId") -> Fazione:
    faction = Fazione.objects.filter(pk=raw, campagna=campaign, archived_at__isnull=True).first()
    if faction is None:
        raise ApiError("lore.faction_not_found", "Fazione non trovata in questa campagna.", field)
    return faction


def _next_order(model, campaign: DatiCampagna) -> int:
    last = model.objects.filter(campagna=campaign, archived_at__isnull=True).order_by("-ordine").first()
    return (last.ordine + 1) if last else 0


@transaction.atomic
def save_faction(user, giocatore: Giocatore, values: dict) -> DatiCampagna:
    require_lore_manager(user, giocatore)
    campaign = require_campaign(giocatore)
    name = _text(values.get("name"), "name", required=True, limit=160)
    duplicate = Fazione.objects.filter(campagna=campaign, nome__iexact=name, archived_at__isnull=True)
    faction_id = values.get("id")
    if faction_id:
        faction = _faction(campaign, faction_id, "id")
        duplicate = duplicate.exclude(pk=faction.pk)
    else:
        faction = Fazione(campagna=campaign, ordine=_next_order(Fazione, campaign))
    if duplicate.exists():
        raise ApiError("lore.faction_duplicate", "Esiste già una fazione con questo nome.", "name")

    faction.nome = name
    faction.descrizione = _text(values.get("description"), "description", limit=4000)
    faction.emblema = _image(values.get("emblemId"), "emblemId")
    faction.reputazione_base = _reputation(values.get("baseReputation", 0), "baseReputation")
    faction.save()
    return campaign


@transaction.atomic
def delete_faction(user, giocatore: Giocatore, faction_id) -> DatiCampagna:
    """Archive a faction, keeping its past events readable."""
    require_lore_manager(user, giocatore)
    campaign = require_campaign(giocatore)
    faction = _faction(campaign, faction_id, "id")
    faction.archived_at = timezone.now()
    faction.save(update_fields=["archived_at", "updated_at"])
    RelazioneFazione.objects.filter(origine=faction).delete()
    RelazioneFazione.objects.filter(destinazione=faction).delete()
    PersonaggioLore.objects.filter(fazione=faction).update(fazione=None)
    return campaign


@transaction.atomic
def save_relations(user, giocatore: Giocatore, entries) -> DatiCampagna:
    """Replace the reaction grid with the submitted cells.

    A cell is how much the target moves for every point the source gains, so
    zero simply means "no reaction" and is stored as an absent row.
    """
    require_lore_manager(user, giocatore)
    campaign = require_campaign(giocatore)
    if not isinstance(entries, list):
        raise ApiError("lore.relations_invalid", "Formato della matrice non valido.", "relations")

    factions = {
        faction.id: faction
        for faction in Fazione.objects.filter(campagna=campaign, archived_at__isnull=True)
    }
    resolved: dict[tuple[int, int], float] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source_id = entry.get("sourceId")
        target_id = entry.get("targetId")
        if source_id not in factions or target_id not in factions:
            raise ApiError("lore.faction_not_found", "Fazione non trovata in questa campagna.", "relations")
        if source_id == target_id:
            raise ApiError(
                "lore.relation_self",
                "Una fazione non può reagire a sé stessa.",
                "relations",
            )
        try:
            coefficient = round(float(entry.get("coefficient", 0)), 3)
        except (TypeError, ValueError) as exc:
            raise ApiError("lore.coefficient_invalid", "Il moltiplicatore deve essere un numero.", "relations") from exc
        if abs(coefficient) > MAX_COEFFICIENT:
            raise ApiError(
                "lore.coefficient_range",
                f"Il moltiplicatore deve essere tra -{MAX_COEFFICIENT} e {MAX_COEFFICIENT}.",
                "relations",
            )
        resolved[(source_id, target_id)] = coefficient

    RelazioneFazione.objects.filter(origine__campagna=campaign).delete()
    RelazioneFazione.objects.bulk_create([
        RelazioneFazione(origine_id=source_id, destinazione_id=target_id, coefficiente=coefficient)
        for (source_id, target_id), coefficient in resolved.items()
        if coefficient
    ])
    return campaign


def _event_entries(campaign: DatiCampagna, raw_entries, mode: str) -> list[tuple[Fazione, int]]:
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ApiError("lore.entries_required", "Selezionare almeno una fazione.", "entries")
    seen: set[int] = set()
    entries: list[tuple[Fazione, int]] = []
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        faction = _faction(campaign, entry.get("factionId"), "entries")
        if faction.id in seen:
            raise ApiError(
                "lore.entry_duplicate",
                f"{faction.nome} è indicata più di una volta nello stesso evento.",
                "entries",
            )
        seen.add(faction.id)
        value = _reputation(entry.get("value"), "entries")
        if mode == EventoReputazione.MODE_ADJUST and value == 0:
            raise ApiError(
                "lore.delta_zero",
                f"La variazione per {faction.nome} deve essere diversa da zero.",
                "entries",
            )
        entries.append((faction, value))
    if not entries:
        raise ApiError("lore.entries_required", "Selezionare almeno una fazione.", "entries")
    return entries


def _propagated_deltas(campaign: DatiCampagna, entries: list[tuple[Fazione, int]]) -> dict[int, int]:
    """Single-hop spread of an adjustment through the reaction grid.

    A propagated change never propagates again, and a faction the master
    already named in the event keeps only the authored value: explicit intent
    always beats the grid.
    """
    authored = {faction.id for faction, _ in entries}
    totals: dict[int, int] = {}
    relations = RelazioneFazione.objects.filter(
        origine_id__in=authored,
        destinazione__campagna=campaign,
        destinazione__archived_at__isnull=True,
    )
    by_source: dict[int, list[RelazioneFazione]] = {}
    for relation in relations:
        by_source.setdefault(relation.origine_id, []).append(relation)
    for faction, delta in entries:
        for relation in by_source.get(faction.id, []):
            if relation.destinazione_id in authored:
                continue
            contribution = int(round(delta * relation.coefficiente))
            if contribution:
                totals[relation.destinazione_id] = totals.get(relation.destinazione_id, 0) + contribution
    return {faction_id: total for faction_id, total in totals.items() if total}


def _event_mode(values: dict) -> str:
    mode = str(values.get("mode") or EventoReputazione.MODE_ADJUST)
    if mode not in {EventoReputazione.MODE_ADJUST, EventoReputazione.MODE_SET}:
        raise ApiError("lore.mode_invalid", "Tipo di modifica non valido.", "mode")
    return mode


def _event_day(values: dict, campaign: DatiCampagna) -> int:
    raw_day = values.get("campaignDay")
    if raw_day in (None, ""):
        return campaign.giorni_da_inizio
    try:
        day = int(raw_day)
    except (TypeError, ValueError) as exc:
        raise ApiError("lore.day_invalid", "Il giorno di campagna deve essere un numero.", "campaignDay") from exc
    if day < 0:
        raise ApiError("lore.day_invalid", "Il giorno di campagna non può essere negativo.", "campaignDay")
    return day


def _build_effects(
    event: EventoReputazione,
    campaign: DatiCampagna,
    entries: list[tuple[Fazione, int]],
    mode: str,
) -> list[EffettoEventoReputazione]:
    effects = [
        EffettoEventoReputazione(
            evento=event,
            fazione=faction,
            delta=0 if mode == EventoReputazione.MODE_SET else value,
            valore_assoluto=value if mode == EventoReputazione.MODE_SET else None,
            propagato=False,
            ordine=index,
        )
        for index, (faction, value) in enumerate(entries)
    ]
    if mode == EventoReputazione.MODE_ADJUST:
        # An absolute correction is an anchor, not a story beat: it stays local.
        offset = len(effects)
        for index, (faction_id, delta) in enumerate(sorted(_propagated_deltas(campaign, entries).items())):
            effects.append(EffettoEventoReputazione(
                evento=event,
                fazione_id=faction_id,
                delta=delta,
                valore_assoluto=None,
                propagato=True,
                ordine=offset + index,
            ))
    return effects


def _authored_signature(event: EventoReputazione) -> list[tuple[int, int]]:
    return [
        (effect.fazione_id, effect.valore_assoluto if effect.valore_assoluto is not None else effect.delta)
        for effect in event.effetti.filter(propagato=False).order_by("ordine", "id")
    ]


@transaction.atomic
def record_event(user, giocatore: Giocatore, values: dict) -> DatiCampagna:
    require_lore_manager(user, giocatore)
    campaign = require_campaign(giocatore)
    mode = _event_mode(values)
    entries = _event_entries(campaign, values.get("entries"), mode)
    raw_time = values.get("campaignTime")
    event = EventoReputazione.objects.create(
        campagna=campaign,
        titolo=_text(values.get("title"), "title", limit=200),
        motivo=_text(values.get("reason"), "reason", required=True, limit=2000),
        modalita=mode,
        giorno_campagna=_event_day(values, campaign),
        ora_campagna=_text(campaign.ora_corrente if raw_time is None else raw_time, "campaignTime", limit=80),
        visibile_ai_giocatori=bool(values.get("visibleToPlayers", True)),
        registrato_da=giocatore.display_name or giocatore.nome,
    )
    EffettoEventoReputazione.objects.bulk_create(_build_effects(event, campaign, entries, mode))
    return campaign


@transaction.atomic
def update_event(user, giocatore: Giocatore, values: dict) -> DatiCampagna:
    """Re-author an existing event.

    Effects are rebuilt only when the mode or an authored value actually
    changed. Correcting a reason or a date therefore never rewrites the
    recorded reactions with today's grid, which matters for imported history
    whose propagation came from a grid that no longer exists.
    """
    require_lore_manager(user, giocatore)
    campaign = require_campaign(giocatore)
    event = EventoReputazione.objects.filter(pk=values.get("id"), campagna=campaign).first()
    if event is None:
        raise ApiError("lore.event_not_found", "Evento non trovato.", "id", status=404)

    mode = _event_mode(values)
    entries = _event_entries(campaign, values.get("entries"), mode)
    rebuild = mode != event.modalita or [(faction.id, value) for faction, value in entries] != _authored_signature(event)

    raw_time = values.get("campaignTime")
    event.titolo = _text(values.get("title"), "title", limit=200)
    event.motivo = _text(values.get("reason"), "reason", required=True, limit=2000)
    event.modalita = mode
    event.giorno_campagna = _event_day(values, campaign)
    event.ora_campagna = _text(event.ora_campagna if raw_time is None else raw_time, "campaignTime", limit=80)
    event.visibile_ai_giocatori = bool(values.get("visibleToPlayers", True))
    event.save()

    if rebuild:
        event.effetti.all().delete()
        EffettoEventoReputazione.objects.bulk_create(_build_effects(event, campaign, entries, mode))
    return campaign


@transaction.atomic
def delete_event(user, giocatore: Giocatore, event_id) -> DatiCampagna:
    """Remove an event so the whole timeline is replayed without it."""
    require_lore_manager(user, giocatore)
    campaign = require_campaign(giocatore)
    event = EventoReputazione.objects.filter(pk=event_id, campagna=campaign).first()
    if event is None:
        raise ApiError("lore.event_not_found", "Evento non trovato.", "id", status=404)
    event.delete()
    return campaign


@transaction.atomic
def save_npc(user, giocatore: Giocatore, values: dict) -> DatiCampagna:
    require_lore_manager(user, giocatore)
    campaign = require_campaign(giocatore)
    name = _text(values.get("name"), "name", required=True, limit=180)
    duplicate = PersonaggioLore.objects.filter(campagna=campaign, nome__iexact=name, archived_at__isnull=True)
    npc_id = values.get("id")
    if npc_id:
        npc = PersonaggioLore.objects.filter(pk=npc_id, campagna=campaign, archived_at__isnull=True).first()
        if npc is None:
            raise ApiError("lore.character_not_found", "Personaggio non trovato in questa campagna.", "id", status=404)
        duplicate = duplicate.exclude(pk=npc.pk)
    else:
        npc = PersonaggioLore(campagna=campaign, ordine=_next_order(PersonaggioLore, campaign))
    if duplicate.exists():
        raise ApiError("lore.character_duplicate", "Esiste già un personaggio con questo nome.", "name")

    faction_id = values.get("factionId")
    npc.nome = name
    npc.ruolo = _text(values.get("role"), "role", limit=160)
    npc.descrizione = _text(values.get("description"), "description", limit=8000)
    npc.ritratto = _image(values.get("portraitId"), "portraitId")
    npc.fazione = _faction(campaign, faction_id, "factionId") if faction_id else None
    npc.visibile_ai_giocatori = bool(values.get("visibleToPlayers", True))
    npc.save()
    return campaign


@transaction.atomic
def delete_npc(user, giocatore: Giocatore, npc_id) -> DatiCampagna:
    require_lore_manager(user, giocatore)
    campaign = require_campaign(giocatore)
    npc = PersonaggioLore.objects.filter(pk=npc_id, campagna=campaign, archived_at__isnull=True).first()
    if npc is None:
        raise ApiError("lore.character_not_found", "Personaggio non trovato in questa campagna.", "id", status=404)
    npc.archived_at = timezone.now()
    npc.save(update_fields=["archived_at", "updated_at"])
    return campaign


@transaction.atomic
def save_timeline_event(user, giocatore: Giocatore, values: dict) -> DatiCampagna:
    """Create or update content used exclusively by Lore > Timeline."""
    require_lore_manager(user, giocatore)
    campaign = require_campaign(giocatore)
    event_id = values.get("id")
    if event_id:
        event = TimelineEvent.objects.filter(
            pk=event_id,
            campagna=campaign,
            archived_at__isnull=True,
        ).first()
        if event is None:
            raise ApiError(
                "lore.timeline_event_not_found",
                "Evento della Timeline non trovato in questa campagna.",
                "id",
                status=404,
            )
    else:
        event = TimelineEvent(campagna=campaign)

    year = _timeline_year(values.get("year"))
    event.nome = _text(values.get("title"), "title", required=True, limit=180)
    event.data_evento = str(year)
    event.ordine_cronologico = year
    event.descrizione = _text(values.get("description"), "description", limit=12000)
    event.immagine = _image(values.get("imageId"), "imageId")
    event.tags = _timeline_tags(values.get("tags"))
    event.save()
    return campaign


@transaction.atomic
def archive_timeline_event(user, giocatore: Giocatore, event_id) -> DatiCampagna:
    require_lore_manager(user, giocatore)
    campaign = require_campaign(giocatore)
    event = TimelineEvent.objects.filter(
        pk=event_id,
        campagna=campaign,
        archived_at__isnull=True,
    ).first()
    if event is None:
        raise ApiError(
            "lore.timeline_event_not_found",
            "Evento della Timeline non trovato in questa campagna.",
            "id",
            status=404,
        )
    event.archived_at = timezone.now()
    event.save(update_fields=["archived_at", "updated_at"])
    return campaign


__all__ = [
    "archive_timeline_event",
    "delete_event",
    "delete_faction",
    "delete_npc",
    "record_event",
    "require_lore_manager",
    "save_faction",
    "save_npc",
    "save_relations",
    "save_timeline_event",
    "update_event",
]
