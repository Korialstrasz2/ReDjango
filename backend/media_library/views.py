from django.views.decorators.http import require_http_methods

from backend.core.api import ApiError, api_error_response, api_response, multipart_payload, request_payload
from backend.core.views import get_local_user

from .models import UploadedImage
from .selectors import get_uploaded_image_for_user, media_detail_payload, media_list_payload, user_can_manage_all_images
from .services import (
    create_uploaded_image,
    delete_uploaded_image,
    move_uploaded_image,
    set_uploaded_image_limited_visibility,
)


def _asset_for_user(user, asset_id: int) -> UploadedImage:
    if not user_can_manage_all_images(user):
        raise ApiError(
            "media.admin_required",
            "Solo un amministratore può spostare o eliminare immagini.",
            status=403,
        )
    try:
        return get_uploaded_image_for_user(user, asset_id)
    except UploadedImage.DoesNotExist as exc:
        raise ApiError("media.not_found", "Immagine non trovata.", status=404) from exc


@require_http_methods(["GET", "POST"])
def media_collection(request):
    user = get_local_user(request)
    if request.method == "GET":
        return api_response(request, media_list_payload(user))

    try:
        asset = create_uploaded_image(user, request.FILES.get("file"), multipart_payload(request))
    except ApiError as error:
        return api_error_response(request, error)
    return api_response(
        request,
        media_detail_payload(asset, user),
        status=201,
        events=[{"type": "media.uploaded", "message": f"{asset.title} è stata aggiunta all'archivio."}],
    )


@require_http_methods(["GET", "PATCH", "DELETE"])
def media_detail(request, asset_id: int):
    user = get_local_user(request)
    try:
        asset = _asset_for_user(user, asset_id)
        if request.method == "GET":
            return api_response(request, media_detail_payload(asset, user))

        if request.method == "PATCH":
            payload = request_payload(request)
            if "limitedVisibility" in payload:
                asset = set_uploaded_image_limited_visibility(asset, payload["limitedVisibility"])
                state = "limitata" if asset.visibilita_limitata else "visibile a tutti"
                return api_response(
                    request,
                    media_detail_payload(asset, user),
                    events=[{"type": "media.visibility_updated", "message": f"{asset.title} è ora {state}."}],
                )
            asset = move_uploaded_image(asset, payload)
            return api_response(
                request,
                media_detail_payload(asset, user),
                events=[{"type": "media.moved", "message": f"{asset.title} è stata spostata."}],
            )

        title = asset.title
        delete_uploaded_image(asset)
        return api_response(request, events=[{"type": "media.deleted", "message": f"{title} è stata eliminata."}])
    except ApiError as error:
        return api_error_response(request, error)
