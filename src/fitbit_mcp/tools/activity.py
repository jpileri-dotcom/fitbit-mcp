from __future__ import annotations

from fitbit_mcp.app import mcp, client


@mcp.tool()
async def get_activity_log_list(
    before_date: str | None = None,
    after_date: str | None = None,
    sort: str = "desc",
    offset: int = 0,
    limit: int = 20,
) -> dict:
    """Get a paginated list of the user's activity log entries.

    Args:
        before_date: Return entries before this date. Format: yyyy-MM-dd or yyyy-MM-ddTHH:mm:ss.
        after_date: Return entries after this date. Format: yyyy-MM-dd or yyyy-MM-ddTHH:mm:ss.
        sort: Sort order. 'asc' with after_date, 'desc' with before_date.
        offset: Pagination offset. Only 0 is supported.
        limit: Number of entries to return. Maximum 100.
    """
    params: dict = {"sort": sort, "offset": offset, "limit": limit}
    if before_date:
        params["beforeDate"] = before_date
    if after_date:
        params["afterDate"] = after_date
    return await client.get("/1/user/-/activities/list.json", params=params)


@mcp.tool()
async def get_daily_activity_summary(date: str) -> dict:
    """Get a summary of the user's activities for a specific date.

    Args:
        date: The date to retrieve. Format: yyyy-MM-dd.
    """
    return await client.get(f"/1/user/-/activities/date/{date}.json")


@mcp.tool()
async def get_activity_goals(period: str = "daily") -> dict:
    """Get the user's activity goals.

    Args:
        period: Goal period. Valid values: 'daily', 'weekly'.
    """
    return await client.get(f"/1/user/-/activities/goals/{period}.json")


@mcp.tool()
async def get_favorite_activities() -> dict:
    """Get the user's favorite activities list."""
    return await client.get("/1/user/-/activities/favorite.json")


@mcp.tool()
async def get_frequent_activities() -> dict:
    """Get the activities the user records most frequently."""
    return await client.get("/1/user/-/activities/frequent.json")


@mcp.tool()
async def get_recent_activities() -> dict:
    """Get a summary of the activities the user recorded recently."""
    return await client.get("/1/user/-/activities/recent.json")


@mcp.tool()
async def get_lifetime_stats() -> dict:
    """Get the user's lifetime activity statistics.

    Returns total distance, floors, and steps for the user's lifetime,
    as well as best day records.
    """
    return await client.get("/1/user/-/activities.json")
