from django.urls import path

from . import audio_views, cache_views, travel_views, views


urlpatterns = [
    path("media/cache-manifest/", cache_views.cache_manifest, name="api-media-cache-manifest"),
    path("media/cache-package/", cache_views.cache_package, name="api-media-cache-package"),
    path("media/cache-package/verify/", cache_views.verify_cache_package, name="api-media-cache-package-verify"),
    path("media/", views.media_collection, name="api-media-list"),
    path("media/<int:asset_id>/", views.media_detail, name="api-media-detail"),
    path("audio/tracks/", audio_views.audio_track_collection, name="api-audio-tracks"),
    path("audio/tracks/<int:track_id>/", audio_views.audio_track_detail, name="api-audio-track-detail"),
    path("travel/maps/", travel_views.travel_map_collection, name="api-travel-maps"),
    path("travel/maps/<int:map_id>/", travel_views.travel_map_detail, name="api-travel-map-detail"),
]
