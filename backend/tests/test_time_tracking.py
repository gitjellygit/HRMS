"""Attendance/time 23–30 security and workflow tests; disposable CI PostgreSQL."""
from datetime import date,datetime,timedelta,timezone
from fastapi.testclient import TestClient
from app.main import app

ORIGIN={"Origin":"http://localhost:3000"}
PASS="ExampleStrong!Pass678"

def sign(c,email,password=PASS):
    r=c.post("/auth/login",json={"email":email,"password":password})
    assert r.status_code==200,r.text

def add(c,name,email,role,manager):
    r=c.post("/core/employees",headers=ORIGIN,json={"account":{
        "name":name,"email":email,"password":PASS,"role":role,
        "designation":"QA Engineer","department":"Engineering",
        "joining_date":str(date.today())},"master":{"manager_id":manager}})
    assert r.status_code==201,r.text
    return r.json()["id"]

def seed(c):
    sign(c,"admin@example.com","test-admin-password-12345")
    admin=c.get("/me").json()["id"]
    manager=add(c,"Time Manager","time.manager.qa@example.org","manager",admin)
    worker=add(c,"Time Worker","time.worker.qa@example.org","employee",manager)
    colleague=add(c,"Time Colleague","time.colleague.qa@example.org","employee",manager)
    return admin,manager,worker,colleague

def test_time_requests_and_manager_authorization():
    with TestClient(app) as c:
        admin,manager,worker,colleague=seed(c)
        c.post("/auth/logout",headers=ORIGIN)
        sign(c,"time.worker.qa@example.org")
        work_date=date.today()-timedelta(days=3)
        bad=c.post("/time/requests",headers=ORIGIN,json={"kind":"overtime",
            "work_date":str(work_date),"reason":"Performed extended work on project"})
        assert bad.status_code==422
        request=c.post("/time/requests",headers=ORIGIN,json={"kind":"overtime",
            "work_date":str(work_date),"hours":2,"reason":"Performed extended project work"})
        assert request.status_code==201,request.text
        req_id=request.json()["id"]
        assert c.get("/time/requests").json()[0]["id"]==req_id
        assert c.get("/time/requests?scope=all").status_code==403
        assert c.post(f"/time/requests/{req_id}/review?approve=true",headers=ORIGIN).status_code==403
        c.post("/auth/logout",headers=ORIGIN)
        sign(c,"time.colleague.qa@example.org")
        assert c.post(f"/time/requests/{req_id}/review?approve=true",headers=ORIGIN).status_code==403
        c.post("/auth/logout",headers=ORIGIN)
        sign(c,"time.manager.qa@example.org")
        assert any(r["id"]==req_id for r in c.get("/time/requests?scope=approvals").json())
        approved=c.post(f"/time/requests/{req_id}/review?approve=true",headers=ORIGIN)
        assert approved.status_code==200,approved.text
        assert approved.json()["status"]=="approved"
        assert c.post(f"/time/requests/{req_id}/review?approve=false",headers=ORIGIN).status_code==409
        assert c.get(f"/time/audits/{req_id}").status_code==200

