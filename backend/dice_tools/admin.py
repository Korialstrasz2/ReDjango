from django.contrib import admin

from .models import DiceRollRecord, DiceSet, DiceTexture


class DiceTextureInline(admin.TabularInline):
    model = DiceTexture
    extra = 0


@admin.register(DiceSet)
class DiceSetAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "is_default", "order", "updated_at")
    list_filter = ("is_active", "is_default", "archived_at")
    search_fields = ("name", "slug", "description")
    readonly_fields = ("created_at", "updated_at", "archived_at")
    inlines = (DiceTextureInline,)


@admin.register(DiceRollRecord)
class DiceRollRecordAdmin(admin.ModelAdmin):
    list_display = ("created_at", "player_name", "character_name", "source", "label", "notation", "total")
    list_filter = ("source", "created_at")
    search_fields = ("player_name", "character_name", "label", "notation")
    readonly_fields = (
        "giocatore",
        "player_name",
        "personaggio",
        "character_name",
        "source",
        "label",
        "notation",
        "rolls",
        "modifier",
        "total",
        "dice_set_name",
        "created_at",
        "updated_at",
        "archived_at",
        "metadata",
    )
