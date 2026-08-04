from django.urls import path

from . import change_views, views


urlpatterns = [
    path("ai/", views.ai_collection, name="api-ai"),
    path("ai/images/", views.ai_image, name="api-ai-image"),
    path("ai/runs/<uuid:run_id>/", views.ai_run, name="api-ai-run"),
    path("ai/dossier/", views.ai_dossier, name="api-ai-dossier"),
    path("ai/dossier/portrait/", views.ai_dossier_portrait, name="api-ai-dossier-portrait"),
    path("ai/providers/", views.ai_management, name="api-ai-providers"),
    path("ai/providers/<int:provider_id>/models/", views.ai_provider_models, name="api-ai-provider-models"),
    path("ai/change-sets/", change_views.ai_change_sets, name="api-ai-change-sets"),
    path("ai/change-sets/<uuid:change_set_id>/", change_views.ai_change_set_detail, name="api-ai-change-set"),
    path("ai/change-sets/<uuid:change_set_id>/operations/", change_views.ai_change_operations, name="api-ai-change-operations"),
    path(
        "ai/change-sets/<uuid:change_set_id>/operations/<int:operation_id>/",
        change_views.ai_change_operation_detail,
        name="api-ai-change-operation",
    ),
    path("ai/change-sets/<uuid:change_set_id>/validate/", change_views.ai_change_set_validate, name="api-ai-change-set-validate"),
    path("ai/change-sets/<uuid:change_set_id>/apply/", change_views.ai_change_set_apply, name="api-ai-change-set-apply"),
    path("ai/change-entities/", change_views.ai_change_entities, name="api-ai-change-entities"),
    path(
        "ai/change-entities/<str:entity_type>/search/",
        change_views.ai_change_entity_search,
        name="api-ai-change-entity-search",
    ),
]
