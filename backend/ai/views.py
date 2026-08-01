from django.views.decorators.http import require_http_methods

from backend.core.api import ApiError, api_error_response, api_response, request_payload
from backend.core.security import get_or_create_giocatore_for_user
from backend.core.views import get_authenticated_user
from backend.media_library.selectors import serialize_uploaded_image

from .npc_dossier import generate_dossier
from .execution import (
    active_execution_run_for,
    cancel_execution_run,
    execution_run_for,
    serialize_execution_run,
    start_chat_run,
    start_image_run,
)
from .selectors import ai_management_payload, ai_workspace_payload
from .services import (
    generate_npc_portrait,
    refresh_provider_models,
    require_ai_manager,
    save_agent,
    save_npc_generation,
    save_provider,
    test_provider,
)


@require_http_methods(["GET", "POST"])
def ai_collection(request):
    user = get_authenticated_user(request)
    giocatore = get_or_create_giocatore_for_user(user)
    if request.method == "GET":
        workspace = ai_workspace_payload(user, giocatore)
        active_run = active_execution_run_for(user)
        workspace["activeRun"] = serialize_execution_run(active_run, user) if active_run else None
        return api_response(request, workspace)
    try:
        run = start_chat_run(user, giocatore, request_payload(request))
    except ApiError as error:
        return api_error_response(request, error)
    return api_response(
        request,
        {"run": serialize_execution_run(run, user)},
        status=202,
        events=[{"type": "ai.queued", "message": "Richiesta AI avviata."}],
    )


@require_http_methods(["POST"])
def ai_image(request):
    user = get_authenticated_user(request)
    giocatore = get_or_create_giocatore_for_user(user)
    try:
        run = start_image_run(user, giocatore, request_payload(request))
    except ApiError as error:
        return api_error_response(request, error)
    return api_response(
        request,
        {"run": serialize_execution_run(run, user)},
        status=202,
        events=[{"type": "ai.image_queued", "message": "Generazione immagine avviata."}],
    )


@require_http_methods(["GET", "DELETE"])
def ai_run(request, run_id):
    user = get_authenticated_user(request)
    try:
        run = cancel_execution_run(user, run_id) if request.method == "DELETE" else execution_run_for(user, run_id)
    except ApiError as error:
        return api_error_response(request, error)
    return api_response(request, {"run": serialize_execution_run(run, user)})


@require_http_methods(["POST"])
def ai_dossier(request):
    """Una bozza di PNG. Non scrive nulla: il salvataggio resta un gesto umano."""

    user = get_authenticated_user(request)
    giocatore = get_or_create_giocatore_for_user(user)
    try:
        result = generate_dossier(user, giocatore, request_payload(request))
    except ApiError as error:
        return api_error_response(request, error)
    return api_response(request, result, events=[{"type": "ai.dossier_ready", "message": "Bozza pronta da rivedere."}])


@require_http_methods(["POST"])
def ai_dossier_portrait(request):
    user = get_authenticated_user(request)
    giocatore = get_or_create_giocatore_for_user(user)
    try:
        asset = generate_npc_portrait(user, giocatore, request_payload(request))
    except ApiError as error:
        return api_error_response(request, error)
    return api_response(
        request,
        {"asset": serialize_uploaded_image(asset, user)},
        status=201,
        events=[{"type": "ai.portrait_created", "message": f"Ritratto di {asset.title} generato."}],
    )


@require_http_methods(["GET", "POST"])
def ai_management(request):
    user = get_authenticated_user(request)
    giocatore = get_or_create_giocatore_for_user(user)
    try:
        require_ai_manager(user, giocatore)
    except ApiError as error:
        return api_error_response(request, error)
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
        if "npcGenerationValues" in payload:
            save_npc_generation(user, giocatore, payload.get("npcGenerationValues", {}))
            return api_response(
                request,
                ai_management_payload(user, giocatore),
                events=[{"type": "ai.npc_generation_saved", "message": "Generazione personaggi aggiornata."}],
            )
        if "agentValues" in payload:
            agent = save_agent(user, giocatore, payload.get("agentValues", {}))
            return api_response(
                request,
                ai_management_payload(user, giocatore),
                events=[{"type": "ai.agent_saved", "message": f"{agent.name} aggiornato."}],
            )
        provider = save_provider(user, giocatore, payload.get("values", {}))
        return api_response(
            request,
            ai_management_payload(user, giocatore),
            events=[{"type": "ai.provider_saved", "message": f"{provider.name} aggiornato."}],
        )
    except ApiError as error:
        return api_error_response(request, error)


@require_http_methods(["POST"])
def ai_provider_models(request, provider_id):
    user = get_authenticated_user(request)
    giocatore = get_or_create_giocatore_for_user(user)
    try:
        provider = refresh_provider_models(user, giocatore, provider_id)
    except ApiError as error:
        return api_error_response(request, error)
    return api_response(
        request,
        ai_management_payload(user, giocatore),
        events=[{"type": "ai.models_refreshed", "message": f"{len(provider.model_catalog)} modelli aggiornati."}],
    )
