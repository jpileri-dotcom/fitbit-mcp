"""MCP tools. Names follow the old Fitbit connector where the Google Health API supports them.

Data types: https://developers.google.com/health/data-types
Nutrition:  https://developers.google.com/health/data-types/nutrition
Filters:    https://developers.google.com/health/filters
"""
from __future__ import annotations

import functools
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from fitbit_mcp import auth, config
from fitbit_mcp import google as g
from fitbit_mcp.app import mcp

logger = logging.getLogger("fitbit_mcp.tools")


def login_message() -> str:
    return ("Google Health is not connected or the login expired. Open this link on your phone, "
            f"sign in with Google and allow access, then ask again: {config.auth_start_url()}")


def tool(fn):
    """Register a tool and turn errors into short readable messages."""

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except auth.AuthRequired:
            return {"error": login_message()}
        except g.ApiError as e:
            return {"error": str(e)}
        except ValueError as e:
            return {"error": f"Invalid input: {e}"}
        except Exception as e:  # noqa: BLE001
            logger.exception("Tool %s failed", fn.__name__)
            return {"error": f"Unexpected error: {e}"}

    return mcp.tool()(wrapper)


async def _range(start_date: str | None, end_date: str | None, default_days: int = 7) -> tuple[date, date]:
    end = await g.resolve_date(end_date)
    start = await g.resolve_date(start_date) if start_date else end - timedelta(days=default_days - 1)
    if end < start:
        raise ValueError("end_date is before start_date")
    return start, end


def _next(d: date) -> str:
    return (d + timedelta(days=1)).isoformat()


def _rdate(p: dict) -> str | None:
    return g.civil_date_str(p.get("civilStartTime"))


def _mins(duration: str | None) -> float | None:
    if duration is None:
        return None
    return round(g._dur_seconds(duration) / 60, 1)


def _r(v: Any, n: int = 2) -> float | None:
    x = g.num(v)
    return None if x is None else round(x, n)


async def _daily(data_type: str, start: date, end: date) -> list[dict]:
    return await g.daily_rollup(data_type, start, end)


# =========================================================================== profile / devices

@tool
async def get_profile() -> dict:
    """Get the user's Google Health profile (age, stride length, member since) and unit/time-zone settings."""
    profile = await g.request("GET", "/users/me/profile")
    settings = await g.user_settings()
    out: dict[str, Any] = {
        "age": profile.get("age"),
        "member_since": g.civil_date_str(profile.get("membershipStartDate")),
        "walking_stride_mm": profile.get("userConfiguredWalkingStrideLengthMm") or profile.get("autoWalkingStrideLengthMm"),
        "running_stride_mm": profile.get("userConfiguredRunningStrideLengthMm") or profile.get("autoRunningStrideLengthMm"),
        "settings": {k: v for k, v in settings.items() if k != "name"},
    }
    try:
        ident = await g.request("GET", "/users/me/identity")
        out["health_user_id"] = ident.get("healthUserId")
        out["legacy_fitbit_user_id"] = ident.get("legacyUserId")
    except g.ApiError:
        pass
    return out


@tool
async def get_devices() -> dict:
    """List paired Fitbit/Pixel devices with battery level and last sync time."""
    devices: list[dict] = []
    token = None
    while True:
        params: dict[str, Any] = {"pageSize": 100}
        if token:
            params["pageToken"] = token
        body = await g.request("GET", "/users/me/pairedDevices", params=params)
        for d in body.get("pairedDevices", []) or []:
            devices.append({
                "device": d.get("deviceVersion"),
                "type": d.get("deviceType"),
                "battery_status": d.get("batteryStatus"),
                "battery_level": d.get("batteryLevel"),
                "last_sync_time": d.get("lastSyncTime"),
            })
        token = body.get("nextPageToken")
        if not token:
            break
    return {"devices": devices}


# =========================================================================== activity

# resource -> (data type, function extracting the daily value from a rollup point)
ACTIVITY_RESOURCES: dict[str, tuple[str, Any]] = {
    "steps": ("steps", lambda p: g.num((p.get("steps") or {}).get("countSum"))),
    "distance_km": ("distance", lambda p: _r((g.num((p.get("distance") or {}).get("millimetersSum")) or 0) / 1e6, 3)),
    "floors": ("floors", lambda p: g.num((p.get("floors") or {}).get("countSum"))),
    "elevation_m": ("altitude", lambda p: _r((g.num((p.get("altitude") or {}).get("gainMillimetersSum")) or 0) / 1000, 1)),
    "calories": ("total-calories", lambda p: _r((p.get("totalCalories") or {}).get("kcalSum"), 0)),
    "activity_calories": ("active-energy-burned", lambda p: _r((p.get("activeEnergyBurned") or {}).get("kcalSum"), 0)),
    "minutes_sedentary": ("sedentary-period", lambda p: _mins((p.get("sedentaryPeriod") or {}).get("durationSum"))),
    "active_minutes": ("active-minutes", lambda p: {
        x.get("activityLevel", "?").lower(): g.num(x.get("activeMinutesSum"))
        for x in (p.get("activeMinutes") or {}).get("activeMinutesRollupByActivityLevel", []) or []
    }),
    "active_zone_minutes": ("active-zone-minutes", lambda p: _azm(p)),
}


