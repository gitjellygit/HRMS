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
                       "role":"super_admin", "designation":"QA"},
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
