from __future__ import annotations

from fitbit_mcp.app import mcp, client


@mcp.tool()
async def get_hrv_by_date(date: str) -> dict:
    """Get heart rate variability (HRV) summary for a specific date.

    Returns daily and sleep RMSSD (root mean square of successive differences)
    values, HRV coverage, and low/high range values.

    Args:
        date: The date to retrieve. Format: yyyy-MM-dd.
    """
    return await client.get(f"/1/user/-/hrv/date/{date}.json")


@mcp.tool()
async def get_hrv_by_range(start_date: str, end_date: str) -> dict:
    """Get heart rate variability (HRV) summary for a date range.

    Args:
        start_date: The start date. Format: yyyy-MM-dd.
        end_date: The end date. Format: yyyy-MM-dd. Maximum range is 30 days.
    """
    return await client.get(
        f"/1/user/-/hrv/date/{start_date}/{end_date}.json"
    )
