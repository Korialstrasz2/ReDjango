from django.contrib import admin

from .models import AudioFile, DatiMappa, ImageCategory, UploadedImage


class V2MediaAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at")
    list_filter = ("archived_at",)

    def get_list_display(self, request):
        field_names = {field.name for field in self.model._meta.fields}
        preferred = ("title", "nome", "category", "group", "folder", "usage_type", "tipo", "primary_tag", "updated_at")
        return tuple(field for field in preferred if field in field_names) or ("id",)

    def get_search_fields(self, request):
        field_names = {field.name for field in self.model._meta.fields}
        preferred = ("title", "nome", "group", "folder", "prompt", "notes")
        return tuple(field for field in preferred if field in field_names)


@admin.register(ImageCategory)
class ImageCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "order", "updated_at")
    list_editable = ("is_active", "order")
    search_fields = ("name", "slug", "description")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("order", "name")
    fieldsets = (
        (None, {"fields": ("name", "slug", "description", "is_active", "order")}),
        (
            "Classificazione automatica",
            {
                "fields": ("usage_types",),
                "description": (
                    "Elenco JSON dei contesti che usano automaticamente questa categoria, "
                    'per esempio ["item_icon", "dice_texture"].'
                ),
            },
        ),
        ("Metadati", {"fields": ("metadata", "created_at", "updated_at", "archived_at"), "classes": ("collapse",)}),
    )


@admin.register(UploadedImage)
class UploadedImageAdmin(V2MediaAdmin):
    list_display = ("title", "category", "group", "visibilita_limitata", "usage_type", "source", "updated_at")
    list_filter = ("visibilita_limitata", "category", "group", "usage_type", "source", "archived_at")
    list_editable = ("visibilita_limitata",)
    search_fields = ("title", "group", "folder", "prompt")
    autocomplete_fields = ("category",)


admin.site.register([AudioFile, DatiMappa], V2MediaAdmin)
