"""Notification removal affects only the authenticated recipient and preserves history."""
from fastapi.testclient import TestClient
from app.main import app,SessionLocal
from app.notification_center import add_inbox
from test_pay_people import seed,login,ORIGIN,PASS


def switch(c,email):
    c.post("/auth/logout",headers=ORIGIN)
    login(c,email,PASS)


def test_mark_read_clear_and_restore_are_scoped_to_owner():
    with TestClient(app) as c:
        admin,hr,worker,other=seed(c)
        with SessionLocal() as db:
            notice=add_inbox(db,hr,"payroll","Salary approval pending",
                 "A proposed compensation change is awaiting your review.","governance")
            db.commit();db.refresh(notice);ident=notice.id
        switch(c,"payroll.hr.qa@example.org")
        result=c.get("/notification-center")
        assert result.status_code==200,result.text
        assert any(item["id"]==ident for item in result.json()["items"])
        assert c.post(f"/notification-center/{ident}/read",headers=ORIGIN).status_code==200
        clear=c.post("/notification-center/archive-read",headers=ORIGIN)
        assert clear.status_code==200,clear.text
        hidden=c.get("/notification-center")
        assert all(item["id"]!=ident for item in hidden.json()["items"])
        archived=c.get("/notification-center?include_archived=true")
        assert any(item["id"]==ident for item in archived.json()["items"])
        switch(c,"payroll.other.qa@example.org")
        assert c.post(f"/notification-center/{ident}/restore",headers=ORIGIN).status_code==404
        switch(c,"payroll.hr.qa@example.org")
        assert c.post(f"/notification-center/{ident}/restore",headers=ORIGIN).status_code==200
        assert any(item["id"]==ident for item in c.get("/notification-center").json()["items"])
