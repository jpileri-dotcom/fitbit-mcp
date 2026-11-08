"""Offline tests: Google endpoints are replaced with a fake transport."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time

os.environ.setdefault("MCP_PATH_SECRET", "testsecret")
os.environ.setdefault("GOOGLE_CLIENT_ID", "cid")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "csecret")
os.environ["DATA_DIR"] = tempfile.mkdtemp()

import httpx  # noqa: E402
import pytest  # noqa: E402

from fitbit_mcp import auth, config  # noqa: E402
from fitbit_mcp import google as g  # noqa: E402
import fitbit_mcp.server  # noqa: E402, F401
from fitbit_mcp import tools  # noqa: E402


class Fake:
    def __init__(self, handler):
        self.calls: list[httpx.Request] = []
        self.handler = handler

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.calls.append(req)
        return self.handler(req)


def install(handler) -> Fake:
    fake = Fake(handler)
    g._http = httpx.AsyncClient(base_url=config.API_BASE, transport=httpx.MockTransport(fake))
    g._tz_cache.clear()
    g._tz_cache.update(settings={"timeZone": "America/New_York"}, t=time.time())
    return fake


@pytest.fixture(autouse=True)
def token():
    auth._write_json(auth._token_path(), {"access_token": "at", "refresh_token": "rt",
                                          "expires_at": time.time() + 3600, "scope": " ".join(config.SCOPES)})
    yield
    auth.clear_token()


def run(coro):
    return asyncio.run(coro)


def test_log_food_body():
    def h(req):
        assert req.url.path == "/v4/users/me/dataTypes/nutrition-log/dataPoints"
        return httpx.Response(200, json={"done": True, "response": {"name": "users/1/dataTypes/nutrition-log/dataPoints/abc"}})
    fake = install(h)
    out = run(tools.log_food(food_name="Chicken", calories=165, meal_type="dinner", date="2026-11-07",
                             time="19:30", protein_g=31, carbs_g=0, fat_g=3.6, sodium_mg=74))
    assert out["id"] == "abc", out
    body = json.loads(fake.calls[0].content)["nutritionLog"]
    assert body["mealType"] == "DINNER"
    assert body["interval"]["startTime"] == "2026-11-08T00:30:00Z"  # 19:30 EST
    assert body["interval"]["startUtcOffset"] == "-18000s"
    assert {"nutrient": "SODIUM", "quantity": {"grams": 0.074}} in body["nutrients"]
    assert {"nutrient": "PROTEIN", "quantity": {"grams": 31}} in body["nutrients"]
    assert body["energy"] == {"kcal": 165}


def test_heart_rate_range_split_into_14_days():
    def h(req):
        if "dailyRollUp" in req.url.path:
            b = json.loads(req.content)
            d = b["range"]["start"]["date"]
            return httpx.Response(200, json={"rollupDataPoints": [
                {"civilStartTime": {"date": d}, "heartRate": {"beatsPerMinuteAvg": 70, "beatsPerMinuteMin": 50, "beatsPerMinuteMax": 150}}]})
        return httpx.Response(200, json={"dataPoints": []})
    fake = install(h)
    run(tools.get_heart_rate_by_range(start_date="2026-09-01", end_date="2026-09-30"))
    hr = [json.loads(c.content) for c in fake.calls if "heart-rate/dataPoints:dailyRollUp" in c.url.path]
    assert len(hr) == 3  # 14 + 14 + 2 days
    for b in hr:
        s, e = b["range"]["start"]["date"], b["range"]["end"]["date"]
        from datetime import date
        assert (date(e["year"], e["month"], e["day"]) - date(s["year"], s["month"], s["day"])).days <= 14


def test_steps_range_split_into_90_days_and_pagination():
    pages = {"n": 0}

    def h(req):
        b = json.loads(req.content)
        pages["n"] += 1
        resp = {"rollupDataPoints": [{"civilStartTime": b["range"]["start"], "steps": {"countSum": "1000"}}]}
        if "pageToken" not in b and b["range"]["start"]["date"]["month"] == 1:
            resp["nextPageToken"] = "p2"
        return httpx.Response(200, json=resp)
    fake = install(h)
    out = run(tools.get_activity_timeseries_by_range(resource="steps", start_date="2026-01-01", end_date="2026-06-30"))
    # 181 days -> requests of 90, 90 and 1 days; the first returns a second page.
    bodies = [json.loads(c.content) for c in fake.calls]
    starts = [(b["range"]["start"]["date"]["month"], b["range"]["start"]["date"]["day"], "pageToken" in b) for b in bodies]
    assert starts == [(1, 1, False), (1, 1, True), (4, 1, False), (6, 30, False)]
    assert len(out["data"]) == 4


def test_auth_expired_message():
    auth.clear_token()
    install(lambda r: httpx.Response(200, json={}))
    out = run(tools.get_sleep_by_date(date="2026-11-07"))
    assert "auth/start?key=testsecret" in out["error"]


def test_refresh_invalid_grant_returns_login_link(monkeypatch):
    auth._write_json(auth._token_path(), {"access_token": "old", "refresh_token": "rt", "expires_at": 0, "scope": ""})

    class R:
        status_code = 400
        content = b"x"
        def json(self):
            return {"error": "invalid_grant"}

    class C:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, *a, **k): return R()

    monkeypatch.setattr(auth.httpx, "AsyncClient", C)
    install(lambda r: httpx.Response(200, json={}))
    out = run(tools.get_food_log(date="2026-11-07"))
    assert "/auth/start" in out["error"]


def test_filter_fallback_and_food_totals():
    def h(req):
        if "filter" in req.url.params:
            return httpx.Response(400, json={"error": {"code": 400, "status": "INVALID_ARGUMENT", "message": "bad",
                                                       "details": [{"reason": "INVALID_DATA_POINT_FILTER"}]}})
        return httpx.Response(200, json={"dataPoints": [
            {"name": "users/1/dataTypes/nutrition-log/dataPoints/a1", "nutritionLog": {
                "interval": {"civilStartTime": {"date": {"year": 2026, "month": 11, "day": 7}, "time": {"hours": 8}}},
                "foodDisplayName": "Oats", "mealType": "BREAKFAST", "energy": {"kcal": 300},
                "nutrients": [{"nutrient": "PROTEIN", "quantity": {"grams": 10}}]}},
            {"name": "users/1/dataTypes/nutrition-log/dataPoints/a2", "nutritionLog": {
                "interval": {"civilStartTime": {"date": {"year": 2026, "month": 11, "day": 6}}},
                "foodDisplayName": "Other day", "energy": {"kcal": 999}}},
        ]})
    install(h)
    out = run(tools.get_food_log(date="2026-11-07"))
    assert [f["food"] for f in out["foods"]] == ["Oats"]
    assert out["totals"]["calories"] == 300 and out["totals"]["protein_g"] == 10


def test_sleep_filter_and_page_size():
    def h(req):
        assert req.url.params["pageSize"] == "25"
        assert 'sleep.interval.civil_end_time >= "2026-11-07"' in req.url.params["filter"]
        if "pageToken" not in req.url.params:
            return httpx.Response(200, json={"dataPoints": [], "nextPageToken": "t"})
        return httpx.Response(200, json={"dataPoints": [{"sleep": {
            "interval": {"civilStartTime": {"date": {"year": 2026, "month": 11, "day": 6}, "time": {"hours": 23}},
                         "civilEndTime": {"date": {"year": 2026, "month": 11, "day": 7}, "time": {"hours": 7}}},
            "summary": {"minutesAsleep": "420", "stagesSummary": [{"type": "DEEP", "minutes": "80"}]},
            "metadata": {"mainSleep": True}}}]})
    fake = install(h)
    out = run(tools.get_sleep_by_date(date="2026-11-07"))
    assert len(fake.calls) == 2
    assert out["sleep"][0]["minutes_asleep"] == 420 and out["sleep"][0]["stages_minutes"]["deep"] == 80


def test_delete_food_log():
    fake = install(lambda r: httpx.Response(200, json={"done": True}))
    out = run(tools.delete_food_log(log_id="abc"))
    assert "Deleted" in out["result"]
    assert json.loads(fake.calls[0].content) == {"names": ["users/me/dataTypes/nutrition-log/dataPoints/abc"]}
    assert fake.calls[0].url.path.endswith("nutrition-log/dataPoints:batchDelete")


def test_log_water_and_weight():
    fake = install(lambda r: httpx.Response(200, json={"done": True, "response": {}}))
    run(tools.log_water(amount=16, unit="fl oz", date="2026-07-01", time="10:00"))
    w = json.loads(fake.calls[0].content)["hydrationLog"]
    assert w["amountConsumed"]["milliliters"] == pytest.approx(473.2, 0.01)
    assert w["interval"]["startUtcOffset"] == "-14400s"  # EDT
    run(tools.log_weight(weight=180, unit="lb", date="2026-07-01", time="07:00"))
    wt = json.loads(fake.calls[1].content)["weight"]
    assert wt["weightGrams"] == pytest.approx(81646.6, 0.1)
    assert wt["sampleTime"]["physicalTime"] == "2026-07-01T11:00:00Z"


def test_account_not_linked_message():
    install(lambda r: httpx.Response(400, json={"error": {"code": 400, "status": "FAILED_PRECONDITION",
                                                          "details": [{"reason": "ACCOUNT_NOT_LINKED"}]}}))
    out = run(tools.get_hrv_by_date(date="2026-11-07"))
    assert "not linked" in out["error"]
