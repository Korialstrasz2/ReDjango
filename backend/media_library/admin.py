from django.contrib import admin

from .models import AudioFile, DatiMappa, UploadedImage, UserMediaAsset


@admin.register(UserMediaAsset)
class UserMediaAssetAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "mime_type", "size_bytes", "created_at")
    list_filter = ("mime_type", "created_at")
    search_fields = ("title", "original_name", "sha256", "notes")
    readonly_fields = ("sha256", "size_bytes", "created_at")


class V2MediaAdmin(admin.ModelAdmin):
    readonly_fields = ("created_at", "updated_at")
    list_filter = ("archived_at",)

    def get_list_display(self, request):
        field_names = {field.name for field in self.model._meta.fields}
        preferred = ("title", "nome", "folder", "usage_type", "tipo", "primary_tag", "updated_at")
        return tuple(field for field in preferred if field in field_names) or ("id",)

    def get_search_fields(self, request):
        field_names = {field.name for field in self.model._meta.fields}
        preferred = ("title", "nome", "folder", "prompt", "notes")
        return tuple(field for field in preferred if field in field_names)


admin.site.register([AudioFile, DatiMappa, UploadedImage], V2MediaAdmin)
