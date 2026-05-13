import os

import requests
from claude_agent_sdk import create_sdk_mcp_server, tool


GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8000")


@tool(
    "GenerateJWT",
    (
        "Mint a short-lived JWT for this agent by calling the gateway's token endpoint. "
        "Call this once at the start of a session and reuse the returned token in the "
        "Authorization: Bearer <token> header on every subsequent curl request. "
        "If a later call returns HTTP 401, call this tool again to refresh."
    ),
    {"agent_id": str},
)
async def generate_jwt(args):
    agent_id = args["agent_id"]
    url = f"{GATEWAY_URL}/api/auth/token/"
    try:
        r = requests.post(url, json={"agent_id": agent_id}, timeout=10)
    except requests.RequestException as e:
        return {
            "content": [{"type": "text", "text": f"network error reaching {url}: {e}"}],
            "is_error": True,
        }
    if r.status_code != 200:
        return {
            "content": [{
                "type": "text",
                "text": f"token endpoint returned {r.status_code}: {r.text}",
            }],
            "is_error": True,
        }
    data = r.json()
    return {
        "content": [{
            "type": "text",
            "text": (
                f"token={data['token']}\n"
                f"expires_in={data['expires_in']}s\n"
                f"gateway={GATEWAY_URL}"
            ),
        }]
    }


jwt_server = create_sdk_mcp_server(name="auth", version="1.0.0", tools=[generate_jwt])