def _azm(p: dict) -> dict:
    a = p.get("activeZoneMinutes") or {}
    fb, ca, pk = (g.num(a.get(k)) or 0 for k in ("sumInFatBurnHeartZone", "sumInCardioHeartZone", "sumInPeakHeartZone"))
    return {"fat_burn": fb, "cardio": ca, "peak": pk, "total": fb + ca + pk}


ActivityResource = Literal["steps", "distance_km", "floors", "elevation_m", "calories", "activity_calories",
                           "minutes_sedentary", "active_minutes", "active_zone_minutes"]


@tool
async def get_daily_activity_summary(date: str = "today") -> dict:
    """Get one day's activity totals: steps, distance, floors, calories burned, active calories,
    active minutes by intensity, Active Zone Minutes, sedentary minutes, heart rate and resting heart rate.

    Args:
        date: yyyy-MM-dd or "today" (user's local time zone).
    """
    d = await g.resolve_date(date)
    out: dict[str, Any] = {"date": d.isoformat()}
    for name, (dtype, extract) in ACTIVITY_RESOURCES.items():
        try:
            pts = await _daily(dtype, d, d)
            out[name] = extract(pts[0]) if pts else None
        except g.ApiError as e:
            out[name] = f"unavailable ({e.status})"
    try:
        hr = await _daily("heart-rate", d, d)
        if hr:
            h = hr[0].get("heartRate") or {}
            out["heart_rate"] = {"avg": _r(h.get("beatsPerMinuteAvg"), 0), "min": h.get("beatsPerMinuteMin"), "max": h.get("beatsPerMinuteMax")}
    except g.ApiError:
        pass
    rhr = await _resting_hr(d, d)
    out["resting_heart_rate"] = rhr[0]["bpm"] if rhr else None
    return out


@tool
async def get_activity_timeseries_by_range(resource: ActivityResource, start_date: str, end_date: str = "today") -> dict:
    """Get one value per day for an activity metric over a date range. Long ranges are split automatically.

    Args:
        resource: steps, distance_km, floors, elevation_m, calories (total burned), activity_calories,
            minutes_sedentary, active_minutes (light/moderate/vigorous), active_zone_minutes.
        start_date: yyyy-MM-dd.
        end_date: yyyy-MM-dd or "today".
    """
    if resource not in ACTIVITY_RESOURCES:
        raise ValueError(f"resource must be one of {list(ACTIVITY_RESOURCES)}")
    start, end = await _range(start_date, end_date)
    dtype, extract = ACTIVITY_RESOURCES[resource]
    pts = await _daily(dtype, start, end)
    return {"resource": resource, "data": [{"date": _rdate(p), "value": extract(p)} for p in pts]}


INTRADAY: dict[str, tuple[str, Any]] = {
    "steps": ACTIVITY_RESOURCES["steps"],
    "distance_km": ACTIVITY_RESOURCES["distance_km"],
    "floors": ACTIVITY_RESOURCES["floors"],
    "elevation_m": ACTIVITY_RESOURCES["elevation_m"],
    "calories": ACTIVITY_RESOURCES["calories"],
    "activity_calories": ACTIVITY_RESOURCES["activity_calories"],
    "active_zone_minutes": ACTIVITY_RESOURCES["active_zone_minutes"],
}
DETAIL = {"1min": 60, "5min": 300, "15min": 900, "30min": 1800, "1h": 3600}


async def _day_window(d: date, start_time: str | None, end_time: str | None) -> tuple[datetime, datetime, Any]:
    tz = await g.user_tz()
    def at(hhmm: str | None, default: datetime) -> datetime:
        if not hhmm:
            return default
        h, m = (int(x) for x in hhmm.split(":")[:2])
        return datetime(d.year, d.month, d.day, h, m, tzinfo=tz)
    day0 = datetime(d.year, d.month, d.day, tzinfo=tz)
    day1 = datetime.combine(d + timedelta(days=1), datetime.min.time(), tzinfo=tz)
    a, b = at(start_time, day0), at(end_time, day1)
    now = datetime.now(tz)
    if b > now:
        b = now
    if b <= a:
        raise ValueError("time window is empty or in the future")
    return a, b, tz


def _local_hhmm(ts: str | None, tz) -> str | None:
    if not ts:
        return None
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt.astimezone(tz).strftime("%H:%M")


