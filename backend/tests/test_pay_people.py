"""Payroll and People Operations contract/security tests against disposable PostgreSQL."""
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app, SessionLocal, Employee, Attendance
from app.payroll import PayrollLine

ORIGIN={"Origin":"http://localhost:3000"}
ADMIN="admin@example.com"
ADMIN_PASS="test-admin-password-12345"
PASS="IntegrationTest!Pass123"
today=date.today()

def login(c,email=ADMIN,password=ADMIN_PASS):
    r=c.post("/auth/login",json={"email":email,"password":password})
    assert r.status_code==200,r.text
    return r.json()

def create(c,email,name,role,manager):
    present=next((x for x in c.get("/employees").json() if x["email"]==email),None)
    if present:return present["id"]
    r=c.post("/core/employees",headers=ORIGIN,json={
        "account":{"email":email,"name":name,"password":PASS,"role":role,
                   "designation":"Test Specialist","department":"Quality",
                   "joining_date":today.isoformat()},
        "master":{"manager_id":manager}})
    assert r.status_code==201,r.text
    return r.json()["id"]

def seed(c):
    login(c)
    admin=c.get("/me").json()["id"]
    hr=create(c,"payroll.hr.qa@example.org","Payroll HR","hr",admin)
    one=create(c,"payroll.person.qa@example.org","Payroll Person","employee",hr)
    other=create(c,"payroll.other.qa@example.org","Other Payroll","employee",hr)
    return admin,hr,one,other

def approved_compensation(kind,payload):
    """Create genuine dual-control approvals using distinct test employees.

    The secondary admin joins in a future year so it is not part of this
    month's payroll; no production account is ever created by this helper.
    """
    from sqlalchemy import select
    from app.main import passwords
    with SessionLocal() as db:
        target=db.get(Employee,payload["employee_id"])
        hr=db.scalar(select(Employee).where(Employee.email=="payroll.hr.qa@example.org"))
        primary=db.scalar(select(Employee).where(Employee.email==ADMIN))
        assert target and hr and primary
        sensitive_target=target.id in (hr.id,primary.id)
        if sensitive_target:
            secondary=db.scalar(select(Employee).where(Employee.email=="qa.secondary.payadmin@example.org"))
            if secondary is None:
                secondary=Employee(name="Secondary QA Payroll Admin",
                    email="qa.secondary.payadmin@example.org",
                    password_hash=passwords.hash(ADMIN_PASS),role="admin",
                    designation="QA independent approver",
                    joining_date=date(today.year+1,1,1),status="active")
                db.add(secondary);db.commit();db.refresh(secondary)
        proposer_email=ADMIN if target.id==hr.id else "payroll.hr.qa@example.org"
        approver_email="qa.secondary.payadmin@example.org" if sensitive_target else ADMIN
    with TestClient(app) as reviewer:
        login(reviewer,proposer_email,ADMIN_PASS if proposer_email==ADMIN else PASS)
        proposed=reviewer.post("/governance/requests",headers=ORIGIN,json={
            "kind":kind,"payload":payload,
            "reason":"QA fixture: independently reviewed compensation setup."})
        assert proposed.status_code==201,proposed.text
        request_id=proposed.json()["id"]
        reviewer.post("/auth/logout",headers=ORIGIN)
        login(reviewer,approver_email,ADMIN_PASS)
        response=reviewer.post(f"/governance/requests/{request_id}/review",headers=ORIGIN,json={
            "approve":True,"reason":"QA fixture: approved by separate administrator."})
        assert response.status_code==200,response.text
        return response


def configure(c,person):
    effective=date(today.year,1,1).isoformat()
    approved_compensation("salary_structure",{"employee_id":person,
            "basic":30000,"hra":12000,"allowances":8000,
            "other_deductions":0,"effective_from":effective})
    approved_compensation("statutory_settings",{
        "employee_id":person,"pf_employee_monthly":1000,
        "esi_employee_monthly":0,"professional_tax_monthly":200,
        "tds_monthly":500,"gratuity_employer_provision":1500,"effective_from":effective})

