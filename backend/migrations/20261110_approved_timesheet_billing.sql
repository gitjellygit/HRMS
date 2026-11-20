-- Phase 3 approved-hours billing and manager timesheet review.
-- Additive only; run after database backup and before deploying updated code.
BEGIN;
ALTER TABLE time_timesheets
 ADD COLUMN IF NOT EXISTS reviewed_by INTEGER REFERENCES employees(id);
ALTER TABLE time_timesheets
 ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;
CREATE TABLE IF NOT EXISTS time_project_assignments (
 employee_id INTEGER NOT NULL REFERENCES employees(id),
 project_id INTEGER NOT NULL REFERENCES projects(id),
 active BOOLEAN NOT NULL DEFAULT true,
 assigned_by INTEGER NOT NULL REFERENCES employees(id),
 PRIMARY KEY(employee_id,project_id)
);
CREATE TABLE IF NOT EXISTS finance_timesheet_invoice_allocations (
 id SERIAL PRIMARY KEY,
 timesheet_id INTEGER NOT NULL REFERENCES time_timesheets(id),
 invoice_id INTEGER NOT NULL REFERENCES finance_invoices(id),
 hours NUMERIC(7,2) NOT NULL CHECK(hours > 0),
 active BOOLEAN NOT NULL DEFAULT true
);
CREATE INDEX IF NOT EXISTS ix_finance_timesheet_invoice_allocations_timesheet_id
 ON finance_timesheet_invoice_allocations(timesheet_id);
CREATE INDEX IF NOT EXISTS ix_finance_timesheet_invoice_allocations_invoice_id
 ON finance_timesheet_invoice_allocations(invoice_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_timesheet_invoice
 ON finance_timesheet_invoice_allocations(timesheet_id) WHERE active = true;
COMMIT;
