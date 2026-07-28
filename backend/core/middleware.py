from ipaddress import ip_address
from urllib.parse import quote

from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from .access import ACCESS_MODE_LOCKED, active_access_mode
from .api import api_response


PUBLIC_EXACT_PATHS = {
    "/login/",
    "/api/auth/session/",
    "/api/auth/login/",
    "/favicon.ico",
}
PUBLIC_PREFIXES = ("/static/", "/admin/")


def _is_api_request(request) -> bool:
    return request.path.startswith("/api/") or "application/json" in request.headers.get("Accept", "")


def _is_loopback_request(request) -> bool:
    candidate = str(request.META.get("REMOTE_ADDR") or "").split("%", 1)[0]
    try:
        return ip_address(candidate).is_loopback
    except ValueError:
        return False


class AccessControlMiddleware:
    """Require a real Django session everywhere outside the login surface."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        is_public = request.path in PUBLIC_EXACT_PATHS or request.path.startswith(PUBLIC_PREFIXES)
        if not is_public and not request.user.is_authenticated:
            if _is_api_request(request):
                return api_response(
                    request,
                    ok=False,
                    status=401,
                    errors=[{
                        "code": "auth.login_required",
                        "message": "Accedi per utilizzare ReDjango.",
                    }],
                )
            next_path = quote(request.get_full_path(), safe="/?=&")
            return redirect(f"{settings.LOGIN_URL}?next={next_path}")

        response = self.get_response(request)
        if request.path.startswith("/api/auth/"):
            response.headers["Cache-Control"] = "no-store"
        return response


class LockedModeMiddleware:
    """Reject remote sockets before static files or authentication are processed."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if active_access_mode() == ACCESS_MODE_LOCKED and not _is_loopback_request(request):
            if _is_api_request(request):
                return api_response(
                    request,
                    ok=False,
                    status=403,
                    errors=[{
                        "code": "security.locked_mode_remote",
                        "message": "ReDjango accetta connessioni soltanto da questo computer.",
                    }],
                )
            return HttpResponseForbidden("ReDjango accetta connessioni soltanto da questo computer.")
        return self.get_response(request)
