-- Phase 3 financial ledger: additive, reversible by table-specific rollback plan.
-- Backup the database before execution; do not remove historic invoices.
BEGIN;
CREATE TABLE IF NOT EXISTS finance_invoice_payments (
 id SERIAL PRIMARY KEY,
 invoice_id INTEGER NOT NULL REFERENCES finance_invoices(id),
 amount NUMERIC(14,2) NOT NULL CHECK (amount > 0),
 received_on DATE NOT NULL,
 reference VARCHAR(120) NOT NULL,
 recorded_by INTEGER NOT NULL REFERENCES employees(id),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 CONSTRAINT uq_invoice_payment_reference UNIQUE(invoice_id,reference)
);
CREATE INDEX IF NOT EXISTS ix_finance_invoice_payments_invoice_id ON finance_invoice_payments(invoice_id);
CREATE TABLE IF NOT EXISTS finance_invoice_credit_notes (
 id SERIAL PRIMARY KEY,
 invoice_id INTEGER NOT NULL REFERENCES finance_invoices(id),
 subtotal NUMERIC(14,2) NOT NULL CHECK (subtotal > 0),
 tax_rate_pct NUMERIC(6,2) NOT NULL,
 tax_amount NUMERIC(14,2) NOT NULL,
 total NUMERIC(14,2) NOT NULL,
 reason TEXT NOT NULL,
 reference VARCHAR(120) NOT NULL,
 issued_on DATE NOT NULL,
 created_by INTEGER NOT NULL REFERENCES employees(id),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 CONSTRAINT uq_invoice_credit_reference UNIQUE(invoice_id,reference)
);
CREATE INDEX IF NOT EXISTS ix_finance_invoice_credit_notes_invoice_id ON finance_invoice_credit_notes(invoice_id);

-- Backfill *previously recorded* paid invoices so historic "paid" labels
-- cannot report as outstanding. The payment reference explains provenance;
-- these are not independently verified bank receipts.
INSERT INTO finance_invoice_payments (invoice_id,amount,received_on,reference,recorded_by)
 SELECT i.id,i.total,COALESCE(i.paid_at::date,i.issue_date),'legacy-paid-status-'||i.id,i.created_by
 FROM finance_invoices i
 WHERE i.status='paid'
   AND NOT EXISTS(SELECT 1 FROM finance_invoice_payments p WHERE p.invoice_id=i.id);
COMMIT;
