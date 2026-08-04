from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.views.decorators.http import require_GET, require_POST

from backend.core.api import ApiError, api_error_response, api_response, request_payload
from backend.core.models import Giocatore
from backend.core.security import effective_role, get_or_create_giocatore_for_user, has_minimum_role
from backend.core.views import get_authenticated_user

from .cache_manifest import media_cache_manifest
from .cache_package import (
    PackageBuildError,
    PackageValidationError,
    build_package_archive,
    verify_package_document,
)


@require_GET
def cache_manifest(request):
    user = get_authenticated_user(request)
    giocatore = get_or_create_giocatore_for_user(user)
    return api_response(request, media_cache_manifest(user, giocatore))


@require_GET
def cache_package(request):
    user = get_authenticated_user(request)
    giocatore = get_or_create_giocatore_for_user(user)
    if not has_minimum_role(effective_role(user, giocatore), Giocatore.ROLE_ADMIN):
        raise PermissionDenied("Soltanto un Amministratore può esportare il pacchetto media.")
    try:
        archive, document = build_package_archive(user, giocatore)
    except PackageBuildError as error:
        return api_error_response(request, ApiError("media.package_build_failed", str(error), status=409))
    campaign_id = document["payload"]["campaign"]["id"]
    response = FileResponse(
        archive,
        as_attachment=True,
        filename=f"redjango-media-campagna-{campaign_id}.zip",
        content_type="application/zip",
    )
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-ReDjango-Package-Files"] = str(len(document["payload"]["files"]))
    response.headers["X-ReDjango-Package-Bytes"] = str(document["payload"]["totalBytes"])
    return response


@require_POST
def verify_cache_package(request):
    user = get_authenticated_user(request)
    giocatore = get_or_create_giocatore_for_user(user)
    current = media_cache_manifest(user, giocatore)
    try:
        payload = request_payload(request)
        verified = verify_package_document(
            payload.get("package"),
            campaign_id=current["campaign"]["id"] if current["campaign"] else None,
            allowed_entries={entry["cacheKey"]: entry for entry in current["entries"]},
        )
    except (ApiError, PackageValidationError) as error:
        api_error = error if isinstance(error, ApiError) else ApiError(
            "media.package_invalid",
            str(error),
            status=400,
        )
        return api_error_response(request, api_error)
    return api_response(request, {
        "scope": current["scope"],
        "campaign": verified["campaign"],
        "files": verified["resolvedFiles"],
        "totalBytes": verified["totalBytes"],
    })


@require_GET
def service_worker(request):
    """Serve the standalone worker at the origin root so it can own `/media/`."""

    path = Path(settings.BASE_DIR) / "frontend" / "static" / "frontend" / "service-worker.js"
    if not path.is_file():
        raise Http404
    response = FileResponse(path.open("rb"), content_type="application/javascript; charset=utf-8")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
