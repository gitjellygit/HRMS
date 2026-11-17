"""Pre-pilot acceptance: time-zone records, monthly WFH, tiered leave, private bonuses, hybrid payslips."""
import io
import zipfile
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app,Attendance,SessionLocal,EmployeeProfile
from app.leave_management import tiered_monthly_entitlement
from test_time_tracking import seed,sign,ORIGIN,PASS

def _switch(client,email,password=PASS):
    client.post("/auth/logout",headers=ORIGIN)
    sign(client,email,password)

def _pdf():
    from reportlab.pdfgen.canvas import Canvas
    data=io.BytesIO()
    p=Canvas(data)
    p.drawString(100,750,"QA Confidential Payslip")
    p.showPage();p.save()
    return data.getvalue()

def test_tiered_fy_credit_and_joining_month_proration():
    fy=2026
    assert tiered_monthly_entitlement(date(2026,4,1),fy,date(2026,4,30),Decimal("1.5"),Decimal("2.5"))==Decimal("1.5")
    assert tiered_monthly_entitlement(date(2026,4,1),fy,date(2026,11,30),Decimal("1.5"),Decimal("2.5"))==Decimal("12")
    assert tiered_monthly_entitlement(date(2026,4,1),fy,date(2027,3,31),Decimal("1.5"),Decimal("2.5"))==Decimal("22")
    assert tiered_monthly_entitlement(date(2026,10,16),fy,date(2026,11,30),Decimal("1.5"),Decimal("2.5"))==Decimal("2.5")
    assert tiered_monthly_entitlement(date(2027,4,1),fy,date(2027,3,31),Decimal("1.5"),Decimal("2.5"))==Decimal("0")

def test_wfh_limit_is_server_side_monthly_and_rejected_day_does_not_count():
    with TestClient(app) as c:
        admin,manager,worker,colleague=seed(c)
        _switch(c,"time.worker.qa@example.org")
        today=date.today()
        y=today.year+(today.month==12)
        m=1 if today.month==12 else today.month+1
        dates=[date(y,m,d).isoformat() for d in (10,11,12)]
        for day in dates[:2]:
            r=c.post("/time/requests",headers=ORIGIN,json={"kind":"wfh","work_date":day,
              "reason":"WFH approval test for monthly policy"})
            assert r.status_code==201,r.text
        third=c.post("/time/requests",headers=ORIGIN,json={"kind":"wfh","work_date":dates[2],
          "reason":"Attempt third WFH day in the same month"})
        assert third.status_code==422,third.text
        assert third.json()["detail"]["field"]=="work_date"
        quota=c.get(f"/time/wfh-balance?year={y}&month={m}")
        assert quota.status_code==200,quota.text
        assert quota.json()["remaining"]==0

def test_hr_punch_audit_uses_local_day_and_inferred_gap_not_employee_access():
    with TestClient(app) as c:
        admin,manager,worker,colleague=seed(c)
        # Nov 17 UTC 22:00 = 17:00 New York (EST) and Nov 18 03:30 UTC = 22:30 EST.
        with SessionLocal() as db:
            db.add(Attendance(employee_id=worker,punch_in=datetime(2026,11,17,22,0,tzinfo=timezone.utc),
                              punch_out=datetime(2026,11,18,0,0,tzinfo=timezone.utc)))
            db.add(Attendance(employee_id=worker,punch_in=datetime(2026,11,18,0,30,tzinfo=timezone.utc),
                              punch_out=datetime(2026,11,18,3,30,tzinfo=timezone.utc)))
            db.commit()
        query=f"/time/employee-punches?employee_id={worker}&work_date=2026-11-17&timezone_name=America/New_York"
        report=c.get(query)
        assert report.status_code==200,report.text
        data=report.json()
        assert data["employee_name"]=="Time Worker"
        assert data["work_hours"]==5
        assert data["break_minutes"]==30
        assert len(data["sessions"])==2
        assert data["sessions"][0]["punch_in"].endswith("-05:00")
        _switch(c,"time.worker.qa@example.org")
        assert c.get(query).status_code==403

def test_bonus_visible_to_owner_and_finance_not_other_employee():
    with TestClient(app) as c:
        admin,manager,worker,colleague=seed(c)
        made=c.post("/bonuses",headers=ORIGIN,json={"employee_id":worker,"amount":15000,
            "period":"2026-11","reason":"Pre-pilot owner-only bonus test"})
        assert made.status_code==201,made.text
        _switch(c,"time.worker.qa@example.org")
        mine=c.get("/bonuses")
        assert mine.status_code==200,mine.text
        assert any(b["employee_id"]==worker for b in mine.json())
        _switch(c,"time.colleague.qa@example.org")
        assert all(b["employee_id"]==colleague for b in c.get("/bonuses").json())

def test_hr_manual_payslip_single_and_bulk_owner_only():
    with TestClient(app) as c:
        admin,manager,worker,colleague=seed(c)
        content=_pdf()
        single=c.post(f"/payroll/manual-payslips?employee_id={worker}&period=2026-11&reason=Manual+November+payroll+pilot",
          headers=ORIGIN,files={"document":("payslip.pdf",content,"application/pdf")})
        assert single.status_code==201,single.text
        docid=single.json()["uploaded"][0]["id"]
        with SessionLocal() as db:
            from sqlalchemy import select
            code=db.scalar(select(EmployeeProfile.employee_code).where(EmployeeProfile.employee_id==colleague))
        archive=io.BytesIO()
        with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{code}.pdf",content)
        bulk=c.post("/payroll/manual-payslips/bulk?period=2026-12&reason=Verified+bulk+import+for+pilot",
          headers=ORIGIN,files={"archive":("monthly.zip",archive.getvalue(),"application/zip")})
        assert bulk.status_code==201,bulk.text
        assert len(bulk.json()["uploaded"])==1
        _switch(c,"time.worker.qa@example.org")
        my=c.get("/payroll/my-payslips")
        assert my.status_code==200,my.text
        assert any(x.get("source")=="manual" and x["period"]=="2026-11" for x in my.json())
        assert c.get(f"/payroll/manual-payslips/{docid}.pdf").status_code==200
        assert c.post(f"/payroll/manual-payslips?employee_id={worker}&period=2026-12&reason=Try+to+overwrite+salary",
             headers=ORIGIN,files={"document":("x.pdf",content,"application/pdf")}).status_code==403
        _switch(c,"time.colleague.qa@example.org")
        assert c.get(f"/payroll/manual-payslips/{docid}.pdf").status_code==403
        assert not any(x.get("source")=="manual" and x["period"]=="2026-11" for x in c.get("/payroll/my-payslips").json())
