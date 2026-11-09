"""Financial correctness tests for voids, tax defaults and missed final billing."""
from datetime import date, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app, SessionLocal
from app.billing_reviews import BillableReview
from test_pay_people import seed, ORIGIN
from test_finance_pricing_salary_components import placement


def configure(client, project, tax="5.00", end=None):
    cfg={"recipient_name":"Pilot Invoice Customer","recipient_email":"billing@example.org",
         "billing_frequency":"monthly","billing_day":15,"payment_terms_days":15,
         "rate_unit":"hour","invoice_rate":"100.00","tax_rate_pct":tax}
    res=client.put(f"/finance/projects/{project}/configuration",headers=ORIGIN,json=cfg)
    assert res.status_code==200,res.text
    if end is not None:
        scheduled=client.put(f"/finance/projects/{project}/billing",headers=ORIGIN,json={
            "recipient_type":"client","recipient_name":"Pilot Invoice Customer",
            "recipient_email":"billing@example.org","billing_day":15,
            "payment_terms_days":15,"billing_frequency":"monthly",
            "end_date":end.isoformat()})
        assert scheduled.status_code==200,scheduled.text


def test_voided_invoice_can_be_replaced_with_same_window():
    with TestClient(app) as c:
        _,_,owner,_=seed(c)
        project=placement(c,owner)
        configure(c,project)
        service_start=date.today()-timedelta(days=2)
        window={"project_id":project,"period_start":service_start.isoformat(),
                "period_end":date.today().isoformat(),"quantity":"2"}
        first=c.post("/finance/invoices",headers=ORIGIN,json=window)
        assert first.status_code==201,first.text
        assert Decimal(str(first.json()["tax_amount"]))==Decimal("10.00")
        void=c.post(f'/finance/invoices/{first.json()["id"]}/status',
                    headers=ORIGIN,json={"status":"void","reference":"Wrong invoice; reissue"})
        assert void.status_code==200,void.text
        replacement=c.post("/finance/invoices",headers=ORIGIN,json=window)
        assert replacement.status_code==201,replacement.text
        assert replacement.json()["id"]!=first.json()["id"]
        assert Decimal(str(replacement.json()["tax_amount"]))==Decimal("10.00")
        assert c.post("/finance/invoices",headers=ORIGIN,json=window).status_code==409


def test_review_without_tax_override_uses_configured_rate():
    with TestClient(app) as c:
        _,_,owner,_=seed(c)
        project=placement(c,owner)
        configure(c,project,tax="12.00")
        with SessionLocal() as db:
            task=BillableReview(project_id=project,period_start=date.today()-timedelta(days=2),
                 period_end=date.today(),scheduled_on=date.today(),status="needs_units")
            db.add(task);db.commit();db.refresh(task)
            task_id=task.id
        response=c.post(f"/finance/reviews/{task_id}/invoice",
                        headers=ORIGIN,json={"quantity":"3"})
        assert response.status_code==201,response.text
        assert Decimal(str(response.json()["tax_rate_pct"]))==Decimal("12.00")
        assert Decimal(str(response.json()["tax_amount"]))==Decimal("36.00")


def test_missed_final_billing_period_creates_review_before_archiving():
    with TestClient(app) as c:
        _,_,owner,_=seed(c)
        project=placement(c,owner)
        yesterday=date.today()-timedelta(days=1)
        configure(c,project,end=yesterday)
        response=c.post("/finance/schedules/run",headers=ORIGIN,
                        json={"project_id":project,"as_of":date.today().isoformat()})
        assert response.status_code==200,response.text
        tasks=response.json()["tasks_created"]
        assert len(tasks)==1,response.json()
        assert tasks[0]["period_end"]==yesterday.isoformat()
        listed=c.get("/finance/projects").json()
        record=next(x for x in listed if x["id"]==project)
        assert record["status"]=="inactive"
        billed=c.post(f'/finance/reviews/{tasks[0]["id"]}/invoice',
                     headers=ORIGIN,json={"quantity":"2"})
        assert billed.status_code==201,billed.text


def test_ended_project_can_reissue_voided_invoice_with_explicit_audit_link():
    with TestClient(app) as c:
        _,_,owner,_=seed(c)
        project=placement(c,owner)
        ended=date.today()-timedelta(days=1)
        configure(c,project,end=ended)
        window={"project_id":project,
                "period_start":(ended-timedelta(days=1)).isoformat(),
                "period_end":ended.isoformat(),"quantity":"5"}
        original=c.post("/finance/invoices",headers=ORIGIN,json=window)
        assert original.status_code==201,original.text
        original_id=original.json()["id"]
        void=c.post(f"/finance/invoices/{original_id}/status",headers=ORIGIN,
                    json={"status":"void","reference":"Billing correction before project closure"})
        assert void.status_code==200,void.text
        exit=c.put(f"/finance/projects/{project}/lifecycle",headers=ORIGIN,json={
            "active":False,"reason":"Project has reached the contractual end date.",
            "end_date":ended.isoformat()})
        assert exit.status_code==200,exit.text
        assert exit.json()["status"]=="inactive"
        manual=c.post("/finance/invoices",headers=ORIGIN,json=window)
        assert manual.status_code==409,manual.text
        invalid=c.post("/finance/invoices",headers=ORIGIN,json={
            **window,"replaces_invoice_id":999999})
        assert invalid.status_code==422,invalid.text
        replacement=c.post("/finance/invoices",headers=ORIGIN,json={
            **window,"replaces_invoice_id":original_id})
        assert replacement.status_code==201,replacement.text
        assert replacement.json()["replaces_invoice_id"]==original_id
        assert replacement.json()["source"]=="replacement"
        assert replacement.json()["id"]!=original_id
        assert c.post("/finance/invoices",headers=ORIGIN,json={
            **window,"replaces_invoice_id":original_id}).status_code==409
        history=c.get(f"/finance/invoices?project_id={project}")
        assert history.status_code==200
        assert len(history.json())==2
        assert any(v["stored_status"]=="void" for v in history.json())
