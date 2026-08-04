from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from backend.core.api import ApiError

from .models import DatiCampagna, Giocatore
from .security import effective_role, has_minimum_role
from .weather import WEATHER_REMINDER_HOURS, WeatherEntry, current_hour, roll_weather, split_weather

CLOCK_FIELDS = ("ora", "giorno")
CLOCK_DIRECTIONS = ("increase", "decrease")
MIN_DAY = 1
MAX_DAY = 1000
SPECIAL_RESOURCE_FIELDS = ("character", "name", "value", "notes", "highlighted")
SPECIAL_RESOURCE_TEXT_LIMITS = {
    "character": 100,
    "name": 120,
    "value": 200,
    "notes": 2_000,
}
SPECIAL_RESOURCE_PROPOSAL_ACTIONS = ("save", "archive", "restore")


def _timestamp() -> str:
    return timezone.now().isoformat()


def _special_resource_store(campaign: DatiCampagna) -> dict[str, Any]:
    """Return a safe, forward-compatible copy of the campaign JSON aggregate."""
    raw = campaign.risorse_speciali if isinstance(campaign.risorse_speciali, dict) else {}
    resources = raw.get("resources") if isinstance(raw.get("resources"), list) else []
    proposals = raw.get("proposals") if isinstance(raw.get("proposals"), list) else []
    return {
        "version": 1,
        "resources": [deepcopy(row) for row in resources if isinstance(row, dict)],
        "proposals": [deepcopy(row) for row in proposals if isinstance(row, dict)],
    }


