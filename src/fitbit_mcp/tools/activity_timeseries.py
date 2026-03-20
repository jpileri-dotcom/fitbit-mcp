from __future__ import annotations

from fitbit_mcp.app import mcp, client


@mcp.tool()
async def get_activity_timeseries_by_period(
    resource: str, date: str, period: str
) -> dict:
    """Get activity time series data for a resource over a period.

    Args:
        resource: The activity resource. Valid values: 'calories', 'caloriesBMR',
            'steps', 'distance', 'floors', 'elevation', 'minutesSedentary',
            'minutesLightlyActive', 'minutesFairlyActive', 'minutesVeryActive',
            'activityCalories'.
        date: The end date. Format: yyyy-MM-dd. Use 'today' for current date.
        period: The time period. Valid values: '1d', '7d', '30d', '1w', '1m',
            '3m', '6m', '1y'.
    """
    return await client.get(
        f"/1/user/-/activities/{resource}/date/{date}/{period}.json"
    )


@mcp.tool()
async def get_activity_timeseries_by_range(
    resource: str, start_date: str, end_date: str
) -> dict:
    """Get activity time series data for a resource over a date range.

    Args:
        resource: The activity resource. Valid values: 'calories', 'caloriesBMR',
            'steps', 'distance', 'floors', 'elevation', 'minutesSedentary',
            'minutesLightlyActive', 'minutesFairlyActive', 'minutesVeryActive',
            'activityCalories'.
        start_date: The start date. Format: yyyy-MM-dd.
        end_date: The end date. Format: yyyy-MM-dd.
    """
    return await client.get(
        f"/1/user/-/activities/{resource}/date/{start_date}/{end_date}.json"
    )
