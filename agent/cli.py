import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from tools import GATEWAY_URL, jwt_server


AGENT_ID = os.environ.get("AGENT_ID", "<set AGENT_ID env var>")
NOTION_PAGE_ID = os.environ.get("NOTION_PAGE_ID", "")
NOTION_BLOCK_ID = os.environ.get("NOTION_BLOCK_ID", "")

SYSTEM_PROMPT = f"""
You are a gateway-bound agent. Available tools:
- GenerateJWT(agent_id): mint a short-lived bearer token.
- Bash: run shell commands (use curl for ALL gateway HTTP).
- Read / Write / Edit: local filesystem only.

Hard rules:
1. Begin by calling GenerateJWT with agent_id={AGENT_ID}. Remember the token; reuse it.
   If GenerateJWT returns an error (is_error=true, non-200, network failure, or
   missing token), STOP immediately. Do NOT issue any curl/Bash gateway calls
   without a valid bearer token. Print the error verbatim and exit the task.
2. For every gateway call, use curl with the bearer token, e.g.:
     curl -sS -w "\\nHTTP %{{http_code}}\\n" -X POST \\
       {GATEWAY_URL}/api/external-services/toolkits/<tk>/actions/<a>/call/ \\
       -H "Authorization: Bearer <token>" \\
       -H "content-type: application/json" \\
       -d '{{"params": {{...}}}}'
3. Never assume direct tools like send_email or update_page exist. Every external
   action goes through the gateway HTTP API.
4. Handle the three outcomes explicitly:
   - 200: print the executed result.
   - 202: extract ticket_id from the JSON, then poll
       GET {GATEWAY_URL}/api/external-services/approvals/<ticket_id>/status/
     every 5 seconds (sleep 5 in bash), up to 12 attempts. Stop early once
     status != "pending". Report the final status and result/reason.
   - 403: print the denial message and continue.
5. If any call returns HTTP 401, regenerate the JWT once and retry that call.
6. Always show the HTTP status code and the response body to the user.
""".strip()


DEFAULT_PROMPT = (
    "Demo the gateway end-to-end against the live Notion MCP server. Steps:\n"
    "1. Call GenerateJWT.\n"
    "2. GET /api/external-services/toolkits/ to discover toolkits.\n"
    "3. GET the actions for the 'notion' toolkit and print their permissions.\n"
    "4. GET the input schema for each action so you know the exact payload shape.\n"
    "   The schemas are Notion-native (e.g. read_page requires `page_id`, update_page\n"
    "   requires `page_id` and `properties`, delete_page requires `block_id`).\n"
    f"5. Use page_id={NOTION_PAGE_ID!r} and block_id={NOTION_BLOCK_ID!r} (from env).\n"
    "   If either is empty, STOP and tell user to set NOTION_PAGE_ID / NOTION_BLOCK_ID.\n"
    "   Do NOT call AskUserQuestion. Do NOT prompt interactively.\n"
    "6. Call read_page with {\"page_id\":\"<page_id>\"} - expect HTTP 200.\n"
    "7. Call update_page with {\"page_id\":\"<page_id>\",\"properties\":{...}} - expect\n"
    "   HTTP 202, then poll the approval status. While polling, print the admin\n"
    "   resolve curl command for the user to run. The resolve endpoint requires\n"
    "   an ADMIN bearer token (NOT the agent JWT). Print this two-step block,\n"
    "   substituting <ticket_id>:\n"
    "     # 1. mint admin token (basic auth = Django superuser)\n"
    "     ADMIN_TOKEN=$(curl -sS -u <user>:<pass> -X POST \\\n"
    "       http://localhost:8000/api/auth/admin-token/ | jq -r .token)\n"
    "     # 2. resolve with bearer\n"
    "     curl -sS -X POST \\\n"
    "       http://localhost:8000/api/external-services/approvals/<ticket_id>/resolve/ \\\n"
    "       -H \"Authorization: Bearer $ADMIN_TOKEN\" \\\n"
    "       -H 'content-type: application/json' \\\n"
    "       -d '{\"decision\":\"approve\"}'\n"
    "   Never print the resolve curl without the Authorization header. Never\n"
    "   reuse the agent JWT for admin endpoints.\n"
    "8. Call delete_page with {\"block_id\":\"<block_id>\"} - expect HTTP 403.\n"
    "9. GET /api/external-services/audit/ and summarize the outcomes recorded."
)


async def main():
    user_prompt = " ".join(sys.argv[1:]).strip() or DEFAULT_PROMPT

    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=[
            "Bash",
            "mcp__auth__GenerateJWT",
        ],
        mcp_servers={"auth": jwt_server},
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(user_prompt)
        async for msg in client.receive_response():
            _render(msg)


def _render(msg):
    cls = type(msg).__name__

    if cls == "AssistantMessage":
        for block in getattr(msg, "content", []) or []:
            btype = type(block).__name__
            if btype == "TextBlock":
                text = getattr(block, "text", "").strip()
                if text:
                    print(f"\n[agent] {text}")
            elif btype == "ToolUseBlock":
                name = getattr(block, "name", "?")
                inp = getattr(block, "input", {}) or {}
                preview = _preview_tool_input(name, inp)
                print(f"\n[tool] {name} {preview}")

    elif cls == "UserMessage":
        for block in getattr(msg, "content", []) or []:
            if type(block).__name__ != "ToolResultBlock":
                continue
            content = getattr(block, "content", "")
            text = _extract_text(content).strip()
            if text:
                indented = "\n".join("  " + ln for ln in text.splitlines())
                print(f"[result]\n{indented}")

    elif cls == "ResultMessage":
        print("\n[done]")


def _preview_tool_input(name, inp):
    if name == "Bash":
        cmd = (inp.get("command") or "").strip().replace("\n", " ")
        return cmd[:200] + ("…" if len(cmd) > 200 else "")
    return str(inp)[:200]


def _extract_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                parts.append(c.get("text", ""))
        return "\n".join(parts)
    return ""


if __name__ == "__main__":
    if AGENT_ID.startswith("<set"):
        print("ERROR: set AGENT_ID env var (see `python manage.py register_notion_mcp`).",
              file=sys.stderr)
        sys.exit(1)
    asyncio.run(main())
