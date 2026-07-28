from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .access import runtime_access_payload
from .api import ApiError, api_error_response, api_response, request_payload
from .login_throttle import (
    clear_login_failures,
    register_login_failure,
    throttle_state,
)
from .security import get_or_create_giocatore_for_user, security_payload


def _session_payload(request) -> dict:
    payload = {
        "authenticated": bool(request.user.is_authenticated),
        "user": None,
        "runtime": runtime_access_payload(),
        "adminUrl": "/admin/",
    }
    if request.user.is_authenticated:
        giocatore = get_or_create_giocatore_for_user(request.user)
        payload["user"] = {
            "id": request.user.id,
            "username": request.user.get_username(),
            "displayName": giocatore.display_name or giocatore.nome,
            "role": security_payload(request.user, giocatore)["role"],
            "canUseDjangoAdmin": bool(request.user.is_staff or request.user.is_superuser),
        }
    return payload


@ensure_csrf_cookie
@require_GET
def session_status(request):
    return api_response(request, _session_payload(request))


@require_POST
def login_session(request):
    retry_after = 0
    try:
        payload = request_payload(request)
        username = str(payload.get("username") or "").strip()
        password = str(payload.get("password") or "")
        if not username or not password:
            raise ApiError(
                "auth.credentials_required",
                "Inserisci nome utente e password.",
                "username",
            )

        state = throttle_state(request, username)
        if state.limited:
            retry_after = state.retry_after
            raise ApiError(
                "auth.too_many_attempts",
                "Troppi tentativi non riusciti. Attendi cinque minuti e riprova.",
                status=429,
            )

        user = authenticate(request, username=username, password=password)
        if user is None or not user.is_active:
            register_login_failure(request, username)
            raise ApiError(
                "auth.invalid_credentials",
                "Nome utente o password non validi.",
                status=401,
            )

        clear_login_failures(request, username)
        login(request, user)
        get_or_create_giocatore_for_user(user)
        return api_response(
            request,
            _session_payload(request),
            events=[{"type": "auth.logged_in", "message": "Accesso effettuato."}],
        )
    except ApiError as error:
        response = api_error_response(request, error)
        if error.status == 429:
            response.headers["Retry-After"] = str(max(1, retry_after))
            response.headers["Cache-Control"] = "no-store"
        return response


@require_POST
def logout_session(request):
    logout(request)
    return api_response(
        request,
        _session_payload(request),
        events=[{"type": "auth.logged_out", "message": "Sessione terminata."}],
    )
