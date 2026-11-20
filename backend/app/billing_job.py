"""Daily invoice scheduler. Run from cron in a configured deployment.

Example (02:00 server time):
0 2 * * * cd /srv/hrms && /srv/hrms/.venv/bin/python -m app.billing_job

Do not run against production before backup/migration and finance sign-off.
"""
import json
from datetime import date
from sqlalchemy import select
from .main import SessionLocal, Employee
from .project_finance import ScheduleIn, run_schedule

def main():
    with SessionLocal() as db:
        # System-generated drafts are attributed to the configured administration account.
        service=db.scalar(select(Employee).where(Employee.role.in_(("admin","super_admin")),
                                             Employee.status=="active").order_by(Employee.id))
        if service is None:
            raise RuntimeError("Cannot run billing job without an active administrator")
        result=run_schedule(ScheduleIn(as_of=date.today()),user=service,db=db)
        print(json.dumps({"as_of":result["as_of"].isoformat(),
          "draft_count":len(result["created"]),
          "skipped_count":len(result["skipped"]),
          "emails_sent":False}))
if __name__=="__main__":
    main()
