from __future__ import annotations

from fitbit_mcp.app import mcp, client


@mcp.tool()
async def get_body_fat_log(date: str) -> dict:
    """Get body fat log entries for a specific date.

    Args:
        date: The date to retrieve. Format: yyyy-MM-dd.
    """
    return await client.get(f"/1/user/-/body/log/fat/date/{date}.json")


@mcp.tool()
async def get_weight_log(date: str) -> dict:
    """Get weight log entries for a specific date.

    Args:
        date: The date to retrieve. Format: yyyy-MM-dd.
    """
    return await client.get(f"/1/user/-/body/log/weight/date/{date}.json")


@mcp.tool()
async def get_body_timeseries_by_period(
    resource: str, date: str, period: str
) -> dict:
    """Get body measurement time series for a resource over a period.

    Args:
        resource: The body resource. Valid values: 'bmi', 'fat', 'weight'.
        date: The end date. Format: yyyy-MM-dd.
        period: The time period. Valid values: '1d', '7d', '30d', '1w', '1m',
            '3m', '6m', '1y'.
    """
    return await client.get(
        f"/1/user/-/body/{resource}/date/{date}/{period}.json"
    )


@mcp.tool()
async def get_body_timeseries_by_range(
    resource: str, start_date: str, end_date: str
) -> dict:
    """Get body measurement time series for a resource over a date range.

    Args:
        resource: The body resource. Valid values: 'bmi', 'fat', 'weight'.
        start_date: The start date. Format: yyyy-MM-dd.
        end_date: The end date. Format: yyyy-MM-dd.
    """
    return await client.get(
        f"/1/user/-/body/{resource}/date/{start_date}/{end_date}.json"
    )


@mcp.tool()
async def get_body_goals() -> dict:
    """Get the user's body weight and body fat goals."""
    return await client.get("/1/user/-/body/log/fat/goal.json")
