from __future__ import annotations

import logging
import sys

from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

# Configure logging to stderr (stdout is reserved for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("fitbit_mcp")

# Import shared instances
from fitbit_mcp.app import mcp, provider  # noqa: E402

# Import all tool modules to register them with the MCP server
import fitbit_mcp.tools  # noqa: E402, F401


# Custom route for Fitbit OAuth callback
@mcp.custom_route("/fitbit-callback", methods=["GET"])
async def fitbit_callback_handler(request: Request) -> Response:
    """Handle the redirect from Fitbit after user authorization."""
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        return Response("Missing code or state parameter", status_code=400)

    try:
        redirect_uri = await provider.handle_fitbit_callback(code, state)
        return RedirectResponse(url=redirect_uri, status_code=302)
    except ValueError as e:
        logger.error(f"Fitbit callback error: {e}")
        return Response(str(e), status_code=400)


def main() -> None:
    """Run the Fitbit MCP server."""
    logger.info("Starting Fitbit MCP server")
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
