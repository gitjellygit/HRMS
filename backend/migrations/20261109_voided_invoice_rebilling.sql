-- Phase 3: permit a replacement invoice after voiding, without losing void history.
-- Apply once to existing PostgreSQL deployments BEFORE running the updated API.
-- Run on a backed-up, quiesced database in a controlled maintenance window.
BEGIN;
ALTER TABLE finance_invoices
    DROP CONSTRAINT IF EXISTS uq_finance_project_invoice_window;
CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_project_invoice_window_active
    ON finance_invoices(project_id, period_start, period_end, recipient_type)
    WHERE status <> 'void';
COMMIT;
