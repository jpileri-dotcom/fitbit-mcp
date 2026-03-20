from __future__ import annotations

from fitbit_mcp.app import mcp, client


@mcp.tool()
async def get_azm_by_period(date: str, period: str) -> dict:
    """Get Active Zone Minutes (AZM) time series for a date and period.

    Returns daily active zone minutes including fat burn, cardio, and peak
    minutes for the specified period.

    Args:
        date: The end date. Format: yyyy-MM-dd. Use 'today' for current date.
        period: The time period. Valid values: '1d', '7d', '30d', '1w', '1m'.
    """
    return await client.get(
        f"/1/user/-/activities/active-zone-minutes/date/{date}/{period}.json"
    )


@mcp.tool()
async def get_azm_by_range(start_date: str, end_date: str) -> dict:
    """Get Active Zone Minutes (AZM) time series for a date range.

    Args:
        start_date: The start date. Format: yyyy-MM-dd.
        end_date: The end date. Format: yyyy-MM-dd.
    """
    return await client.get(
        f"/1/user/-/activities/active-zone-minutes/date/{start_date}/{end_date}.json"
    )
