
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from gateway import mcp_client
from gateway.models import Action, Agent, Toolkit


WANTED = {
    "API-retrieve-a-page": {
        "slug": "read_page",
        "name": "Read Page",
        "default_permission": "always_allow",
    },
    "API-patch-page": {
        "slug": "update_page",
        "name": "Update Page",
        "default_permission": "requires_approval",
    },
    "API-delete-a-block": {
        "slug": "delete_page",
        "name": "Delete Block (destructive)",
        "default_permission": "always_deny",
    },
}


class Command(BaseCommand):
    help = "Register the Notion toolkit by discovering tools from the live MCP server."

    def handle(self, *args, **options):
        if not settings.NOTION_TOKEN:
            raise CommandError(
                "NOTION_TOKEN env var not set. Export it before running this command."
            )

        self.stdout.write("Connecting to Notion MCP server (npx)...")
        tools = mcp_client.list_tools()
        self.stdout.write(f"Discovered {len(tools)} tools.")

        by_name = {t["name"]: t for t in tools}
        missing = [n for n in WANTED if n not in by_name]
        if missing:
            raise CommandError(
                "Notion MCP server did not expose expected tools: "
                f"{missing}. Update the WANTED mapping."
            )

        tk, _ = Toolkit.objects.update_or_create(
            slug="notion",
            defaults={
                "name": "Notion",
                "description": "Notion via official MCP server.",
            },
        )

        for mcp_name, cfg in WANTED.items():
            tool = by_name[mcp_name]
            Action.objects.update_or_create(
                toolkit=tk,
                slug=cfg["slug"],
                defaults={
                    "name": cfg["name"],
                    "description": tool["description"],
                    "input_schema": tool["inputSchema"],
                    "output_schema": {},
                    "default_permission": cfg["default_permission"],
                    "mcp_tool_name": mcp_name,
                },
            )

        agent, _ = Agent.objects.get_or_create(
            name="demo-agent",
            defaults={"is_active": True},
        )

        self.stdout.write(self.style.SUCCESS(f"Toolkit: {tk.slug}"))
        for mcp_name, cfg in WANTED.items():
            self.stdout.write(
                f"  - {cfg['slug']} -> {cfg['default_permission']} "
                f"(mcp: {mcp_name})"
            )
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Agent: {agent.name}"))
        self.stdout.write(self.style.WARNING(f"AGENT_ID={agent.id}"))
        self.stdout.write("")
        self.stdout.write("Export it for the agent CLI:")
        self.stdout.write(f"  export AGENT_ID={agent.id}")
