"""Run from scheduler: python -m app.leave_email_worker

One invocation drains a bounded batch. Configure regular invocation in the
deployment scheduler; API requests never wait for SMTP.
"""
import json
from .main import SessionLocal
from .leave_management import deliver_queued_emails

def main():
    with SessionLocal() as db:
        result=deliver_queued_emails(db,limit=50)
    print(json.dumps(result))

if __name__=="__main__":
    main()
