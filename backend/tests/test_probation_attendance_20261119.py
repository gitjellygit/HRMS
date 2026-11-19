"""Probation proration and HR team attendance release gates."""
from datetime import date, timedelta, datetime, timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.main import app, SessionLocal, Attendance, Employee
from app.leave_management import (
    PolicyIn, LeavePolicy, add_calendar_months, eligibility_date,
    prorated_entitlement, tiered_monthly_entitlement
)
from test_pay_people import seed, login, PASS, ORIGIN

def test_calendar_month_probation_and_policy_validation():
    assert add_calendar_months(date(2026,1,31),1)==date(2026,2,28)
    assert add_calendar_months(date(2024,1,31),1)==date(2024,2,29)
    assert add_calendar_months(date(2026,11,30),3)==date(2027,2,28)
    assert eligibility_date(date(2026,7,10),{"probation_allowed":False,"probation_months":3})==date(2026,10,10)
    assert eligibility_date(date(2026,7,10),{"probation_allowed":True,"probation_months":3})==date(2026,7,10)
    eligible=eligibility_date(date(2026,7,10),{"probation_allowed":False,"probation_months":3})
    annual=prorated_entitlement(Decimal(22),eligible,2026,"financial")
    assert Decimal(0)<annual<Decimal(22)
    monthly=[Decimal("1.5")]*8+[Decimal("2.5")]*4
    assert tiered_monthly_entitlement(eligible,2026,date(2026,10,9),Decimal(0),Decimal(0),monthly,"financial")==0
    assert Decimal(0)<tiered_monthly_entitlement(eligible,2026,date(2027,3,31),Decimal(0),Decimal(0),monthly,"financial")<Decimal(22)
    assert PolicyIn(leave_type="casual").probation_months==3
    assert PolicyIn(leave_type="casual").probation_allowed is False
    with pytest.raises(ValidationError):
        PolicyIn(leave_type="casual",probation_months=13)
    with pytest.raises(ValidationError):
        PolicyIn(leave_type="casual",probation_months=-1)


def test_new_joiner_entitlement_starts_after_probation_and_versions_are_recorded():
    with TestClient(app) as client:
        admin,hr,worker,other=seed(client)
        with SessionLocal() as db:
            record=db.get(Employee,worker)
            # Synthetic dates: joining today means an employee with three-month
            # probation should not get future annual or monthly leave credits.
            record.joining_date=date.today()
            db.commit()
        with SessionLocal() as db:
            configured={p.leave_type for p in db.query(LeavePolicy).all()}
        kind=next((name for name in ("paternity","maternity","comp_off","sick","earned")
                   if name not in configured),None)
        if kind is None:
            pytest.skip("All suitable leave types already have a policy")
        config={
            "leave_type":kind,"year_type":"financial","annual_days":24,
            "probation_months":3,"probation_allowed":False,
            "approval_chain":["hr"],"change_reason":"QA three-month probation allocation"
        }
        updated=client.put("/leave/policies",headers=ORIGIN,json=config)
        assert updated.status_code==200,updated.text
        balance=client.get("/leave/balances?employee_id="+str(worker))
        assert balance.status_code==200,balance.text
        allocated=next(x["allocated"] for x in balance.json() if x["leave_type"]==kind)
        assert allocated==0,"No annual leave before probation eligibility"
        policies=client.get("/leave/policies")
        assert policies.status_code==200
        policy=next(x for x in policies.json() if x["leave_type"]==kind)
        assert policy["probation_months"]==3
        assert policy["probation_allowed"] is False
        history=client.get("/leave/policies/"+kind+"/history")
        assert history.status_code==200
        assert history.json()[0]["terms"]["probation_months"]==3
        client.post("/auth/logout",headers=ORIGIN)
        login(client,"payroll.person.qa@example.org",PASS)
        start=date.today()+timedelta(days=7)
        while start.weekday()>=5:start+=timedelta(days=1)
        denied=client.post("/leave/requests",headers=ORIGIN,json={
            "leave_type":kind,"start_date":str(start),"end_date":str(start),
            "reason":"Testing leave request before probation ends"})
        assert denied.status_code==422,denied.text
        assert "probation" in denied.text.lower()


def test_hr_team_attendance_is_paginated_and_employees_cannot_browse_team():
    with TestClient(app) as client:
        admin,hr,worker,other=seed(client)
        today=date.today()
        query=f"/attendance/team?start_date={today-timedelta(days=30)}&end_date={today}"
        with SessionLocal() as db:
            db.add(Attendance(employee_id=worker,punch_in=datetime.now(timezone.utc),
                              punch_out=None))
            db.commit()
        result=client.get(query)
        assert result.status_code==200,result.text
        assert isinstance(result.json()["items"],list)
        assert any(x["employee_id"]==worker for x in result.json()["items"])
        assert all("employee_name" in x for x in result.json()["items"])
        with SessionLocal() as db:
            db.add(Attendance(employee_id=worker,
                              punch_in=datetime(today.year,today.month,today.day,0,0,tzinfo=timezone.utc)-timedelta(hours=2),
                              punch_out=datetime(today.year,today.month,today.day,0,0,tzinfo=timezone.utc)-timedelta(hours=1)))
            db.commit()
        local=client.get(query+"&start_utc_offset=-330&end_utc_offset=-330")
        assert local.status_code==200,local.text
        assert any(x["employee_id"]==worker for x in local.json()["items"])
        invalid=client.get(query+"&start_utc_offset=2000")
        assert invalid.status_code==422
        too_wide=client.get(f"/attendance/team?start_date={today-timedelta(days=400)}&end_date={today}")
        assert too_wide.status_code==422
        bad_page=client.get(query+"&limit=999")
        assert bad_page.status_code==422
        client.post("/auth/logout",headers=ORIGIN)
        login(client,"payroll.person.qa@example.org",PASS)
        assert client.get(query).status_code==403
