-- Durable email outbox for Phase 4 leave notifications.
-- Apply after a verified backup and before upgrading the API or worker.
BEGIN;
CREATE TABLE IF NOT EXISTS leave_email_outbox (
 id SERIAL PRIMARY KEY,
 recipient_id INTEGER NOT NULL REFERENCES employees(id),
 request_id INTEGER REFERENCES leave_requests_v2(id),
 subject VARCHAR(160) NOT NULL,
 message TEXT NOT NULL,
 status VARCHAR(24) NOT NULL DEFAULT 'queued',
 attempts INTEGER NOT NULL DEFAULT 0,
 last_error VARCHAR(500) NOT NULL DEFAULT '',
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 sent_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_leave_email_outbox_recipient_id ON leave_email_outbox(recipient_id);
CREATE INDEX IF NOT EXISTS ix_leave_email_outbox_status ON leave_email_outbox(status);
COMMIT;
