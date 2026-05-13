from django.contrib import admin

from . import models


@admin.register(models.Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "id")


@admin.register(models.Toolkit)
class ToolkitAdmin(admin.ModelAdmin):
    list_display = ("slug", "name")
    search_fields = ("slug", "name")


@admin.register(models.Action)
class ActionAdmin(admin.ModelAdmin):
    list_display = ("toolkit", "slug", "name", "default_permission")
    list_filter = ("toolkit", "default_permission")
    search_fields = ("slug", "name")


@admin.register(models.PermissionOverride)
class PermissionOverrideAdmin(admin.ModelAdmin):
    list_display = ("agent", "action", "permission")
    list_filter = ("permission",)


@admin.register(models.ApprovalTicket)
class ApprovalTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "agent", "action", "status", "created_at", "expires_at")
    list_filter = ("status",)
    readonly_fields = (
        "id", "agent", "action", "params", "created_at", "expires_at",
        "status", "result", "rejection_reason",
    )

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(models.AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "agent_display", "toolkit_slug", "action_slug", "outcome")
    list_filter = ("outcome", "toolkit_slug")
    search_fields = ("agent_display", "toolkit_slug", "action_slug")
    readonly_fields = [
        "agent",
        "agent_display",
        "toolkit",
        "action",
        "toolkit_slug",
        "action_slug",
        "params",
        "outcome",
        "timestamp",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
