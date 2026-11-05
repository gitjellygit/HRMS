"""Finance rate overrides and dynamic salary component acceptance tests."""
from datetime import date, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app, SessionLocal
from app.payroll import calculate
from test_pay_people import seed, create, configure, login, PASS, ORIGIN

def placement(c,owner):
    r=c.post("/project-management/projects",headers=ORIGIN,json={
        "name":"QA Finance Pricing Placement",
        "client":"Example Client","candidate_name":"Candidate Example",
        "vendor_name":"Vendor Example","prime_vendor_name":"Prime Example",
        "engagement_type":"c2c","rate":"68.00","currency":"USD",
        "rate_unit":"hour","sourced_by_id":owner,
        "start_date":(date.today()-timedelta(days=7)).isoformat()})
    assert r.status_code==201,r.text
    return r.json()["id"]

def test_accountant_can_set_percentage_or_fixed_recipient_rate_and_tax():
    with TestClient(app) as c:
        admin,hr,one,other=seed(c)
        accountant=create(c,"finance.pricing.qa@example.org","Finance Pricing QA","accountant",admin)
        pid=placement(c,one)
        c.post("/auth/logout",headers=ORIGIN)
        login(c,"finance.pricing.qa@example.org",PASS)
        cfg=c.put(f"/finance/projects/{pid}/billing",headers=ORIGIN,json={
            "recipient_type":"client","recipient_name":"Client Accounts",
            "recipient_email":"invoices@example.org","recipient_phone":"+1 555 0100",
            "billing_address":"Accounts Payable, Example Avenue",
            "billing_day":15,"payment_terms_days":10})
        assert cfg.status_code==200,cfg.text
        pct=c.put(f"/finance/projects/{pid}/charges",headers=ORIGIN,json={
            "recipient_type":"client","pricing_mode":"percentage",
            "pricing_value":"20.00","tax_rate_pct":"5.00"})
        assert pct.status_code==200,pct.text
        assert Decimal(str(pct.json()["effective_rate"]))==Decimal("13.60")
        data={"project_id":pid,"period_start":(date.today()-timedelta(days=2)).isoformat(),
              "period_end":date.today().isoformat(),"quantity":"10"}
        made=c.post("/finance/invoices",headers=ORIGIN,json=data)
        assert made.status_code==201,made.text
        inv=made.json()
        assert Decimal(str(inv["unit_rate"]))==Decimal("13.60")
        assert Decimal(str(inv["subtotal"]))==Decimal("136.00")
        assert Decimal(str(inv["tax_amount"]))==Decimal("6.80")
        assert Decimal(str(inv["total"]))==Decimal("142.80")
        # Editing a price never retroactively mutates an already created invoice.
        fixed=c.put(f"/finance/projects/{pid}/charges",headers=ORIGIN,json={
            "recipient_type":"client","pricing_mode":"fixed_rate",
            "pricing_value":"42.50","tax_rate_pct":"0"})
        assert fixed.status_code==200
        saved=c.get(f"/finance/invoices?project_id={pid}").json()
        assert Decimal(str(saved[0]["unit_rate"]))==Decimal("13.60")
        assert c.put(f"/finance/projects/{pid}/charges",headers=ORIGIN,json={
           "recipient_type":"vendor","pricing_mode":"percentage",
           "pricing_value":"101","tax_rate_pct":"0"}).status_code==422
        assert c.put(f"/finance/projects/{pid}/charges",headers=ORIGIN,json={
           "recipient_type":"candidate","pricing_mode":"fixed_rate",
           "pricing_value":"-1","tax_rate_pct":"0"}).status_code==422
        c.post("/auth/logout",headers=ORIGIN)
        login(c,"payroll.person.qa@example.org",PASS)
        assert c.put(f"/finance/projects/{pid}/charges",headers=ORIGIN,json={
           "recipient_type":"client","pricing_mode":"fixed_rate",
           "pricing_value":"30.00"}).status_code==403

def test_hr_salary_components_adjust_payroll_and_employee_cannot_edit():
    with TestClient(app) as c:
        admin,hr,one,other=seed(c)
        configure(c,one)
        effective=date(date.today().year,1,1).isoformat()
        first=c.put("/payroll/components",headers=ORIGIN,json={
          "employee_id":one,"code":"shift_bonus","title":"Night shift bonus",
          "kind":"earning","amount":"1500.00","effective_from":effective})
        assert first.status_code==200,first.text
        second=c.put("/payroll/components",headers=ORIGIN,json={
          "employee_id":one,"code":"parking_deduction","title":"Parking deduction",
          "kind":"deduction","amount":"200.00","effective_from":effective})
        assert second.status_code==200,second.text
        with SessionLocal() as db:
            person=db.get(__import__("app.main",fromlist=["Employee"]).Employee,one)
            row=calculate(db,person,date.today().strftime("%Y-%m"))
            assert Decimal(str(row["gross"]))==Decimal("51500.00")
            assert Decimal(str(row["net"]))==Decimal("49600.00")
        # A new offer template may opt in to the reviewed salary breakdown.
        template=c.post("/people/offer-templates",headers=ORIGIN,json={
          "name":"QA Dynamic Salary Offer","content":
          "Dear {{employee_name}}, your compensation:\\n{{salary_breakdown}}"})
        assert template.status_code==201,template.text
        offer=c.post("/people/offers",headers=ORIGIN,json={
          "employee_id":one,"template_id":template.json()["id"],
          "title":"Test Engineer","annual_ctc":"1200000.00",
          "joining_date":date.today().isoformat()})
        assert offer.status_code==201,offer.text
        from app.people_operations import Offer
        with SessionLocal() as db:
            record=db.get(Offer,offer.json()["id"])
            assert "Night shift bonus (earning): INR 1500.00/month" in record.rendered_content
            assert "Parking deduction (deduction): INR 200.00/month" in record.rendered_content
        c.post("/auth/logout",headers=ORIGIN)
        login(c,"payroll.person.qa@example.org",PASS)
        mine=c.get(f"/payroll/components?employee_id={one}")
        assert mine.status_code==200 and len(mine.json())>=2
        assert c.get(f"/payroll/components?employee_id={other}").status_code==403
        assert c.put("/payroll/components",headers=ORIGIN,json={
          "employee_id":one,"code":"invalid","title":"Unauthorized",
          "kind":"earning","amount":"10","effective_from":effective}).status_code==403
