-- Explicit two-rate monthly leave accrual (April-Nov, December-March).
-- Apply on a backed-up, tested database before deploying the matching application code.
ALTER TABLE leave_policies
  ADD COLUMN IF NOT EXISTS late_year_monthly_accrual NUMERIC(7,2) NOT NULL DEFAULT 0;
