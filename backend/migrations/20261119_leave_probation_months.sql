-- Policy-specific probation duration. Existing policy versions retain their previous
-- probation_allowed terms (historical balances must not be changed retroactively).
ALTER TABLE leave_policies
  ADD COLUMN IF NOT EXISTS probation_months INTEGER NOT NULL DEFAULT 3;
ALTER TABLE leave_policies
  ADD CONSTRAINT leave_policies_probation_months_range
  CHECK (probation_months BETWEEN 0 AND 12);
