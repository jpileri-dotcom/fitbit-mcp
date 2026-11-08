import os
import tempfile

os.environ.setdefault("MCP_PATH_SECRET", "testsecret")
os.environ.setdefault("GOOGLE_CLIENT_ID", "cid")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "csecret")
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())

from fitbit_mcp.tools import _merge_duplicate_exercises  # noqa: E402


def _pt(name, start, end, platform, pkg=None, metrics=None, display="Strength training"):
    app = {"packageName": pkg} if pkg else {"webClientId": "227TGP"}
    return {"name": f"users/1/dataTypes/exercise/dataPoints/{name}",
            "dataSource": {"platform": platform, "application": app},
            "exercise": {"displayName": display, "interval": {"startTime": start, "endTime": end},
                         "metricsSummary": metrics or {}}}


def test_merges_shifted_peloton_pair():
    hk = _pt("1", "2026-11-02T13:32:00Z", "2026-11-02T13:50:00Z", "HEALTH_KIT", "com.Peloton.Draper")
    fb = _pt("2", "2026-11-02T13:50:00Z", "2026-11-02T14:09:00Z", "FITBIT_WEB_API",
             metrics={"caloriesKcal": 65}, display="Peloton - 18 min Strength+ Workout")
    walk = _pt("3", "2026-11-02T16:00:00Z", "2026-11-02T16:18:00Z", "FITBIT", display="Walk")
    out = _merge_duplicate_exercises([hk, fb, walk])
    assert len(out) == 2
    m = out[0]
    assert m["exercise"]["interval"]["startTime"] == "2026-11-02T13:32:00Z"
    assert m["exercise"]["metricsSummary"]["caloriesKcal"] == 65
    assert m["exercise"]["displayName"].startswith("Peloton")


def test_keeps_separate_workouts():
    a = _pt("1", "2026-11-02T13:32:00Z", "2026-11-02T13:50:00Z", "HEALTH_KIT", "com.Peloton.Draper")
    b = _pt("2", "2026-11-02T18:00:00Z", "2026-11-02T18:45:00Z", "FITBIT_WEB_API", display="Peloton - 45 min Ride")
    assert len(_merge_duplicate_exercises([a, b])) == 2
