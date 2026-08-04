from django.contrib import admin

from .models import (
    AIAgentProfile,
    AIChangeOperation,
    AIChangeSet,
    AIConversation,
    AIExecutionRun,
    AIProvider,
)


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


@admin.register(AIAgentProfile)
class AIAgentProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "mode", "minimum_role", "provider", "max_iterations", "is_enabled", "is_default")
    list_filter = ("mode", "minimum_role", "is_enabled", "is_default")
    search_fields = ("name", "slug", "description", "instructions")
    ordering = ("order", "name")


@admin.register(AIConversation)
class AIConversationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "agent", "updated_at")
    search_fields = ("title", "user__username")
    readonly_fields = ("created_at", "updated_at", "history", "transcript")
    ordering = ("-updated_at",)


@admin.register(AIExecutionRun)
class AIExecutionRunAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "status", "user", "provider", "created_at", "completed_at")
    list_filter = ("kind", "status", "provider")
    search_fields = ("id", "user__username")
    readonly_fields = (
        "id", "created_at", "updated_at", "request_payload", "result", "error",
        "started_at", "completed_at",
    )
    ordering = ("-created_at",)


class ReadOnlyAuditAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


@admin.register(AIChangeSet)
class AIChangeSetAdmin(ReadOnlyAuditAdmin):
    list_display = ("id", "status", "title", "user", "agent", "revision", "created_at", "validated_at", "applied_at")
    list_filter = ("status", "agent")
    search_fields = ("id", "title", "user__username", "request_text")
    ordering = ("-updated_at",)


@admin.register(AIChangeOperation)
class AIChangeOperationAdmin(ReadOnlyAuditAdmin):
    list_display = ("change_set", "position", "entity_type", "action", "target_id", "selected", "status")
    list_filter = ("entity_type", "action", "selected", "status")
    search_fields = ("change_set__id", "display_label", "target_id")
    ordering = ("-change_set__updated_at", "position")