@tool
async def get_activity_intraday(resource: Literal["steps", "distance_km", "floors", "elevation_m", "calories",
                                                  "activity_calories", "active_zone_minutes"],
                                date: str = "today", detail_level: Literal["1min", "5min", "15min", "30min", "1h"] = "15min",
                                start_time: str | None = None, end_time: str | None = None) -> dict:
    """Get intraday activity for one day in time buckets. Empty buckets are left out.

    Args:
        resource: steps, distance_km, floors, elevation_m, calories, activity_calories, active_zone_minutes.
        date: yyyy-MM-dd or "today".
        detail_level: bucket size: 1min, 5min, 15min, 30min or 1h.
        start_time: optional HH:mm local time.
        end_time: optional HH:mm local time.
    """
    if resource not in INTRADAY:
        raise ValueError(f"resource must be one of {list(INTRADAY)}")
    d = await g.resolve_date(date)
    a, b, tz = await _day_window(d, start_time, end_time)
    dtype, extract = INTRADAY[resource]
    pts = await g.rollup(dtype, a, b, DETAIL[detail_level])
    data = []
    for p in pts:
        v = extract(p)
        if v in (None, 0, 0.0) or (isinstance(v, dict) and not v.get("total")):
            continue
        data.append({"time": _local_hhmm(p.get("startTime"), tz), "value": v})
    data.sort(key=lambda x: x["time"] or "")
    return {"resource": resource, "date": d.isoformat(), "detail_level": detail_level, "data": data}


@tool
async def get_azm_by_range(start_date: str, end_date: str = "today") -> dict:
    """Get daily Active Zone Minutes (fat burn, cardio, peak, total) for a date range.

    Args:
        start_date: yyyy-MM-dd.
        end_date: yyyy-MM-dd or "today".
    """
    start, end = await _range(start_date, end_date)
    pts = await _daily("active-zone-minutes", start, end)
    return {"data": [{"date": _rdate(p), **_azm(p)} for p in pts]}


@tool
async def get_activity_log_list(after_date: str | None = None, before_date: str | None = None, limit: int = 20) -> dict:
    """List logged or auto-detected exercises (walks, runs, workouts), newest first.

    Args:
        after_date: yyyy-MM-dd, include exercises starting on or after this date. Default: 30 days ago.
        before_date: yyyy-MM-dd, include exercises starting before this date. Default: none.
        limit: maximum number of exercises (1-100).
    """
    limit = max(1, min(int(limit), 100))
    after = await g.resolve_date(after_date) if after_date else (await g.today()) - timedelta(days=30)
    f = f'exercise.interval.civil_start_time >= "{after.isoformat()}"'
    if before_date:
        f += f' AND exercise.interval.civil_start_time < "{date.fromisoformat(before_date).isoformat()}"'
    pts = await g.list_points("exercise", f, max_points=limit)
    out = []
    for p in pts:
        e = p.get("exercise") or {}
        iv = e.get("interval") or {}
        m = e.get("metricsSummary") or {}
        dist = g.num(m.get("distanceMillimeters"))
        out.append({
            "id": (p.get("name") or "").split("/")[-1] or None,
            "name": e.get("displayName"),
            "type": e.get("exerciseType"),
            "start": g.interval_local(iv, "start"),
            "end": g.interval_local(iv, "end"),
            "active_minutes": _mins(e.get("activeDuration")),
            "calories": _r(m.get("caloriesKcal"), 0),
            "steps": g.num(m.get("steps")),
            "distance_km": _r(dist / 1e6, 2) if dist else None,
            "avg_heart_rate": g.num(m.get("averageHeartRateBeatsPerMinute")),
            "active_zone_minutes": g.num(m.get("activeZoneMinutes")),
            "notes": e.get("notes"),
        })
    return {"exercises": out}


# =========================================================================== heart

async def _resting_hr(start: date, end: date) -> list[dict]:
    f = f'daily_resting_heart_rate.date >= "{start.isoformat()}" AND daily_resting_heart_rate.date < "{_next(end)}"'

    def keep(p):
        ds = g.civil_date_str((p.get("dailyRestingHeartRate") or {}).get("date"))
        return ds is not None and start.isoformat() <= ds <= end.isoformat()

    try:
        pts = await g.list_points("daily-resting-heart-rate", f, fallback=keep)
    except g.ApiError:
        return []
    out = [{"date": g.civil_date_str(p["dailyRestingHeartRate"].get("date")),
            "bpm": g.num(p["dailyRestingHeartRate"].get("beatsPerMinute"))} for p in pts if p.get("dailyRestingHeartRate")]
    return sorted(out, key=lambda x: x["date"] or "")


