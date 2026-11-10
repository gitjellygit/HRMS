"""Approved-timesheet billing protects quantity, permissions and rebilling."""
from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app
from test_pay_people import seed, login, ORIGIN, PASS, ADMIN, ADMIN_PASS
from test_finance_pricing_salary_components import placement
from test_hardening_billing import configure


def switch(c,email,password=PASS):
    c.post("/auth/logout",headers=ORIGIN)
    login(c,email,password)


def test_approved_hours_are_only_billed_once_and_released_when_voided():
    with TestClient(app) as c:
        admin,hr,one,other=seed(c)
        project=placement(c,one)
        configure(c,project,tax="5.00")
        switch(c,"payroll.person.qa@example.org")
        created=c.post("/time/timesheets",headers=ORIGIN,json={
            "work_date":date.today().isoformat(),"hours":"4.50",
            "project_id":project,"task":"Development work against assigned deliverables"})
        assert created.status_code==201,created.text
        timesheet=created.json()["id"]
        assert c.post(f"/time/timesheets/{timesheet}/review",headers=ORIGIN,
            json={"approve":True,"reason":"Self-review should not be allowed"}).status_code==403
        submitted=c.post(f"/time/timesheets/{timesheet}/submit",headers=ORIGIN)
        assert submitted.status_code==200,submitted.text
        assert c.put(f"/time/timesheets/{timesheet}",headers=ORIGIN,json={
            "work_date":date.today().isoformat(),"hours":"6.00",
            "project_id":project,"task":"Illegal edit after submission"}).status_code==409
        switch(c,"payroll.hr.qa@example.org")
        approved=c.post(f"/time/timesheets/{timesheet}/review",headers=ORIGIN,json={
            "approve":True,"reason":"Manager verified completed deliverables"})
        assert approved.status_code==200,approved.text
        assert approved.json()["status"]=="approved"
        assert c.post(f"/time/timesheets/{timesheet}/review",headers=ORIGIN,json={
            "approve":True,"reason":"Must reject repeated approval"}).status_code==409
        switch(c,ADMIN,ADMIN_PASS)
        before=c.get(f"/finance/projects/{project}/approved-timesheets",params={
            "period_start":date.today().isoformat(),"period_end":date.today().isoformat()})
        assert before.status_code==200,before.text
        assert Decimal(str(before.json()["unbilled_hours"]))==Decimal("4.50")
        bill=c.post("/finance/invoices/from-approved-timesheets",headers=ORIGIN,json={
            "project_id":project,"period_start":date.today().isoformat(),
            "period_end":date.today().isoformat()})
        assert bill.status_code==201,bill.text
        assert Decimal(str(bill.json()["quantity"]))==Decimal("4.50")
        assert Decimal(str(bill.json()["tax_amount"]))==Decimal("22.50")
        assert bill.json()["approved_timesheet_count"]==1
        repeat=c.post("/finance/invoices/from-approved-timesheets",headers=ORIGIN,json={
            "project_id":project,"period_start":date.today().isoformat(),
            "period_end":date.today().isoformat()})
        assert repeat.status_code==409,repeat.text
        no_more=c.get(f"/finance/projects/{project}/approved-timesheets",params={
            "period_start":date.today().isoformat(),"period_end":date.today().isoformat()})
        assert Decimal(str(no_more.json()["unbilled_hours"]))==0
        void=c.post(f'/finance/invoices/{bill.json()["id"]}/status',headers=ORIGIN,
            json={"status":"void","reference":"Project billing correction after QA review"})
        assert void.status_code==200,void.text
        renewed=c.post("/finance/invoices/from-approved-timesheets",headers=ORIGIN,json={
            "project_id":project,"period_start":date.today().isoformat(),
            "period_end":date.today().isoformat()})
        assert renewed.status_code==201,renewed.text
        assert renewed.json()["id"]!=bill.json()["id"]


def test_assigned_project_allows_employee_time_submission_but_rejects_unassigned():
    with TestClient(app) as c:
        admin,hr,one,other=seed(c)
        project=placement(c,one)
        switch(c,"payroll.other.qa@example.org")
        denied=c.post("/time/timesheets",headers=ORIGIN,json={
            "work_date":date.today().isoformat(),"hours":"2",
            "project_id":project,"task":"Unassigned project work"})
        assert denied.status_code==422,denied.text
        switch(c,ADMIN,ADMIN_PASS)
        assn=c.put("/time/project-assignments",headers=ORIGIN,json={
            "employee_id":other,"project_id":project,"active":True})
        assert assn.status_code==200,assn.text
        switch(c,"payroll.other.qa@example.org")
        allowed=c.post("/time/timesheets",headers=ORIGIN,json={
            "work_date":date.today().isoformat(),"hours":"2",
            "project_id":project,"task":"Approved assignment delivery"})
        assert allowed.status_code==201,allowed.text
        assert c.post(f'/time/timesheets/{allowed.json()["id"]}/submit',headers=ORIGIN).status_code==200
        switch(c,ADMIN,ADMIN_PASS)
        c.put("/time/project-assignments",headers=ORIGIN,json={
            "employee_id":other,"project_id":project,"active":False})
        switch(c,"payroll.other.qa@example.org")
        denied_again=c.post("/time/timesheets",headers=ORIGIN,json={
            "work_date":date.today().isoformat(),"hours":"2",
            "project_id":project,"task":"Disallowed after unassignment"})
        assert denied_again.status_code==422,denied_again.text