def _special_resource_values(values: Any, current: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = values if isinstance(values, dict) else {}
    cleaned = {
        field: current.get(field, "") if current else ""
        for field in SPECIAL_RESOURCE_FIELDS
    }
    for field, limit in SPECIAL_RESOURCE_TEXT_LIMITS.items():
        if field in raw:
            cleaned[field] = str(raw.get(field) or "").strip()[:limit]
    if "highlighted" in raw:
        cleaned["highlighted"] = bool(raw["highlighted"])
    else:
        cleaned["highlighted"] = bool(cleaned.get("highlighted"))
    if not cleaned["name"]:
        raise ApiError(
            "campaign.special_resource_name_required",
            "Dai un nome alla risorsa speciale.",
            "name",
        )
    return cleaned


def _resource_by_id(store: dict[str, Any], resource_id: str) -> dict[str, Any]:
    resource = next((row for row in store["resources"] if row.get("id") == resource_id), None)
    if not resource:
        raise ApiError(
            "campaign.special_resource_not_found",
            "Risorsa speciale non trovata.",
            status=404,
        )
    return resource


def _actor_snapshot(giocatore: Giocatore) -> dict[str, Any]:
    return {
        "id": giocatore.id,
        "name": giocatore.display_name or giocatore.nome,
    }


def special_resources_payload(campaign: DatiCampagna, giocatore: Giocatore) -> dict[str, Any]:
    store = _special_resource_store(campaign)
    can_manage = has_minimum_role(effective_role(giocatore.user, giocatore), Giocatore.ROLE_MASTER)
    proposals = store["proposals"] if can_manage else [
        row for row in store["proposals"] if row.get("proposedBy", {}).get("id") == giocatore.id
    ]
    return {
        "resources": sorted(
            store["resources"],
            key=lambda row: (bool(row.get("archivedAt")), int(row.get("order") or 0), str(row.get("name") or "")),
        ),
        "proposals": sorted(proposals, key=lambda row: str(row.get("createdAt") or ""), reverse=True)[:50],
        "canManage": can_manage,
    }


def campaign_payload(campaign: DatiCampagna, selected_campaign_id: int | None, giocatore: Giocatore) -> dict:
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
        "specialResources": special_resources_payload(campaign, giocatore),
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
        "campaigns": [campaign_payload(campaign, selected_id, giocatore) for campaign in campaigns],
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


def require_campaign_master(user, giocatore: Giocatore, message: str | None = None) -> None:
    if not has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER):
        raise ApiError(
            "campaign.forbidden",
            message or "Solo Master e Amministratori possono modificare questa parte della campagna.",
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


def _new_resource(values: dict[str, Any], giocatore: Giocatore, order: int) -> dict[str, Any]:
    now = _timestamp()
    return {
        "id": uuid4().hex,
        **values,
        "order": order,
        "archivedAt": None,
        "createdAt": now,
        "updatedAt": now,
        "updatedBy": _actor_snapshot(giocatore),
    }


def _apply_resource_values(resource: dict[str, Any], values: dict[str, Any], giocatore: Giocatore) -> None:
    resource.update(values)
    resource["updatedAt"] = _timestamp()
    resource["updatedBy"] = _actor_snapshot(giocatore)


def _stage_special_resource_proposal(
    store: dict[str, Any],
    giocatore: Giocatore,
    action: str,
    resource: dict[str, Any] | None,
    values: dict[str, Any] | None = None,
) -> None:
    if action not in SPECIAL_RESOURCE_PROPOSAL_ACTIONS:
        raise ApiError("campaign.special_resource_action_invalid", "Operazione non valida.", "action")
    proposed_values = deepcopy(values or {})
    before_values: dict[str, Any] = {}
    if action == "save" and resource:
        proposed_values = {
            field: value
            for field, value in proposed_values.items()
            if value != resource.get(field)
        }
        if not proposed_values:
            raise ApiError(
                "campaign.special_resource_no_changes",
                "Non ci sono modifiche da proporre.",
            )
        before_values = {field: resource.get(field) for field in proposed_values}
    now = _timestamp()
    store["proposals"].append({
        "id": uuid4().hex,
        "resourceId": resource.get("id") if resource else None,
        "resourceName": resource.get("name") if resource else (values or {}).get("name", "Nuova risorsa"),
        "action": action,
        "before": before_values,
        "values": proposed_values,
        "baseUpdatedAt": resource.get("updatedAt") if resource else None,
        "status": "pending",
        "proposedBy": _actor_snapshot(giocatore),
        "createdAt": now,
        "reviewedAt": None,
        "reviewedBy": None,
    })
    # Keep a useful audit tail without allowing this small campaign JSON to grow forever.
    if len(store["proposals"]) > 200:
        pending = [row for row in store["proposals"] if row.get("status") == "pending"]
        reviewed = [row for row in store["proposals"] if row.get("status") != "pending"][-100:]
        store["proposals"] = reviewed + pending


@transaction.atomic
def save_special_resource(
    user,
    giocatore: Giocatore,
    campaign_id: int,
    resource_id: str | None,
    values: Any,
) -> tuple[dict, bool]:
    giocatore = Giocatore.objects.select_for_update().get(pk=giocatore.pk)
    campaign = _selected_campaign(giocatore, campaign_id, "modificarne le risorse speciali")
    store = _special_resource_store(campaign)
    resource = _resource_by_id(store, resource_id) if resource_id else None
    cleaned = _special_resource_values(values, resource)
    can_manage = has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)
    if can_manage:
        if resource:
            _apply_resource_values(resource, cleaned, giocatore)
        else:
            active_count = sum(1 for row in store["resources"] if not row.get("archivedAt"))
            store["resources"].append(_new_resource(cleaned, giocatore, active_count))
    else:
        _stage_special_resource_proposal(store, giocatore, "save", resource, cleaned)
    campaign.risorse_speciali = store
    campaign.save(update_fields=["risorse_speciali", "updated_at"])
    return campaigns_payload(giocatore), not can_manage


@transaction.atomic
def archive_special_resource(
    user,
    giocatore: Giocatore,
    campaign_id: int,
    resource_id: str,
    archived: bool,
) -> tuple[dict, bool]:
    giocatore = Giocatore.objects.select_for_update().get(pk=giocatore.pk)
    campaign = _selected_campaign(giocatore, campaign_id, "modificarne le risorse speciali")
    store = _special_resource_store(campaign)
    resource = _resource_by_id(store, resource_id)
    can_manage = has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)
    action = "archive" if archived else "restore"
    if can_manage:
        resource["archivedAt"] = _timestamp() if archived else None
        resource["updatedAt"] = _timestamp()
        resource["updatedBy"] = _actor_snapshot(giocatore)
    else:
        _stage_special_resource_proposal(store, giocatore, action, resource)
    campaign.risorse_speciali = store
    campaign.save(update_fields=["risorse_speciali", "updated_at"])
    return campaigns_payload(giocatore), not can_manage


