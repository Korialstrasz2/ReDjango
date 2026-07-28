from django.views.decorators.http import require_http_methods

from backend.core.api import ApiError, api_error_response, api_response, multipart_payload, request_payload
from backend.core.security import get_or_create_giocatore_for_user
from backend.core.views import get_authenticated_user

from .travel_selectors import serialize_travel_map, travel_maps_payload
from .travel_services import create_travel_map, get_travel_map, update_travel_map


@require_http_methods(["GET", "POST"])
def travel_map_collection(request):
    user = get_authenticated_user(request)
    giocatore = get_or_create_giocatore_for_user(user)
    if request.method == "GET":
        return api_response(request, travel_maps_payload(user, giocatore))
    try:
        travel_map = create_travel_map(user, giocatore, request.FILES.get("file"), multipart_payload(request))
        return api_response(
            request,
            {"map": serialize_travel_map(travel_map)},
            status=201,
            events=[{"type": "travel.map_created", "message": f"{travel_map.nome} è stata aggiunta a Viaggio."}],
        )
    except ApiError as error:
        return api_error_response(request, error)


@require_http_methods(["PATCH"])
def travel_map_detail(request, map_id: int):
    user = get_authenticated_user(request)
    giocatore = get_or_create_giocatore_for_user(user)
    try:
        travel_map = get_travel_map(giocatore, map_id)
        travel_map = update_travel_map(user, giocatore, travel_map, request_payload(request))
        return api_response(
            request,
            {"map": serialize_travel_map(travel_map)},
            events=[{"type": "travel.map_updated", "message": "Mappa globale aggiornata."}],
        )
    except ApiError as error:
        return api_error_response(request, error)