@tool
async def get_heart_rate_by_range(start_date: str, end_date: str = "today") -> dict:
    """Get daily heart rate (average/min/max), resting heart rate, and time in heart rate zones for a date range.
    Requests are split into 14-day pieces automatically.

    Args:
        start_date: yyyy-MM-dd.
        end_date: yyyy-MM-dd or "today".
    """
    start, end = await _range(start_date, end_date)
    days: dict[str, dict] = {}
    for p in await _daily("heart-rate", start, end):
        h = p.get("heartRate") or {}
        days.setdefault(_rdate(p), {}).update(avg_bpm=_r(h.get("beatsPerMinuteAvg"), 0),
                                              min_bpm=h.get("beatsPerMinuteMin"), max_bpm=h.get("beatsPerMinuteMax"))
    try:
        for p in await _daily("time-in-heart-rate-zone", start, end):
            zones = (p.get("timeInHeartRateZone") or {}).get("timeInHeartRateZones", []) or []
            days.setdefault(_rdate(p), {})["minutes_in_zone"] = {z.get("heartRateZone", "?").lower(): _mins(z.get("duration")) for z in zones}
    except g.ApiError:
        pass
    for r in await _resting_hr(start, end):
        days.setdefault(r["date"], {})["resting_bpm"] = r["bpm"]
    return {"data": [{"date": k, **v} for k, v in sorted(days.items(), key=lambda kv: kv[0] or "")]}


@tool
async def get_heart_rate_intraday(date: str = "today", detail_level: Literal["1min", "5min", "15min", "30min", "1h"] = "5min",
                                  start_time: str | None = None, end_time: str | None = None) -> dict:
    """Get heart rate through one day in time buckets (average, min, max bpm per bucket).

    Args:
        date: yyyy-MM-dd or "today".
        detail_level: 1min, 5min, 15min, 30min or 1h.
        start_time: optional HH:mm local time.
        end_time: optional HH:mm local time.
    """
    d = await g.resolve_date(date)
    a, b, tz = await _day_window(d, start_time, end_time)
    pts = await g.rollup("heart-rate", a, b, DETAIL[detail_level])
    data = []
    for p in pts:
        h = p.get("heartRate") or {}
        if h.get("beatsPerMinuteAvg") is None:
            continue
        data.append({"time": _local_hhmm(p.get("startTime"), tz), "avg": _r(h.get("beatsPerMinuteAvg"), 0),
                     "min": h.get("beatsPerMinuteMin"), "max": h.get("beatsPerMinuteMax")})
    data.sort(key=lambda x: x["time"] or "")
    return {"date": d.isoformat(), "detail_level": detail_level, "data": data}


async def _daily_list(data_type: str, field: str, start: date, end: date) -> list[dict]:
    snake = data_type.replace("-", "_")
    f = f'{snake}.date >= "{start.isoformat()}" AND {snake}.date < "{_next(end)}"'

    def keep(p):
        ds = g.civil_date_str((p.get(field) or {}).get("date"))
        return ds is not None and start.isoformat() <= ds <= end.isoformat()

    pts = await g.list_points(data_type, f, fallback=keep)
    rows = [p[field] for p in pts if p.get(field)]
    return sorted(rows, key=lambda r: g.civil_date_str(r.get("date")) or "")


def _hrv_row(r: dict) -> dict:
    return {"date": g.civil_date_str(r.get("date")),
            "daily_rmssd_ms": _r(r.get("averageHeartRateVariabilityMilliseconds"), 1),
            "deep_sleep_rmssd_ms": _r(r.get("deepSleepRootMeanSquareOfSuccessiveDifferencesMilliseconds"), 1),
            "non_rem_heart_rate": g.num(r.get("nonRemHeartRateBeatsPerMinute")),
            "entropy": _r(r.get("entropy"), 3)}


@tool
async def get_hrv_by_date(date: str = "today") -> dict:
    """Get heart rate variability (RMSSD) for one night/day.

    Args:
        date: yyyy-MM-dd or "today".
    """
    d = await g.resolve_date(date)
    rows = await _daily_list("daily-heart-rate-variability", "dailyHeartRateVariability", d, d)
    return {"data": [_hrv_row(r) for r in rows]}


@tool
async def get_hrv_by_range(start_date: str, end_date: str = "today") -> dict:
    """Get daily heart rate variability (RMSSD) for a date range.

    Args:
        start_date: yyyy-MM-dd.
        end_date: yyyy-MM-dd or "today".
    """
    start, end = await _range(start_date, end_date)
    rows = await _daily_list("daily-heart-rate-variability", "dailyHeartRateVariability", start, end)
    return {"data": [_hrv_row(r) for r in rows]}


# =========================================================================== sleep

