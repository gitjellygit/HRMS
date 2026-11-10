-- Phase 3 internal invoice numbering and optional India GST draft calculations.
-- Supplier registration, recipient registration, place-of-supply, statutory
-- applicability, SAC and e-invoicing rules require business/tax-team validation.
-- Run after backup. This does NOT make old/new invoices legal GST tax invoices.
BEGIN;
CREATE TABLE IF NOT EXISTS finance_invoice_series (
 fiscal_year INTEGER PRIMARY KEY,
 next_number INTEGER NOT NULL DEFAULT 1
);
ALTER TABLE finance_invoices ADD COLUMN IF NOT EXISTS invoice_number VARCHAR(50);
ALTER TABLE finance_invoices ADD COLUMN IF NOT EXISTS tax_scheme VARCHAR(20) NOT NULL DEFAULT 'generic';
ALTER TABLE finance_invoices ADD COLUMN IF NOT EXISTS supplier_gstin VARCHAR(15) NOT NULL DEFAULT '';
ALTER TABLE finance_invoices ADD COLUMN IF NOT EXISTS recipient_gstin VARCHAR(15) NOT NULL DEFAULT '';
ALTER TABLE finance_invoices ADD COLUMN IF NOT EXISTS sac_code VARCHAR(8) NOT NULL DEFAULT '';
ALTER TABLE finance_invoices ADD COLUMN IF NOT EXISTS place_of_supply VARCHAR(2) NOT NULL DEFAULT '';
ALTER TABLE finance_invoices ADD COLUMN IF NOT EXISTS cgst_amount NUMERIC(14,2) NOT NULL DEFAULT 0;
ALTER TABLE finance_invoices ADD COLUMN IF NOT EXISTS sgst_amount NUMERIC(14,2) NOT NULL DEFAULT 0;
ALTER TABLE finance_invoices ADD COLUMN IF NOT EXISTS igst_amount NUMERIC(14,2) NOT NULL DEFAULT 0;
-- Historic rows keep explicit legacy identifiers, not misleading current-year
-- fiscal sequences. New invoices receive proper yearly separate sequences.
UPDATE finance_invoices SET invoice_number='JG/LEGACY/'||id WHERE invoice_number IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_invoices_invoice_number
 ON finance_invoices(invoice_number) WHERE invoice_number IS NOT NULL;
COMMIT;
