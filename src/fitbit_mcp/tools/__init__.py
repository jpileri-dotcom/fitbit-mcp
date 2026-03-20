# Import all tool modules so their @app.tool() decorators register with the server.
from fitbit_mcp.tools import (  # noqa: F401
    activity,
    activity_timeseries,
    azm,
    body,
    breathing_rate,
    cardio_score,
    devices,
    friends,
    heart_rate,
    hrv,
    intraday,
    nutrition,
    sleep,
    spo2,
    temperature,
    user,
)
