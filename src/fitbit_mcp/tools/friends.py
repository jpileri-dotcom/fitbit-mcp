from __future__ import annotations

from fitbit_mcp.app import mcp, client


@mcp.tool()
async def get_friends() -> dict:
    """Get the user's friends list.

    Returns a list of the user's Fitbit friends with their display names
    and profile information.
    """
    return await client.get("/1.1/user/-/friends.json")


@mcp.tool()
async def get_leaderboard() -> dict:
    """Get the user's friends leaderboard.

    Returns a ranked list of friends by step count for the current week.
    """
    return await client.get("/1.1/user/-/leaderboard.json")
