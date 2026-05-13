import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone


PERMISSION_CHOICES = [
    ("always_allow", "always_allow"),
    ("requires_approval", "requires_approval"),
    ("always_deny", "always_deny"),
]


class Agent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.id})"

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_staff(self):
        return False

    @property
    def is_superuser(self):
        return False


class Toolkit(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.slug


class Action(models.Model):
    toolkit = models.ForeignKey(Toolkit, on_delete=models.CASCADE, related_name="actions")
    slug = models.SlugField()
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    input_schema = models.JSONField(default=dict, blank=True)
    output_schema = models.JSONField(default=dict, blank=True)
    default_permission = models.CharField(max_length=32, choices=PERMISSION_CHOICES)
    mcp_tool_name = models.CharField(max_length=128, blank=True, default="")

    class Meta:
        unique_together = ("toolkit", "slug")

    def __str__(self):
        return f"{self.toolkit.slug}.{self.slug}"


class PermissionOverride(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="overrides")
    action = models.ForeignKey(Action, on_delete=models.CASCADE)
    permission = models.CharField(max_length=32, choices=PERMISSION_CHOICES)

    class Meta:
        unique_together = ("agent", "action")

    def __str__(self):
        return f"{self.agent_id}:{self.action_id}={self.permission}"


def _default_ticket_expiry():
    return timezone.now() + timedelta(hours=24)


class ApprovalTicket(models.Model):
    STATUS_CHOICES = [
        ("pending", "pending"),
        ("approved", "approved"),
        ("rejected", "rejected"),
        ("expired", "expired"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="tickets")
    action = models.ForeignKey(Action, on_delete=models.CASCADE)
    params = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    result = models.JSONField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_default_ticket_expiry)

    def is_expired(self):
        return self.status == "pending" and self.expires_at < timezone.now()


class AuditLog(models.Model):
    OUTCOME_CHOICES = [
        ("allowed", "allowed"),
        ("denied", "denied"),
        ("pending", "pending"),
        ("approved", "approved"),
        ("rejected", "rejected"),
        ("expired", "expired"),
    ]
    agent = models.ForeignKey(
        Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs"
    )
    agent_uuid = models.UUIDField(null=True, blank=True)
    agent_display = models.CharField(max_length=200, blank=True)
    toolkit = models.ForeignKey(Toolkit, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.ForeignKey(Action, on_delete=models.SET_NULL, null=True, blank=True)
    toolkit_slug = models.CharField(max_length=64, blank=True)
    action_slug = models.CharField(max_length=64, blank=True)
    params = models.JSONField(default=dict, blank=True)
    outcome = models.CharField(max_length=16, choices=OUTCOME_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise RuntimeError("AuditLog is append-only and cannot be updated")
        if self.agent:
            if not self.agent_uuid:
                self.agent_uuid = self.agent.id
            if not self.agent_display:
                self.agent_display = self.agent.name
        if self.toolkit and not self.toolkit_slug:
            self.toolkit_slug = self.toolkit.slug
        if self.action and not self.action_slug:
            self.action_slug = self.action.slug
        super().save(*args, **kwargs)
