from django.urls import path

from . import views

urlpatterns = [
    path("characters/", views.character_collection, name="api-characters"),
    path("characters/<int:character_id>/", views.character_detail, name="api-character-detail"),
]
