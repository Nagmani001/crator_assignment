from .models import Action, Agent, PermissionOverride


def resolve(agent: Agent, action: Action) -> str:
    override = PermissionOverride.objects.filter(agent=agent, action=action).first()
    return override.permission if override else action.default_permission
