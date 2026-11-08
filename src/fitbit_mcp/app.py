"""Shared FastMCP instance. The MCP endpoint lives at /<MCP_PATH_SECRET>/mcp."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from fitbit_mcp import config

mcp = FastMCP(
    name="Fitbit (Google Health)",
    instructions=(
        "Read and log the user's Fitbit data through the Google Health API: activity, heart rate, HRV, sleep, "
        "SpO2, breathing rate, skin temperature, cardio fitness, weight, food and water. Dates are yyyy-MM-dd "
        "in the user's local time zone; 'today' is accepted. To log food, call log_food with total calories "
        "and macros for the amount eaten (estimate if needed). If a tool returns a sign-in link, show the link "
        "to the user."
    ),
    host="0.0.0.0",
    port=config.PORT,
    streamable_http_path=f"/{config.MCP_PATH_SECRET or 'disabled'}/mcp",
    stateless_http=True,
    json_response=True,
)