def _sleep_row(p: dict, include_stages: bool) -> dict:
    s = p.get("sleep") or {}
    iv = s.get("interval") or {}
    sm = s.get("summary") or {}
    md = s.get("metadata") or {}
    row = {
        "date_of_sleep": g.interval_local_date(iv, "end"),
        "start": g.interval_local(iv, "start"),
        "end": g.interval_local(iv, "end"),
        "main_sleep": md.get("mainSleep"),
        "nap": md.get("nap"),
        "type": s.get("type"),
        "minutes_asleep": g.num(sm.get("minutesAsleep")),
        "minutes_awake": g.num(sm.get("minutesAwake")),
        "minutes_in_bed": g.num(sm.get("minutesInSleepPeriod")),
        "minutes_to_fall_asleep": g.num(sm.get("minutesToFallAsleep")),
        "stages_minutes": {},
    }
    for st in sm.get("stagesSummary", []) or []:
        row["stages_minutes"][(st.get("type") or "?").lower()] = g.num(st.get("minutes"))
    if not row["stages_minutes"]:
        row.pop("stages_minutes")
    if include_stages:
        row["stages"] = [{"type": x.get("type"), "start": x.get("startTime"), "end": x.get("endTime")} for x in s.get("stages", []) or []]
    return row


async def _sleep(start: date, end: date, include_stages: bool) -> list[dict]:
    f = f'sleep.interval.civil_end_time >= "{start.isoformat()}" AND sleep.interval.civil_end_time < "{_next(end)}"'

    def keep(p):
        ds = g.interval_local_date((p.get("sleep") or {}).get("interval"), "end")
        return ds is not None and start.isoformat() <= ds <= end.isoformat()

    pts = await g.list_points("sleep", f, max_points=500, fallback=keep)
    rows = [_sleep_row(p, include_stages) for p in pts]
    return sorted(rows, key=lambda r: r["end"] or "")


@tool
async def get_sleep_by_date(date: str = "today", include_stages: bool = False) -> dict:
    """Get sleep sessions that ended on a date (last night's sleep for "today"): time asleep, awake,
    and minutes in light/deep/REM stages.

    Args:
        date: yyyy-MM-dd or "today".
        include_stages: also return each stage segment (long output).
    """
    d = await g.resolve_date(date)
    return {"sleep": await _sleep(d, d, include_stages)}


@tool
async def get_sleep_by_date_range(start_date: str, end_date: str = "today") -> dict:
    """Get sleep sessions for a date range (by wake-up date), with stage minutes.

    Args:
        start_date: yyyy-MM-dd.
        end_date: yyyy-MM-dd or "today".
    """
    start, end = await _range(start_date, end_date)
    return {"sleep": await _sleep(start, end, False)}


# =========================================================================== vitals

@tool
async def get_spo2_by_range(start_date: str, end_date: str = "today") -> dict:
    """Get nightly blood oxygen (SpO2) average, lower and upper bounds for a date range.

    Args:
        start_date: yyyy-MM-dd.
        end_date: yyyy-MM-dd or "today".
    """
    start, end = await _range(start_date, end_date)
    rows = await _daily_list("daily-oxygen-saturation", "dailyOxygenSaturation", start, end)
    return {"data": [{"date": g.civil_date_str(r.get("date")), "avg_pct": _r(r.get("averagePercentage"), 1),
                      "min_pct": _r(r.get("lowerBoundPercentage"), 1), "max_pct": _r(r.get("upperBoundPercentage"), 1)} for r in rows]}


@tool
async def get_breathing_rate_by_range(start_date: str, end_date: str = "today") -> dict:
    """Get nightly breathing rate (breaths per minute during main sleep) for a date range.

    Args:
        start_date: yyyy-MM-dd.
        end_date: yyyy-MM-dd or "today".
    """
    start, end = await _range(start_date, end_date)
    rows = await _daily_list("daily-respiratory-rate", "dailyRespiratoryRate", start, end)
    return {"data": [{"date": g.civil_date_str(r.get("date")), "breaths_per_minute": _r(r.get("breathsPerMinute"), 1)} for r in rows]}


@tool
async def get_skin_temperature_by_range(start_date: str, end_date: str = "today") -> dict:
    """Get nightly skin temperature and its difference from the user's 30-day baseline (Celsius).

    Args:
        start_date: yyyy-MM-dd.
        end_date: yyyy-MM-dd or "today".
    """
    start, end = await _range(start_date, end_date)
    rows = await _daily_list("daily-sleep-temperature-derivations", "dailySleepTemperatureDerivations", start, end)
    out = []
    for r in rows:
        n, b = g.num(r.get("nightlyTemperatureCelsius")), g.num(r.get("baselineTemperatureCelsius"))
        out.append({"date": g.civil_date_str(r.get("date")), "nightly_c": _r(n), "baseline_c": _r(b),
                    "relative_c": _r(n - b) if n is not None and b is not None else None})
    return {"data": out}


