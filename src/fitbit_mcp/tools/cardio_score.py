from __future__ import annotations

from fitbit_mcp.app import mcp, client


@mcp.tool()
async def get_cardio_score_by_date(date: str) -> dict:
    """Get cardio fitness score (VO2 Max) summary for a specific date.

    Returns the estimated VO2 Max value, which represents the maximum rate
    of oxygen consumption during exercise.

    Args:
        date: The date to retrieve. Format: yyyy-MM-dd.
    """
    return await client.get(f"/1/user/-/cardioscore/date/{date}.json")


@mcp.tool()
async def get_cardio_score_by_range(start_date: str, end_date: str) -> dict:
    """Get cardio fitness score (VO2 Max) summary for a date range.

    Args:
        start_date: The start date. Format: yyyy-MM-dd.
        end_date: The end date. Format: yyyy-MM-dd. Maximum range is 30 days.
    """
    return await client.get(
        f"/1/user/-/cardioscore/date/{start_date}/{end_date}.json"
    )