@transaction.atomic
def reorder_special_resources(
    user,
    giocatore: Giocatore,
    campaign_id: int,
    resource_ids: Any,
) -> dict:
    require_campaign_master(
        user,
        giocatore,
        "Solo Master e Amministratori possono riordinare le risorse speciali.",
    )
    giocatore = Giocatore.objects.select_for_update().get(pk=giocatore.pk)
    campaign = _selected_campaign(giocatore, campaign_id, "riordinarne le risorse speciali")
    store = _special_resource_store(campaign)
    active_ids = [row.get("id") for row in store["resources"] if not row.get("archivedAt")]
    ordered_ids = [str(value) for value in resource_ids] if isinstance(resource_ids, list) else []
    if len(ordered_ids) != len(set(ordered_ids)) or set(ordered_ids) != set(active_ids):
        raise ApiError(
            "campaign.special_resource_order_invalid",
            "L'ordine deve contenere una sola volta tutte le risorse attive.",
            "resourceIds",
        )
    positions = {resource_id: index for index, resource_id in enumerate(ordered_ids)}
    for resource in store["resources"]:
        if resource.get("id") in positions:
            resource["order"] = positions[resource["id"]]
    campaign.risorse_speciali = store
    campaign.save(update_fields=["risorse_speciali", "updated_at"])
    return campaigns_payload(giocatore)


@transaction.atomic
def review_special_resource_proposal(
    user,
    giocatore: Giocatore,
    campaign_id: int,
    proposal_id: str,
    approve: bool,
) -> dict:
    require_campaign_master(
        user,
        giocatore,
        "Solo Master e Amministratori possono esaminare le proposte.",
    )
    giocatore = Giocatore.objects.select_for_update().get(pk=giocatore.pk)
    campaign = _selected_campaign(giocatore, campaign_id, "esaminarne le proposte")
    store = _special_resource_store(campaign)
    proposal = next((row for row in store["proposals"] if row.get("id") == proposal_id), None)
    if not proposal or proposal.get("status") != "pending":
        raise ApiError(
            "campaign.special_resource_proposal_not_found",
            "Proposta non trovata o già esaminata.",
            status=404,
        )
    resource_id = proposal.get("resourceId")
    resource = _resource_by_id(store, resource_id) if resource_id else None
    if approve and resource and proposal.get("baseUpdatedAt") != resource.get("updatedAt"):
        raise ApiError(
            "campaign.special_resource_proposal_stale",
            "La risorsa è cambiata dopo questa proposta. Rifiutala e chiedi una nuova modifica.",
            status=409,
        )
    if approve:
        action = proposal.get("action")
        if action == "save":
            cleaned = _special_resource_values(proposal.get("values"), resource)
            if resource:
                _apply_resource_values(resource, cleaned, giocatore)
            else:
                active_count = sum(1 for row in store["resources"] if not row.get("archivedAt"))
                store["resources"].append(_new_resource(cleaned, giocatore, active_count))
        elif action in ("archive", "restore") and resource:
            resource["archivedAt"] = _timestamp() if action == "archive" else None
            resource["updatedAt"] = _timestamp()
            resource["updatedBy"] = _actor_snapshot(giocatore)
        else:
            raise ApiError("campaign.special_resource_action_invalid", "Operazione proposta non valida.")
    proposal["status"] = "approved" if approve else "rejected"
    proposal["reviewedAt"] = _timestamp()
    proposal["reviewedBy"] = _actor_snapshot(giocatore)
    campaign.risorse_speciali = store
    campaign.save(update_fields=["risorse_speciali", "updated_at"])
    return campaigns_payload(giocatore)
