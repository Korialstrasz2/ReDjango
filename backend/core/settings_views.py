from django.views.decorators.http import require_http_methods

from .api import ApiError, api_error_response, api_response, request_payload
from .security import get_or_create_giocatore_for_user
from .settings_selectors import settings_payload
from .settings_services import (
    redeem_role_code,
    request_character_assignments,
    save_setting_overrides,
    select_game_role,
    update_player_alias,
)
from .views import get_local_user


@require_http_methods(["GET", "POST"])
def settings_collection(request):
    user = get_local_user(request)
    giocatore = get_or_create_giocatore_for_user(user)
    if request.method == "GET":
        return api_response(request, settings_payload(user, giocatore))

    try:
        payload = request_payload(request)
        event = {"type": "settings.saved", "message": "Impostazioni salvate."}
        if "profile" in payload:
            profile = payload.get("profile")
            if not isinstance(profile, dict):
                raise ApiError("player.profile_invalid", "Il profilo giocatore non è valido.", "profile")
            giocatore = update_player_alias(giocatore, profile.get("alias"))
            event = {"type": "player.alias_saved", "message": "Alias aggiornato."}
        elif "assignmentRequest" in payload:
            assignment = payload.get("assignmentRequest")
            if not isinstance(assignment, dict):
                raise ApiError("player.assignment_invalid", "La richiesta di assegnazione non è valida.", "assignmentRequest")
            request_character_assignments(giocatore, assignment.get("characterIds"), assignment.get("message", ""))
            event = {"type": "player.assignment_requested", "message": "Richiesta di assegnazione inviata."}
        elif "roleCode" in payload:
            role_code = payload.get("roleCode")
            if not isinstance(role_code, dict):
                raise ApiError("player.role_code_invalid", "La richiesta del codice di accesso non è valida.", "roleCode")
            giocatore = redeem_role_code(user, giocatore, role_code.get("targetRole"), role_code.get("code"))
            event = {"type": "player.role_updated", "message": "Livello di accesso aggiornato."}
        elif "roleSelection" in payload:
            role_selection = payload.get("roleSelection")
            if not isinstance(role_selection, dict):
                raise ApiError("player.role_invalid", "La selezione del livello di accesso non è valida.", "roleSelection")
            giocatore = select_game_role(
                user,
                giocatore,
                role_selection.get("targetRole"),
                role_selection.get("code", ""),
            )
            event = {"type": "player.role_updated", "message": "Livello di accesso aggiornato."}
        else:
            save_setting_overrides(user, giocatore, payload.get("settings", {}))
        return api_response(
            request,
            settings_payload(user, giocatore),
            events=[event],
        )
    except ApiError as error:
        return api_error_response(request, error)
