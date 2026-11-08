"""Thin async client for the Google Health API v4.

Reference: https://developers.google.com/health/reference/rest
Range limits: https://developers.google.com/health/data-types#query_constraints
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo

import httpx

from fitbit_mcp import auth, config

logger = logging.getLogger("fitbit_mcp.google")

# rollUp / dailyRollUp maximum range per request.
FOURTEEN_DAY_TYPES = {"heart-rate", "active-minutes", "total-calories", "calories-in-heart-rate-zone"}
SESSION_PAGE_TYPES = {"sleep", "exercise"}  # page size capped at 25


def max_range_days(data_type: str) -> int:
    return 14 if data_type in FOURTEEN_DAY_TYPES else 90


class ApiError(Exception):
    def __init__(self, status: int, message: str, reason: str = ""):
        super().__init__(message)
        self.status = status
        self.reason = reason


def _error_reasons(body: dict) -> list[str]:
    out = []
    err = body.get("error", {}) if isinstance(body, dict) else {}
    if err.get("status"):
        out.append(err["status"])
    for d in err.get("details", []) or []:
        if d.get("reason"):
            out.append(d["reason"])
        md = d.get("metadata") or {}
        if md.get("detailedReasons"):
            out.append(str(md["detailedReasons"]))
    return out


_http: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(base_url=config.API_BASE, timeout=45)
    return _http


async def request(method: str, path: str, *, params: dict | None = None, json: Any = None) -> dict:
    token = await auth.get_access_token()
    refreshed = False
    for attempt in range(4):
        r = await _client().request(
            method, path, params=params, json=json,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        if r.status_code == 401 and not refreshed:
            token = await auth.get_access_token(force_refresh=True)
            refreshed = True
            continue
        if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
            await asyncio.sleep(2 ** (attempt + 1))
            continue
        break
    try:
        body = r.json() if r.content else {}
    except ValueError:
        body = {"raw": r.text[:500]}
    if r.status_code == 401:
        raise auth.AuthRequired()
    if r.status_code >= 400:
        reasons = _error_reasons(body)
        msg = (body.get("error", {}) or {}).get("message") if isinstance(body, dict) else None
        reason = " ".join(reasons)
        if "ACCOUNT_NOT_LINKED" in reason:
            raise ApiError(400, "Your Google Account is not linked to Google Health yet. Open the Google Health "
                                "(Fitbit) app, sign in with your Google Account, finish moving your Fitbit account, "
                                "then open the sign-in link again: " + config.auth_start_url(), reason)
        if "MISSING_OAUTH_SCOPE" in reason or r.status_code == 403:
            raise ApiError(403, f"Google refused access ({msg or reason}). You may have unticked a permission "
                                f"on the Google sign-in screen. Sign in again and allow all boxes: "
                                f"{config.auth_start_url()}", reason)
        raise ApiError(r.status_code, f"Google Health API error {r.status_code}: {msg or body} {reason}".strip(), reason)
    return body


# ---------------------------------------------------------------- user time zone

_tz_cache: dict[str, Any] = {}


async def user_settings() -> dict:
    if _tz_cache.get("t", 0) > time.time() - 3600 and "settings" in _tz_cache:
        return _tz_cache["settings"]
    try:
        s = await request("GET", "/users/me/settings")
    except ApiError as e:
        logger.warning("Could not read settings: %s", e)
        s = {}
    _tz_cache.update(settings=s, t=time.time())
    return s


async def user_tz() -> ZoneInfo | timezone:
    s = await user_settings()
    if s.get("timeZone"):
        try:
            return ZoneInfo(s["timeZone"])
        except Exception:  # noqa: BLE001
            pass
    if s.get("utcOffset"):
        return timezone(timedelta(seconds=_dur_seconds(s["utcOffset"])))
    return timezone.utc


def _dur_seconds(d: str) -> float:
    try:
        return float(str(d).rstrip("s"))
    except ValueError:
        return 0.0


async def today() -> date:
    return datetime.now(await user_tz()).date()


async def resolve_date(s: str | None) -> date:
    if not s or s.lower() == "today":
        return await today()
    return date.fromisoformat(s)


async def local_to_utc(d: date, hhmm: str | None = None) -> tuple[datetime, str]:
    """Return (UTC datetime, UTC offset as protobuf Duration string) for a local date/time."""
    tz = await user_tz()
    if hhmm:
        h, m = (int(x) for x in hhmm.split(":")[:2])
        local = datetime(d.year, d.month, d.day, h, m, tzinfo=tz)
    else:
        now = datetime.now(tz)
        local = now if d == now.date() else datetime(d.year, d.month, d.day, 12, 0, tzinfo=tz)
    off = local.utcoffset() or timedelta(0)
    return local.astimezone(timezone.utc), f"{int(off.total_seconds())}s"


def rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- list

def _is_filter_error(e: ApiError) -> bool:
    return e.status == 400 and "FILTER" in e.reason.upper()


async def list_points(data_type: str, filter_: str | None = None, *, max_points: int = 5000,
                      fallback: Callable[[dict], bool] | None = None) -> list[dict]:
    """List data points with automatic pagination.

    If Google rejects the filter and a fallback predicate is given, list without a filter
    (newest first) and filter on our side.
    """
    page_size = 25 if data_type in SESSION_PAGE_TYPES else min(max_points, 10000)
    try:
        return await _paginate(data_type, filter_, page_size, max_points)
    except ApiError as e:
        if fallback is None or not _is_filter_error(e):
            raise
        logger.warning("Filter rejected for %s (%s); falling back to client-side filtering", data_type, e.reason)
        pts = await _paginate(data_type, None, page_size, max(max_points, 1000))
        return [p for p in pts if fallback(p)]


async def _paginate(data_type: str, filter_: str | None, page_size: int, max_points: int) -> list[dict]:
    out: list[dict] = []
    token = None
    while True:
        params: dict[str, Any] = {"pageSize": page_size}
        if filter_:
            params["filter"] = filter_
        if token:
            params["pageToken"] = token
        body = await request("GET", f"/users/me/dataTypes/{data_type}/dataPoints", params=params)
        out.extend(body.get("dataPoints", []) or [])
        token = body.get("nextPageToken")
        if not token or len(out) >= max_points:
            return out[:max_points]


# ---------------------------------------------------------------- rollups

def _civil(d: date) -> dict:
    return {"date": {"year": d.year, "month": d.month, "day": d.day}, "time": {"hours": 0, "minutes": 0, "seconds": 0, "nanos": 0}}


def date_chunks(start: date, end_inclusive: date, max_days: int) -> Iterable[tuple[date, date]]:
    """Yield [chunk_start, chunk_end_exclusive) pairs no longer than max_days."""
    cur = start
    stop = end_inclusive + timedelta(days=1)
    while cur < stop:
        nxt = min(cur + timedelta(days=max_days), stop)
        yield cur, nxt
        cur = nxt


async def daily_rollup(data_type: str, start: date, end_inclusive: date) -> list[dict]:
    """One rollup point per civil day, split into 14- or 90-day requests, paginated."""
    if end_inclusive < start:
        raise ValueError("end date is before start date")
    out: list[dict] = []
    lim = max_range_days(data_type)
    for a, b in date_chunks(start, end_inclusive, lim):
        token = None
        while True:
            body: dict[str, Any] = {"range": {"start": _civil(a), "end": _civil(b)}, "windowSizeDays": 1, "pageSize": lim}
            if token:
                body["pageToken"] = token
            resp = await request("POST", f"/users/me/dataTypes/{data_type}/dataPoints:dailyRollUp", json=body)
            out.extend(resp.get("rollupDataPoints", []) or [])
            token = resp.get("nextPageToken")
            if not token:
                break
    return out


async def rollup(data_type: str, start: datetime, end: datetime, window_seconds: int) -> list[dict]:
    """Physical-time rollup (intraday buckets), split by range limit, paginated."""
    out: list[dict] = []
    lim = timedelta(days=max_range_days(data_type))
    cur = start
    while cur < end:
        nxt = min(cur + lim, end)
        token = None
        while True:
            body: dict[str, Any] = {
                "range": {"startTime": rfc3339(cur), "endTime": rfc3339(nxt)},
                "windowSize": f"{window_seconds}s",
                "pageSize": 10000,
            }
            if token:
                body["pageToken"] = token
            resp = await request("POST", f"/users/me/dataTypes/{data_type}/dataPoints:rollUp", json=body)
            out.extend(resp.get("rollupDataPoints", []) or [])
            token = resp.get("nextPageToken")
            if not token:
                break
        cur = nxt
    return out


async def create_point(data_type: str, point: dict) -> dict:
    return await request("POST", f"/users/me/dataTypes/{data_type}/dataPoints", json=point)


async def batch_delete(data_type: str, names: list[str]) -> dict:
    return await request("POST", f"/users/me/dataTypes/{data_type}/dataPoints:batchDelete", json={"names": names})


# ---------------------------------------------------------------- small helpers

def civil_date_str(c: dict | None) -> str | None:
    if not c:
        return None
    d = c.get("date", c)
    if not d.get("year"):
        return None
    return f"{d['year']:04d}-{d.get('month', 1):02d}-{d.get('day', 1):02d}"


def civil_dt_str(c: dict | None) -> str | None:
    ds = civil_date_str(c)
    if not ds:
        return None
    t = (c or {}).get("time") or {}
    return f"{ds} {t.get('hours', 0):02d}:{t.get('minutes', 0):02d}"


def interval_local(iv: dict | None, which: str = "start") -> str | None:
    """Local "yyyy-MM-dd HH:MM" for an interval's start or end.

    Uses civilStartTime/civilEndTime when Google sends them. Many points (for example sleep and
    exercise synced from Fitbit or HealthKit) only carry startTime/endTime plus a UTC offset, so
    fall back to computing local time from those.
    """
    iv = iv or {}
    civil = iv.get("civilStartTime" if which == "start" else "civilEndTime")
    if civil:
        return civil_dt_str(civil)
    ts = iv.get(f"{which}Time")
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    off = timedelta(seconds=_dur_seconds(iv.get(f"{which}UtcOffset") or "0s"))
    return (dt.astimezone(timezone.utc) + off).strftime("%Y-%m-%d %H:%M")


def interval_local_date(iv: dict | None, which: str = "start") -> str | None:
    s = interval_local(iv, which)
    return s[:10] if s else None


def num(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
