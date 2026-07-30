"""Write operations for Gestione Player.

Every operation here touches credentials or permissions, so it is reserved to the
game administrator. The Django ``User`` and the ``Giocatore`` are always created,
updated and validated together: a player without an account cannot log in, and an
account without a profile has no role, no campaign and no characters.
"""

from __future__ import annotations

import re
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .api import ApiError
from .models import CharacterAssignmentRequest, DatiCampagna, Giocatore
from .player_management_selectors import (
    assigned_character_ids,
    player_management_overview,
    selectable_characters,
)
from .security import effective_role, has_minimum_role


USERNAME_RE = re.compile(r"^[\w.@+-]+$")
MAX_ASSIGNED_CHARACTERS = 50


def require_player_manager(user, giocatore: Giocatore) -> None:
    if not has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_ADMIN):
        raise ApiError(
            "players.forbidden",
            "Solo un amministratore può gestire i giocatori e le loro credenziali.",
            status=403,
        )


def _overview(giocatore: Giocatore, saved_player_id: int | None = None) -> dict[str, Any]:
    return {**player_management_overview(giocatore), "savedPlayerId": saved_player_id}


def _clean_name(raw: Any) -> str:
    name = str(raw or "").strip()
    if not name:
        raise ApiError("players.name_required", "Inserisci il nome del giocatore.", "name")
    if len(name) > 120:
        raise ApiError("players.name_too_long", "Il nome può contenere al massimo 120 caratteri.", "name")
    return name


def _clean_display_name(raw: Any, fallback: str) -> str:
    display_name = str(raw or "").strip() or fallback
    if len(display_name) > 120:
        raise ApiError("players.alias_too_long", "L'alias può contenere al massimo 120 caratteri.", "displayName")
    return display_name


def _clean_username(raw: Any) -> str:
    username = str(raw or "").strip()
    if not username:
        raise ApiError("players.username_required", "Inserisci il nome utente per l'accesso.", "username")
    if len(username) > 150:
        raise ApiError("players.username_too_long", "Il nome utente può contenere al massimo 150 caratteri.", "username")
    if not USERNAME_RE.fullmatch(username):
        raise ApiError(
            "players.username_invalid",
            "Il nome utente può contenere solo lettere, numeri e i caratteri . @ + - _",
            "username",
        )
    return username


def _clean_role(raw: Any) -> str:
    role = str(raw or "")
    if role not in Giocatore.ROLE_RANKS:
        raise ApiError("players.role_invalid", "Il livello di accesso scelto non è valido.", "role")
    return role


def _clean_campaign(raw: Any) -> DatiCampagna | None:
    if raw in (None, "", 0, "0"):
        return None
    try:
        return DatiCampagna.objects.get(pk=int(raw))
    except (TypeError, ValueError, DatiCampagna.DoesNotExist) as exc:
        raise ApiError("players.campaign_not_found", "Campagna non trovata.", "activeCampaignId", 404) from exc


def _validated_password(raw: Any, username: str) -> str:
    password = str(raw or "")
    if not password:
        raise ApiError("players.password_required", "Inserisci una password.", "password")
    try:
        validate_password(password)
    except ValidationError as exc:
        raise ApiError("players.password_weak", " ".join(exc.messages), "password") from exc
    if password.strip().lower() == username.strip().lower():
        raise ApiError(
            "players.password_is_username",
            "La password non può coincidere con il nome utente.",
            "password",
        )
    return password


def _assert_name_available(name: str, *, exclude_id: int | None = None) -> None:
    duplicates = Giocatore.objects.filter(nome__iexact=name)
    if exclude_id is not None:
        duplicates = duplicates.exclude(pk=exclude_id)
    if duplicates.exists():
        raise ApiError("players.name_taken", f"Esiste già un giocatore chiamato «{name}».", "name", 409)


def _assert_username_available(username: str, *, exclude_user_id: int | None = None) -> None:
    duplicates = get_user_model().objects.filter(username__iexact=username)
    if exclude_user_id is not None:
        duplicates = duplicates.exclude(pk=exclude_user_id)
    if duplicates.exists():
        raise ApiError("players.username_taken", f"Il nome utente «{username}» è già in uso.", "username", 409)


def _locked_player(player_id: Any) -> Giocatore:
    try:
        return (
            Giocatore.objects.select_for_update()
            .select_related("user", "active_campaign")
            .get(pk=int(player_id))
        )
    except (TypeError, ValueError, Giocatore.DoesNotExist) as exc:
        raise ApiError("players.not_found", "Giocatore non trovato.", "playerId", 404) from exc


@transaction.atomic
def create_player(user, giocatore: Giocatore, values: dict[str, Any]) -> dict[str, Any]:
    require_player_manager(user, giocatore)
    if not isinstance(values, dict):
        raise ApiError("players.invalid_payload", "I dati del giocatore devono essere un oggetto.", "values")

    name = _clean_name(values.get("name"))
    username = _clean_username(values.get("username") or name)
    display_name = _clean_display_name(values.get("displayName"), name)
    role = _clean_role(values.get("role") or Giocatore.ROLE_USER)
    campaign = _clean_campaign(values.get("activeCampaignId"))
    password = _validated_password(values.get("password"), username)
    _assert_name_available(name)
    _assert_username_available(username)

    account = get_user_model().objects.create_user(username=username, password=password)
    created = Giocatore.objects.create(
        user=account,
        nome=name,
        display_name=display_name,
        role=role,
        active_campaign=campaign,
    )
    return {"overview": _overview(giocatore, created.id), "playerName": display_name}


