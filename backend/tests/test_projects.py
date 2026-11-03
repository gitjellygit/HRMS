"""Project management API smoke coverage."""
from fastapi.testclient import TestClient
from app.main import SessionLocal
from app.project_management import sync_matured_bonuses
from datetime import date, timedelta
from app.main import app

ORIGIN={"Origin":"http://localhost:3000"}

def test_project_management():
    with TestClient(app) as client:
        login=client.post("/auth/login",json={"email":"admin@example.com","password":"test-admin-password-12345"})
        assert login.status_code==200,login.text
        me=client.get("/me").json()
        owner_id=me["id"]
        preview=client.get("/project-management/next-number")
        assert preview.status_code==200,preview.text
        assert preview.json()["project_number"].startswith("JG-P-")
        invalid=client.post("/project-management/projects",headers=ORIGIN,json={"name":"Implementation","client":"","engagement_type":"c2c","rate":80})
        assert invalid.status_code==422
        project=client.post("/project-management/projects",headers=ORIGIN,json={
            "name":"Platform Modernization", "client":"Acme Corporation",
            "candidate_name":"Alex Engineer","vendor_name":"Talent Partner",
            "prime_vendor_name":"Prime Consulting","engagement_type":"c2c",
            "rate":95,"currency":"USD","rate_unit":"hour",
            "description":"Modernization and API development",
            "sourced_by_id":owner_id,"start_date":str(date.today()-timedelta(days=31)),
            "bonus_amount_inr":15000})
        assert project.status_code==201,project.text
        data=project.json()
        assert data["project_number"].startswith("JG-P-")
        assert data["client"]=="Acme Corporation"
        assert data["candidate_name"]=="Alex Engineer"
        assert data["prime_vendor_name"]=="Prime Consulting"
        assert data["rate"]==95
        assert data["sourced_by_id"]==owner_id
        assert data["bonus_status"]=="eligible"
        assert data["bonus_amount_inr"]==15000
        awarded=client.post("/project-management/projects/"+str(data["id"])+"/award-bonus",headers=ORIGIN)
        assert awarded.status_code==201,awarded.text
        assert awarded.json()["amount_inr"]==15000
        assert client.post("/project-management/projects/"+str(data["id"])+"/award-bonus",headers=ORIGIN).status_code==409
        assert client.get("/project-management/projects/"+str(data["id"])).status_code==200
        assert any(p["project_number"]==data["project_number"] for p in client.get("/project-management/projects").json())
        another=client.post("/project-management/projects",headers=ORIGIN,json={
            "name":"Engineering Support","client":"Northwind Ltd","engagement_type":"w2",
            "rate":62.5,"currency":"USD","rate_unit":"hour",
            "sourced_by_id":owner_id,"start_date":str(date.today()+timedelta(days=2)),
            "bonus_amount_inr":10000})
        assert another.status_code==201,another.text
        assert another.json()["project_number"]!=data["project_number"]
        assert another.json()["bonus_status"]=="waiting"
        assert client.post("/project-management/projects/"+str(another.json()["id"])+"/award-bonus",headers=ORIGIN).status_code==409
        # Automatic catch-up creates exactly one award per matured project.
        mature=client.post("/project-management/projects",headers=ORIGIN,json={
            "name":"Data Engineering Rollout","client":"Global Retail",
            "engagement_type":"c2c","rate":70,"currency":"USD","rate_unit":"hour",
            "sourced_by_id":owner_id,"start_date":str(date.today()-timedelta(days=40)),
            "bonus_amount_inr":10000})
        assert mature.status_code==201,mature.text
        with SessionLocal() as session:
            assert sync_matured_bonuses(session)==1
            assert sync_matured_bonuses(session)==0
        assert client.get("/project-management/projects/"+str(mature.json()["id"])).json()["bonus_status"]=="awarded"
        assert len(client.get("/project-management/my-bonuses").json())>=2

        # Punch In/Punch Out buttons follow server state.
        before=client.get("/attendance/status")
        assert before.status_code==200
        first=client.post("/attendance/punch",headers=ORIGIN)
        assert first.status_code==200
        changed=client.get("/attendance/status").json()
        assert changed["checked_in"]!=before.json()["checked_in"]
        second=client.post("/attendance/punch",headers=ORIGIN)
        assert second.status_code==200
        assert client.get("/attendance/status").json()["checked_in"]==before.json()["checked_in"]
        client.post("/auth/logout",headers=ORIGIN)
        employee=client.post("/auth/login",json={"email":"leave.employee@example.org","password":"TestingPassword123!"})
        # Other tests may not share this user's existence. If absent, use a seeded account.
        if employee.status_code==200:
            assert client.get("/project-management/next-number").status_code==403
            assert client.post("/project-management/projects",headers=ORIGIN,json={
                "name":"Unauthorized Project","client":"Acme","engagement_type":"c2c","rate":50}).status_code==403
