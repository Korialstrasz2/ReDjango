from django.contrib import admin

from .models import (
    CharacterTemplate,
    CombatEvent,
    CombatModifier,
    CombatModifierState,
    HexType,
    MapHex,
    MapHexTerrain,
    MapMetadata,
    MapParticipant,
    MapParticipantFootprint,
    MapSnapshot,
    MapType,
    TurnPlanAction,
    TurnPlanStep,
)


class MapParticipantFootprintInline(admin.TabularInline):
    model = MapParticipantFootprint
    extra = 0


@admin.register(MapParticipant)
class MapParticipantAdmin(admin.ModelAdmin):
    list_display = ("character", "map", "active", "anchor_q", "anchor_r", "order")
    list_filter = ("map", "active")
    search_fields = ("character__nome", "map__name")
    inlines = (MapParticipantFootprintInline,)


class MapHexTerrainInline(admin.TabularInline):
    model = MapHexTerrain
    extra = 0


@admin.register(MapHex)
class MapHexAdmin(admin.ModelAdmin):
    list_display = ("map", "q", "r", "blocked", "revealed", "overlay_color")
    list_filter = ("map", "blocked", "revealed")
    inlines = (MapHexTerrainInline,)


class MapParticipantInline(admin.TabularInline):
    model = MapParticipant
    extra = 0
    show_change_link = True


class MapHexInline(admin.TabularInline):
    model = MapHex
    extra = 0
    show_change_link = True
    fields = ("q", "r", "overlay_color", "overlay_opacity", "blocked", "revealed")


@admin.register(MapMetadata)
class MapMetadataAdmin(admin.ModelAdmin):
    list_display = ("name", "map_type", "orientation", "rows", "columns", "revision", "updated_at")
    list_filter = ("map_type", "orientation", "is_default")
    search_fields = ("name",)
    readonly_fields = ("revision", "created_at", "updated_at")
    fieldsets = (
        ("Identità", {"fields": ("name", "map_type", "image", "created_by", "is_default", "active_character")}),
        ("Griglia", {"fields": ("orientation", "rows", "columns", "hex_size", "grid_offset_x", "grid_offset_y")}),
        ("Immagine", {"fields": ("image_scale", "image_offset_x", "image_offset_y")}),
        ("Vista salvata", {"fields": ("viewport_scale", "viewport_offset_x", "viewport_offset_y")}),
        ("Nebbia di guerra", {"fields": ("fog_enabled", "fog_opacity")}),
        ("Versione", {"fields": ("revision", "created_at", "updated_at")}),
    )
    inlines = (MapParticipantInline, MapHexInline)


@admin.register(MapType)
class MapTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "default_orientation", "default_rows", "default_columns", "active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(HexType)
class HexTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "movement_multiplier", "impassable", "color", "active", "order")
    list_editable = ("movement_multiplier", "impassable", "color", "active", "order")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(CharacterTemplate)
class CharacterTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "active", "updated_at")
    list_filter = ("active",)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "description")


@admin.register(CombatModifier)
class CombatModifierAdmin(admin.ModelAdmin):
    list_display = ("name", "scope", "attack_bonus", "damage_bonus", "penetration_flat", "penetration_percent", "active", "order")
    list_editable = ("attack_bonus", "damage_bonus", "penetration_flat", "penetration_percent", "active", "order")


class TurnPlanStepInline(admin.TabularInline):
    model = TurnPlanStep
    extra = 0


@admin.register(TurnPlanAction)
class TurnPlanActionAdmin(admin.ModelAdmin):
    list_display = ("name", "map", "character", "action_type", "cost_ap", "committed_at")
    list_filter = ("map", "action_type", "committed_at")
    inlines = (TurnPlanStepInline,)


admin.site.register(CombatModifierState)
admin.site.register(CombatEvent)


@admin.register(MapSnapshot)
class MapSnapshotAdmin(admin.ModelAdmin):
    list_display = ("map", "label", "revision", "created_by", "created_at")
    list_filter = ("map", "created_at")
    search_fields = ("map__name", "label")
    readonly_fields = ("state", "created_at")
