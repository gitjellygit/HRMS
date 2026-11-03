"""Project management API smoke coverage."""
from fastapi.testclient import TestClient
from app.main import app

ORIGIN={"Origin":"http://localhost:3000"}

def test_project_management():
    with TestClient(app) as client:
        login=client.post("/auth/login",json={"email":"admin@example.com","password":"test-admin-password-12345"})
        assert login.status_code==200,login.text
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
            "description":"Modernization and API development"})
        assert project.status_code==201,project.text
        data=project.json()
        assert data["project_number"].startswith("JG-P-")
        assert data["client"]=="Acme Corporation"
        assert data["candidate_name"]=="Alex Engineer"
        assert data["prime_vendor_name"]=="Prime Consulting"
        assert data["rate"]==95
        assert client.get("/project-management/projects/"+str(data["id"])).status_code==200
        assert any(p["project_number"]==data["project_number"] for p in client.get("/project-management/projects").json())
        another=client.post("/project-management/projects",headers=ORIGIN,json={
            "name":"Engineering Support","client":"Northwind Ltd","engagement_type":"w2",
            "rate":62.5,"currency":"USD","rate_unit":"hour"})
        assert another.status_code==201,another.text
        assert another.json()["project_number"]!=data["project_number"]
        client.post("/auth/logout",headers=ORIGIN)
        employee=client.post("/auth/login",json={"email":"leave.employee@example.org","password":"TestingPassword123!"})
        # Other tests may not share this user's existence. If absent, use a seeded account.
        if employee.status_code==200:
            assert client.get("/project-management/next-number").status_code==403
            assert client.post("/project-management/projects",headers=ORIGIN,json={
                "name":"Unauthorized Project","client":"Acme","engagement_type":"c2c","rate":50}).status_code==403
