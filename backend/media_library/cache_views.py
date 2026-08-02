from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.views.decorators.http import require_GET

from backend.core.api import api_response
from backend.core.security import get_or_create_giocatore_for_user
from backend.core.views import get_authenticated_user

from .cache_manifest import media_cache_manifest


@require_GET
def cache_manifest(request):
    user = get_authenticated_user(request)
    giocatore = get_or_create_giocatore_for_user(user)
    return api_response(request, media_cache_manifest(user, giocatore))


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
