-- Pre-pilot manual payslips: append-only imports, employee-private access.
-- A manual import is a replacement for display purposes, not deletion of prior history.
CREATE TABLE IF NOT EXISTS pay_manual_payslips (
    id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    period VARCHAR(7) NOT NULL,
    original_name VARCHAR(180) NOT NULL,
    storage_key VARCHAR(80) NOT NULL UNIQUE,
    uploaded_by INTEGER NOT NULL REFERENCES employees(id),
    reason VARCHAR(500) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_pay_manual_employee ON pay_manual_payslips(employee_id);
CREATE INDEX IF NOT EXISTS ix_pay_manual_period ON pay_manual_payslips(period);
