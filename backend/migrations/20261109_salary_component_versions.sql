-- Phase 2: immutable salary component revisions.
-- Apply only after backing up an isolated/staged PostgreSQL database.
BEGIN;
CREATE TABLE IF NOT EXISTS pay_salary_component_versions (
    id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    code VARCHAR(35) NOT NULL,
    title VARCHAR(100) NOT NULL,
    kind VARCHAR(15) NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    effective_from DATE NOT NULL,
    active BOOLEAN NOT NULL,
    changed_by INTEGER NOT NULL REFERENCES employees(id),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_pay_salary_component_versions_employee_id
    ON pay_salary_component_versions(employee_id);
CREATE INDEX IF NOT EXISTS ix_pay_salary_component_versions_code
    ON pay_salary_component_versions(code);
CREATE INDEX IF NOT EXISTS ix_pay_salary_component_versions_lookup
    ON pay_salary_component_versions(employee_id,code,effective_from DESC,id DESC);
COMMIT;