@tool
async def get_cardio_score_by_range(start_date: str, end_date: str = "today") -> dict:
    """Get daily cardio fitness score (VO2 max, ml/kg/min) and fitness level for a date range.

    Args:
        start_date: yyyy-MM-dd.
        end_date: yyyy-MM-dd or "today".
    """
    start, end = await _range(start_date, end_date)
    rows = await _daily_list("daily-vo2-max", "dailyVo2Max", start, end)
    return {"data": [{"date": g.civil_date_str(r.get("date")), "vo2_max": _r(r.get("vo2Max"), 1),
                      "level": r.get("cardioFitnessLevel"), "estimated": r.get("estimated")} for r in rows]}


# =========================================================================== body

def _sample_local(st: dict | None) -> str | None:
    return g.civil_dt_str((st or {}).get("civilTime"))


@tool
async def get_weight_log(start_date: str | None = None, end_date: str = "today") -> dict:
    """Get individual weight and body fat entries for a date range (default: last 30 days).

    Args:
        start_date: yyyy-MM-dd. Default 30 days before end_date.
        end_date: yyyy-MM-dd or "today".
    """
    start, end = await _range(start_date, end_date, default_days=30)
    f = f'weight.sample_time.civil_time >= "{start.isoformat()}" AND weight.sample_time.civil_time < "{_next(end)}"'
    pts = await g.list_points("weight", f)
    weights = []
    for p in pts:
        w = p.get("weight") or {}
        grams = g.num(w.get("weightGrams"))
        if grams is None:
            continue
        weights.append({"time": _sample_local(w.get("sampleTime")), "kg": _r(grams / 1000, 2),
                        "lb": _r(grams / 453.59237, 1), "notes": w.get("notes"),
                        "id": (p.get("name") or "").split("/")[-1] or None})
    fats = []
    try:
        f2 = f'body_fat.sample_time.civil_time >= "{start.isoformat()}" AND body_fat.sample_time.civil_time < "{_next(end)}"'
        for p in await g.list_points("body-fat", f2):
            b = p.get("bodyFat") or {}
            fats.append({"time": _sample_local(b.get("sampleTime")), "percent": _r(b.get("percentage"), 1)})
    except g.ApiError:
        pass
    weights.sort(key=lambda x: x["time"] or "")
    fats.sort(key=lambda x: x["time"] or "")
    return {"weight": weights, "body_fat": fats}


@tool
async def get_body_timeseries_by_range(resource: Literal["weight", "fat"], start_date: str, end_date: str = "today") -> dict:
    """Get daily average weight (kg and lb) or body fat percentage for a date range. Days without a
    measurement are left out. BMI is not provided by the Google Health API.

    Args:
        resource: "weight" or "fat".
        start_date: yyyy-MM-dd.
        end_date: yyyy-MM-dd or "today".
    """
    start, end = await _range(start_date, end_date, default_days=30)
    if resource == "weight":
        pts = await _daily("weight", start, end)
        data = []
        for p in pts:
            gr = g.num((p.get("weight") or {}).get("weightGramsAvg"))
            if gr:
                data.append({"date": _rdate(p), "kg": _r(gr / 1000), "lb": _r(gr / 453.59237, 1)})
        return {"resource": "weight", "data": data}
    if resource == "fat":
        pts = await _daily("body-fat", start, end)
        return {"resource": "fat", "data": [{"date": _rdate(p), "percent": _r((p.get("bodyFat") or {}).get("bodyFatPercentageAvg"), 1)}
                                            for p in pts if (p.get("bodyFat") or {}).get("bodyFatPercentageAvg") is not None]}
    raise ValueError('resource must be "weight" or "fat"')


@tool
async def log_weight(weight: float, unit: Literal["lb", "kg"] = "lb", date: str = "today", time: str | None = None) -> dict:
    """Log a body weight measurement.

    Args:
        weight: the weight value.
        unit: "lb" or "kg".
        date: yyyy-MM-dd or "today".
        time: optional HH:mm local time. Default: now (today) or noon (other days).
    """
    grams = weight * (453.59237 if unit == "lb" else 1000)
    if not 0 < grams <= 1_000_000:
        raise ValueError("weight out of range")
    d = await g.resolve_date(date)
    utc, off = await g.local_to_utc(d, time)
    op = await g.create_point("weight", {"weight": {"sampleTime": {"physicalTime": g.rfc3339(utc), "utcOffset": off},
                                                   "weightGrams": round(grams, 1)}})
    return _op_result(op, f"Logged {weight} {unit} on {d.isoformat()}.")


# =========================================================================== nutrition

MEALS = {
    "breakfast": "BREAKFAST", "morning snack": "BEFORE_LUNCH", "lunch": "LUNCH",
    "afternoon snack": "BEFORE_DINNER", "dinner": "DINNER", "evening snack": "AFTER_DINNER",
    "snack": "SNACK", "anytime": "ANYTIME", "before breakfast": "BEFORE_BREAKFAST",
}