def test_salary_and_pdf_privacy_and_payroll_approval():
    with TestClient(app) as c:
        admin,hr,one,other=seed(c)
        period=today.strftime("%Y-%m")
        # Every eligible employee has reviewed salary + tax configuration.
        staff=c.get("/employees").json()
        for emp in staff:
            if emp["joining_date"]<=date(today.year,today.month,
                    28 if today.month==2 else 30 if today.month in (4,6,9,11) else 31).isoformat():
                configure(c,emp["id"])
        with SessionLocal() as db:
            for emp in staff:
                if emp["status"]!="active":continue
                present=db.scalar(select(Attendance.id).where(
                    Attendance.employee_id==emp["id"],Attendance.punch_out.is_not(None)))
                if not present:
                    db.add(Attendance(employee_id=emp["id"],
                       punch_in=datetime(today.year,today.month,2,9,tzinfo=timezone.utc),
                       punch_out=datetime(today.year,today.month,2,18,tzinfo=timezone.utc)))
            db.commit()
        new=c.post("/payroll/runs",headers=ORIGIN,json={"period":period})
        assert new.status_code==201,new.text
        run_id=new.json()["id"]
        dup=c.post("/payroll/runs",headers=ORIGIN,json={"period":period})
        assert dup.status_code==409
        run=c.get(f"/payroll/runs/{run_id}")
        assert run.status_code==200,run.text
        assert len(run.json()["lines"])>=2
        own_line=next(x for x in run.json()["lines"] if x["employee_id"]==one)
        from app.payroll import money, ym_bounds
        start,end=ym_bounds(period)
        person=next(e for e in staff if e["id"]==one)
        joined=date.fromisoformat(person["joining_date"])
        service_days=(end-max(start,joined)).days+1
        expected_gross=money(Decimal(50000)*Decimal(service_days)/Decimal((end-start).days+1))
        assert Decimal(str(own_line["gross"]))==expected_gross
        assert Decimal(str(own_line["net"]))==expected_gross-Decimal("1700.00")
        assert c.post(f"/payroll/runs/{run_id}/approve",headers=ORIGIN).status_code==403
        c.post("/auth/logout",headers=ORIGIN)
        login(c,"payroll.hr.qa@example.org",PASS)
        approval=c.post(f"/payroll/runs/{run_id}/approve",headers=ORIGIN)
        assert approval.status_code==200,approval.text
        publish=c.post(f"/payroll/runs/{run_id}/publish",headers=ORIGIN)
        assert publish.status_code==200,publish.text
        assert publish.json()["money_transferred"] is False
        c.post("/auth/logout",headers=ORIGIN)
        login(c,"payroll.person.qa@example.org",PASS)
        slips=c.get("/payroll/my-payslips")
        assert slips.status_code==200
        line_id=next(x["line_id"] for x in slips.json() if x["period"]==period)
        own_pdf=c.get(f"/payroll/payslips/{line_id}.pdf")
        assert own_pdf.status_code==200 and own_pdf.content.startswith(b"%PDF-")
        assert c.get("/payroll/runs").status_code==403
        assert c.get("/payroll/structures?employee_id="+str(other)).status_code==403
        with SessionLocal() as db:
            foreign=db.scalar(select(PayrollLine.id).where(
                PayrollLine.run_id==run_id,PayrollLine.employee_id==other))
        assert c.get(f"/payroll/payslips/{foreign}.pdf").status_code==403

