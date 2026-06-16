from django.contrib.auth import get_user_model
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET

from .api import api_response


def get_local_user(request):
    if request.user.is_authenticated:
        return request.user

    User = get_user_model()
    user, created = User.objects.get_or_create(
        username="local_master",
        defaults={"is_staff": True, "is_superuser": False},
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


@ensure_csrf_cookie
def index(request):
    return render(request, "index.html")


@require_GET
def health(request):
    return api_response(request, {"service": "ReDjango", "status": "ready"})


@ensure_csrf_cookie
@require_GET
def bootstrap(request):
    user = get_local_user(request)
    return api_response(
        request,
        {
            "user": {
                "id": user.id,
                "username": user.username,
                "isAuthenticated": request.user.is_authenticated,
            },
            "menus": [
                {"id": "dashboard", "label": "Main Menu"},
                {"id": "characters", "label": "Characters"},
                {"id": "media", "label": "Media Vault"},
            ],
        }
    )
