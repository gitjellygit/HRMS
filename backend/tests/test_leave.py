"""Leave management integration coverage against disposable PostgreSQL."""
from datetime import date, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app
from app.leave_management import prorated_entitlement, fy_start_year

ORIGIN={"Origin":"http://localhost:3000"}
def account(name,email,role):
    return {"name":name,"email":email,"password":"TestingPassword123!",
            "role":role,"designation":"Team Member","department":"Engineering",
            "joining_date":"2026-11-03"}

def test_financial_year_proration():
    from decimal import Decimal
    assert fy_start_year(date(2027, 3, 31))==2026
    assert fy_start_year(date(2027, 4, 1))==2027
    assert prorated_entitlement(Decimal("12"),date(2026,12,1),2026)==Decimal("4")
    assert prorated_entitlement(Decimal("12"),date(2026,4,1),2026)==Decimal("12")
    assert prorated_entitlement(Decimal("12"),date(2027,4,1),2026)==Decimal("0")


def test_leave_workflow():
    with TestClient(app) as c:
        admin=c.post("/auth/login",json={"email":"admin@example.com","password":"test-admin-password-12345"})
        assert admin.status_code==200,admin.text
        manager=c.post("/core/employees",headers=ORIGIN,
            json={"account":account("Leave Manager","leave.manager@example.org","manager"),"master":{}})
        assert manager.status_code==201,manager.text
        manager_id=manager.json()["id"]
        employee=c.post("/core/employees",headers=ORIGIN,json={
            "account":account("Leave Employee","leave.employee@example.org","employee"),
            "master":{"manager_id":manager_id}})
        assert employee.status_code==201,employee.text
        employee_id=employee.json()["id"]
        policy=c.put("/leave/policies",headers=ORIGIN,json={
            "leave_type":"casual","annual_days":12,"approval_chain":["manager","hr"],
            "probation_allowed":True,"active":True})
        assert policy.status_code==200,policy.text
        assert c.get("/leave/policies").status_code==200
        expected=float(prorated_entitlement(Decimal("12"),date(2026,11,3),2026))
        assert c.get("/leave/balances?employee_id="+str(employee_id)+"&year=2026").json()[0]["remaining"]==expected
        desk=c.get("/leave/hr-overview?fy=2026")
        assert desk.status_code==200,desk.text
        assert next(e for e in desk.json()["employees"] if e["id"]==employee_id)["leave_balances"][0]["remaining"]==expected
        c.post("/auth/logout",headers=ORIGIN)
        assert c.post("/auth/login",json={"email":"leave.employee@example.org","password":"TestingPassword123!"}).status_code==200
        assert c.get("/leave/balances?employee_id="+str(manager_id)).status_code==403
        this_monday=date(2026,11,9)
        requested=c.post("/leave/requests",headers=ORIGIN,json={
            "leave_type":"casual","start_date":str(this_monday),"end_date":str(this_monday),
            "day_part":"half","reason":"Family appointment"})
        assert requested.status_code==201,requested.text
        assert requested.json()["days"]==0.5
        request_id=requested.json()["id"]
        assert c.get("/leave/balances?year=2026").json()[0]["remaining"]==expected-0.5
        assert c.get("/leave/requests?scope=approvals").json()==[]
        assert c.post("/leave/requests/"+str(request_id)+"/review",headers=ORIGIN,json={"action":"approve"}).status_code==403
        c.post("/auth/logout",headers=ORIGIN)
        assert c.post("/auth/login",json={"email":"leave.manager@example.org","password":"TestingPassword123!"}).status_code==200
        assert len(c.get("/leave/requests?scope=approvals").json())==1
        approved=c.post("/leave/requests/"+str(request_id)+"/review",headers=ORIGIN,json={"action":"approve"})
        assert approved.status_code==200,approved.text
        assert approved.json()["current_stage"]=="hr"
        assert c.get("/leave/requests?scope=approvals").json()==[]
        c.post("/auth/logout",headers=ORIGIN)
        assert c.post("/auth/login",json={"email":"admin@example.com","password":"test-admin-password-12345"}).status_code==200
        second=c.post("/leave/requests/"+str(request_id)+"/review",headers=ORIGIN,json={"action":"approve"})
        assert second.status_code==200 and second.json()["status"]=="approved",second.text
        assert c.get("/leave/reports?year=2026").status_code==200
        c.post("/auth/logout",headers=ORIGIN)
        assert c.post("/auth/login",json={"email":"leave.employee@example.org","password":"TestingPassword123!"}).status_code==200
        withdrawn=c.post("/leave/requests/"+str(request_id)+"/withdraw",headers=ORIGIN)
        assert withdrawn.status_code==200 and withdrawn.json()["cancellation_requested"]
        c.post("/auth/logout",headers=ORIGIN)
        assert c.post("/auth/login",json={"email":"admin@example.com","password":"test-admin-password-12345"}).status_code==200
        cancellation_queue=c.get("/leave/requests?scope=approvals").json()
        assert any(row["id"]==request_id and row["cancellation_requested"] for row in cancellation_queue)
        cancelled=c.post("/leave/requests/"+str(request_id)+"/review",headers=ORIGIN,json={"action":"cancel_approve"})
        assert cancelled.status_code==200 and cancelled.json()["status"]=="cancelled",cancelled.text
        assert c.get("/leave/balances?employee_id="+str(employee_id)+"&year=2026").json()[0]["remaining"]==expected
        holiday=c.post("/leave/holidays",headers=ORIGIN,json={"name":"Office Holiday","holiday_date":"2026-11-10","location":"all","optional":False})
        assert holiday.status_code==201,holiday.text
        assert len(c.get("/leave/holidays?year=2026").json())>=1
        assert c.get("/leave/notifications").status_code==200
        assert c.get("/leave/calendar?year=2026&month=11").status_code==200
        assert c.get("/leave/reports?format=csv&year=2026").status_code==200
        assert c.get("/leave/requests/"+str(request_id)+"/history").status_code==200
        assert c.post("/leave/delegations",headers=ORIGIN,json={"delegate_id":manager_id,"start_date":"2026-11-01","end_date":"2026-11-30"}).status_code==201
        assert c.get("/leave/delegations").status_code==200
