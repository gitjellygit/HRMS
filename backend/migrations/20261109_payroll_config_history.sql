-- Phase 2: immutable effective-dated pay configuration change history.
-- Run only after taking and verifying a database backup.
BEGIN;
CREATE TABLE IF NOT EXISTS pay_config_versions (
    id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    kind VARCHAR(20) NOT NULL,
    effective_from DATE NOT NULL,
    payload TEXT NOT NULL,
    changed_by INTEGER NOT NULL REFERENCES employees(id),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_pay_config_versions_employee_id
    ON pay_config_versions(employee_id);
CREATE INDEX IF NOT EXISTS ix_pay_config_versions_kind
    ON pay_config_versions(kind);
CREATE INDEX IF NOT EXISTS ix_pay_config_versions_employee_effective
    ON pay_config_versions(employee_id,kind,effective_from DESC,id DESC);
COMMIT;
