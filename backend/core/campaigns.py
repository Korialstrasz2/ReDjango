from __future__ import annotations

from django.db import transaction

from backend.core.api import ApiError

from .models import DatiCampagna, Giocatore


def campaign_payload(campaign: DatiCampagna, selected_campaign_id: int | None) -> dict:
    return {
        "id": campaign.id,
        "name": campaign.nome,
        "isActive": campaign.attiva,
        "isSelected": campaign.id == selected_campaign_id,
        "weather": campaign.meteo,
        "currentTime": campaign.ora_corrente,
        "daysSinceStart": campaign.giorni_da_inizio,
        "sharedNotes": campaign.note_condivise,
    }


def campaigns_payload(giocatore: Giocatore) -> dict:
    campaigns = list(DatiCampagna.objects.filter(archived_at__isnull=True).order_by("-attiva", "nome"))
    selected_id = giocatore.active_campaign_id
    if selected_id not in {campaign.id for campaign in campaigns}:
        selected_id = next((campaign.id for campaign in campaigns if campaign.attiva), None)
    if selected_id is None and campaigns:
        selected_id = campaigns[0].id
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


@transaction.atomic
def update_shared_campaign_notes(giocatore: Giocatore, campaign_id: int, content: str) -> dict:
    giocatore = Giocatore.objects.select_for_update().get(pk=giocatore.pk)
    if giocatore.active_campaign_id != campaign_id:
        raise ApiError(
            "campaign.not_selected",
            "Seleziona la campagna prima di modificarne le note condivise.",
            status=409,
        )
    try:
        campaign = DatiCampagna.objects.select_for_update().get(
            pk=campaign_id,
            archived_at__isnull=True,
        )
    except DatiCampagna.DoesNotExist as exc:
        raise ApiError("campaign.not_found", "Campagna non trovata.", status=404) from exc
    if len(content) > 30_000:
        raise ApiError(
            "campaign.notes_too_long",
            "Le note condivise possono contenere al massimo 30000 caratteri.",
            "content",
        )
    campaign.note_condivise = content
    campaign.save(update_fields=["note_condivise", "updated_at"])
    return campaigns_payload(giocatore)
