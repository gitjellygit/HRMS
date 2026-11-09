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
