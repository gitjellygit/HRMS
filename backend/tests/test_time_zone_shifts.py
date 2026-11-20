"""Named US shift zones and DST rules are retained by the API."""
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient
from app.main import app, SessionLocal, Attendance
from test_time_tracking import seed, ORIGIN


def test_us_shift_zones_save_and_follow_daylight_saving():
    eastern = ZoneInfo("America/New_York")
    central = ZoneInfo("America/Chicago")
    for zone, winter, summer in [(eastern, -5, -4), (central, -6, -5)]:
        assert datetime(2026, 1, 15, 9, tzinfo=zone).utcoffset() == timedelta(hours=winter)
        assert datetime(2026, 7, 15, 9, tzinfo=zone).utcoffset() == timedelta(hours=summer)

    with TestClient(app) as client:
        _, _, worker, _ = seed(client)
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


def test_daily_attendance_uses_each_rostered_us_zone():
    with TestClient(app) as client:
        _, _, worker, _ = seed(client)
        expected_dates=[]
        with SessionLocal() as db:
            for i, tz in enumerate(("America/New_York","America/Chicago"),start=2):
                work_date=date.today()-timedelta(days=i)
                response=client.post("/time/shifts",headers=ORIGIN,json={
                    "name":"Rotating QA "+tz,"start_time":"09:00","end_time":"18:00",
                    "timezone":tz})
                assert response.status_code==201,response.text
                assigned=client.put("/time/roster",headers=ORIGIN,json={
                    "employee_id":worker,"shift_id":response.json()["id"],"work_date":str(work_date)})
                assert assigned.status_code==200,assigned.text
                start=datetime.combine(work_date,time(9,30),tzinfo=ZoneInfo(tz))
                db.add(Attendance(employee_id=worker,punch_in=start,punch_out=start+timedelta(hours=8)))
                expected_dates.append(str(work_date))
            db.commit()
        daily=client.get(f"/time/daily?employee_id={worker}")
        assert daily.status_code==200,daily.text
        for work_date in expected_dates:
            record=next(row for row in daily.json() if row["date"]==work_date)
            assert record["late"] is True
            assert record["sessions"]>=1
