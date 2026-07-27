from django.urls import path

from . import settings_views, views

urlpatterns = [
    path("health/", views.health, name="api-health"),
    path("bootstrap/", views.bootstrap, name="api-bootstrap"),
    path("settings/", settings_views.settings_collection, name="api-settings"),
]
