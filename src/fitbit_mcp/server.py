from __future__ import annotations

import hmac
import html
import logging
import sys

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", stream=sys.stderr)
logger = logging.getLogger("fitbit_mcp")

from fitbit_mcp import auth, config  # noqa: E402
from fitbit_mcp import google as g  # noqa: E402
from fitbit_mcp.app import mcp  # noqa: E402
import fitbit_mcp.tools  # noqa: E402, F401  (registers tools)


def _page(title: str, body: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title></head><body style='font-family:system-ui;max-width:32rem;"
        f"margin:2rem auto;padding:0 1rem;font-size:1.1rem;line-height:1.5'><h2>{html.escape(title)}</h2>{body}</body></html>",
        status_code=status,
    )


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> Response:
    return JSONResponse({"ok": True, "configured": not config.missing_config(), "google_linked": auth.has_token()})


@mcp.custom_route("/auth/start", methods=["GET"])
async def auth_start(request: Request) -> Response:
    key = request.query_params.get("key", "")
    if not config.MCP_PATH_SECRET or not hmac.compare_digest(key, config.MCP_PATH_SECRET):
        return _page("Link not valid", "<p>This sign-in link is missing its key. Use the full link Claude gave you.</p>", 403)
    if config.missing_config():
        return _page("Server not configured", "<p>The Google client ID or secret is missing on the server.</p>", 500)
    return RedirectResponse(auth.new_auth_url(), status_code=302)


@mcp.custom_route("/auth/callback", methods=["GET"])
async def auth_callback(request: Request) -> Response:
    err = request.query_params.get("error")
    if err:
        return _page("Sign-in cancelled", f"<p>Google said: {html.escape(err)}. Open the sign-in link again to retry.</p>", 400)
    code, state = request.query_params.get("code"), request.query_params.get("state", "")
    if not code or not auth.consume_state(state):
        return _page("Link expired", "<p>This sign-in attempt expired or was already used. Open the sign-in link again.</p>", 400)
    try:
        tok = await auth.exchange_code(code)
    except ValueError as e:
        logger.error("Token exchange failed: %s", e)
        return _page("Sign-in failed", f"<p>{html.escape(str(e))}</p>", 400)
    granted = set(tok["scope"].split())
    missing = [s.rsplit(".", 2)[-2] + "." + s.rsplit(".", 1)[-1] for s in config.SCOPES if s not in granted]
    try:
        await g.request("GET", "/users/me/identity")
    except g.ApiError as e:
        return _page("Not linked to Google Health", f"<p>{html.escape(str(e))}</p>", 400)
    note = ""
    if missing:
        note = ("<p><b>Some permissions were not allowed:</b> " + html.escape(", ".join(missing)) +
                ". Tools that need them will fail. Open the sign-in link again and tick every box to fix this.</p>")
    return _page("Connected", "<p>Google Health is connected. You can close this page and go back to Claude.</p>" + note)


def main() -> None:
    missing = config.missing_config()
    if missing:
        logger.error("Missing configuration: %s. MCP endpoint is disabled until these are set.", ", ".join(missing))
    logger.info("Starting server on port %s", config.PORT)
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
