from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path

from backend.core.views import index
from backend.api_v1 import api as api_v1

urlpatterns = [
    path("admin/", admin.site.urls),
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
