"""Independent payroll approval and negative authorization regressions."""
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from test_pay_people import seed, login, ORIGIN, ADMIN_PASS, PASS


def switch(c,email,password=PASS):
    c.post("/auth/logout",headers=ORIGIN)
    login(c,email,password)


def propose(c,kind,payload):
    return c.post("/governance/requests",headers=ORIGIN,json={
        "kind":kind,"payload":payload,"reason":"Verified compensation change with documented approval."})


def test_salary_and_statutory_require_independent_review_and_no_self_edits():
    with TestClient(app) as c:
        admin,hr,worker,other=seed(c)
        data={"employee_id":worker,"basic":"40000.00","hra":"12000.00",
              "allowances":"3000.00","other_deductions":"0.00",
              "effective_from":date.today().isoformat()}
        assert c.put("/payroll/structures",headers=ORIGIN,json=data).status_code==403
        assert c.put("/payroll/statutory",headers=ORIGIN,json={
            "employee_id":worker,"effective_from":date.today().isoformat()}).status_code==403
        assert propose(c,"salary_structure",{**data,"employee_id":admin}).status_code==403
        switch(c,"payroll.hr.qa@example.org")
        assert propose(c,"salary_structure",{**data,"employee_id":hr}).status_code==403
        request=propose(c,"salary_structure",data)
        assert request.status_code==201,request.text
        request_id=request.json()["id"]
        assert not c.get(f"/payroll/structures?employee_id={worker}").json()
        assert c.post(f"/governance/requests/{request_id}/review",headers=ORIGIN,
                      json={"approve":True,"reason":"Independent compensation review approved."}).status_code==403
        switch(c,"admin@example.com",ADMIN_PASS)
        assert c.post(f"/governance/requests/{request_id}/review",headers=ORIGIN,
                      json={"approve":True,"reason":"Approved independent salary configuration."}).status_code==200
        rows=c.get(f"/payroll/structures?employee_id={worker}").json()
        assert len(rows)==1 and float(rows[0]["basic"])==40000
        assert c.post(f"/governance/requests/{request_id}/review",headers=ORIGIN,
                      json={"approve":True,"reason":"Duplicate review attempt rejected."}).status_code==409
        switch(c,"payroll.hr.qa@example.org")
        config={"employee_id":worker,"effective_from":date.today().isoformat(),
                "pf_employee_monthly":"1200","esi_employee_monthly":"0",
                "professional_tax_monthly":"200","tds_monthly":"300",
                "gratuity_employer_provision":"1500"}
        statutory=propose(c,"statutory_settings",config)
        assert statutory.status_code==201,statutory.text
        switch(c,"admin@example.com",ADMIN_PASS)
        approved=c.post(f'/governance/requests/{statutory.json()["id"]}/review',
            headers=ORIGIN,json={"approve":True,"reason":"Independent statutory amounts validated."})
        assert approved.status_code==200,approved.text
        assert float(c.get(f"/payroll/statutory?employee_id={worker}").json()[0]["pf_employee_monthly"])==1200
        history=c.get(f"/payroll/config-history?employee_id={worker}")
        assert history.status_code==200
        assert {r["kind"] for r in history.json()}=={"salary","statutory"}


def test_component_and_reviewer_self_edit_are_blocked():
    with TestClient(app) as c:
        admin,hr,worker,other=seed(c)
        component={"employee_id":worker,"code":"qa_shift","title":"QA night shift",
                   "kind":"earning","amount":"800.00",
                   "effective_from":date.today().isoformat(),"active":True}
        assert c.put("/payroll/components",headers=ORIGIN,json=component).status_code==403
        switch(c,"payroll.hr.qa@example.org")
        bad=propose(c,"salary_component",{**component,"employee_id":hr})
        assert bad.status_code==403
        req=propose(c,"salary_component",component)
        assert req.status_code==201,req.text
        switch(c,"admin@example.com",ADMIN_PASS)
        review=c.post(f'/governance/requests/{req.json()["id"]}/review',
            headers=ORIGIN,json={"approve":True,"reason":"Component reviewed with documentary justification."})
        assert review.status_code==200,review.text
        components=c.get(f"/payroll/components?employee_id={worker}")
        assert any(r["code"]=="qa_shift" for r in components.json())
        switch(c,"payroll.hr.qa@example.org")
        own_admin=propose(c,"salary_component",{**component,"employee_id":admin})
        assert own_admin.status_code==201
        switch(c,"admin@example.com",ADMIN_PASS)
        blocked=c.post(f'/governance/requests/{own_admin.json()["id"]}/review',
            headers=ORIGIN,json={"approve":True,"reason":"Should not approve my own compensation."})
        assert blocked.status_code==403
