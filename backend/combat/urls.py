from django.urls import path

from . import views


app_name = "combat"

urlpatterns = [
    path("", views.workspace, name="workspace"),
    path("actions/", views.actions, name="actions"),
    path("maps/<int:map_id>/events/", views.event_stream, name="events"),
]

