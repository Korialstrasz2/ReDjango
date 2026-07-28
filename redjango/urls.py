from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path

from backend.core import auth_views, system_views
from backend.core.views import index
from backend.api_v1 import api as api_v1

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/session/", auth_views.session_status, name="auth-session"),
    path("api/auth/login/", auth_views.login_session, name="auth-login"),
    path("api/auth/logout/", auth_views.logout_session, name="auth-logout"),
    path("api/system/restart/", system_views.restart_server, name="system-restart"),
    path("", index, name="index"),
    path("api/", include("backend.core.urls")),
    path("api/", include("backend.characters.urls")),
    path("api/", include("backend.media_library.urls")),
    path("api/combat/", include("backend.combat.urls")),
    path("api/v1/", api_v1.urls),
    re_path(r"^(?!api/|admin/|media/|static/).*$", index, name="spa-fallback"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
