from django.contrib import admin

from .models import (
    BottoneCombat,
    ContenitoreInventario,
    EffettiPersonaggio,
    EffettoPersonalizzato,
    Equip,
    Faretra,
    Note,
    OperazioneEffettoPersonalizzato,
    Personaggio,
    SkillPersonaggio,
    TiroCompetenza,
    VoceContenitoreInventario,
    Zaino,
)


class V2CharacterAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at")
    list_filter = ("archived_at",)

    def get_list_display(self, request):
        field_names = {field.name for field in self.model._meta.fields}
        preferred = ("nome", "nome_interno", "tipologia", "livello", "updated_at")
        return tuple(field for field in preferred if field in field_names) or ("id",)

    def get_search_fields(self, request):
        field_names = {field.name for field in self.model._meta.fields}
        preferred = ("nome", "nome_interno", "tipologia", "dettagli_personaggio", "background", "notes")
        return tuple(field for field in preferred if field in field_names)


admin.site.register(
    [ContenitoreInventario, VoceContenitoreInventario, EffettiPersonaggio, Equip, Faretra, Note, Personaggio, SkillPersonaggio, TiroCompetenza, Zaino],
    V2CharacterAdmin,
)


@admin.register(BottoneCombat)
class BottoneCombatAdmin(admin.ModelAdmin):
    list_display = ("nome", "personaggio", "pubblico", "attivo", "tieni_attivo_in_combat", "ordine")
    list_filter = ("pubblico", "attivo", "tieni_attivo_in_combat")
    search_fields = ("nome", "testo_da_mostrare", "personaggio__nome")
    list_editable = ("pubblico", "attivo", "tieni_attivo_in_combat", "ordine")


class OperazioneEffettoInline(admin.TabularInline):
    model = OperazioneEffettoPersonalizzato
    extra = 0


@admin.register(EffettoPersonalizzato)
class EffettoPersonalizzatoAdmin(admin.ModelAdmin):
    list_display = ("nome", "personaggio", "temporaneo", "ordine")
    list_filter = ("temporaneo", "icona")
    search_fields = ("nome", "personaggio__nome", "origine", "descrizione")
    inlines = (OperazioneEffettoInline,)
