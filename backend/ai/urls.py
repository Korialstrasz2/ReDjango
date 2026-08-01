from django.urls import path

from . import views


urlpatterns = [
    path("ai/", views.ai_collection, name="api-ai"),
    path("ai/images/", views.ai_image, name="api-ai-image"),
    path("ai/runs/<uuid:run_id>/", views.ai_run, name="api-ai-run"),
    path("ai/dossier/", views.ai_dossier, name="api-ai-dossier"),
    path("ai/dossier/portrait/", views.ai_dossier_portrait, name="api-ai-dossier-portrait"),
    path("ai/providers/", views.ai_management, name="api-ai-providers"),
    path("ai/providers/<int:provider_id>/models/", views.ai_provider_models, name="api-ai-provider-models"),
]
