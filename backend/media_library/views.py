from django.http import Http404
from django.views.decorators.http import require_http_methods

from backend.core.api import ApiError, api_error_response, api_response, multipart_payload
from backend.core.views import get_local_user

from .models import UserMediaAsset
from .selectors import get_media_asset_for_user, media_detail_payload, media_list_payload
from .services import create_media_asset, delete_media_asset


def _asset_for_user(user, asset_id: int) -> UserMediaAsset:
    try:
        return get_media_asset_for_user(user, asset_id)
    except UserMediaAsset.DoesNotExist as exc:
        raise Http404("Media asset not found") from exc


@require_http_methods(["GET", "POST"])
def media_collection(request):
    user = get_local_user(request)

    if request.method == "GET":
        return api_response(request, media_list_payload(user))

    try:
        asset = create_media_asset(user, request.FILES.get("file"), multipart_payload(request))
    except ApiError as error:
        return api_error_response(request, error)
    return api_response(
        request,
        media_detail_payload(asset),
        status=201,
        events=[{"type": "media.uploaded", "message": f"{asset.title} copied into user media."}],
    )


@require_http_methods(["GET", "DELETE"])
def media_detail(request, asset_id: int):
    user = get_local_user(request)
    asset = _asset_for_user(user, asset_id)

    if request.method == "GET":
        return api_response(request, media_detail_payload(asset))

    title = asset.title
    delete_media_asset(asset)
    return api_response(request, events=[{"type": "media.deleted", "message": f"{title} deleted."}])
