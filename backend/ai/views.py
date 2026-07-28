from django.views.decorators.http import require_http_methods

from backend.core.api import ApiError, api_error_response, api_response, request_payload
from backend.core.security import get_or_create_giocatore_for_user
from backend.core.views import get_authenticated_user
from backend.media_library.selectors import serialize_uploaded_image

from .selectors import ai_management_payload, ai_workspace_payload
from .services import ask_assistant, generate_image, save_provider, test_provider


@require_http_methods(["GET", "POST"])
def ai_collection(request):
    user = get_authenticated_user(request)
    giocatore = get_or_create_giocatore_for_user(user)
    if request.method == "GET":
        return api_response(request, ai_workspace_payload(user, giocatore))
    try:
        result = ask_assistant(user, giocatore, request_payload(request))
    except ApiError as error:
        return api_error_response(request, error)
    return api_response(request, result, events=[{"type": "ai.replied", "message": "Risposta pronta."}])


@require_http_methods(["POST"])
def ai_image(request):
    user = get_authenticated_user(request)
    giocatore = get_or_create_giocatore_for_user(user)
    try:
        asset = generate_image(user, giocatore, request_payload(request))
    except ApiError as error:
        return api_error_response(request, error)
    return api_response(
        request,
        {"asset": serialize_uploaded_image(asset, user)},
        status=201,
        events=[{"type": "ai.image_created", "message": f"{asset.title} è stata aggiunta all'archivio."}],
    )


@require_http_methods(["GET", "POST"])
def ai_management(request):
    user = get_authenticated_user(request)
    giocatore = get_or_create_giocatore_for_user(user)
    if request.method == "GET":
        return api_response(request, ai_management_payload(user, giocatore))

    payload = request_payload(request)
    try:
        if "test" in payload:
            result = test_provider(user, giocatore, payload.get("test"))
            return api_response(
                request,
                {**ai_management_payload(user, giocatore), "test": result},
                events=[{"type": "ai.tested", "message": result["message"]}],
            )
        provider = save_provider(user, giocatore, payload.get("values", {}))
        return api_response(
            request,
            ai_management_payload(user, giocatore),
            events=[{"type": "ai.provider_saved", "message": f"{provider.name} aggiornato."}],
        )
    except ApiError as error:
        return api_error_response(request, error)
