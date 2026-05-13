from django.db import migrations, models


def backfill(apps, schema_editor):
    AuditLog = apps.get_model("gateway", "AuditLog")
    AuditLog.objects.filter(agent_uuid__isnull=True, agent__isnull=False).update(
        agent_uuid=models.F("agent_id")
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("gateway", "0002_auditlog_agent_uuid"),
    ]
    operations = [
        migrations.RunPython(backfill, reverse_code=noop),
    ]
