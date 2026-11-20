"""Regression coverage for completed safeguards already on main."""
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app, SessionLocal, Employee
from app.payroll import calculate
from app.leave_management import LeaveRequest
from app.billing_reviews import ApprovedUnits
from test_pay_people import seed, login, configure, ORIGIN, PASS


def test_privileged_lifecycle_and_role_escalation_rejected():
    with TestClient(app) as client:
        admin_id, hr_id, employee_id, _ = seed(client)
        lifecycle = {"event": "exited", "note": "Verified security regression test"}
        assert client.post(f"/core/employees/{admin_id}/lifecycle",
                           json=lifecycle, headers=ORIGIN).status_code == 403
        account = {"name": "Unauthorized Superadmin", "email": "unauthorized.root.qa@example.org",
                   "password": PASS, "role": "super_admin", "designation": "QA",
                   "department": "Quality", "joining_date": date.today().isoformat()}
        assert client.post("/core/employees", headers=ORIGIN,
                           json={"account": account, "master": {}}).status_code == 403
        assert client.post("/employees", headers=ORIGIN, json=account).status_code == 410  # retired legacy endpoint
        client.post("/auth/logout", headers=ORIGIN)
        login(client, "payroll.hr.qa@example.org", PASS)
        assert client.post(f"/core/employees/{admin_id}/lifecycle",
                           headers=ORIGIN, json=lifecycle).status_code == 403


def test_partial_employee_update_keeps_reporting_manager():
    with TestClient(app) as client:
        admin, hr, employee_id, _ = seed(client)
        before = client.get(f"/core/employees/{employee_id}").json()
        assert before["master"]["manager_id"] == hr
        result = client.put(f"/core/employees/{employee_id}", headers=ORIGIN,
                            json={"address": "QA address updated without changing manager"})
        assert result.status_code == 200, result.text
        after = client.get(f"/core/employees/{employee_id}").json()
        assert after["master"]["manager_id"] == hr
        assert after["master"]["project_bonus_inr"] == before["master"]["project_bonus_inr"]
        invalid = client.put(f"/core/employees/{employee_id}", headers=ORIGIN,
                             json={"manager_id": None})
        assert invalid.status_code == 422


def test_half_day_lop_uses_approved_leave_duration_not_calendar_day():
    with TestClient(app) as client:
        _, hr, employee_id, _ = seed(client)
        configure(client, employee_id)
        current = date.today()
        target = date(current.year, current.month, 1)
        while target.weekday() >= 5:
            target += timedelta(days=1)
        with SessionLocal() as session:
            person = session.get(Employee, employee_id)
            person.joining_date = date(current.year, current.month, 1)
            session.flush()
            baseline = calculate(session, person, current.strftime("%Y-%m"))
            record = LeaveRequest(employee_id=employee_id, leave_type="loss_of_pay",
                                  start_date=target, end_date=target,
                                  day_part="half", days=Decimal("0.5"),
                                  reason="Half-day payroll regression", status="approved",
                                  chain="manager", current_stage=1,
                                  manager_snapshot_id=hr)
            session.add(record)
            session.flush()
            changed = calculate(session, person, current.strftime("%Y-%m"))
            assert changed["lop_days"] - baseline["lop_days"] == Decimal("0.5")
            session.rollback()


def test_reviewed_billing_tax_defaults_to_project_configuration():
    assert ApprovedUnits(quantity=Decimal("10")).tax_rate_pct is None
    assert ApprovedUnits(quantity=Decimal("10"), tax_rate_pct=Decimal("0")).tax_rate_pct == 0
