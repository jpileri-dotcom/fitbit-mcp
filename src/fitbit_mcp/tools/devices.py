from __future__ import annotations

from fitbit_mcp.app import mcp, client


@mcp.tool()
async def get_devices() -> dict:
    """Get a list of Fitbit devices paired to the user's account.

    Returns device information including device type, firmware version,
    battery level, and last sync time.
    """
    return await client.get("/1/user/-/devices.json")
