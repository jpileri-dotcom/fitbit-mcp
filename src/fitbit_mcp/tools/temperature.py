from __future__ import annotations

from fitbit_mcp.app import mcp, client


@mcp.tool()
async def get_core_temperature_by_date(date: str) -> dict:
    """Get core body temperature summary for a specific date.

    Args:
        date: The date to retrieve. Format: yyyy-MM-dd.
    """
    return await client.get(f"/1/user/-/temp/core/date/{date}.json")


@mcp.tool()
async def get_core_temperature_by_range(start_date: str, end_date: str) -> dict:
    """Get core body temperature summary for a date range.

    Args:
        start_date: The start date. Format: yyyy-MM-dd.
        end_date: The end date. Format: yyyy-MM-dd. Maximum range is 30 days.
    """
    return await client.get(
        f"/1/user/-/temp/core/date/{start_date}/{end_date}.json"
    )


@mcp.tool()
async def get_skin_temperature_by_date(date: str) -> dict:
    """Get skin temperature summary for a specific date.

    Returns the relative skin temperature variation from baseline.

    Args:
        date: The date to retrieve. Format: yyyy-MM-dd.
    """
    return await client.get(f"/1/user/-/temp/skin/date/{date}.json")


@mcp.tool()
async def get_skin_temperature_by_range(start_date: str, end_date: str) -> dict:
    """Get skin temperature summary for a date range.

    Args:
        start_date: The start date. Format: yyyy-MM-dd.
        end_date: The end date. Format: yyyy-MM-dd. Maximum range is 30 days.
    """
    return await client.get(
        f"/1/user/-/temp/skin/date/{start_date}/{end_date}.json"
    )
