-- JellyGit HRMS: finance cadence/rate-basis additive migration.
-- Apply once to a backed-up PostgreSQL instance in an approved maintenance window.
-- Existing billing records default to monthly; existing invoice rates default to
-- hourly for compatibility. No published invoice amount or project rate is changed.
BEGIN;
ALTER TABLE finance_project_billing
    ADD COLUMN IF NOT EXISTS billing_frequency VARCHAR(20) NOT NULL DEFAULT 'monthly';
ALTER TABLE finance_project_charges
    ADD COLUMN IF NOT EXISTS rate_unit VARCHAR(20) NOT NULL DEFAULT 'hour';
COMMIT;
