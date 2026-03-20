from __future__ import annotations

from fitbit_mcp.app import mcp, client


@mcp.tool()
async def get_spo2_by_date(date: str) -> dict:
    """Get blood oxygen saturation (SpO2) summary for a specific date.

    Returns average, minimum, and maximum SpO2 values recorded during sleep.

    Args:
        date: The date to retrieve. Format: yyyy-MM-dd.
    """
    return await client.get(f"/1/user/-/spo2/date/{date}.json")


@mcp.tool()
async def get_spo2_by_range(start_date: str, end_date: str) -> dict:
    """Get blood oxygen saturation (SpO2) summary for a date range.

    Args:
        start_date: The start date. Format: yyyy-MM-dd.
        end_date: The end date. Format: yyyy-MM-dd. Maximum range is 30 days.
    """
    return await client.get(
        f"/1/user/-/spo2/date/{start_date}/{end_date}.json"
    )
