from django.contrib import admin

from .models import AIProvider


@admin.register(AIProvider)
class AIProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "purpose", "kind", "model", "is_enabled", "is_default", "updated_at")
    list_filter = ("purpose", "kind", "is_enabled", "archived_at")
    list_editable = ("is_enabled",)
    search_fields = ("name", "slug", "model", "base_url")
    readonly_fields = ("created_at", "updated_at", "secret_state")
    ordering = ("purpose", "order", "name")
    fieldsets = (
        (None, {"fields": ("name", "slug", "purpose", "kind", "auth_strategy", "order")}),
        ("Endpoint", {"fields": ("base_url", "model", "options")}),
        (
            "Credenziale",
            {
                "fields": ("secret_state",),
                "description": "La chiave è cifrata a riposo e non è leggibile da qui. Si inserisce da Gestione AI.",
            },
        ),
        ("Stato", {"fields": ("is_enabled", "is_default")}),
        ("Metadati", {"fields": ("metadata", "created_at", "updated_at", "archived_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Chiave configurata")
    def secret_state(self, instance: AIProvider) -> str:
        return "Sì" if instance.has_secret else "No"
