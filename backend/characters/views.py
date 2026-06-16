from django.http import Http404
from django.views.decorators.http import require_http_methods

from backend.core.api import ApiError, api_error_response, api_response, request_payload
from backend.core.views import get_local_user

from .models import Character
from .selectors import character_detail_payload, character_list_payload, get_character_for_user
from .services import create_character, delete_character, update_character


def _character_or_404(user, character_id: int) -> Character:
    try:
        return get_character_for_user(user, character_id)
    except Character.DoesNotExist as exc:
        raise Http404("Character not found") from exc


@require_http_methods(["GET", "POST"])
def character_collection(request):
    user = get_local_user(request)

    if request.method == "GET":
        return api_response(request, character_list_payload(user))

    try:
        character = create_character(user, request_payload(request))
    except ApiError as error:
        return api_error_response(request, error)
    return api_response(
        request,
        character_detail_payload(character),
        status=201,
        events=[{"type": "character.created", "message": f"{character.name} created."}],
    )


@require_http_methods(["GET", "PATCH", "DELETE"])
def character_detail(request, character_id: int):
    user = get_local_user(request)
    character = _character_or_404(user, character_id)

    if request.method == "GET":
        return api_response(request, character_detail_payload(character))

    if request.method == "DELETE":
        name = character.name
        delete_character(character)
        return api_response(request, events=[{"type": "character.deleted", "message": f"{name} deleted."}])

    try:
        character = update_character(character, request_payload(request), user)
    except ApiError as error:
        return api_error_response(request, error)
    return api_response(
        request,
        character_detail_payload(character),
        events=[{"type": "character.saved", "message": f"{character.name} saved."}],
    )
