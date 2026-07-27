from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from backend.core.api import ApiError, api_error_response, api_response, request_payload
from backend.core.models import Giocatore
from backend.core.security import effective_role, get_or_create_giocatore_for_user, has_minimum_role
from backend.core.views import get_local_user

from .selectors import personaggi_payload_for
from .services.selection import select_personaggio_for_giocatore


def _identity(request):
    user = get_local_user(request)
    return user, get_or_create_giocatore_for_user(user)


def _can_control_all_characters(user, giocatore: Giocatore) -> bool:
    return has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_MASTER)


@ensure_csrf_cookie
@require_GET
def list_personaggi(request):
    user, giocatore = _identity(request)
    can_control_all = _can_control_all_characters(user, giocatore)
    return api_response(
        request,
        personaggi_payload_for(
            giocatore,
            can_manage_items=can_control_all,
            include_all=can_control_all,
        ),
    )


@require_POST
def select_personaggio(request):
    try:
        user, giocatore = _identity(request)
        can_control_all = _can_control_all_characters(user, giocatore)
        payload = request_payload(request)
        raw_personaggio_id = payload.get("personaggioId") or payload.get("id")
        personaggio_id = int(raw_personaggio_id)
        giocatore = select_personaggio_for_giocatore(
            giocatore,
            personaggio_id,
            include_all=can_control_all,
        )
        return api_response(
            request,
            personaggi_payload_for(
                giocatore,
                can_manage_items=can_control_all,
                include_all=can_control_all,
            ),
            events=[{"type": "personaggio.selected", "message": "Personaggio selezionato."}],
        )
    except ApiError as error:
        return api_error_response(request, error)
    except (TypeError, ValueError):
        return api_error_response(
            request,
            ApiError("personaggio.invalid_id", "È richiesto un identificativo valido del personaggio.", "personaggioId"),
        )
