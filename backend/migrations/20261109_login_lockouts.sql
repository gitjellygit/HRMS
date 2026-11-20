-- Phase 1 login hardening: persistent failed-attempt lockouts.
-- Execute only after taking a database backup; existing employee rows are preserved.
BEGIN;
CREATE TABLE IF NOT EXISTS sec_login_failures (
    employee_id INTEGER PRIMARY KEY REFERENCES employees(id),
    failed_count INTEGER NOT NULL DEFAULT 0,
    locked_at TIMESTAMPTZ,
    locked_until TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_sec_login_failures_locked_until
    ON sec_login_failures(locked_until);
COMMIT;
