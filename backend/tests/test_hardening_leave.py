"""Leave/exit reliability regressions (deterministic and role-restricted)."""
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.leave_management import fy_start_year
from test_pay_people import seed, login, PASS, ORIGIN


def switch(client,email,password=PASS):
    client.post("/auth/logout",headers=ORIGIN)
    login(client,email,password)


def test_hr_override_requires_reason_and_inactive_overview_is_safe():
    with TestClient(app) as c:
        admin,hr,employee,other=seed(c)
        cfg=c.put("/leave/policies",headers=ORIGIN,json={
            "leave_type":"casual","annual_days":12,"probation_allowed":True,
            "approval_chain":["manager","hr"],"active":True})
        assert cfg.status_code==200,cfg.text
        day=date.today()+timedelta(days=7)
        while day.weekday()>=5:
            day+=timedelta(days=1)
        switch(c,"payroll.person.qa@example.org")
        requested=c.post("/leave/requests",headers=ORIGIN,json={
            "leave_type":"casual","start_date":str(day),"end_date":str(day),
            "reason":"Regression test family appointment","day_part":"half"})
        assert requested.status_code==201,requested.text
        leave_id=requested.json()["id"]
        switch(c,"admin@example.com","test-admin-password-12345")
        without_reason=c.post(f"/leave/requests/{leave_id}/review",headers=ORIGIN,
                              json={"action":"approve"})
        assert without_reason.status_code==422,without_reason.text
        escalated=c.post(f"/leave/requests/{leave_id}/review",headers=ORIGIN,
                         json={"action":"approve","note":"Manager unavailable; HR emergency approval"})
        assert escalated.status_code==200,escalated.text
        history=c.get(f"/leave/requests/{leave_id}/history").json()
        assert any(x["action"]=="override_approve" for x in history)
        exited=c.post(f"/core/employees/{employee}/lifecycle",headers=ORIGIN,json={
            "event":"exited","note":"Testing inactive employee on HR dashboard",
            "effective_date":str(date.today())})
        assert exited.status_code==200,exited.text
        overview=c.get(f"/leave/hr-overview?fy={fy_start_year(date.today())}")
        assert overview.status_code==200,overview.text
        assert all(x["id"]!=employee for x in overview.json()["employees"])


def test_pending_encashment_reserves_balance_and_reduces_next_year_carry():
    with TestClient(app) as c:
        admin,hr,employee,other=seed(c)
        cfg=c.put("/leave/policies",headers=ORIGIN,json={
            "leave_type":"casual","annual_days":12,"carry_forward_limit":12,
            "probation_allowed":True,"encashment_allowed":True,
            "approval_chain":["manager","hr"],"active":True})
        assert cfg.status_code==200,cfg.text
        fy=fy_start_year(date.today())
        before=c.get(f"/leave/balances?employee_id={other}&year={fy}").json()
        casual=next(b for b in before if b["leave_type"]=="casual")
        switch(c,"payroll.other.qa@example.org")
        pending=c.post("/leave/encashment",headers=ORIGIN,json={
            "leave_type":"casual","year":fy,"days":"0.5"})
        assert pending.status_code==201,pending.text
        balances=c.get(f"/leave/balances?year={fy}").json()
        updated=next(b for b in balances if b["leave_type"]=="casual")
        assert updated["reserved_encashment"]>=0.5
        assert updated["remaining"]==casual["remaining"]-0.5
        switch(c,"admin@example.com","test-admin-password-12345")
        approved=c.post(f'/leave/encashment/{pending.json()["id"]}/review?approve=true',
                        headers=ORIGIN)
        assert approved.status_code==200,approved.text
        after=c.get(f"/leave/balances?employee_id={other}&year={fy}").json()
        updated=next(b for b in after if b["leave_type"]=="casual")
        assert updated["reserved_encashment"]==0
        assert updated["encashed"]>=0.5
