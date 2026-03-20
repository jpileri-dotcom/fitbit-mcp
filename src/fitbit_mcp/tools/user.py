from __future__ import annotations

from fitbit_mcp.app import mcp, client


@mcp.tool()
async def get_profile() -> dict:
    """Get the authenticated user's Fitbit profile.

    Returns user information including display name, age, height, weight,
    timezone, and account settings.
    """
    return await client.get("/1/user/-/profile.json")


@mcp.tool()
async def get_badges() -> dict:
    """Get the user's earned badges.

    Returns a list of badges the user has achieved, including badge type,
    date earned, and description.
    """
    return await client.get("/1/user/-/badges.json")
