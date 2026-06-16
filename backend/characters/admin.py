from django.contrib import admin

from .models import BorsaReagenti, Character, Equip, Faretra, Note, Personaggio, Zaino


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "ancestry", "archetype", "level", "updated_at")
    list_filter = ("ancestry", "archetype", "level")
    search_fields = ("name", "ancestry", "archetype", "notes")


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


admin.site.register([BorsaReagenti, Equip, Faretra, Note, Personaggio, Zaino], V2CharacterAdmin)
