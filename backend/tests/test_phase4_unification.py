"""Phase 4 canonical leave views, settlement gates and delivery queue coverage."""
from datetime import date
from fastapi.testclient import TestClient
from app.main import app,SessionLocal
from app.leave_management import LeaveEmailDelivery,deliver_queued_emails,notify
from test_pay_people import seed,ORIGIN


def test_legacy_leave_routes_do_not_disagree_with_canonical_dashboard():
    with TestClient(app) as c:
        admin,hr,worker,other=seed(c)
        assert c.get("/core/hr-overview",headers=ORIGIN).status_code==410
        assert c.put("/core/leave-entitlements",headers=ORIGIN,json={}).status_code==410
        assert c.get("/leaves",headers=ORIGIN).status_code==410
        current=c.get("/leave/hr-overview",headers=ORIGIN)
        assert current.status_code==200,current.text
        dashboard=c.get("/dashboard",headers=ORIGIN)
        assert dashboard.status_code==200,dashboard.text
        assert dashboard.json()["pending_leaves"]==current.json()["pending_leave_requests"]


def test_employee_lifecycle_exit_requires_settled_case():
    with TestClient(app) as c:
        admin,hr,worker,other=seed(c)
        attempt=c.post(f"/core/employees/{worker}/lifecycle",headers=ORIGIN,json={
            "event":"exited","note":"Employee departure after the planned notice period.",
            "effective_date":date.today().isoformat()})
        assert attempt.status_code==409,attempt.text
        assert attempt.json()["detail"]["field"]=="exit_case"


def test_leave_email_outbox_is_durable_and_worker_can_retry(monkeypatch):
    with TestClient(app) as c:
        admin,hr,worker,other=seed(c)
        with SessionLocal() as db:
            notify(db,hr,"Test leave approval pending from direct manager",None)
            db.commit()
        entries=c.get("/leave/email-outbox",headers=ORIGIN)
        assert entries.status_code==200,entries.text
        row=next(item for item in entries.json()
                 if item["recipient_id"]==hr and item["status"]=="queued")
        email_id=row["id"]
        calls=[]
        monkeypatch.setattr("app.leave_management.email_notice",
                            lambda address,subject,message:calls.append((address,subject,message)))
        with SessionLocal() as db:
            result=deliver_queued_emails(db,limit=100)
        assert result["delivered"]>=1
        assert any("payroll.hr.qa@example.org"==call[0] for call in calls)
        with SessionLocal() as db:
            item=db.get(LeaveEmailDelivery,email_id)
            assert item.status=="sent" and item.attempts==1 and item.sent_at is not None
        again=c.post(f"/leave/email-outbox/{email_id}/retry",headers=ORIGIN)
        assert again.status_code==409
