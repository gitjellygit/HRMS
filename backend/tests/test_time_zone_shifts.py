"""Named US shift zones and DST rules are retained by the API."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient
from app.main import app
from test_time_tracking import seed, ORIGIN


def test_us_shift_zones_save_and_follow_daylight_saving():
    eastern = ZoneInfo("America/New_York")
    central = ZoneInfo("America/Chicago")
    for zone, winter, summer in [(eastern, -5, -4), (central, -6, -5)]:
        assert datetime(2026, 1, 15, 9, tzinfo=zone).utcoffset() == timedelta(hours=winter)
        assert datetime(2026, 7, 15, 9, tzinfo=zone).utcoffset() == timedelta(hours=summer)

    with TestClient(app) as client:
        seed(client)
        for tz in ("America/New_York", "America/Chicago"):
            result = client.post("/time/shifts", headers=ORIGIN, json={
                "name": "QA " + tz, "start_time": "09:00", "end_time": "18:00",
                "break_minutes": 60, "timezone": tz})
            assert result.status_code == 201, result.text
            shifts = client.get("/time/shifts").json()
            saved = next(x for x in shifts if x["id"] == result.json()["id"])
            assert saved["timezone"] == tz
        invalid = client.post("/time/shifts", headers=ORIGIN, json={
            "name": "Invalid zone", "start_time": "09:00", "end_time": "18:00",
            "timezone": "EST"})
        assert invalid.status_code == 422
