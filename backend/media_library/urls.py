from django.urls import path

from . import views

urlpatterns = [
    path("media/", views.media_collection, name="api-media"),
    path("media/<int:asset_id>/", views.media_detail, name="api-media-detail"),
]
