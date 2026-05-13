from rest_framework import serializers

from . import models


class ToolkitSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Toolkit
        fields = ["slug", "name", "description"]


class ActionSerializer(serializers.ModelSerializer):
    permission = serializers.SerializerMethodField()

    class Meta:
        model = models.Action
        fields = ["slug", "name", "description", "permission"]

    def get_permission(self, obj):
        resolver = self.context.get("resolver")
        agent = self.context.get("agent")
        if resolver and agent:
            return resolver(agent, obj)
        return obj.default_permission


class PermissionOverrideSerializer(serializers.ModelSerializer):
    action_slug = serializers.CharField(source="action.slug", read_only=True)
    toolkit_slug = serializers.CharField(source="action.toolkit.slug", read_only=True)

    class Meta:
        model = models.PermissionOverride
        fields = ["action", "action_slug", "toolkit_slug", "permission"]


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AuditLog
        fields = [
            "id",
            "agent",
            "agent_uuid",
            "agent_display",
            "toolkit_slug",
            "action_slug",
            "params",
            "outcome",
            "timestamp",
        ]
