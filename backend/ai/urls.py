from django.urls import path

from . import views


urlpatterns = [
    path("ai/", views.ai_collection, name="api-ai"),
    path("ai/images/", views.ai_image, name="api-ai-image"),
    path("ai/providers/", views.ai_management, name="api-ai-providers"),
]