def _op_result(op: dict, ok: str) -> dict:
    if op.get("error"):
        return {"error": f"Google rejected the request: {op['error'].get('message')}"}
    resp = op.get("response") or {}
    name = resp.get("name") or ""
    out = {"result": ok if op.get("done", True) else ok + " (Google is still processing it)"}
    if name:
        out["id"] = name.split("/")[-1]
    return out


def _food_row(p: dict) -> dict:
    n = p.get("nutritionLog") or {}
    iv = n.get("interval") or {}
    nutrients = {x.get("nutrient", "?").lower(): _r((x.get("quantity") or {}).get("grams"), 3) for x in n.get("nutrients", []) or []}
    serving = n.get("serving") or {}
    return {
        "id": (p.get("name") or "").split("/")[-1] or None,
        "food": n.get("foodDisplayName"),
        "meal": (n.get("mealType") or "").lower() or None,
        "time": g.interval_local(iv, "start"),
        "servings": serving.get("amount"),
        "unit": serving.get("foodMeasurementUnitDisplayName"),
        "calories": _r((n.get("energy") or {}).get("kcal"), 0),
        "carbs_g": _r((n.get("totalCarbohydrate") or {}).get("grams"), 1),
        "fat_g": _r((n.get("totalFat") or {}).get("grams"), 1),
        "protein_g": nutrients.get("protein"),
        "fiber_g": nutrients.get("dietary_fiber"),
        "sugar_g": nutrients.get("sugar"),
        "sodium_mg": _r(nutrients["sodium"] * 1000, 0) if nutrients.get("sodium") is not None else None,
        "other_nutrients_g": {k: v for k, v in nutrients.items() if k not in ("protein", "dietary_fiber", "sugar", "sodium")} or None,
    }


async def _session_list(data_type: str, field: str, d: date) -> list[dict]:
    snake = data_type.replace("-", "_")
    f = f'{snake}.interval.civil_start_time >= "{d.isoformat()}" AND {snake}.interval.civil_start_time < "{_next(d)}"'

    def keep(p):
        return g.interval_local_date((p.get(field) or {}).get("interval"), "start") == d.isoformat()

    return await g.list_points(data_type, f, max_points=2000, fallback=keep)


@tool
async def get_food_log(date: str = "today") -> dict:
    """Get all foods logged on a date with calories and macros, plus daily totals. Each entry has an
    "id" that delete_food_log accepts.

    Args:
        date: yyyy-MM-dd or "today".
    """
    d = await g.resolve_date(date)
    rows = [_food_row(p) for p in await _session_list("nutrition-log", "nutritionLog", d)]
    rows.sort(key=lambda r: r["time"] or "")

    def total(k):
        vals = [r[k] for r in rows if r.get(k) is not None]
        return round(sum(vals), 1) if vals else 0

    return {"date": d.isoformat(), "foods": rows,
            "totals": {k: total(k) for k in ("calories", "carbs_g", "fat_g", "protein_g", "fiber_g", "sugar_g", "sodium_mg")}}


@tool
async def get_water_log(date: str = "today") -> dict:
    """Get water/drink entries logged on a date and the total in ml and US fluid ounces.

    Args:
        date: yyyy-MM-dd or "today".
    """
    d = await g.resolve_date(date)
    rows = []
    for p in await _session_list("hydration-log", "hydrationLog", d):
        h = p.get("hydrationLog") or {}
        ml = g.num((h.get("amountConsumed") or {}).get("milliliters")) or 0
        rows.append({"id": (p.get("name") or "").split("/")[-1] or None,
                     "time": g.interval_local(h.get("interval"), "start"), "ml": _r(ml, 0)})
    rows.sort(key=lambda r: r["time"] or "")
    total = sum(r["ml"] or 0 for r in rows)
    return {"date": d.isoformat(), "entries": rows, "total_ml": round(total), "total_fl_oz": round(total / 29.5735, 1)}


NUTRIENT_ARGS = {
    "protein_g": ("PROTEIN", 1), "fiber_g": ("DIETARY_FIBER", 1), "sugar_g": ("SUGAR", 1),
    "saturated_fat_g": ("SATURATED_FAT", 1), "trans_fat_g": ("TRANS_FAT", 1),
    "sodium_mg": ("SODIUM", 0.001), "cholesterol_mg": ("CHOLESTEROL", 0.001),
    "potassium_mg": ("POTASSIUM", 0.001), "calcium_mg": ("CALCIUM", 0.001), "iron_mg": ("IRON", 0.001),
    "caffeine_mg": ("CAFFEINE", 0.001),
}


