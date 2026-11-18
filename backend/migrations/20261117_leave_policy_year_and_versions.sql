-- Release gate: run after PR #48 migrations, before starting the updated API.
-- Records permanent year basis and immutable effective-dated leave policy snapshots.
ALTER TABLE leave_policies
  ADD COLUMN IF NOT EXISTS year_type VARCHAR(12) NOT NULL DEFAULT 'financial';
CREATE TABLE IF NOT EXISTS leave_policy_versions (
  id SERIAL PRIMARY KEY,
  leave_type VARCHAR(30) NOT NULL,
  effective_from DATE NOT NULL,
  snapshot_json TEXT NOT NULL,
  actor_id INTEGER NULL REFERENCES employees(id),
  reason VARCHAR(500) NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_leave_policy_version_effective UNIQUE(leave_type,effective_from)
);
CREATE INDEX IF NOT EXISTS ix_leave_policy_versions_leave_type
  ON leave_policy_versions(leave_type);
CREATE INDEX IF NOT EXISTS ix_leave_policy_versions_effective_from
  ON leave_policy_versions(effective_from);
-- Backfill legacy policy terms so old entitlement and carry-forward periods
-- continue to use the terms in force before policy-versioning was introduced.
INSERT INTO leave_policy_versions(leave_type,effective_from,snapshot_json,reason)
SELECT p.leave_type, DATE '2000-01-01',
  json_build_object(
    'annual_days',COALESCE(p.annual_days,0)::text,
    'monthly_accrual',COALESCE(p.monthly_accrual,0)::text,
    'late_year_monthly_accrual',COALESCE(p.late_year_monthly_accrual,0)::text,
    'monthly_schedule',CASE WHEN p.monthly_schedule IS NOT NULL THEN p.monthly_schedule::json ELSE NULL END,
    'carry_forward_limit',COALESCE(p.carry_forward_limit,0)::text,
    'year_type',COALESCE(p.year_type,'financial'),
    'active',p.active,'approval_chain',p.approval_chain,
    'probation_allowed',p.probation_allowed,'encashment_allowed',p.encashment_allowed
  )::text,
  'Pre-versioning baseline (migration)'
FROM leave_policies p
ON CONFLICT (leave_type,effective_from) DO NOTHING;
