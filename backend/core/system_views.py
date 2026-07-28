from django.views.decorators.http import require_POST

from .access import runtime_access_payload, schedule_managed_restart
from .api import ApiError, api_error_response, api_response
from .models import Giocatore
from .security import effective_role, get_or_create_giocatore_for_user, has_minimum_role


@require_POST
def restart_server(request):
    try:
        giocatore = get_or_create_giocatore_for_user(request.user)
        if not has_minimum_role(effective_role(request.user, giocatore), Giocatore.ROLE_ADMIN):
            raise ApiError(
                "system.restart_forbidden",
                "Solo un amministratore può riavviare il server.",
                status=403,
            )

        runtime = runtime_access_payload()
        if not runtime["restartRequired"]:
            raise ApiError(
                "system.restart_not_required",
                "La modalità configurata è già attiva.",
                status=409,
            )
        if not schedule_managed_restart():
            raise ApiError(
                "system.restart_unavailable",
                "La modalità è stata salvata, ma questo processo non è gestito dal launcher. Riavvia ReDjango manualmente.",
                status=409,
            )
        return api_response(
            request,
            {"accepted": True, "runtime": runtime},
            events=[{"type": "system.restart_scheduled", "message": "Riavvio del server avviato."}],
        )
    except ApiError as error:
        return api_error_response(request, error)