def test_shifts_rosters_swap_colleague_consent_and_timesheets():
    with TestClient(app) as c:
        admin,manager,worker,colleague=seed(c)
        first=c.post("/time/shifts",headers=ORIGIN,json={
            "name":"Office day","start_time":"09:00","end_time":"18:00","break_minutes":60})
        second=c.post("/time/shifts",headers=ORIGIN,json={
            "name":"Evening support","start_time":"15:00","end_time":"00:00","break_minutes":45})
        assert first.status_code==201 and second.status_code==201
        a,b=first.json()["id"],second.json()["id"]
        day=str(date.today()+timedelta(days=7))
        for who,shift in [(worker,a),(colleague,b)]:
            r=c.put("/time/roster",headers=ORIGIN,json={"employee_id":who,"shift_id":shift,"work_date":day})
            assert r.status_code==200,r.text
        c.post("/auth/logout",headers=ORIGIN)
        sign(c,"time.worker.qa@example.org")
        swapped=c.post("/time/requests",headers=ORIGIN,json={"kind":"shift_swap",
            "target_employee_id":colleague,"work_date":day,"reason":"Exchange for appointment coverage"})
        assert swapped.status_code==201,swapped.text
        req=swapped.json()["id"]
        assert swapped.json()["status"]=="pending_colleague"
        assert c.post(f"/time/requests/{req}/review?approve=true",headers=ORIGIN).status_code==403
        c.post("/auth/logout",headers=ORIGIN)
        sign(c,"time.colleague.qa@example.org")
        assert c.post(f"/time/requests/{req}/colleague-response?accept=true",headers=ORIGIN).status_code==200
        c.post("/auth/logout",headers=ORIGIN)
        sign(c,"time.manager.qa@example.org")
        assert c.post(f"/time/requests/{req}/review?approve=true",headers=ORIGIN).status_code==200
        c.post("/auth/logout",headers=ORIGIN)
        sign(c,"time.worker.qa@example.org")
        roster=c.get("/time/roster")
        assert roster.status_code==200 and roster.json()[0]["shift_id"]==b
        work=c.post("/time/timesheets",headers=ORIGIN,json={"work_date":str(date.today()),
            "task":"Prepare release checklist","hours":3,"note":"Completed QA tests"})
        assert work.status_code==201,work.text
        assert c.post("/time/timesheets",headers=ORIGIN,json={
            "work_date":str(date.today()),"task":"Impossible hours","hours":22}).status_code==422
        assert c.post(f"/time/timesheets/{work.json()['id']}/submit",headers=ORIGIN).json()["status"]=="submitted"

def test_geofence_cannot_be_bypassed_and_biometric_needs_device_secret():
    with TestClient(app) as c:
        admin,manager,worker,colleague=seed(c)
        p=c.put("/time/policy",headers=ORIGIN,json={
            "location":"all","geo_required":True,"office_lat":23.2500,"office_lon":77.4100,
            "radius_meters":250,"grace_minutes":10,"half_day_under_hours":4,
            "overtime_after_hours":9,"auto_deduct":False})
        assert p.status_code==200,p.text
        c.post("/auth/logout",headers=ORIGIN)
        sign(c,"time.worker.qa@example.org")
        assert c.post("/attendance/punch",headers=ORIGIN).status_code==403
        assert c.post("/time/punch",headers=ORIGIN,json={
            "consent":True,"lat":23.30,"lon":77.49,"accuracy_m":5}).status_code==403
        check=c.post("/time/punch",headers=ORIGIN,json={
            "consent":True,"lat":23.2500,"lon":77.4100,"accuracy_m":8})
        assert check.status_code==200,check.text
        check2=c.post("/time/punch",headers=ORIGIN,json={
            "consent":True,"lat":23.2500,"lon":77.4100,"accuracy_m":8})
        assert check2.status_code==200 and check2.json()["punch_out"] is not None
        assert c.get("/time/daily").json()[0]["sessions"]>=1
        c.post("/auth/logout",headers=ORIGIN)
        assert c.post("/time/biometric/events",json={
            "device_event_id":"test-device-qa-0001","employee_id":worker,
            "direction":"in","observed_at":datetime.now(timezone.utc).isoformat()}).status_code==403

def test_regularization_creates_an_audited_corrected_session():
    with TestClient(app) as c:
        admin,manager,worker,colleague=seed(c)
        c.post("/auth/logout",headers=ORIGIN)
        sign(c,"time.worker.qa@example.org")
        start=datetime.now(timezone.utc)-timedelta(days=10,hours=3)
        end=start+timedelta(hours=6)
        request=c.post("/time/requests",headers=ORIGIN,json={
            "kind":"regularization","work_date":start.date().isoformat(),
            "reason":"Missed both punches due to a system outage",
            "proposed_in":start.isoformat(),"proposed_out":end.isoformat()})
        assert request.status_code==201,request.text
        c.post("/auth/logout",headers=ORIGIN)
        sign(c,"time.manager.qa@example.org")
        approve=c.post("/time/requests/"+str(request.json()["id"])+"/review?approve=true",headers=ORIGIN)
        assert approve.status_code==200,approve.text
        assert approve.json()["status"]=="approved"
