from django.contrib import admin

from .models import DiceSet, DiceTexture


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
