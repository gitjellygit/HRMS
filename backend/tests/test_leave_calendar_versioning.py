"""Release-blocking calendar-year and dated leave-policy regression coverage."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app, SessionLocal
from app.leave_management import (
    PolicyIn, LeaveIn, LeavePolicy, LeavePolicyVersion, policy_bounds,
    policy_start_year, tiered_monthly_entitlement, terms_at, policy_versions,
)
from test_pay_people import login, seed, ORIGIN


def test_financial_calendar_boundaries_and_leap_year():
    assert policy_start_year(date(2026,3,31),"financial")==2025
    assert policy_start_year(date(2026,4,1),"financial")==2026
    assert policy_start_year(date(2026,3,31),"calendar")==2026
    assert policy_bounds(2026,"financial")==(date(2026,4,1),date(2027,3,31))
    assert policy_bounds(2026,"calendar")==(date(2026,1,1),date(2026,12,31))
    assert (policy_bounds(2024,"calendar")[1]-policy_bounds(2024,"calendar")[0]).days+1==366
    assert (policy_bounds(2023,"financial")[1]-policy_bounds(2023,"financial")[0]).days+1==366


def test_calendar_month_order_and_joining_proration():
    amounts=[Decimal("2")]*12
    assert tiered_monthly_entitlement(date(2026,1,1),2026,date(2026,12,31),
        Decimal(0),Decimal(0),amounts,"calendar")==Decimal(24)
    assert tiered_monthly_entitlement(date(2026,1,1),2026,date(2026,1,31),
        Decimal(0),Decimal(0),amounts,"calendar")==Decimal(2)
    assert tiered_monthly_entitlement(date(2026,1,16),2026,date(2026,1,31),
        Decimal(0),Decimal(0),amounts,"calendar")==Decimal(1)
    different=[Decimal("1")]*8+[Decimal("3")]*4
    assert tiered_monthly_entitlement(date(2026,1,1),2026,date(2026,12,31),
        Decimal(0),Decimal(0),different,"calendar")==Decimal(20)
    assert tiered_monthly_entitlement(date(2026,1,1),2026,date(2026,8,31),
        Decimal(0),Decimal(0),different,"calendar")==Decimal(8)


def test_policy_validator_rejects_invalid_schedules_and_backdating():
    with pytest.raises(ValidationError):
        PolicyIn(leave_type="earned",year_type="calendar",monthly_schedule=[Decimal(-1)]+[Decimal(0)]*11)
    with pytest.raises(ValidationError):
        PolicyIn(leave_type="earned",year_type="calendar",monthly_schedule=[Decimal("0.25")]*11)
    with pytest.raises(ValidationError):
        PolicyIn(leave_type="earned",year_type="calendar",monthly_schedule=[Decimal(1)]*12,annual_days=12)
    with pytest.raises(ValidationError):
        PolicyIn(leave_type="earned",effective_from=date.today()-timedelta(days=1))
    # Crossing April is valid for calendar-year leave; business rule is enforced
    # by the endpoint using the selected leave type, not a fixed FY validator.
    LeaveIn(leave_type="earned",start_date=date(2027,3,31),
            end_date=date(2027,4,1),reason="Two-day leave request")


def test_calendar_policy_versions_and_current_terms_are_immutable():
    with TestClient(app) as client:
        admin,hr,worker,other=seed(client)
        today=date.today()
        first={"leave_type":"paternity","year_type":"calendar","annual_days":20,
               "effective_from":today.isoformat(),"approval_chain":["hr"],
               "change_reason":"QA: create calendar leave policy"}
        with SessionLocal() as db:
            initial=db.query(LeavePolicy).filter_by(leave_type="paternity").first()
        if initial:
            # Repeated local runs might already have another test's policy.
            pytest.skip("Calendar policy type already initialized in this test database")
        created=client.put("/leave/policies",headers=ORIGIN,json=first)
        assert created.status_code==200,created.text
        before=client.get(f"/leave/balances?employee_id={worker}").json()
        prior=next(b for b in before if b["leave_type"]=="paternity")
        assert prior["year_type"]=="calendar"
        next_day=today+timedelta(days=1)
        revised={**first,"annual_days":24,"effective_from":next_day.isoformat(),
                 "change_reason":"QA: approved prospective leave policy revision"}
        response=client.put("/leave/policies",headers=ORIGIN,json=revised)
        assert response.status_code==200,response.text
        after=client.get(f"/leave/balances?employee_id={worker}").json()
        current=next(b for b in after if b["leave_type"]=="paternity")
        assert current["allocated"]==prior["allocated"],"Future policy must not revise already granted entitlement"
        history=client.get("/leave/policies/paternity/history")
        assert history.status_code==200,history.text
        entries=history.json()
        assert len(entries)==2
        assert entries[0]["terms"]["annual_days"]=="24"
        assert entries[1]["terms"]["annual_days"]=="20"
        assert entries[0]["effective_from"]==next_day.isoformat()
        with SessionLocal() as db:
            current=db.query(LeavePolicy).filter_by(leave_type="paternity").first()
            versions=policy_versions(db,current)
            assert terms_at(versions,today)["annual_days"]=="20"
            assert terms_at(versions,next_day)["annual_days"]=="24"
        old=client.put("/leave/policies",headers=ORIGIN,json={
            **revised,"effective_from":today.isoformat()})
        assert old.status_code==422
        change_basis=client.put("/leave/policies",headers=ORIGIN,json={
            **revised,"year_type":"financial","effective_from":(next_day+timedelta(days=1)).isoformat()})
        assert change_basis.status_code==422
        client.post("/auth/logout",headers=ORIGIN)
        login(client,"payroll.person.qa@example.org","IntegrationTest!Pass123")
        assert client.get("/leave/policies/paternity/history").status_code==403
