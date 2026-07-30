"""Read models for Gestione Player.

A player is two records: the Django ``User`` that holds the credentials and the
``Giocatore`` that holds the game role, the active campaign and the assigned
character list. The management screen always shows them together, so both are
serialised side by side here.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth.password_validation import password_validators_help_texts
from django.db.models import Q

from backend.characters.models import Personaggio

from .models import CharacterAssignmentRequest, DatiCampagna, Giocatore


ROLE_LABELS = dict(Giocatore.ROLE_CHOICES)


def selectable_characters():
    """Characters an admin may hand out, ordered the way the picker shows them."""
    return (
        Personaggio.objects.filter(archived_at__isnull=True)
        .filter(
            Q(metadata__seed_kind__isnull=True)
            | ~Q(metadata__seed_kind="empty_personaggio_template")
        )
        .select_related("campagna")
        .order_by("nome", "id")
    )


def assigned_character_ids(giocatore: Giocatore) -> list[int]:
    raw = giocatore.character_ids if isinstance(giocatore.character_ids, list) else []
    ids: list[int] = []
    for value in raw:
        try:
            candidate = int(value)
        except (TypeError, ValueError):
            continue
        if candidate not in ids:
            ids.append(candidate)
    return ids


def _serialize_player(
    giocatore: Giocatore,
    characters_by_id: dict[int, Personaggio],
    pending_by_player: dict[int, list[dict[str, Any]]],
) -> dict[str, Any]:
    user = giocatore.user
    ordered_ids = assigned_character_ids(giocatore)
    return {
        "id": giocatore.id,
        "name": giocatore.nome,
        "displayName": giocatore.display_name or giocatore.nome,
        "role": giocatore.role,
        "roleLabel": ROLE_LABELS.get(giocatore.role, giocatore.role),
        "username": user.get_username() if user else "",
        "hasAccount": user is not None,
        "accountActive": bool(user.is_active) if user else False,
        "canUseDjangoAdmin": bool(user and (user.is_staff or user.is_superuser)),
        "lastLogin": user.last_login.isoformat() if user and user.last_login else "",
        "activeCampaignId": giocatore.active_campaign_id,
        "activeCampaignName": giocatore.active_campaign.nome if giocatore.active_campaign_id else "",
        "activeCharacterId": giocatore.active_character_id,
        "activeCharacterName": (
            characters_by_id[giocatore.active_character_id].nome
            if giocatore.active_character_id in characters_by_id
            else ""
        ),
        "characters": [
            {
                "id": character_id,
                "name": characters_by_id[character_id].nome,
                "campaignName": (
                    characters_by_id[character_id].campagna.nome
                    if characters_by_id[character_id].campagna_id
                    else ""
                ),
                # A character assigned outside the player's active campaign is
                # hidden in game: the list must say so instead of looking fine.
                "inActiveCampaign": (
                    not giocatore.active_campaign_id
                    or characters_by_id[character_id].campagna_id == giocatore.active_campaign_id
                ),
            }
            for character_id in ordered_ids
            if character_id in characters_by_id
        ],
        "missingCharacterIds": [
            character_id for character_id in ordered_ids if character_id not in characters_by_id
        ],
        "pendingRequests": pending_by_player.get(giocatore.id, []),
    }


def player_management_overview(current_giocatore: Giocatore | None = None) -> dict[str, Any]:
    characters = list(selectable_characters())
    characters_by_id = {character.id: character for character in characters}
    assignments_by_character: dict[int, list[str]] = {}
    players = list(
        Giocatore.objects.filter(archived_at__isnull=True)
        .select_related("user", "active_campaign", "active_character")
        .order_by("nome")
    )
    for player in players:
        for character_id in assigned_character_ids(player):
            assignments_by_character.setdefault(character_id, []).append(
                player.display_name or player.nome
            )

    pending_by_player: dict[int, list[dict[str, Any]]] = {}
    pending_requests = (
        CharacterAssignmentRequest.objects.filter(
            status=CharacterAssignmentRequest.STATUS_PENDING,
            archived_at__isnull=True,
        )
        .select_related("personaggio")
        .order_by("-created_at")
    )
    for request in pending_requests:
        pending_by_player.setdefault(request.giocatore_id, []).append({
            "characterId": request.personaggio_id,
            "characterName": request.personaggio.nome,
            "message": request.message,
        })

    return {
        "players": [
            _serialize_player(player, characters_by_id, pending_by_player)
            for player in players
        ],
        "roles": [{"value": value, "label": label} for value, label in Giocatore.ROLE_CHOICES],
        "campaigns": [
            {"value": "", "label": "Nessuna campagna"},
            *(
                {"value": str(campaign.id), "label": campaign.nome}
                for campaign in DatiCampagna.objects.filter(archived_at__isnull=True).order_by("nome")
            ),
        ],
        "characters": [
            {
                "id": character.id,
                "name": character.nome,
                "type": character.tipologia,
                "level": character.livello,
                "campaignId": character.campagna_id,
                "campaignName": character.campagna.nome if character.campagna_id else "",
                "assignedTo": assignments_by_character.get(character.id, []),
            }
            for character in characters
        ],
        "currentPlayerId": current_giocatore.id if current_giocatore else None,
        "passwordHelp": _password_help(),
        # A write action overwrites this with the player it just touched, so the
        # screen can keep - or move to - the right selection.
        "savedPlayerId": None,
    }


def _password_help() -> list[str]:
    """The active Django password validators, so the form states the rules up front."""
    return list(password_validators_help_texts())