def test_expense_receipt_review_and_role_permissions():
    with TestClient(app) as c:
        admin,hr,one,other=seed(c)
        c.post("/auth/logout",headers=ORIGIN)
        login(c,"payroll.person.qa@example.org",PASS)
        made=c.post("/payroll/expenses",headers=ORIGIN,json={
          "title":"Work equipment purchase","category":"equipment","amount":"2200.00",
          "incurred_on":today.isoformat(),"note":"Approved business equipment"})
        assert made.status_code==201,made.text
        claim=made.json()["id"]
        assert c.get("/payroll/expenses?scope=all").status_code==403
        assert c.post(f"/payroll/expenses/{claim}/review",headers=ORIGIN,json={"approve":True}).status_code==403
        uploaded=c.post(f"/payroll/expenses/{claim}/receipt",headers=ORIGIN,
                        files={"receipt":("receipt.pdf",b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF","application/pdf")})
        assert uploaded.status_code==200,uploaded.text
        c.post("/auth/logout",headers=ORIGIN)
        login(c,"payroll.other.qa@example.org",PASS)
        assert c.get(f"/payroll/expenses/{claim}/receipt").status_code==403
        c.post("/auth/logout",headers=ORIGIN)
        login(c,"payroll.hr.qa@example.org",PASS)
        assert c.get(f"/payroll/expenses/{claim}/receipt").status_code==200
        reviewed=c.post(f"/payroll/expenses/{claim}/review",headers=ORIGIN,json={"approve":True})
        assert reviewed.status_code==200 and reviewed.json()["status"]=="approved"
        assert c.post(f"/payroll/expenses/{claim}/review",headers=ORIGIN,json={"approve":False}).status_code==409

def test_offers_onboarding_tickets_and_announcements():
    with TestClient(app) as c:
        admin,hr,one,other=seed(c)
        templ=c.post("/people/offer-templates",headers=ORIGIN,json={
         "name":"QA Offer "+str(int(datetime.now().timestamp())),
         "content":"Dear {{employee_name}}, we offer the {{job_title}} role at INR {{annual_ctc}}. Joining on {{joining_date}}."})
        assert templ.status_code==201,templ.text
        offer=c.post("/people/offers",headers=ORIGIN,json={
          "employee_id":one,"template_id":templ.json()["id"],"title":"QA Engineer",
          "annual_ctc":"1200000.00","joining_date":today.isoformat()})
        assert offer.status_code==201,offer.text
        oid=offer.json()["id"]
        assert c.post(f"/people/offers/{oid}/send",headers=ORIGIN).status_code==200
        task=c.post("/people/onboarding",headers=ORIGIN,json={
           "employee_id":one,"category":"asset","title":"Allocate QA laptop","asset_code":"JGT-QA-001",
           "assigned_to":hr})
        assert task.status_code==201,task.text
        tid=task.json()["id"]
        notice=c.post("/people/announcements",headers=ORIGIN,json={
            "title":"QA policy acknowledgement","body":"Please read and acknowledge the updated HR policy.",
            "requires_ack":True})
        assert notice.status_code==201,notice.text
        nid=notice.json()["id"]
        c.post("/auth/logout",headers=ORIGIN)
        login(c,"payroll.person.qa@example.org",PASS)
        assert c.get("/people/analytics").status_code==403
        assert c.get("/people/audit").status_code==403
        assert c.get("/people/offer-templates").status_code==403
        assert c.get(f"/people/offers/{oid}.pdf").status_code==200
        bad=c.post(f"/people/offers/{oid}/sign",headers=ORIGIN,json={
            "printed_name":"Wrong Name","consent":True})
        assert bad.status_code==422
        signed=c.post(f"/people/offers/{oid}/sign",headers=ORIGIN,json={
            "printed_name":"Payroll Person","consent":True})
        assert signed.status_code==200,signed.text
        assert signed.json()["signature_type"]=="internal_acknowledgment_not_qualified_esign"
        ack=c.post(f"/people/announcements/{nid}/ack",headers=ORIGIN)
        assert ack.status_code==200
        ticket=c.post("/people/tickets",headers=ORIGIN,json={
           "category":"payroll","subject":"Payslip clarification",
           "description":"Please clarify the statutory deduction on my payslip."})
        assert ticket.status_code==201,ticket.text
        c.post("/auth/logout",headers=ORIGIN)
        login(c,"payroll.hr.qa@example.org",PASS)
        taskdone=c.post(f"/people/onboarding/{tid}/complete",headers=ORIGIN)
        assert taskdone.status_code==200
        reply=c.post(f"/people/tickets/{ticket.json()['id']}/review",headers=ORIGIN,json={
           "status":"resolved","reply":"We will send the reviewed breakdown."})
        assert reply.status_code==200,reply.text
        assert c.get("/people/analytics").status_code==200
        assert len(c.get("/people/audit").json())>=3

def test_exit_clearance_and_notification_outbox():
    with TestClient(app) as c:
        admin,hr,one,other=seed(c)
        rules=c.put("/people/notification-rules",headers=ORIGIN,json={
           "event":"approval","email":True,"sms":True,"push":False,"whatsapp":False})
        assert rules.status_code==200,rules.text
        q=c.post("/people/notifications/queue",headers=ORIGIN,json={
           "employee_id":one,"event":"approval","subject":"Approval update",
           "body":"Your reimbursement requires attention."})
        assert q.status_code==200 and q.json()["delivered"] is False
        c.post("/auth/logout",headers=ORIGIN)
        login(c,"payroll.person.qa@example.org",PASS)
        msg=c.get("/people/notifications")
        assert msg.status_code==200 and any(n["channel"]=="sms" and n["status"]=="queued" for n in msg.json())
        exitreq=c.post("/people/exits",headers=ORIGIN,json={
          "reason":"Career transition and relocation",
          "notice_days":30,"requested_date":today.isoformat()})
        assert exitreq.status_code==201,exitreq.text
        xid=exitreq.json()["id"]
        assert c.post(f"/people/exits/{xid}/review",headers=ORIGIN,json={"status":"approved"}).status_code==403
        c.post("/auth/logout",headers=ORIGIN)
        login(c,"payroll.hr.qa@example.org",PASS)
        rejected=c.post(f"/people/exits/{xid}/review",headers=ORIGIN,json={
          "status":"settled","final_settlement_inr":"15000.00","clearance_assets":False})
        assert rejected.status_code==422
        approved=c.post(f"/people/exits/{xid}/review",headers=ORIGIN,json={"status":"approved"})
        assert approved.status_code==200,approved.text
        allocated=c.post("/people/assets",headers=ORIGIN,json={
            "employee_id":one,"name":"QA allocated laptop","serial_number":"QA-LAP-"+str(xid)})
        assert allocated.status_code==201,allocated.text
        a_id=allocated.json()["id"]
        assert c.post(f"/people/exits/{xid}/clearances",headers=ORIGIN,json={
            "kind":"assets","note":"Returned all assigned assets."}).status_code==409
        assert c.post(f"/people/assets/{a_id}/return",headers=ORIGIN).status_code==200
        for kind in ("assets","it","finance"):
            cleared=c.post(f"/people/exits/{xid}/clearances",headers=ORIGIN,json={
                "kind":kind,"note":"QA clearance verified for "+kind})
            assert cleared.status_code==201,cleared.text
        settled=c.post(f"/people/exits/{xid}/review",headers=ORIGIN,json={
          "status":"settled","final_settlement_inr":"15000.00",
          "clearance_assets":True,"clearance_it":True,"clearance_finance":True})
        assert settled.status_code==200 and settled.json()["settlement_paid"] is False
