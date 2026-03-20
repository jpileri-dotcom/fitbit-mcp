from __future__ import annotations

from fitbit_mcp.app import mcp, client


@mcp.tool()
async def get_sleep_by_date(date: str) -> dict:
    """Get sleep log entries for a specific date.

    Args:
        date: The date to retrieve sleep data for. Format: yyyy-MM-dd.
    """
    return await client.get(f"/1.2/user/-/sleep/date/{date}.json")


@mcp.tool()
async def get_sleep_by_date_range(start_date: str, end_date: str) -> dict:
    """Get sleep log entries for a date range.

    Args:
        start_date: The start date. Format: yyyy-MM-dd.
        end_date: The end date. Format: yyyy-MM-dd. Maximum range is 100 days.
    """
    return await client.get(
        f"/1.2/user/-/sleep/date/{start_date}/{end_date}.json"
    )


@mcp.tool()
async def get_sleep_log_list(
    before_date: str | None = None,
    after_date: str | None = None,
    sort: str = "desc",
    offset: int = 0,
    limit: int = 20,
) -> dict:
    """Get a paginated list of the user's sleep log entries.

    Args:
        before_date: Return entries before this date. Format: yyyy-MM-dd.
        after_date: Return entries after this date. Format: yyyy-MM-dd.
        sort: Sort order. 'asc' with after_date, 'desc' with before_date.
        offset: Pagination offset. Only 0 is supported.
        limit: Number of entries to return. Maximum 100.
    """
    params: dict = {"sort": sort, "offset": offset, "limit": limit}
    if before_date:
        params["beforeDate"] = before_date
    if after_date:
        params["afterDate"] = after_date
    return await client.get("/1.2/user/-/sleep/list.json", params=params)


@mcp.tool()
async def get_sleep_goal() -> dict:
    """Get the user's sleep goal.

    Returns the target sleep duration in minutes.
    """
    return await client.get("/1.2/user/-/sleep/goal.json")
