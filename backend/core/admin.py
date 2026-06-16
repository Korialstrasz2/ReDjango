from django.contrib import admin

from .models import (
    CampaignLoreEntry,
    CampaignLoreRelation,
    Competenze,
    Curiosita,
    DatiCampagna,
    EffettiEMalattie,
    EffettiSkill,
    FamigliaSkill,
    Giocatore,
    GlobalModifiers,
    Guida,
    HallOfFameCharacter,
    Messaggio,
    Negozio,
    NomiRazzeInfo,
    Oggetto,
    Skill,
    TimelineEvent,
    TipoArma,
    Unit,
)


class V2Admin(admin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at")
    list_filter = ("archived_at",)

    def get_list_display(self, request):
        field_names = {field.name for field in self.model._meta.fields}
        preferred = (
            "nome",
            "name",
            "title",
            "categoria",
            "tipo",
            "role",
            "attiva",
            "updated_at",
        )
        display = tuple(field for field in preferred if field in field_names)
        return display or ("id",)

    def get_search_fields(self, request):
        field_names = {field.name for field in self.model._meta.fields}
        preferred = (
            "nome",
            "name",
            "title",
            "descrizione",
            "description",
            "contenuto",
            "content",
            "slug",
        )
        return tuple(field for field in preferred if field in field_names)


admin.site.register(
    [
        CampaignLoreEntry,
        CampaignLoreRelation,
        Competenze,
        Curiosita,
        DatiCampagna,
        EffettiEMalattie,
        EffettiSkill,
        FamigliaSkill,
        Giocatore,
        GlobalModifiers,
        Guida,
        HallOfFameCharacter,
        Messaggio,
        Negozio,
        NomiRazzeInfo,
        Oggetto,
        Skill,
        TimelineEvent,
        TipoArma,
        Unit,
    ],
    V2Admin,
)
