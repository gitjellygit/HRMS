"""Authorization and first-login security integration tests in a disposable PostgreSQL database."""
from datetime import date
from fastapi.testclient import TestClient
from app.main import app

ORIGIN={"Origin":"http://localhost:3000"}
PASSWORD="TestingStrong!2345"

def account(name,email,role="employee"):
    return {"name":name,"email":email,"password":PASSWORD,"role":role,
            "designation":"QA Engineer","department":"Engineering","joining_date":str(date.today())}

def create(c, name,email,role,manager_id):
    r=c.post("/core/employees",headers=ORIGIN,
             json={"account":account(name,email,role),"master":{"manager_id":manager_id}})
    assert r.status_code==201,r.text
    return r.json()["id"]

def login(c,email,password=PASSWORD):
    response=c.post("/auth/login",json={"email":email,"password":password})
    assert response.status_code==200,response.text
    return response.json()

def test_employee_project_access_and_appraisals():
    with TestClient(app) as c:
        login(c,"admin@example.com","test-admin-password-12345")
        admin_id=c.get("/me").json()["id"]
        manager_id=create(c,"Private Manager","private.manager.qa@example.org","manager",admin_id)
        first=create(c,"First Developer","first.developer.qa@example.org","employee",manager_id)
        second=create(c,"Second Developer","second.developer.qa@example.org","employee",manager_id)
        assert c.post("/core/employees",headers=ORIGIN,json={
            "account":account("Missing Manager","missing.manager.qa@example.org"),
            "master":{}}).status_code==422
        def project(name,owner):
            p=c.post("/project-management/projects",headers=ORIGIN,json={
                "name":name,"client":"QA Client","engagement_type":"c2c","rate":95,
                "start_date":str(date.today()),"sourced_by_id":owner})
            assert p.status_code==201,p.text
            return p.json()["id"]
        first_project=project("First Private Project",first)
        second_project=project("Second Private Project",second)
        a1=c.post("/appraisals",headers=ORIGIN,json={
            "employee_id":first,"period":"2026-Q4","rating":4,"feedback":"QA positive"})
        a2=c.post("/appraisals",headers=ORIGIN,json={
            "employee_id":second,"period":"2026-Q4","rating":3,"feedback":"QA followup"})
        assert a1.status_code==201 and a2.status_code==201
        assert {first_project,second_project}.issubset({p["id"] for p in c.get("/project-management/projects").json()})
        assert len(c.get("/appraisals").json())>=2
        c.post("/auth/logout",headers=ORIGIN)
        login(c,"first.developer.qa@example.org")
        assert c.get("/dashboard").status_code==200
        assert c.get("/dashboard").json()["active_projects"]==1
        own=c.get("/project-management/projects").json()
        assert [p["id"] for p in own]==[first_project]
        assert c.get("/project-management/projects/"+str(second_project)).status_code==404
        assert c.get("/projects/"+str(second_project)+"/team").status_code==404
        assert [p["id"] for p in c.get("/projects").json()]==[first_project]
        assert all(p["employee_id"]==first for p in c.get("/appraisals").json())
        assert c.get("/core/org-chart").status_code==200
        assert c.get("/core/me").status_code==200
        assert c.get("/policies/project-bonus").status_code==403
        assert c.get("/employees").status_code==403


def test_hr_password_reset_sends_link_without_exposing_credentials(monkeypatch):
    from urllib.parse import urlsplit,parse_qs
    messages=[]
    monkeypatch.setattr("app.main.send_reset_mail",lambda email,link: messages.append((email,link)))
    with TestClient(app) as c:
        login(c,"admin@example.com","test-admin-password-12345")
        admin=c.get("/me").json()["id"]
        manager=create(c,"Credential Manager","credential.manager.qa@example.org","manager",admin)
        person=create(c,"Credential Person","credential.person.qa@example.org","employee",manager)
        reset=c.post("/core/employees/"+str(person)+"/reset-password",
                     headers=ORIGIN,json={"reason":"Password compromised and HR reviewed"})
        assert reset.status_code==200,reset.text
        assert reset.json()["reset_email_sent"] is True
        assert "temporary_password" not in reset.json()
        assert messages[0][0]=="credential.person.qa@example.org"
        token=parse_qs(urlsplit(messages[0][1]).query)["reset"][0]
        c.post("/auth/logout",headers=ORIGIN)
        new_password="CompletelyNew!Pass789"
        changed=c.post("/auth/reset-password",headers=ORIGIN,
                       json={"token":token,"password":new_password})
        assert changed.status_code==200,changed.text
        assert c.post("/auth/reset-password",headers=ORIGIN,
               json={"token":token,"password":"AnotherNew!Pass567"}).status_code==400
        assert c.post("/auth/login",json={
            "email":"credential.person.qa@example.org","password":PASSWORD}).status_code==401
        signed=login(c,"credential.person.qa@example.org",new_password)
        assert signed["user"]["must_change_password"] is False
        assert c.get("/dashboard").status_code==200
        assert c.post("/auth/change-password",headers=ORIGIN,json={
            "current_password":new_password,"new_password":"AnotherNew!Pass567"}).status_code==200
