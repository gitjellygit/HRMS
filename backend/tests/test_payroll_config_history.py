"""Payroll configuration history cannot retroactively change historical calculations."""
from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app, SessionLocal, Employee
from app.payroll import calculate
from test_pay_people import seed, configure, ORIGIN


def test_future_salary_and_statutory_rates_do_not_change_current_month():
    with TestClient(app) as client:
        _,_,person,_=seed(client)
        configure(client,person)
        period=date.today().strftime("%Y-%m")
        with SessionLocal() as db:
            before=calculate(db,db.get(Employee,person),period)
        future=date(date.today().year+1,1,1).isoformat()
        new_salary=client.put("/payroll/structures",headers=ORIGIN,json={
            "employee_id":person,"basic":"90000","hra":"20000",
            "allowances":"10000","other_deductions":"0","effective_from":future})
        assert new_salary.status_code==200,new_salary.text
        new_tax=client.put("/payroll/statutory",headers=ORIGIN,json={
            "employee_id":person,"pf_employee_monthly":"5000",
            "esi_employee_monthly":"0","professional_tax_monthly":"200",
            "tds_monthly":"10000","gratuity_employer_provision":"2500",
            "effective_from":future})
        assert new_tax.status_code==200,new_tax.text
        with SessionLocal() as db:
            current=calculate(db,db.get(Employee,person),period)
        assert current["gross"]==before["gross"]
        assert current["net"]==before["net"]
        history=client.get(f"/payroll/config-history?employee_id={person}")
        assert history.status_code==200,history.text
        records=history.json()
        assert len([r for r in records if r["kind"]=="salary"])==2
        assert len([r for r in records if r["kind"]=="statutory"])==2
        assert any(r["effective_from"]==future for r in records)
