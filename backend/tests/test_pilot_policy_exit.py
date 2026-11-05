"""Employee-pilot policy scope and exit checklist permission regression."""
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from test_pay_people import seed, login, PASS, ORIGIN

def switch(client,email,password=PASS):
    client.post("/auth/logout",headers=ORIGIN)
    login(client,email,password)

def test_targeted_policy_and_private_attachment_download():
    with TestClient(app) as c:
        admin,hr,employee,other=seed(c)
        created=c.post("/policies/records",headers=ORIGIN,json={
            "title":"Employee pilot confidentiality policy",
            "category":"security","description":"Confidential company policy for selected QA employees only.",
            "effective_date":date.today().isoformat(),"active":True,
            "audience_ids":[employee]})
        assert created.status_code==201,created.text
        pid=created.json()["id"]
        upload=c.post(f"/policies/records/{pid}/attachments",headers=ORIGIN,
                      files={"document":("policy.pdf",b"%PDF-1.4\n% example\n%%EOF", "application/pdf")})
        assert upload.status_code==201,upload.text
        aid=upload.json()["id"]
        switch(c,"payroll.other.qa@example.org")
        assert all(p["id"]!=pid for p in c.get("/policies/records").json())
        assert c.get(f"/policies/records/{pid}/attachments/{aid}").status_code==404
        switch(c,"payroll.person.qa@example.org")
        visible=c.get("/policies/records")
        assert any(p["id"]==pid for p in visible.json())
        assert c.get(f"/policies/records/{pid}/attachments/{aid}").status_code==200
        assert c.post(f"/policies/records/{pid}/attachments",headers=ORIGIN,
                      files={"document":("x.pdf",b"%PDF-1.4", "application/pdf")}).status_code==403

def test_hr_initiates_exit_and_assigns_employee_and_hr_checklist():
    with TestClient(app) as c:
        admin,hr,employee,other=seed(c)
        created=c.post("/exit-workflow/cases",headers=ORIGIN,json={
            "employee_id":employee,"reason":"QA planned employee exit and handover",
            "notice_days":30,"requested_date":date.today().isoformat()})
        assert created.status_code==201,created.text
        exit_id=created.json()["id"]
        tasks=c.get(f"/exit-workflow/cases/{exit_id}/tasks")
        assert tasks.status_code==200
        items=tasks.json()
        assert any(t["assignee_role"]=="hr" for t in items)
        assert any(t["assignee_role"]=="employee" for t in items)
        hr_task=next(t for t in items if t["assignee_role"]=="hr")
        employee_task=next(t for t in items if t["assignee_role"]=="employee")
        switch(c,"payroll.person.qa@example.org")
        owned=c.get(f"/exit-workflow/cases/{exit_id}/tasks").json()
        assert all(t["assignee_role"]=="employee" for t in owned)
        assert c.post(f"/exit-workflow/tasks/{hr_task['id']}/complete",headers=ORIGIN,
                      json={"note":"Not allowed to finish HR work"}).status_code==403
        assert c.post(f"/exit-workflow/tasks/{employee_task['id']}/complete",headers=ORIGIN,
                      json={"note":"Returned access badge to reception"}).status_code==200
        switch(c,"payroll.hr.qa@example.org")
        assert c.post(f"/exit-workflow/tasks/{hr_task['id']}/complete",headers=ORIGIN,
                      json={"note":"Verified employee company assets"}).status_code==200
        assert c.post(f"/exit-workflow/tasks/{hr_task['id']}/complete",headers=ORIGIN,
                      json={"note":"Double completion attempt"}).status_code==409
