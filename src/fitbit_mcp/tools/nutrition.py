from __future__ import annotations

from fitbit_mcp.app import mcp, client


@mcp.tool()
async def get_food_log(date: str) -> dict:
    """Get food log entries for a specific date.

    Returns a summary of foods consumed, including calories, macronutrients,
    and individual food entries.

    Args:
        date: The date to retrieve. Format: yyyy-MM-dd.
    """
    return await client.get(f"/1/user/-/foods/log/date/{date}.json")


@mcp.tool()
async def get_water_log(date: str) -> dict:
    """Get water consumption log for a specific date.

    Returns water entries and total consumption in milliliters.

    Args:
        date: The date to retrieve. Format: yyyy-MM-dd.
    """
    return await client.get(f"/1/user/-/foods/log/water/date/{date}.json")


@mcp.tool()
async def get_food_goals() -> dict:
    """Get the user's daily calorie consumption and food plan goals."""
    return await client.get("/1/user/-/foods/log/goal.json")


@mcp.tool()
async def get_water_goal() -> dict:
    """Get the user's daily water consumption goal."""
    return await client.get("/1/user/-/foods/log/water/goal.json")


@mcp.tool()
async def get_favorite_foods() -> dict:
    """Get the user's favorite foods list."""
    return await client.get("/1/user/-/foods/log/favorite.json")


@mcp.tool()
async def get_frequent_foods() -> dict:
    """Get foods the user logs most frequently."""
    return await client.get("/1/user/-/foods/log/frequent.json")


@mcp.tool()
async def get_recent_foods() -> dict:
    """Get foods the user has logged recently."""
    return await client.get("/1/user/-/foods/log/recent.json")


@mcp.tool()
async def get_meals() -> dict:
    """Get all user-created meals.

    Returns a list of saved meals with their food components.
    """
    return await client.get("/1/user/-/meals.json")


@mcp.tool()
async def search_foods(query: str) -> dict:
    """Search the Fitbit food database.

    Searches both public foods and user's private/custom foods.

    Args:
        query: The search term for finding foods.
    """
    return await client.get("/1/foods/search.json", params={"query": query})
