"""Shared application instances — imported by server.py and all tool modules."""
from __future__ import annotations

import os

from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl

from fitbit_mcp.client import FitbitClient
from fitbit_mcp.oauth_provider import FitbitOAuthProvider

# Initialize the Fitbit API client
client = FitbitClient()

# Server URL from environment
server_url = os.environ.get("SERVER_URL", "http://localhost:8000")

# Initialize the OAuth provider, linking it to the client for token handoff
provider = FitbitOAuthProvider(
    server_url=server_url,
    on_fitbit_tokens=lambda access_token, refresh_token, expires_in: client.set_tokens(
        access_token, refresh_token, expires_in
    ),
)

# Configure MCP auth settings
auth_settings = AuthSettings(
    issuer_url=AnyHttpUrl(server_url),
    client_registration_options=ClientRegistrationOptions(
        enabled=True,
        valid_scopes=["fitbit"],
        default_scopes=["fitbit"],
    ),
    required_scopes=["fitbit"],
    resource_server_url=None,  # Combined AS+RS mode
)

# Initialize the MCP server with OAuth
# host="0.0.0.0" is required for Docker networking
mcp = FastMCP(
    name="Fitbit MCP Server",
    instructions="Access Fitbit health and fitness data including activity, sleep, heart rate, and more.",
    auth_server_provider=provider,
    auth=auth_settings,
    host="0.0.0.0",
    port=8000,
    streamable_http_path="/",
)