@transaction.atomic
def update_player(user, giocatore: Giocatore, player_id: Any, values: dict[str, Any]) -> dict[str, Any]:
    require_player_manager(user, giocatore)
    if not isinstance(values, dict):
        raise ApiError("players.invalid_payload", "I dati del giocatore devono essere un oggetto.", "values")

    player = _locked_player(player_id)
    name = _clean_name(values.get("name", player.nome))
    display_name = _clean_display_name(values.get("displayName", player.display_name), name)
    role = _clean_role(values.get("role", player.role))
    _assert_name_available(name, exclude_id=player.pk)

    # Demoting yourself would immediately close this screen, and a game admin who
    # is not a Django superuser could not get the role back without the code.
    if player.pk == giocatore.pk and role != player.role:
        raise ApiError(
            "players.self_role_locked",
            "Non puoi cambiare il tuo livello di accesso da qui: usa Impostazioni → Profilo.",
            "role",
            409,
        )

    player.nome = name
    player.display_name = display_name
    player.role = role
    if "activeCampaignId" in values:
        player.active_campaign = _clean_campaign(values.get("activeCampaignId"))
    player.save(update_fields=["nome", "display_name", "role", "active_campaign", "updated_at"])

    account = player.user
    if account is not None:
        account_fields: list[str] = []
        if "username" in values:
            username = _clean_username(values.get("username"))
            if username.lower() != account.get_username().lower():
                _assert_username_available(username, exclude_user_id=account.pk)
            account.username = username
            account_fields.append("username")
        if "accountActive" in values:
            active = bool(values.get("accountActive"))
            if player.pk == giocatore.pk and not active:
                raise ApiError(
                    "players.self_disable_locked",
                    "Non puoi disattivare il tuo stesso accesso.",
                    "accountActive",
                    409,
                )
            account.is_active = active
            account_fields.append("is_active")
        if account_fields:
            account.save(update_fields=account_fields)
    elif values.get("username"):
        username = _clean_username(values.get("username"))
        _assert_username_available(username)
        password = _validated_password(values.get("password"), username)
        player.user = get_user_model().objects.create_user(username=username, password=password)
        player.save(update_fields=["user", "updated_at"])

    return {"overview": _overview(giocatore, player.id), "playerName": player.display_name or player.nome}


@transaction.atomic
def set_player_password(user, giocatore: Giocatore, player_id: Any, password: Any) -> dict[str, Any]:
    require_player_manager(user, giocatore)
    player = _locked_player(player_id)
    account = player.user
    if account is None:
        raise ApiError(
            "players.account_missing",
            "Questo giocatore non ha ancora un account di accesso: assegnagli un nome utente.",
            "playerId",
            409,
        )
    validated = _validated_password(password, account.get_username())
    account.set_password(validated)
    account.save(update_fields=["password"])
    return {"overview": _overview(giocatore, player.id), "playerName": player.display_name or player.nome}


@transaction.atomic
def assign_player_characters(user, giocatore: Giocatore, player_id: Any, character_ids: Any) -> dict[str, Any]:
    require_player_manager(user, giocatore)
    if not isinstance(character_ids, list):
        raise ApiError("players.characters_invalid", "La selezione dei personaggi non è valida.", "characterIds")
    try:
        requested_ids = list(dict.fromkeys(int(value) for value in character_ids))
    except (TypeError, ValueError) as exc:
        raise ApiError("players.characters_invalid", "La selezione dei personaggi non è valida.", "characterIds") from exc
    if len(requested_ids) > MAX_ASSIGNED_CHARACTERS:
        raise ApiError(
            "players.characters_too_many",
            f"Puoi assegnare al massimo {MAX_ASSIGNED_CHARACTERS} personaggi a un giocatore.",
            "characterIds",
        )

    player = _locked_player(player_id)
    available = {character.id for character in selectable_characters().filter(id__in=requested_ids)}
    unknown = [character_id for character_id in requested_ids if character_id not in available]
    if unknown:
        raise ApiError(
            "players.character_not_found",
            "Uno dei personaggi selezionati non è disponibile.",
            "characterIds",
            404,
        )

    previous_ids = set(assigned_character_ids(player))
    player.character_ids = requested_ids
    # The active character has to stay inside the roster, otherwise the player
    # keeps a sheet nobody assigned any more.
    if player.active_character_id not in requested_ids:
        player.active_character_id = requested_ids[0] if requested_ids else None
    player.save(update_fields=["character_ids", "active_character", "updated_at"])

    added_ids = [character_id for character_id in requested_ids if character_id not in previous_ids]
    if added_ids:
        CharacterAssignmentRequest.objects.filter(
            giocatore=player,
            personaggio_id__in=added_ids,
            status=CharacterAssignmentRequest.STATUS_PENDING,
        ).update(
            status=CharacterAssignmentRequest.STATUS_APPROVED,
            reviewed_at=timezone.now(),
        )

    return {
        "overview": _overview(giocatore, player.id),
        "playerName": player.display_name or player.nome,
        "assignedCount": len(requested_ids),
    }
