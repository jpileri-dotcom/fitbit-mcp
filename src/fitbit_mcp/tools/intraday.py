from __future__ import annotations

from fitbit_mcp.app import mcp, client


@mcp.tool()
async def get_activity_intraday(
    resource: str, date: str, detail_level: str = "15min"
) -> dict:
    """Get intraday activity data for a specific date.

    Returns granular activity data at the specified time resolution.
    Requires a 'Personal' app type on dev.fitbit.com.

    Args:
        resource: The activity resource. Valid values: 'calories', 'steps',
            'distance', 'floors', 'elevation'.
        date: The date to retrieve. Format: yyyy-MM-dd.
        detail_level: Time series detail level. Valid values: '1min', '5min', '15min'.
    """
    return await client.get(
        f"/1/user/-/activities/{resource}/date/{date}/1d/{detail_level}.json"
    )


@mcp.tool()
async def get_heart_rate_intraday(
    date: str, detail_level: str = "1min"
) -> dict:
    """Get intraday heart rate data for a specific date.

    Returns heart rate measurements at the specified time resolution.
    Requires a 'Personal' app type on dev.fitbit.com.

    Args:
        date: The date to retrieve. Format: yyyy-MM-dd.
        detail_level: Time series detail level. Valid values: '1sec', '1min'.
    """
    return await client.get(
        f"/1/user/-/activities/heart/date/{date}/1d/{detail_level}.json"
    )


@mcp.tool()
async def get_breathing_rate_intraday(date: str) -> dict:
    """Get intraday breathing rate data for a specific date.

    Returns granular breathing rate measurements during sleep.
    Requires a 'Personal' app type on dev.fitbit.com.

    Args:
        date: The date to retrieve. Format: yyyy-MM-dd.
    """
    return await client.get(f"/1/user/-/br/date/{date}/all.json")


@mcp.tool()
async def get_hrv_intraday(date: str) -> dict:
    """Get intraday heart rate variability (HRV) data for a specific date.

    Returns granular RMSSD measurements during sleep periods.
    Requires a 'Personal' app type on dev.fitbit.com.

    Args:
        date: The date to retrieve. Format: yyyy-MM-dd.
    """
    return await client.get(f"/1/user/-/hrv/date/{date}/all.json")


@mcp.tool()
async def get_spo2_intraday(date: str) -> dict:
    """Get intraday blood oxygen saturation (SpO2) data for a specific date.

    Returns granular SpO2 measurements during sleep.
    Requires a 'Personal' app type on dev.fitbit.com.

    Args:
        date: The date to retrieve. Format: yyyy-MM-dd.
    """
    return await client.get(f"/1/user/-/spo2/date/{date}/all.json")


@mcp.tool()
async def get_azm_intraday(
    date: str, detail_level: str = "15min"
) -> dict:
    """Get intraday Active Zone Minutes data for a specific date.

    Returns granular active zone minutes data at the specified resolution.
    Requires a 'Personal' app type on dev.fitbit.com.

    Args:
        date: The date to retrieve. Format: yyyy-MM-dd.
        detail_level: Time series detail level. Valid values: '1min', '5min', '15min'.
    """
    return await client.get(
        f"/1/user/-/activities/active-zone-minutes/date/{date}/1d/{detail_level}.json"
    )
