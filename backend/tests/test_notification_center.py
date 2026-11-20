"""Employee-scoped in-app notification acceptance and announcement delivery tests."""
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from test_pay_people import seed, login, PASS, ORIGIN

def switch(c,email,password=PASS):
    c.post("/auth/logout",headers=ORIGIN)
    login(c,email,password)

def test_hr_announcement_fans_out_to_employee_and_read_archive_are_private():
    with TestClient(app) as c:
        admin,hr,employee,other=seed(c)
        published=c.post("/people/announcements",headers=ORIGIN,json={
            "title":"QA employee-pilot policy news",
            "body":"Employees should read the new pilot policy and complete their assigned HR checklist.",
            "requires_ack":True})
        assert published.status_code==201,published.text
        assert published.json()["recipients"]>=4
        switch(c,"payroll.person.qa@example.org")
        inbox=c.get("/notification-center")
        assert inbox.status_code==200,inbox.text
        notice=next(n for n in inbox.json()["items"] if n["title"]=="QA employee-pilot policy news")
        assert not notice["read"] and not notice["archived"]
        assert notice["destination"]=="people"
        assert inbox.json()["unread_count"]>=1
        nid=notice["id"]
        marked=c.post(f"/notification-center/{nid}/read",headers=ORIGIN)
        assert marked.status_code==200
        assert c.post(f"/notification-center/{nid}/read",headers=ORIGIN).status_code==200
        item=next(n for n in c.get("/notification-center").json()["items"] if n["id"]==nid)
        assert item["read"] is True
        assert c.post(f"/notification-center/{nid}/archive",headers=ORIGIN).status_code==200
        assert all(n["id"]!=nid for n in c.get("/notification-center").json()["items"])
        historical=c.get("/notification-center?include_archived=true")
        item=next(n for n in historical.json()["items"] if n["id"]==nid)
        assert item["archived"] is True
        # Archiving inbox never acknowledges a required company policy.
        announcements=c.get("/people/announcements").json()
        assert next(n for n in announcements if n["id"]==published.json()["id"])["acknowledged"] is False
        switch(c,"payroll.other.qa@example.org")
        assert c.post(f"/notification-center/{nid}/read",headers=ORIGIN).status_code==404
        assert c.post(f"/notification-center/{nid}/archive",headers=ORIGIN).status_code==404
        second=c.get("/notification-center").json()
        assert any(n["title"]=="QA employee-pilot policy news" and not n["read"] for n in second["items"])

def test_queue_creates_inapp_notice_and_mark_all_read_only_for_current_user():
    with TestClient(app) as c:
        admin,hr,employee,other=seed(c)
        notification=c.post("/people/notifications/queue",headers=ORIGIN,json={
            "employee_id":employee,"event":"approval",
            "subject":"QA Leave request status update",
            "body":"Your leave approval has progressed to the next reviewer."})
        assert notification.status_code==200
        switch(c,"payroll.person.qa@example.org")
        inbox=c.get("/notification-center").json()
        assert any(x["title"]=="QA Leave request status update" for x in inbox["items"])
        result=c.post("/notification-center/read-all",headers=ORIGIN)
        assert result.status_code==200 and result.json()["marked"]>=1
        assert c.get("/notification-center").json()["unread_count"]==0
        assert c.get("/notification-center?limit=0").status_code==422
        assert c.get("/notification-center?limit=201").status_code==422
        switch(c,"payroll.other.qa@example.org")
        assert all(x["title"]!="QA Leave request status update" for x in c.get("/notification-center").json()["items"])
