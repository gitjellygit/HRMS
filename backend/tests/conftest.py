"""Reset CI's disposable PostgreSQL between test cases.

Guarded by HRMS_TEST_RESET_DB=1: NEVER enable this against local/staging/production
data. The GitHub Actions backend service owns a dedicated ephemeral database.
"""
import os
import pytest
from sqlalchemy import text
from app.main import Base, engine


@pytest.fixture(autouse=True)
def isolated_backend_database():
    if (os.environ.get("HRMS_TEST_RESET_DB") != "1"
            or os.environ.get("CI") != "true"
            or engine.url.database != "hrms_test"):
        yield
        return
    Base.metadata.create_all(bind=engine)
    names=", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        if names:
            conn.execute(text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE"))
        for sequence in ("hrms_employee_code_seq", "hrms_project_number_seq"):
            conn.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {sequence} START WITH 1"))
            conn.execute(text(f"ALTER SEQUENCE {sequence} RESTART WITH 1"))
    yield


@pytest.fixture(autouse=True)
def activated_staff_for_legacy_workflows(monkeypatch,request):
    """Legacy integration suites start with fully onboarded fixture employees.

    Real employee creation remains must_change_password=True. The dedicated
    hardening test exercises that actual first-login requirement independently.
    This fixture ONLY runs with the disposable CI PostgreSQL test database.
    """
    if (os.environ.get("HRMS_TEST_RESET_DB")!="1"
            or os.environ.get("CI")!="true"
            or engine.url.database!="hrms_test"
            or request.node.name.startswith("test_first_login_")):
        yield
        return
    from fastapi.testclient import TestClient
    from app.main import SessionLocal, Employee
    original=TestClient.post
    def post_and_activate(self,url,*args,**kwargs):
        result=original(self,url,*args,**kwargs)
        if (str(url).split("?")[0]=="/core/employees"
                and result.status_code==201):
            employee_id=result.json().get("id")
            if employee_id:
                with SessionLocal() as session:
                    staff=session.get(Employee,employee_id)
                    if staff:
                        staff.must_change_password=False
                        session.commit()
        return result
    monkeypatch.setattr(TestClient,"post",post_and_activate)
    yield
