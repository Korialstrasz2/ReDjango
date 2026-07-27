from django.urls import path

from . import travel_views, views


urlpatterns = [
    path("media/", views.media_collection, name="api-media-list"),
    path("media/<int:asset_id>/", views.media_detail, name="api-media-detail"),
    path("travel/maps/", travel_views.travel_map_collection, name="api-travel-maps"),
    path("travel/maps/<int:map_id>/", travel_views.travel_map_detail, name="api-travel-map-detail"),
]