@tool
async def log_food(food_name: str, calories: float, meal_type: Literal["breakfast", "morning snack", "lunch", "afternoon snack",
                                                                      "dinner", "evening snack", "snack", "anytime"] = "anytime",
                   date: str = "today", time: str | None = None, servings: float = 1.0,
                   carbs_g: float | None = None, fat_g: float | None = None, protein_g: float | None = None,
                   fiber_g: float | None = None, sugar_g: float | None = None, saturated_fat_g: float | None = None,
                   trans_fat_g: float | None = None, sodium_mg: float | None = None, cholesterol_mg: float | None = None,
                   potassium_mg: float | None = None, calcium_mg: float | None = None, iron_mg: float | None = None,
                   caffeine_mg: float | None = None) -> dict:
    """Log a food to the user's Fitbit/Google Health food log. Give the TOTAL nutrition for the amount eaten
    (all servings combined). Estimate values if the user does not give them; calories are required.

    Args:
        food_name: what was eaten, e.g. "Greek yogurt with honey".
        calories: total kcal for the amount eaten.
        meal_type: breakfast, morning snack, lunch, afternoon snack, dinner, evening snack, snack, anytime.
        date: yyyy-MM-dd or "today".
        time: optional HH:mm local time. Default: now (today) or noon (other days).
        servings: number of servings (for display only; nutrition values are totals).
        carbs_g, fat_g, protein_g, fiber_g, sugar_g, saturated_fat_g, trans_fat_g: grams.
        sodium_mg, cholesterol_mg, potassium_mg, calcium_mg, iron_mg, caffeine_mg: milligrams.
    """
    if not food_name.strip():
        raise ValueError("food_name is empty")
    if not 0 <= calories <= 100000:
        raise ValueError("calories out of range")
    d = await g.resolve_date(date)
    start, off = await g.local_to_utc(d, time)
    end = start + timedelta(minutes=1)
    log: dict[str, Any] = {
        "interval": {"startTime": g.rfc3339(start), "startUtcOffset": off, "endTime": g.rfc3339(end), "endUtcOffset": off},
        "foodDisplayName": food_name.strip()[:200],
        "mealType": MEALS.get(meal_type, "ANYTIME"),
        "energy": {"kcal": round(calories, 1)},
        "totalCarbohydrate": {"grams": round(carbs_g or 0, 2)},
        "totalFat": {"grams": round(fat_g or 0, 2)},
        "serving": {"amount": servings},
    }
    vals = locals()
    nutrients = []
    for arg, (enum, factor) in NUTRIENT_ARGS.items():
        v = vals.get(arg)
        if v is not None:
            nutrients.append({"nutrient": enum, "quantity": {"grams": round(v * factor, 4)}})
    if nutrients:
        log["nutrients"] = nutrients
    op = await g.create_point("nutrition-log", {"nutritionLog": log})
    return _op_result(op, f"Logged {food_name} ({round(calories)} kcal) as {meal_type} on {d.isoformat()}.")


@tool
async def log_water(amount: float, unit: Literal["fl oz", "ml", "cup"] = "fl oz", date: str = "today", time: str | None = None) -> dict:
    """Log water or another drink.

    Args:
        amount: quantity consumed.
        unit: "fl oz" (US), "ml" or "cup" (US cup).
        date: yyyy-MM-dd or "today".
        time: optional HH:mm local time. Default: now (today) or noon (other days).
    """
    factor = {"fl oz": 29.5735, "ml": 1.0, "cup": 236.588}[unit]
    enum = {"fl oz": "FLUID_OUNCE_US", "ml": "MILLILITER", "cup": "CUP_US"}[unit]
    ml = amount * factor
    if not 0 < ml <= 100000:
        raise ValueError("amount out of range")
    d = await g.resolve_date(date)
    start, off = await g.local_to_utc(d, time)
    end = start + timedelta(seconds=1)
    op = await g.create_point("hydration-log", {"hydrationLog": {
        "interval": {"startTime": g.rfc3339(start), "startUtcOffset": off, "endTime": g.rfc3339(end), "endUtcOffset": off},
        "amountConsumed": {"milliliters": round(ml, 1), "userProvidedUnit": enum}}})
    return _op_result(op, f"Logged {amount} {unit} of water on {d.isoformat()}.")


@tool
async def delete_food_log(log_id: str) -> dict:
    """Delete a food log entry. Get the id from get_food_log. Only entries this connector created can be
    deleted (Google allows apps to delete only their own data).

    Args:
        log_id: the "id" from get_food_log.
    """
    log_id = log_id.strip()
    name = log_id if log_id.startswith("users/") else f"users/me/dataTypes/nutrition-log/dataPoints/{log_id}"
    op = await g.batch_delete("nutrition-log", [name])
    if op.get("error"):
        return {"error": f"Google rejected the delete: {op['error'].get('message')}"}
    return {"result": f"Deleted food log entry {log_id.split('/')[-1]}."}
