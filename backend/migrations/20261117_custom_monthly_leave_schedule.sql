-- Add optional custom financial-year monthly accrual schedule (Apr-Mar).
-- NULL retains prior annual/tiered leave policy semantics.
ALTER TABLE leave_policies
  ADD COLUMN IF NOT EXISTS monthly_schedule TEXT;
