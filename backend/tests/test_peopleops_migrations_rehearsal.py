"""Migration rehearsal on a disposable legacy Postgres schema, including idempotence."""
import json
import os
import uuid
from pathlib import Path

import psycopg
import pytest

ROOT=Path(__file__).resolve().parents[1]/"migrations"
SCRIPTS=[
    "20261117_custom_monthly_leave_schedule.sql",
    "20261117_company_letterhead.sql",
    "20261117_offer_logo_snapshot.sql",
    "20261117_onboarding_categories.sql",
    "20261117_announcement_media_audience.sql",
    "20261117_activity_agent_devices.sql",
    "20261117_activity_agent_app_usage.sql",
    "20261117_leave_policy_year_and_versions.sql",
    "20261119_leave_probation_months.sql",
]

def test_peopleops_migrations_apply_twice_and_preserve_legacy_policy():
    url=os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("Needs disposable PostgreSQL CI database")
    url=url.replace("postgresql+psycopg://","postgresql://")
    schema="qa_migrations_"+uuid.uuid4().hex[:12]
    with psycopg.connect(url,autocommit=True) as conn:
        with conn.cursor() as cursor:
            cursor.execute(f'CREATE SCHEMA "{schema}"')
            try:
                cursor.execute(f'SET search_path TO "{schema}",public')
                cursor.execute("""CREATE TABLE employees (id SERIAL PRIMARY KEY)""")
                cursor.execute("""CREATE TABLE leave_policies(
                   id SERIAL PRIMARY KEY,leave_type VARCHAR(30) UNIQUE,
                   annual_days NUMERIC(7,2) DEFAULT 0,
                   monthly_accrual NUMERIC(7,2) DEFAULT 0,
                   late_year_monthly_accrual NUMERIC(7,2) DEFAULT 0,
                   carry_forward_limit NUMERIC(7,2) DEFAULT 0,
                   encashment_allowed BOOLEAN DEFAULT FALSE,
                   probation_allowed BOOLEAN DEFAULT TRUE,
                   approval_chain VARCHAR(100) DEFAULT 'manager,hr',
                   active BOOLEAN DEFAULT TRUE)""")
                cursor.execute("""INSERT INTO leave_policies
                  (leave_type,annual_days,monthly_accrual,carry_forward_limit)
                  VALUES ('earned',18,0,5)""")
                cursor.execute("CREATE TABLE people_offers (id SERIAL PRIMARY KEY)")
                cursor.execute("CREATE TABLE people_announcements (id SERIAL PRIMARY KEY)")
                for _ in range(2):
                    for name in SCRIPTS:
                        cursor.execute((ROOT/name).read_text())
                cursor.execute("SELECT year_type FROM leave_policies WHERE leave_type='earned'")
                assert cursor.fetchone()[0]=="financial"
                cursor.execute("SELECT probation_months FROM leave_policies WHERE leave_type=\'earned\'")
                assert cursor.fetchone()[0]==3
                cursor.execute("SELECT snapshot_json FROM leave_policy_versions WHERE leave_type='earned'")
                rows=cursor.fetchall()
                assert len(rows)==1
                terms=json.loads(rows[0][0])
                assert terms["annual_days"]=="18.00"
                assert terms["carry_forward_limit"]=="5.00"
                cursor.execute("SELECT COUNT(*) FROM people_onboarding_categories")
                assert cursor.fetchone()[0]==5
                for table,column in (
                    ("leave_policies","monthly_schedule"),
                    ("leave_policies","probation_months"),
                    ("people_offers","letterhead_logo_key"),
                    ("people_announcements","audience_ids"),
                    ("activity_agent_devices","app_usage_json")):
                    cursor.execute("""SELECT 1 FROM information_schema.columns
                        WHERE table_schema=%s AND table_name=%s AND column_name=%s""",
                        (schema,table,column))
                    assert cursor.fetchone(),f"{table}.{column} missing"
            finally:
                cursor.execute("SET search_path TO public")
                cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
