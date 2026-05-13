from .models import Action
from . import mcp_client


def run(action: Action, params: dict) -> dict:
    if not action.mcp_tool_name:
        raise RuntimeError(
            f"Action {action.toolkit.slug}.{action.slug} has no mcp_tool_name. "
            f"Run: python manage.py register_notion_mcp"
        )
    return mcp_client.call_tool(action.mcp_tool_name, params)
