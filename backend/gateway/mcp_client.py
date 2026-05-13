"""
Notion MCP client wrapper.

Spawns the official `@notionhq/notion-mcp-server` via npx, talks stdio MCP,
returns parsed JSON. One subprocess per call — simple, slow (~1s overhead),
fine for assignment scope.

Caveats:
- Per-call subprocess spawn. Move to a persistent session if latency hurts.
- asyncio.run cannot be called from inside an existing event loop. Django sync
  views are fine here. From async contexts, switch to asgiref.async_to_sync.
- Subprocess stderr inherits to parent — useful for debugging.
"""

import asyncio
import json
import os

from django.conf import settings
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _server_params() -> StdioServerParameters:
    token = settings.NOTION_TOKEN
    if not token:
        raise RuntimeError("NOTION_TOKEN not set in environment.")
    headers = json.dumps(
        {"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28"}
    )
    env = {**os.environ, "OPENAPI_MCP_HEADERS": headers}
    return StdioServerParameters(
        command="npx",
        args=["-y", "@notionhq/notion-mcp-server"],
        env=env,
    )


async def _async_list_tools() -> list[dict]:
    params = _server_params()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            resp = await session.list_tools()
            return [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "inputSchema": t.inputSchema or {},
                }
                for t in resp.tools
            ]


async def _async_call_tool(name: str, arguments: dict) -> dict:
    params = _server_params()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
            text = "".join(
                getattr(block, "text", "") for block in (result.content or [])
            )
            if result.isError:
                raise RuntimeError(f"MCP tool {name} returned error: {text}")
            if not text:
                return {}
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"raw": text}


def list_tools() -> list[dict]:
    return asyncio.run(_async_list_tools())


def call_tool(name: str, arguments: dict) -> dict:
    return asyncio.run(_async_call_tool(name, arguments))
