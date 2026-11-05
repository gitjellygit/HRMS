"""Finance/governance acceptance and boundary regression suite.

120 deterministic boundary cases + live PostgreSQL user-role workflows.
These tests operate on a disposable CI database, never production.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app, SessionLocal, Employee
from app.project_finance import live_period, ClientInvoice, ProjectBilling
from app.leave_management import prorated_entitlement, fy_bounds, fy_start_year
from test_pay_people import login, create, seed, PASS, ORIGIN

today=date.today()
def sign_out(c):
    c.post("/auth/logout",headers=ORIGIN)
def switch(c,email,password=PASS):
    sign_out(c);login(c,email,password)

@pytest.mark.parametrize("idx",range(80),ids=lambda i:"invoice-window-%03d"%i)
def test_invoice_period_boundaries(idx):
    # Exercise start-date, end-date, inactive-state and future-service guards.
    start_offset=1+(idx%8)
    duration=idx//8
    start=today-timedelta(days=start_offset)
    end=start+timedelta(days=duration)
    p=SimpleNamespace(status="inactive" if idx%13==0 else "active")
    d=SimpleNamespace(start_date=start)
    cap=today-timedelta(days=3) if idx%5==0 else None
    profile=SimpleNamespace(stopped_at=None,end_date=cap)
    # The expected precedence follows the public business rule: inactive first,
    # then future service, then contractual end cap.
    invalid=p.status!="active" or end>today or (cap is not None and end>cap)
    if invalid:
        with pytest.raises(HTTPException) as exc:
            live_period(p,d,profile,start,end,today)
        assert exc.value.status_code in (409,422)
    else:
        assert live_period(p,d,profile,start,end,today) is None

@pytest.mark.parametrize("idx",range(40),ids=lambda i:"joining-prorata-%03d"%i)
def test_joining_proration_rounding_and_boundaries(idx):
    fy=today.year-1 if today.month<4 else today.year
    lo,hi=fy_bounds(fy)
    annual=Decimal("12") if idx%2==0 else Decimal("18")
    joining=lo+timedelta(days=idx*9)
    if joining>hi:joining=hi
    days=max(0,(hi-max(lo,joining)).days+1)
    calendar=(hi-lo).days+1
    expected=((annual*Decimal(days)/Decimal(calendar)*2).quantize(
        Decimal("1"),rounding=ROUND_HALF_UP))/2
    assert prorated_entitlement(annual,joining,fy)==expected
    assert Decimal(0)<=expected<=annual

def setup_project(c,sourced_id,days_back=20):
    unique=str(datetime.now().timestamp()).replace(".","")
    payload={"name":"QA placement "+unique,"client":"Bensys Client",
      "candidate_name":"QA Candidate","vendor_name":"QA Vendor",
      "prime_vendor_name":"QA Prime Vendor","engagement_type":"c2c",
      "rate":"125.00","currency":"USD","rate_unit":"hour",
      "sourced_by_id":sourced_id,"start_date":(today-timedelta(days=days_back)).isoformat()}
    r=c.post("/project-management/projects",headers=ORIGIN,json=payload)
    assert r.status_code==201,r.text
    return r.json()["id"]

def billing(c,project_id,recipient="client",end_date=None,day=15):
    r=c.put(f"/finance/projects/{project_id}/billing",headers=ORIGIN,json={
      "recipient_type":recipient,"recipient_name":"QA Invoice Recipient",
      "recipient_email":"billing.qa@example.org","recipient_phone":"+1-212-555-0131",
      "billing_address":"Test business address","billing_day":day,
      "payment_terms_days":10,"end_date":end_date.isoformat() if end_date else None})
    assert r.status_code==200,r.text
    return r.json()

def test_accountant_sees_candidate_and_vendor_but_cannot_manage_project():
    with TestClient(app) as c:
        admin,hr,one,other=seed(c)
        accountant=create(c,"finance.qa@example.org","Finance Accountant","accountant",admin)
        p=setup_project(c,one)
        switch(c,"finance.qa@example.org")
        seen=c.get("/finance/projects")
        assert seen.status_code==200,seen.text
        record=next(x for x in seen.json() if x["id"]==p)
        assert record["candidate_name"]=="QA Candidate"
        assert record["vendor_name"]=="QA Vendor"
        assert record["sourced_by_id"]==one and record["rate"]==125
        assert c.get("/project-management/projects/"+str(p)).status_code==200
        assert c.post("/project-management/projects",headers=ORIGIN,json={}).status_code==403
        assert c.put(f"/finance/projects/{p}/lifecycle",headers=ORIGIN,json={
          "active":False,"reason":"Cannot deactivate as accountant"}).status_code==403
        billing(c,p,recipient="vendor")
        switch(c,"payroll.person.qa@example.org")
        assert c.get("/finance/projects").status_code==403
        assert c.get("/finance/invoices").status_code==403

def test_manual_invoice_status_pdf_payment_and_duplicate_period():
    with TestClient(app) as c:
        admin,hr,one,other=seed(c)
        p=setup_project(c,one)
        billing(c,p,"candidate")
        switch(c,"finance.qa@example.org")
        start=today-timedelta(days=5)
        form={"project_id":p,"period_start":start.isoformat(),"period_end":today.isoformat(),
              "quantity":"40.00","tax_rate_pct":"5.00","issue_date":today.isoformat()}
        r=c.post("/finance/invoices",headers=ORIGIN,json=form)
        assert r.status_code==201,r.text
        invoice=r.json();iid=invoice["id"]
        assert Decimal(str(invoice["subtotal"]))==Decimal("5000.00")
        assert Decimal(str(invoice["tax_amount"]))==Decimal("250.00")
        assert Decimal(str(invoice["total"]))==Decimal("5250.00")
        assert invoice["recipient_type"]=="candidate"
        pdf=c.get(f"/finance/invoices/{iid}.pdf")
        assert pdf.status_code==200 and pdf.content.startswith(b"%PDF-")
        assert c.post("/finance/invoices",headers=ORIGIN,json=form).status_code==409
        assert c.post(f"/finance/invoices/{iid}/status",headers=ORIGIN,json={
            "status":"paid"}).status_code==409
        assert c.post(f"/finance/invoices/{iid}/status",headers=ORIGIN,json={
            "status":"sent","reference":"QA dispatched by accounts"}).status_code==200
        paid=c.post(f"/finance/invoices/{iid}/status",headers=ORIGIN,json={
            "status":"paid","reference":"BANK-QA-001"})
        assert paid.status_code==200,paid.text
        assert paid.json()["status"]=="paid"
        assert c.post(f"/finance/invoices/{iid}/status",headers=ORIGIN,json={
            "status":"void"}).status_code==409
        switch(c,"payroll.other.qa@example.org")
        assert c.get(f"/finance/invoices/{iid}.pdf").status_code==403

def test_inactive_project_never_generates_manual_or_scheduled_bills():
    with TestClient(app) as c:
        admin,hr,one,other=seed(c)
        p=setup_project(c,one)
        billing(c,p)
        state=c.put(f"/finance/projects/{p}/lifecycle",headers=ORIGIN,json={
            "active":False,"reason":"Placement terminated after final approved period"})
        assert state.status_code==200,state.text
        assert state.json()["status"]=="inactive"
        bill=c.post("/finance/invoices",headers=ORIGIN,json={
           "project_id":p,"period_start":(today-timedelta(days=3)).isoformat(),
           "period_end":today.isoformat(),"quantity":"1","tax_rate_pct":"0"})
        assert bill.status_code==409
        schedule=c.post("/finance/schedules/run",headers=ORIGIN,json={
            "as_of":today.isoformat(),"project_id":p})
        assert schedule.status_code==200 and schedule.json()["created"]==[]
        assert c.put(f"/finance/projects/{p}/billing",headers=ORIGIN,json={
            "recipient_type":"vendor","recipient_name":"Unexpected Invoice",
            "billing_day":15}).status_code==409

def test_final_invoice_respects_contract_end_and_stops_later_schedule():
    with TestClient(app) as c:
        admin,hr,one,other=seed(c)
        p=setup_project(c,one)
        end=today-timedelta(days=2)
        billing(c,p,end_date=end)
        impossible=c.post("/finance/invoices",headers=ORIGIN,json={
           "project_id":p,"period_start":(end-timedelta(days=2)).isoformat(),
           "period_end":today.isoformat(),"quantity":3,"tax_rate_pct":0})
        assert impossible.status_code==409
        accepted=c.post("/finance/invoices",headers=ORIGIN,json={
           "project_id":p,"period_start":(end-timedelta(days=2)).isoformat(),
           "period_end":end.isoformat(),"quantity":3,"tax_rate_pct":0})
        assert accepted.status_code==201,accepted.text
        assert accepted.json()["period_end"]==end.isoformat()
        schedule=c.post("/finance/schedules/run",headers=ORIGIN,json={
           "as_of":today.isoformat(),"project_id":p})
        assert schedule.status_code==200,schedule.text
        assert not schedule.json()["created"]
        assert any(x["reason"]=="project ended; schedule disabled" for x in schedule.json()["skipped"])
        assert c.get("/finance/projects").json()[0]["status"] in ("active","inactive")

def test_policy_requires_independent_admin_and_reason_for_leave_override():
    with TestClient(app) as c:
        admin,hr,one,other=seed(c)
        switch(c,"payroll.hr.qa@example.org")
        assert c.post("/policies/records",headers=ORIGIN,json={
         "title":"Wrong direct publishing","category":"general",
         "description":"HR must not publish this without approval",
         "effective_date":today.isoformat()}).status_code==403
        assert c.put("/leave/allocations",headers=ORIGIN,json={
         "employee_id":one,"year":fy_start_year(today),"leave_type":"casual",
         "allocated_days":15}).status_code==403
        proposed=c.post("/governance/requests",headers=ORIGIN,json={
         "kind":"company_policy","reason":"Update employee orientation requirements",
         "payload":{"title":"QA Orientation "+str(datetime.now().timestamp()),
          "category":"onboarding","description":"Every new staff member must complete the orientation checklist.",
          "effective_date":today.isoformat(),"active":True}})
        assert proposed.status_code==201,proposed.text
        req=proposed.json()["id"]
        assert c.post(f"/governance/requests/{req}/review",headers=ORIGIN,json={
         "approve":True,"reason":"HR should not approve its own request."}).status_code==403
        switch(c,"payroll.person.qa@example.org")
        assert c.get("/governance/requests").status_code==403
        switch(c)
        review=c.post(f"/governance/requests/{req}/review",headers=ORIGIN,json={
          "approve":True,"reason":"Reviewed and approved as company policy"})
        assert review.status_code==200,review.text
        assert c.post(f"/governance/requests/{req}/review",headers=ORIGIN,json={
          "approve":True,"reason":"Duplicate admin approval request"}).status_code==409
        assert any(x["title"].startswith("QA Orientation") for x in c.get("/policies/records").json())

def test_leave_manual_allocation_requires_approval_and_updates_balance():
    with TestClient(app) as c:
        admin,hr,one,other=seed(c)
        fy=fy_start_year(today)
        configured=c.put("/leave/policies",headers=ORIGIN,json={
          "leave_type":"casual","annual_days":12,"monthly_accrual":0,
          "approval_chain":["manager","hr"],"probation_allowed":True,"active":True})
        assert configured.status_code==200,configured.text
        old=c.get(f"/leave/balances?employee_id={one}&year={fy}")
        assert old.status_code==200,old.text
        switch(c,"payroll.hr.qa@example.org")
        bad=c.post("/governance/requests",headers=ORIGIN,json={
          "kind":"leave_allocation","reason":"short","payload":{
          "employee_id":one,"year":fy,"leave_type":"casual","allocated_days":14}})
        assert bad.status_code==422
        request=c.post("/governance/requests",headers=ORIGIN,json={
          "kind":"leave_allocation","reason":"Documented correction for leave allocation after HR review",
          "payload":{"employee_id":one,"year":fy,"leave_type":"casual","allocated_days":"14.5"}})
        assert request.status_code==201,request.text
        switch(c)
        prior=c.get(f"/leave/balances?employee_id={one}&year={fy}").json()
        before=next(x["allocated"] for x in prior if x["leave_type"]=="casual")
        approval=c.post("/governance/requests/"+str(request.json()["id"])+"/review",headers=ORIGIN,json={
           "approve":True,"reason":"Supporting correction has been verified"})
        assert approval.status_code==200,approval.text
        after=c.get(f"/leave/balances?employee_id={one}&year={fy}").json()
        assert next(x["allocated"] for x in after if x["leave_type"]=="casual")==14.5

def test_employee_login_logout_and_no_admin_for_own_photo_or_password():
    with TestClient(app) as c:
        admin,hr,one,other=seed(c)
        switch(c,"payroll.person.qa@example.org")
        assert c.get("/me").status_code==200
        assert c.get("/me/presence").status_code==200
        assert c.put("/me/presence",headers=ORIGIN,json={"status":"busy"}).status_code==200
        assert c.get("/governance/requests").status_code==403
        assert c.post("/auth/logout",headers=ORIGIN).status_code==200
        assert c.get("/me").status_code==401

def test_invoice_rejects_future_date_and_zero_quantity():
    with TestClient(app) as c:
        admin,hr,one,other=seed(c)
        p=setup_project(c,one);billing(c,p)
        base={"project_id":p,"period_start":(today-timedelta(days=2)).isoformat(),
              "period_end":today.isoformat(),"quantity":1,"tax_rate_pct":0}
        assert c.post("/finance/invoices",headers=ORIGIN,json={**base,"quantity":0}).status_code==422
        assert c.post("/finance/invoices",headers=ORIGIN,json={
           **base,"issue_date":(today+timedelta(days=1)).isoformat()}).status_code==422
        assert c.post("/finance/invoices",headers=ORIGIN,json={
           **base,"period_end":(today+timedelta(days=1)).isoformat()}).status_code==422
