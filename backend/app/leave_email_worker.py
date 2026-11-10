"""SMTP outbox processor (run as isolated service; never from an API request).

One-shot: python -m app.leave_email_worker
Service:  python -m app.leave_email_worker --loop
"""
import json
import logging
import sys
import time
from .main import SessionLocal
from .leave_management import deliver_queued_emails

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger(__name__)

def once():
    with SessionLocal() as db:
        result=deliver_queued_emails(db,limit=50)
    logger.info("Leave email outbox: %s",json.dumps(result))
    return result

def main():
    if "--loop" in sys.argv:
        while True:
            try:
                once()
            except Exception:
                logger.exception("Leave email outbox worker iteration failed")
            time.sleep(60)
    else:
        once()

if __name__=="__main__":
    main()
