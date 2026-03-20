from __future__ import annotations

from fitbit_mcp.app import mcp, client


@mcp.tool()
async def get_heart_rate_by_period(date: str, period: str) -> dict:
    """Get heart rate time series data for a date and period.

    Returns resting heart rate and heart rate zones (Out of Range, Fat Burn,
    Cardio, Peak) with minutes and calories for each zone.

    Args:
        date: The end date. Format: yyyy-MM-dd. Use 'today' for current date.
        period: The time period. Valid values: '1d', '7d', '30d', '1w', '1m'.
    """
    return await client.get(
        f"/1/user/-/activities/heart/date/{date}/{period}.json"
    )


@mcp.tool()
async def get_heart_rate_by_range(start_date: str, end_date: str) -> dict:
    """Get heart rate time series data for a date range.

    Returns resting heart rate and heart rate zones for each day in the range.

    Args:
        start_date: The start date. Format: yyyy-MM-dd.
        end_date: The end date. Format: yyyy-MM-dd.
    """
    return await client.get(
        f"/1/user/-/activities/heart/date/{start_date}/{end_date}.json"
    )
