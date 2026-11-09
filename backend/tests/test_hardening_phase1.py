"""Security and data-integrity regressions for phase-1 hardening."""
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app, SessionLocal
from app.employee_core import EmployeeCore
from test_pay_people import seed, login, ORIGIN, PASS


def switch(client, email, password=PASS):
    client.post("/auth/logout", headers=ORIGIN)
    login(client, email, password)


def test_privileged_lifecycle_and_role_creation_are_blocked():
    with TestClient(app) as client:
        admin, hr, worker, _ = seed(client)
        lifecycle = {"event":"exited","note":"Security regression test must deny this exit"}
        assert client.post(f"/core/employees/{admin}/lifecycle",
                           headers=ORIGIN, json=lifecycle).status_code == 403
        elevated = client.post("/core/employees", headers=ORIGIN, json={
            "account":{"email":"security.no.super.qa@example.org",
                       "name":"Disallowed Super Admin", "password":PASS,
                       "role":"super_admin", "designation":"QA","department":"Quality"},
            "master":{}
        })
        assert elevated.status_code == 403, elevated.text
        switch(client, "payroll.hr.qa@example.org")
        assert client.post(f"/core/employees/{admin}/lifecycle",
                           headers=ORIGIN, json=lifecycle).status_code == 403


def test_partial_master_update_keeps_manager_and_legacy_writes_retired():
    with TestClient(app) as client:
        _, hr, worker, _ = seed(client)
        with SessionLocal() as db:
            original = db.get(EmployeeCore, worker)
            assert original is not None
            manager_id = original.manager_id
            bonus = original.project_bonus_inr
        response = client.put(f"/core/employees/{worker}", headers=ORIGIN,
                              json={"address":"Test address, never personal data"})
        assert response.status_code == 200, response.text
        with SessionLocal() as db:
            updated = db.get(EmployeeCore, worker)
            assert updated.manager_id == manager_id
            assert updated.project_bonus_inr == bonus
        assert client.put(f"/core/employees/{worker}", headers=ORIGIN,
                          json={"manager_id":None}).status_code == 422
        assert client.post("/employees", headers=ORIGIN, json={
            "name":"Legacy employee", "email":"legacy.qa@example.org",
            "password":PASS,"role":"employee","designation":"Test employee", "department":"Quality"}).status_code == 410
        assert client.post("/leaves", headers=ORIGIN, json={
            "leave_type":"casual", "start_date":"2026-11-13",
            "end_date":"2026-11-13", "reason":"Legacy bypass"}).status_code == 410


def test_invalid_sensitive_change_returns_field_error():
    with TestClient(app) as client:
        seed(client)
        switch(client, "payroll.person.qa@example.org")
        for field, invalid in (("pan","INVALID"), ("aadhaar","1234"), ("bank_ifsc","bad")):
            r=client.post("/core/me/change-requests",headers=ORIGIN,
                          json={"field_name":field,"value":invalid})
            assert r.status_code == 422, r.text
            assert r.json()["detail"]["field"] == field


def test_case_insensitive_login_and_reset_email_privacy(monkeypatch):
    from fastapi import HTTPException
    def broken_mail(*args, **kwargs):
        raise HTTPException(503, "SMTP unavailable")
    with TestClient(app) as client:
        seed(client)
        client.post("/auth/logout",headers=ORIGIN)
        upper=client.post("/auth/login",json={
            "email":"ADMIN@EXAMPLE.COM","password":"test-admin-password-12345"})
        assert upper.status_code==200,upper.text
        monkeypatch.setattr("app.main.send_reset_mail",broken_mail)
        existing=client.post("/auth/forgot-password",headers=ORIGIN,json={
            "email":"payroll.person.qa@example.org"})
        unknown=client.post("/auth/forgot-password",headers=ORIGIN,json={
            "email":"nonexistent.reset.qa@example.org"})
        assert existing.status_code==200,existing.text
        assert unknown.status_code==200,unknown.text
        assert existing.json()==unknown.json()


def test_login_five_failures_lock_and_notify_hr():
    with TestClient(app) as client:
        admin,hr,worker,_=seed(client)
        client.post("/auth/logout",headers=ORIGIN)
        for number in range(1,6):
            result=client.post("/auth/login",json={
                "email":"payroll.person.qa@example.org","password":"Incorrect!Password123"})
            assert result.status_code==(423 if number==5 else 401),result.text
        valid=client.post("/auth/login",json={
            "email":"payroll.person.qa@example.org","password":PASS})
        assert valid.status_code==423
        login(client,"admin@example.com","test-admin-password-12345")
        locks=client.get("/security/login-lockouts")
        assert locks.status_code==200,locks.text
        assert any(x["employee_id"]==worker and x["failed_attempts"]==5 for x in locks.json())
        inbox=client.get("/notification-center").json()["items"]
        assert any(x["event"]=="security" and "locked" in x["title"].lower() for x in inbox)
        unlocked=client.post(f"/security/login-lockouts/{worker}/unlock",headers=ORIGIN)
        assert unlocked.status_code==200,unlocked.text
        client.post("/auth/logout",headers=ORIGIN)
        login(client,"payroll.person.qa@example.org",PASS)


def test_first_login_requires_employee_password_change():
    with TestClient(app) as client:
        login(client,"admin@example.com","test-admin-password-12345")
        admin_id=client.get("/me").json()["id"]
        new_user=client.post("/core/employees",headers=ORIGIN,json={
            "account":{"email":"first.login.qa@example.org",
                       "name":"First Login QA","password":PASS,"role":"employee",
                       "designation":"QA Specialist","department":"Quality"},
            "master":{"manager_id":admin_id}})
        assert new_user.status_code==201,new_user.text
        client.post("/auth/logout",headers=ORIGIN)
        first=client.post("/auth/login",json={
            "email":"first.login.qa@example.org","password":PASS})
        assert first.status_code==200,first.text
        assert first.json()["user"]["must_change_password"] is True
        assert client.get("/dashboard").status_code==403
        chosen="NewlyChosen!Password789"
        updated=client.post("/auth/change-password",headers=ORIGIN,
                            json={"current_password":PASS,"new_password":chosen})
        assert updated.status_code==200,updated.text
        assert client.get("/dashboard").status_code==401
        relogin=client.post("/auth/login",json={
            "email":"first.login.qa@example.org","password":chosen})
        assert relogin.status_code==200,relogin.text
        assert relogin.json()["user"]["must_change_password"] is False
        assert client.get("/dashboard").status_code==200
