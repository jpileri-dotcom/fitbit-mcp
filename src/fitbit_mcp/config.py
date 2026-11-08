"""Runtime configuration, read from environment variables (set as Fly secrets)."""
from __future__ import annotations

import os

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
# Random string that protects the MCP endpoint and the /auth/start page.
MCP_PATH_SECRET = os.environ.get("MCP_PATH_SECRET", "")
# Public base URL of this server, without a trailing slash.
PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://fitbit-mcp.fly.dev").rstrip("/")
DATA_DIR = os.environ.get("DATA_DIR", "/data")
PORT = int(os.environ.get("PORT", "8000"))

REDIRECT_URI = f"{PUBLIC_URL}/auth/callback"
API_BASE = "https://health.googleapis.com/v4"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

# Only the scopes the tools use. See https://developers.google.com/health/scopes
_P = "https://www.googleapis.com/auth/googlehealth."
SCOPES = [
    _P + "activity_and_fitness.readonly",
    _P + "health_metrics_and_measurements.readonly",
    _P + "health_metrics_and_measurements.writeonly",  # log_weight
    _P + "sleep.readonly",
    _P + "nutrition.readonly",
    _P + "nutrition.writeonly",  # log_food, log_water, delete_food_log
    _P + "profile.readonly",  # get_profile
    _P + "settings.readonly",  # get_devices, user time zone
]


def auth_start_url() -> str:
    return f"{PUBLIC_URL}/auth/start?key={MCP_PATH_SECRET}"


def missing_config() -> list[str]:
    names = {
        "GOOGLE_CLIENT_ID": GOOGLE_CLIENT_ID,
        "GOOGLE_CLIENT_SECRET": GOOGLE_CLIENT_SECRET,
        "MCP_PATH_SECRET": MCP_PATH_SECRET,
    }
    return [k for k, v in names.items() if not v]
