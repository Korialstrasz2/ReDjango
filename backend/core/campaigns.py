from __future__ import annotations

from django.db import transaction

from backend.core.api import ApiError

from .models import DatiCampagna, Giocatore
from .security import effective_role, has_minimum_role
from .weather import WEATHER_REMINDER_HOURS, WeatherEntry, current_hour, roll_weather, split_weather

CLOCK_FIELDS = ("ora", "giorno")
CLOCK_DIRECTIONS = ("increase", "decrease")
MIN_DAY = 1
MAX_DAY = 1000


def campaign_payload(campaign: DatiCampagna, selected_campaign_id: int | None) -> dict:
    weather_label, weather_effects = split_weather(campaign.meteo)
    return {
        "id": campaign.id,
        "name": campaign.nome,
        "isActive": campaign.attiva,
        "isSelected": campaign.id == selected_campaign_id,
        "weather": campaign.meteo,
        "weatherLabel": weather_label,
        "weatherEffects": weather_effects,
        "currentTime": campaign.ora_corrente,
        "currentHour": current_hour(campaign.ora_corrente),
        "daysSinceStart": campaign.giorni_da_inizio,
        "sharedNotes": campaign.note_condivise,
    }


def selected_campaign_id(giocatore: Giocatore) -> int | None:
    """The campaign the player is effectively on.

    A player who never chose one still sits in the globally active campaign, so
    the top bar and the actions behind it agree on a single answer.
    """
    campaigns = list(DatiCampagna.objects.filter(archived_at__isnull=True).order_by("-attiva", "nome"))
    if giocatore.active_campaign_id in {campaign.id for campaign in campaigns}:
        return giocatore.active_campaign_id
    return campaigns[0].id if campaigns else None


def campaigns_payload(giocatore: Giocatore) -> dict:
    campaigns = list(DatiCampagna.objects.filter(archived_at__isnull=True).order_by("-attiva", "nome"))
    selected_id = selected_campaign_id(giocatore)
    return {
        "activeCampaignId": selected_id,
        "campaigns": [campaign_payload(campaign, selected_id) for campaign in campaigns],
    }


@transaction.atomic
def select_campaign(giocatore: Giocatore, campaign_id: int) -> dict:
    giocatore = Giocatore.objects.select_for_update().get(pk=giocatore.pk)
    try:
        campaign = DatiCampagna.objects.select_for_update().get(
            pk=campaign_id,
            archived_at__isnull=True,
        )
    except DatiCampagna.DoesNotExist as exc:
        raise ApiError("campaign.not_found", "Campagna non trovata.", status=404) from exc

    DatiCampagna.objects.exclude(pk=campaign.pk).filter(attiva=True).update(attiva=False)
    if not campaign.attiva:
        campaign.attiva = True
        campaign.save(update_fields=["attiva", "updated_at"])

    giocatore.active_campaign = campaign
    if giocatore.active_character_id and giocatore.active_character.campagna_id != campaign.id:
        giocatore.active_character = None
    giocatore.save(update_fields=["active_campaign", "active_character", "updated_at"])
    return campaigns_payload(giocatore)


def require_campaign_master(user, giocatore: Giocatore) -> None:
    if not has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER):
        raise ApiError(
            "campaign.forbidden",
            "Solo Master e Amministratori possono cambiare orologio e meteo della campagna.",
            status=403,
        )


def _selected_campaign(giocatore: Giocatore, campaign_id: int, purpose: str) -> DatiCampagna:
    if selected_campaign_id(giocatore) != campaign_id:
        raise ApiError(
            "campaign.not_selected",
            f"Seleziona la campagna prima di {purpose}.",
            status=409,
        )
    try:
        return DatiCampagna.objects.select_for_update().get(
            pk=campaign_id,
            archived_at__isnull=True,
        )
    except DatiCampagna.DoesNotExist as exc:
        raise ApiError("campaign.not_found", "Campagna non trovata.", status=404) from exc


@transaction.atomic
def update_campaign_clock(
    user,
    giocatore: Giocatore,
    campaign_id: int,
    field: str,
    direction: str,
) -> tuple[dict, bool]:
    """Move the campaign clock one step and say whether a weather roll is due.

    The Elder sidebar wrapped the hour around midnight, kept the day inside
    1…1000, and reminded the master to roll the weather every six hours or on
    any day change. The rules live here instead of in the arrows.
    """
    require_campaign_master(user, giocatore)
    if field not in CLOCK_FIELDS:
        raise ApiError("campaign.clock_field_invalid", "Campo dell'orologio non valido.", "field")
    if direction not in CLOCK_DIRECTIONS:
        raise ApiError("campaign.clock_direction_invalid", "Direzione dell'orologio non valida.", "direction")
    giocatore = Giocatore.objects.select_for_update().get(pk=giocatore.pk)
    campaign = _selected_campaign(giocatore, campaign_id, "modificarne l'orologio")
    step = 1 if direction == "increase" else -1

    if field == "ora":
        hour = (current_hour(campaign.ora_corrente) + step) % 24
        campaign.ora_corrente = str(hour)
        campaign.save(update_fields=["ora_corrente", "updated_at"])
        weather_reminder = hour in WEATHER_REMINDER_HOURS
    else:
        day = min(MAX_DAY, max(MIN_DAY, campaign.giorni_da_inizio + step))
        weather_reminder = day != campaign.giorni_da_inizio
        campaign.giorni_da_inizio = day
        campaign.save(update_fields=["giorni_da_inizio", "updated_at"])

    return campaigns_payload(giocatore), weather_reminder


@transaction.atomic
def reroll_campaign_weather(user, giocatore: Giocatore, campaign_id: int) -> tuple[dict, WeatherEntry, bool]:
    """Roll the campaign weather, returning the payload, the entry and whether it held."""
    require_campaign_master(user, giocatore)
    giocatore = Giocatore.objects.select_for_update().get(pk=giocatore.pk)
    campaign = _selected_campaign(giocatore, campaign_id, "tirarne il meteo")
    entry, prolonged = roll_weather(campaign.meteo)
    if campaign.meteo != entry.name:
        campaign.meteo = entry.name
        campaign.save(update_fields=["meteo", "updated_at"])
    return campaigns_payload(giocatore), entry, prolonged


@transaction.atomic
def update_shared_campaign_notes(giocatore: Giocatore, campaign_id: int, content: str) -> dict:
    giocatore = Giocatore.objects.select_for_update().get(pk=giocatore.pk)
    campaign = _selected_campaign(giocatore, campaign_id, "modificarne le note condivise")
    if len(content) > 30_000:
        raise ApiError(
            "campaign.notes_too_long",
            "Le note condivise possono contenere al massimo 30000 caratteri.",
            "content",
        )
    campaign.note_condivise = content
    campaign.save(update_fields=["note_condivise", "updated_at"])
    return campaigns_payload(giocatore)
