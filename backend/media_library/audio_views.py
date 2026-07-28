from django.views.decorators.http import require_http_methods

from backend.core.api import ApiError, api_error_response, api_response, multipart_payload, request_payload
from backend.core.security import get_or_create_giocatore_for_user
from backend.core.views import get_authenticated_user

from .audio_selectors import audio_library_payload, serialize_audio_track
from .audio_services import create_audio_track, delete_audio_track, get_audio_track, update_audio_track


@require_http_methods(["GET", "POST"])
def audio_track_collection(request):
    user = get_authenticated_user(request)
    giocatore = get_or_create_giocatore_for_user(user)
    if request.method == "GET":
        return api_response(request, audio_library_payload(user, giocatore))
    try:
        track = create_audio_track(user, giocatore, request.FILES.get("file"), multipart_payload(request))
    except ApiError as error:
        return api_error_response(request, error)
    return api_response(
        request,
        {"track": serialize_audio_track(track), **audio_library_payload(user, giocatore)},
        status=201,
        events=[{"type": "audio.track_created", "message": f"{track.title} è entrata nella colonna sonora."}],
    )


@require_http_methods(["PATCH", "DELETE"])
def audio_track_detail(request, track_id: int):
    user = get_authenticated_user(request)
    giocatore = get_or_create_giocatore_for_user(user)
    try:
        track = get_audio_track(track_id)
        if request.method == "PATCH":
            track = update_audio_track(user, giocatore, track, request_payload(request))
            return api_response(
                request,
                {"track": serialize_audio_track(track), **audio_library_payload(user, giocatore)},
                events=[{"type": "audio.track_updated", "message": f"{track.title} è stata aggiornata."}],
            )

        title = delete_audio_track(user, giocatore, track)
        return api_response(
            request,
            audio_library_payload(user, giocatore),
            events=[{"type": "audio.track_deleted", "message": f"{title} è stata eliminata."}],
        )
    except ApiError as error:
        return api_error_response(request, error)
