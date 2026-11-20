"""Protect draft payroll against incomplete employee setup and unsafe recalculation."""
from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app
from test_pay_people import seed, configure, ORIGIN


def test_missing_salary_does_not_block_draft_and_can_be_recalculated():
    with TestClient(app) as client:
        admin,hr,person,other=seed(client)
        period=date.today().strftime("%Y-%m")
        # No employee has a salary structure yet: create an exception-marked draft,
        # never an apparently payable zero-salary payroll.
        made=client.post("/payroll/runs",headers=ORIGIN,json={"period":period})
        assert made.status_code==201,made.text
        run_id=made.json()["id"]
        before=client.get(f"/payroll/runs/{run_id}")
        assert before.status_code==200,before.text
        errors=[line for line in before.json()["lines"] if line["exceptions"].startswith("Payroll setup:")]
        assert any(line["employee_id"]==person for line in errors)
        assert all(Decimal(str(line["net"]))==0 for line in errors)
        assert client.post("/payroll/runs",headers=ORIGIN,json={"period":period}).status_code==409
        # A second-person approver still cannot approve incomplete salary data.
        client.post("/auth/logout",headers=ORIGIN)
        sign=client.post("/auth/login",json={
            "email":"payroll.hr.qa@example.org","password":"IntegrationTest!Pass123"})
        assert sign.status_code==200,sign.text
        denied=client.post(f"/payroll/runs/{run_id}/approve",headers=ORIGIN)
        assert denied.status_code==409,denied.text
        client.post("/auth/logout",headers=ORIGIN)
        admin_login=client.post("/auth/login",json={
            "email":"admin@example.com","password":"test-admin-password-12345"})
        assert admin_login.status_code==200,admin_login.text
        configure(client,person)
        adjusted=client.post(f"/payroll/runs/{run_id}/recalculate",headers=ORIGIN)
        assert adjusted.status_code==200,adjusted.text
        after=client.get(f"/payroll/runs/{run_id}").json()
        revised=next(line for line in after["lines"] if line["employee_id"]==person)
        assert not revised["exceptions"].startswith("Payroll setup:")
        assert Decimal(str(revised["gross"])) > 0
        assert any(line["exceptions"].startswith("Payroll setup:") for line in after["lines"]
                   if line["employee_id"]!=person)
        assert client.post(f"/payroll/runs/{run_id}/recalculate",headers=ORIGIN).status_code==200
        assert after["status"]=="draft"
