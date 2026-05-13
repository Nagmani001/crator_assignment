from django.core.management.base import BaseCommand

from gateway.models import Action, Agent, Toolkit


NOTION_ACTIONS = [
    {
        "slug": "read_page",
        "name": "Read Page",
        "description": "Fetch the contents of a Notion page by id.",
        "input_schema": {
            "type": "object",
            "properties": {"page_id": {"type": "string"}},
            "required": ["page_id"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "page": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                    },
                }
            },
        },
        "default_permission": "always_allow",
    },
    {
        "slug": "update_page",
        "name": "Update Page",
        "description": "Update one or more fields on a Notion page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string"},
                "fields": {"type": "object"},
            },
            "required": ["page_id", "fields"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string"},
                "updated": {"type": "boolean"},
                "updated_fields": {"type": "array", "items": {"type": "string"}},
            },
        },
        "default_permission": "requires_approval",
    },
    {
        "slug": "delete_page",
        "name": "Delete Page",
        "description": "Permanently delete a Notion page.",
        "input_schema": {
            "type": "object",
            "properties": {"page_id": {"type": "string"}},
            "required": ["page_id"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string"},
                "deleted": {"type": "boolean"},
            },
        },
        "default_permission": "always_deny",
    },
]


class Command(BaseCommand):
    help = (
        "Seed the toolkit catalog with MOCK Notion actions (offline dev only). "
        "For real MCP-driven registration use `register_notion_mcp`. "
        "Rows seeded by this command have empty mcp_tool_name and are NOT executable."
    )

    def handle(self, *args, **options):
        tk, _ = Toolkit.objects.update_or_create(
            slug="notion",
            defaults={
                "name": "Notion",
                "description": "Mock Notion toolkit for the gateway demo.",
            },
        )

        for spec in NOTION_ACTIONS:
            Action.objects.update_or_create(
                toolkit=tk,
                slug=spec["slug"],
                defaults={
                    "name": spec["name"],
                    "description": spec["description"],
                    "input_schema": spec["input_schema"],
                    "output_schema": spec["output_schema"],
                    "default_permission": spec["default_permission"],
                },
            )

        agent, created = Agent.objects.get_or_create(
            name="demo-agent",
            defaults={"is_active": True},
        )

        self.stdout.write(self.style.SUCCESS(f"Toolkit: {tk.slug}"))
        for spec in NOTION_ACTIONS:
            self.stdout.write(f"  - {spec['slug']} -> {spec['default_permission']}")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Agent: {agent.name}"))
        self.stdout.write(self.style.WARNING(f"AGENT_ID={agent.id}"))
        self.stdout.write("")
        self.stdout.write("Export it for the agent CLI:")
        self.stdout.write(f"  export AGENT_ID={agent.id}")
