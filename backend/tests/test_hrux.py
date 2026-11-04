"""Employee lifecycle and identity UX contracts, disposable PostgreSQL only."""
from datetime import date,timedelta
from fastapi.testclient import TestClient
from app.main import app,SessionLocal
from app.employee_core import sync_probation_periods

ORIGIN={"Origin":"http://localhost:3000"}

def employee(name,email,code="",phone="9876543210",joined=None):
    return {"name":name,"email":email,"password":"SecureTempPass!1234","role":"employee",
            "designation":"Software Developer","department":"Engineering",
            "employee_code":code,"phone":phone,
            "joining_date":str(joined or date.today())}

def test_employee_ids_phone_password_and_deactivation():
    with TestClient(app) as c:
        assert c.post("/auth/login",json={"email":"admin@example.com","password":"test-admin-password-12345"}).status_code==200
        generated=c.post("/employees/generate-code",headers=ORIGIN)
        assert generated.status_code==200,generated.text
        code=generated.json()["employee_code"]
        number=int(code[3:])
        another=c.post("/employees/generate-code",headers=ORIGIN)
        assert int(another.json()["employee_code"][3:])==number+1
        invalid_phone=c.post("/core/employees",headers=ORIGIN,json={
            "account":employee("Test Invalid","invalid.phone.hrux@example.org",phone="1234567890"),"master":{}})
        assert invalid_phone.status_code==422,invalid_phone.text
        created=c.post("/core/employees",headers=ORIGIN,json={
            "account":employee("Ravi Tester","ravi.hrux@example.org",code,"+91 98765 43210"),"master":{}})
        assert created.status_code==201,created.text
        employee_id=created.json()["id"]
        assert created.json()["employee_code"]==code
        assert created.json()["phone"]=="+919876543210"
        assert created.json()["probation_end_date"]==(date.today()+timedelta(days=90)).isoformat()
        duplicate=c.post("/core/employees",headers=ORIGIN,json={
            "account":employee("Second Tester","second.hrux@example.org",code),"master":{}})
        assert duplicate.status_code==409,duplicate.text
        elevated=f"JG-{number+120:03d}"
        manual=c.post("/core/employees",headers=ORIGIN,json={
            "account":employee("Higher Number","higher.hrux@example.org",elevated),"master":{}})
        assert manual.status_code==201,manual.text
        next_code=c.post("/employees/generate-code",headers=ORIGIN)
        assert int(next_code.json()["employee_code"][3:])==number+121
        bad_reset=c.post(f"/core/employees/{employee_id}/reset-password",
                         headers=ORIGIN,json={"reason":"too short"})
        assert bad_reset.status_code==422
        reset=c.post(f"/core/employees/{employee_id}/reset-password",
                     headers=ORIGIN,json={"reason":"Employee lost account credentials"})
        assert reset.status_code==200,reset.text
        temp=reset.json()["temporary_password"]
        assert len(temp)>=20
        c.post("/auth/logout",headers=ORIGIN)
        assert c.post("/auth/login",json={"email":"ravi.hrux@example.org",
                                         "password":"SecureTempPass!1234"}).status_code==401
        assert c.post("/auth/login",json={"email":"ravi.hrux@example.org","password":temp}).status_code==200
        assert c.get(f"/core/employees/{employee_id}").status_code==200
        assert c.post(f"/core/employees/{employee_id}/deactivate",
                      headers=ORIGIN,json={"reason":"Employment ended by HR request"}).status_code==403
        c.post("/auth/logout",headers=ORIGIN)
        assert c.post("/auth/login",json={"email":"admin@example.com",
                                         "password":"test-admin-password-12345"}).status_code==200
        bad=c.post(f"/core/employees/{employee_id}/deactivate",
                   headers=ORIGIN,json={"reason":"short"})
        assert bad.status_code==422
        deactivated=c.post(f"/core/employees/{employee_id}/deactivate",
                           headers=ORIGIN,json={"reason":"End of assignment and formal exit"})
        assert deactivated.status_code==200,deactivated.text
        assert deactivated.json()["status"]=="inactive"
        history=c.get(f"/core/employees/{employee_id}/lifecycle").json()
        assert any(x["event"]=="deactivated" and "formal exit" in x["note"] for x in history)
        c.post("/auth/logout",headers=ORIGIN)
        assert c.post("/auth/login",json={"email":"ravi.hrux@example.org","password":temp}).status_code==401


def test_policy_records_and_90_day_confirmation():
    with TestClient(app) as c:
        assert c.post("/auth/login",json={"email":"admin@example.com",
                                         "password":"test-admin-password-12345"}).status_code==200
        policy=c.post("/policies/records",headers=ORIGIN,json={
            "title":"Bench Sales Attendance Policy","category":"attendance",
            "description":"Team members should submit attendance daily, including approved field visits.",
            "effective_date":str(date.today()),"active":True})
        assert policy.status_code==201,policy.text
        records=c.get("/policies/records")
        assert records.status_code==200
        assert any(x["id"]==policy.json()["id"] for x in records.json())
        joined=date.today()-timedelta(days=100)
        former=c.post("/core/employees",headers=ORIGIN,json={
            "account":employee("Older Joiner","older.joiner.hrux@example.org",joined=joined),
            "master":{}})
        assert former.status_code==201,former.text
        id=former.json()["id"]
        assert former.json()["effective_lifecycle"]=="confirmed"
        with SessionLocal() as db:
            assert sync_probation_periods(db)>=1
        updated=c.get(f"/core/employees/{id}")
        assert updated.status_code==200
        assert updated.json()["master"]["lifecycle"]=="confirmed"
        assert updated.json()["probation_days_remaining"]==0


def test_custom_project_number_and_generation():
    with TestClient(app) as c:
        assert c.post("/auth/login",json={"email":"admin@example.com",
                                         "password":"test-admin-password-12345"}).status_code==200
        owner=c.get("/me").json()["id"]
        generated=c.post("/project-management/generate-number",headers=ORIGIN)
        assert generated.status_code==200,generated.text
        code=generated.json()["project_number"]
        number=int(code[5:])
        draft={"name":"Manual Code QA Project","client":"QA Billing Client",
               "engagement_type":"c2c","rate":55,"sourced_by_id":owner,
               "start_date":str(date.today()),"project_number":code}
        saved=c.post("/project-management/projects",headers=ORIGIN,json=draft)
        assert saved.status_code==201,saved.text
        assert saved.json()["project_number"]==code
        dupe=c.post("/project-management/projects",headers=ORIGIN,json={
            **draft,"name":"Second Named Project"})
        assert dupe.status_code==409,dupe.text
        override=f"JG-P-{number+50:04d}"
        custom=c.post("/project-management/projects",headers=ORIGIN,json={
            **draft,"name":"Advanced Manual Project","project_number":override})
        assert custom.status_code==201,custom.text
        next_number=c.post("/project-management/generate-number",headers=ORIGIN)
        assert int(next_number.json()["project_number"][5:])==number+51
        malformed=c.post("/project-management/projects",headers=ORIGIN,json={
            **draft,"name":"Malformed Number","project_number":"BAD-12"})
        assert malformed.status_code==422
