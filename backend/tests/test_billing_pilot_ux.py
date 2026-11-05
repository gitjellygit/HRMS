"""Pilot billing UX: atomic configuration, cadence persistence and HR lifecycle."""
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import app
from test_pay_people import seed, login, PASS, ORIGIN

def switch(client,email,password=PASS):
    client.post("/auth/logout",headers=ORIGIN)
    login(client,email,password)

def test_accountant_single_save_and_hr_only_deactivation():
    with TestClient(app) as c:
        admin,hr,employee,other=seed(c)
        project=c.post("/project-management/projects",headers=ORIGIN,json={
            "name":"QA Weekly Billing Project","client":"Finance Test Client",
            "engagement_type":"c2c","rate":"78.00","currency":"USD","rate_unit":"hour",
            "sourced_by_id":employee,"start_date":(date.today()-timedelta(days=30)).isoformat()})
        assert project.status_code==201,project.text
        pid=project.json()["id"]
        switch(c,"payroll.person.qa@example.org")
        forbidden=c.put(f"/finance/projects/{pid}/configuration",headers=ORIGIN,json={
            "recipient_name":"QA Billing Account","recipient_email":"qa@example.com",
            "billing_frequency":"weekly","billing_day":5,
            "payment_terms_days":30,"rate_unit":"hour","invoice_rate":20,"tax_rate_pct":5})
        assert forbidden.status_code==403
        switch(c,"payroll.accountant.qa@example.org")
        result=c.put(f"/finance/projects/{pid}/configuration",headers=ORIGIN,json={
            "recipient_name":"QA Billing Account","recipient_email":"qa@example.com",
            "recipient_phone":"+1-555-0100","billing_address":"Example billing office",
            "billing_frequency":"weekly","billing_day":5,"payment_terms_days":30,
            "rate_unit":"hour","invoice_rate":20,"tax_rate_pct":5})
        assert result.status_code==200,result.text
        assert result.json()["saved"] is True
        listing=c.get("/finance/projects").json()
        stored=next(x for x in listing if x["id"]==pid)
        assert stored["billing"]["billing_frequency"]=="weekly"
        assert stored["billing"]["payment_terms_days"]==30
        assert stored["billing"]["recipient_name"]=="QA Billing Account"
        assert float(stored["charges"][0]["pricing_value"])==20
        assert stored["charges"][0]["rate_unit"]=="hour"
        assert float(stored["rate"])==78
        assert c.put(f"/finance/projects/{pid}/lifecycle",headers=ORIGIN,json={
            "active":False,"reason":"Closing contract after assignment"}).status_code==403
        switch(c,"payroll.hr.qa@example.org")
        invalid=c.put(f"/finance/projects/{pid}/lifecycle",headers=ORIGIN,json={
            "active":False,"reason":"short"})
        assert invalid.status_code==422
        end=c.put(f"/finance/projects/{pid}/lifecycle",headers=ORIGIN,json={
            "active":False,"end_date":None,"reason":"Client project engagement completed"})
        assert end.status_code==200,end.text
        assert end.json()["status"]=="inactive"
        assert c.get("/project-management/projects").json()[0]["status"]=="inactive"
        switch(c,"payroll.accountant.qa@example.org")
        blocked=c.put(f"/finance/projects/{pid}/configuration",headers=ORIGIN,json={
            "recipient_name":"QA Billing Account","billing_frequency":"monthly",
            "billing_day":15,"payment_terms_days":15,"rate_unit":"hour",
            "invoice_rate":21,"tax_rate_pct":0})
        assert blocked.status_code==409

def test_billing_configuration_invalid_rate_and_cadence_rejected():
    with TestClient(app) as c:
        admin,hr,employee,other=seed(c)
        project=c.post("/project-management/projects",headers=ORIGIN,json={
            "name":"QA Cadence Validation","client":"Finance Test Client",
            "engagement_type":"c2c","rate":"78.00","currency":"USD","rate_unit":"hour",
            "sourced_by_id":employee,"start_date":(date.today()-timedelta(days=30)).isoformat()})
        pid=project.json()["id"]
        path=f"/finance/projects/{pid}/configuration"
        config={"recipient_name":"QA Billing Account","billing_day":15,
                "payment_terms_days":30,"rate_unit":"hour","invoice_rate":78,
                "tax_rate_pct":5,"billing_frequency":"monthly"}
        assert c.put(path,headers=ORIGIN,json={**config,"invoice_rate":0}).status_code==422
        assert c.put(path,headers=ORIGIN,json={**config,"billing_frequency":"daily"}).status_code==422
        assert c.put(path,headers=ORIGIN,json={**config,"tax_rate_pct":101}).status_code==422
        assert c.put(path,headers=ORIGIN,json=config).status_code==200
