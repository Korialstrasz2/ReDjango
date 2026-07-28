from django.contrib import admin

from .models import (
    EffettoEventoReputazione,
    EventoReputazione,
    Fazione,
    PersonaggioLore,
    RelazioneFazione,
)


class RelazioneFazioneInline(admin.TabularInline):
    model = RelazioneFazione
    fk_name = "origine"
    extra = 0
    autocomplete_fields = ["destinazione"]


@admin.register(Fazione)
class FazioneAdmin(admin.ModelAdmin):
    list_display = ["nome", "campagna", "reputazione_base", "ordine", "archived_at"]
    list_filter = ["campagna"]
    search_fields = ["nome"]
    ordering = ["campagna", "ordine", "nome"]
    inlines = [RelazioneFazioneInline]


class EffettoEventoReputazioneInline(admin.TabularInline):
    model = EffettoEventoReputazione
    extra = 0
    autocomplete_fields = ["fazione"]


@admin.register(EventoReputazione)
class EventoReputazioneAdmin(admin.ModelAdmin):
    list_display = ["__str__", "campagna", "modalita", "giorno_campagna", "visibile_ai_giocatori"]
    list_filter = ["campagna", "modalita", "visibile_ai_giocatori"]
    search_fields = ["titolo", "motivo"]
    ordering = ["campagna", "giorno_campagna"]
    inlines = [EffettoEventoReputazioneInline]


@admin.register(PersonaggioLore)
class PersonaggioLoreAdmin(admin.ModelAdmin):
    list_display = ["nome", "ruolo", "campagna", "fazione", "visibile_ai_giocatori", "archived_at"]
    list_filter = ["campagna", "fazione", "visibile_ai_giocatori"]
    search_fields = ["nome", "ruolo"]
    ordering = ["campagna", "ordine", "nome"]
