-- Policy-specific probation duration. Existing policy versions retain their previous
-- probation_allowed terms (historical balances must not be changed retroactively).
ALTER TABLE leave_policies
  ADD COLUMN IF NOT EXISTS probation_months INTEGER NOT NULL DEFAULT 3;
DO $migration$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='leave_policies_probation_months_range') THEN
  ALTER TABLE leave_policies
    ADD CONSTRAINT leave_policies_probation_months_range
    CHECK (probation_months BETWEEN 0 AND 12);
 END IF;
END
$migration$;
