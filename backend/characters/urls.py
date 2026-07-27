from django.urls import path

from . import views


urlpatterns = [
    path("personaggi/", views.list_personaggi, name="api-personaggi-list"),
    path("personaggi/select/", views.select_personaggio, name="api-personaggi-select"),
]
