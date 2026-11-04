"""Integration smoke test for Employee Core; runs against isolated CI PostgreSQL."""
import os
from datetime import date, timedelta

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

os.environ.setdefault("HRMS_PII_KEY", Fernet.generate_key().decode())

from app.main import app, SessionLocal, Employee
from app.employee_core import EmployeeCore

ORIGIN={"Origin":"http://localhost:3000"}

def account(name, email, role="employee"):
    return {"name":name,"email":email,"password":"MySecurePassword1!","role":role,
            "designation":"Software Engineer","department":"Engineering",
            "joining_date":"2026-11-03"}

def test_employee_core_end_to_end():
    with TestClient(app) as client:
        response=client.post("/auth/login",json={"email":"admin@example.com","password":"test-admin-password-12345"})
        assert response.status_code==200,response.text
        admin_id=client.get("/me").json()["id"]
        unit=client.post("/core/units",headers=ORIGIN,json={"kind":"department","name":"Engineering","code":"ENG"})
        assert unit.status_code==201,unit.text
        assert client.get("/core/units").status_code==200
        duplicate_name=client.post("/core/units",headers=ORIGIN,
            json={"kind":"department","name":" engineering ","code":"ENG-SECOND"})
        assert duplicate_name.status_code==409,duplicate_name.text
        duplicate_code=client.post("/core/units",headers=ORIGIN,
            json={"kind":"department","name":"Engineering Two","code":"ENG"})
        assert duplicate_code.status_code==409,duplicate_code.text
        new_dept=client.post("/core/units",headers=ORIGIN,
            json={"kind":"department","name":"Talent Acquisition","code":"TALENT-ACQUISITION"})
        assert new_dept.status_code==201,new_dept.text
        department_choices=client.get("/core/units?kind=department").json()
        assert any(row["id"]==new_dept.json()["id"] for row in department_choices)

        manager=client.post("/core/employees",headers=ORIGIN,
            json={"account":account("Morgan Manager","morgan.manager@example.org","manager"),"master":{"department_id":unit.json()["id"],"manager_id":admin_id}})
        assert manager.status_code==201,manager.text
        manager_id=manager.json()["id"]
        person=client.post("/core/employees",headers=ORIGIN,
            json={"account":account("Aarav Sharma","aarav.sharma@example.org"),
                  "master":{"manager_id":manager_id,"department_id":unit.json()["id"],"pan":"ABCDE1234F"}})
        assert person.status_code==201,person.text
        employee_id=person.json()["id"]
        assert person.json()["employee_code"]=="JG-002"
        assert person.json()["master"]["manager_id"]==manager_id
        # API uses the selected department ID, even if a client sends stale text.
        hr_employee=client.post("/core/employees",headers=ORIGIN,json={
            "account":account("Tara Kapoor","tara.kapoor@example.org"),
            "master":{"department_id":new_dept.json()["id"],"manager_id":manager_id}})
        assert hr_employee.status_code==201,hr_employee.text
        assert hr_employee.json()["department"]=="Talent Acquisition"

        with SessionLocal() as session:
            core=session.get(EmployeeCore,employee_id)
            assert core.pan and "ABCDE1234F" not in core.pan

        chart=client.get("/core/org-chart")
        assert chart.status_code==200
        assert any(x["id"]==employee_id and x["manager_id"]==manager_id for x in chart.json())

        upload=client.post("/core/employees/"+str(employee_id)+"/documents?category=certificate&expiry_date="+(date.today()+timedelta(days=12)).isoformat(),
                           headers=ORIGIN,files={"document":("cert.pdf",b"%PDF-1.7\nTest content","application/pdf")})
        assert upload.status_code==201,upload.text
        alerts=client.get("/core/document-alerts")
        assert alerts.status_code==200 and any(d["document_id"]==upload.json()["id"] for d in alerts.json())

        exported=client.get("/core/employees-export?format=csv")
        assert exported.status_code==200 and b"Aarav Sharma" in exported.content
        assert b"ABCDE1234F" not in exported.content

        preview=client.post("/core/employees-import?dry_run=true",headers=ORIGIN,
              files={"document":("employees.csv",b"name,email,designation,department,role\nPriya Kapoor,priya.kapoor@example.org,QA Engineer,Quality,employee\n","text/csv")})
        assert preview.status_code==200,preview.text
        assert preview.json()["valid"] is True

        client.post("/auth/logout",headers=ORIGIN)
        employee_login=client.post("/auth/login",json={"email":"aarav.sharma@example.org","password":"MySecurePassword1!"})
        assert employee_login.status_code==200
        employee_profile=client.get("/core/me")
        assert employee_profile.status_code==200
        assert employee_profile.json()["master"]["pan"]=="••••"
        assert client.get("/core/employees/"+str(manager_id)).status_code==403
        change=client.post("/core/me/change-requests",headers=ORIGIN,
                           json={"field_name":"address","value":"10 Lake Road, Noida"})
        assert change.status_code==201,change.text
        change_id=change.json()["id"]
        assert client.get("/core/changes").json()[0]["status"]=="pending"

        client.post("/auth/logout",headers=ORIGIN)
        assert client.post("/auth/login",json={"email":"admin@example.com","password":"test-admin-password-12345"}).status_code==200
        approval=client.post("/core/changes/"+str(change_id)+"/review",headers=ORIGIN,json={"approve":True})
        assert approval.status_code==200,approval.text
        assert client.get("/core/employees/"+str(employee_id)).json()["master"]["address"]=="10 Lake Road, Noida"
        lifecycle=client.post("/core/employees/"+str(employee_id)+"/lifecycle",headers=ORIGIN,
                              json={"event":"confirmed","note":"Probation completed","effective_date":"2026-11-03"})
        assert lifecycle.status_code==200
        assert client.get("/core/employees/"+str(employee_id)+"/lifecycle").json()[0]["event"]=="confirmed"
