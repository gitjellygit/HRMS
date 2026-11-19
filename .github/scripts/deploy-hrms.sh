#!/usr/bin/env bash
set -Eeuo pipefail
TARGET_SHA="${1:?Pass verified SHA}"
SCHEMA_APPROVAL="${2:-}"
[[ "$TARGET_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "Invalid SHA"; exit 1; }
cd /opt/jellygit/hrms
test -f .env
git diff --quiet && git diff --cached --quiet
git fetch --no-tags origin main
git cat-file -e "$TARGET_SHA^{commit}"
PREVIOUS_SHA="$(git rev-parse HEAD)"
if [[ "$PREVIOUS_SHA" == "$TARGET_SHA" ]]; then echo "Already deployed"; exit 0; fi
# Schema-bearing releases need an explicit approval AND verification of the target
# schema already installed on the VPS. This approval covers only the ten known
# additive migrations from 2026-11-17, never arbitrary future SQL/Compose changes.
CHANGED="$(git diff --name-only "$PREVIOUS_SHA" "$TARGET_SHA" -- backend/migrations/ docker-compose.yml)"
if [[ -n "$CHANGED" ]]; then
  if [[ "$SCHEMA_APPROVAL" == "APPROVE-20261119-PROBATION" ]]; then
    # Exactly the one approved migration may change. A Compose edit, a new
    # migration, or any additional SQL changes require a fresh review.
    if [[ "$CHANGED" != "backend/migrations/20261119_leave_probation_months.sql" ]]; then
      echo "Probation approval cannot cover unreviewed migrations or Compose edits."
      printf '%s\n' "$CHANGED"
      exit 1
    fi
    echo "Verifying the approved probation schema on the VPS."
    docker compose exec -T db sh -c 'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
DO $probation_gate$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='leave_policies'
      AND column_name='probation_months'
      AND data_type='integer' AND is_nullable='NO'
      AND column_default LIKE '%3%'
  ) THEN
    RAISE EXCEPTION 'Missing or unexpected leave_policies.probation_months; apply reviewed migration first';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.leave_policies'::regclass
      AND conname='leave_policies_probation_months_range'
      AND contype='c' AND convalidated
  ) THEN
    RAISE EXCEPTION 'Missing validated probation_months range constraint';
  END IF;
  IF EXISTS (SELECT 1 FROM leave_policies WHERE probation_months NOT BETWEEN 0 AND 12) THEN
    RAISE EXCEPTION 'Invalid probation_months values detected';
  END IF;
END $probation_gate$;
SQL
    echo "Reviewed probation migration verified; release may continue."
  elif [[ "$SCHEMA_APPROVAL" == "APPROVE-20261117-MIGRATIONS" ]]; then
  EXPECTED="$(printf '%s\n' \
    backend/migrations/20261117_activity_agent_app_usage.sql \
    backend/migrations/20261117_activity_agent_devices.sql \
    backend/migrations/20261117_announcement_media_audience.sql \
    backend/migrations/20261117_company_letterhead.sql \
    backend/migrations/20261117_custom_monthly_leave_schedule.sql \
    backend/migrations/20261117_leave_policy_year_and_versions.sql \
    backend/migrations/20261117_manual_payslips.sql \
    backend/migrations/20261117_offer_logo_snapshot.sql \
    backend/migrations/20261117_onboarding_categories.sql \
    backend/migrations/20261117_tiered_leave_accrual.sql)"
  # Only this precise reviewed migration set, and no Docker Compose change.
  if [[ "$CHANGED" != "$EXPECTED" ]]; then
    echo "Unexpected migration/Compose diff. Refusing approval. Changed paths:"
    printf '%s\n' "$CHANGED"
    exit 1
  fi
  echo "Reviewed migration set recognized. Verifying schema in VPS PostgreSQL."
  docker compose exec -T db sh -c 'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
DO $schema_gate$
DECLARE missing text;
BEGIN
  SELECT string_agg(required_path, ', ' ORDER BY required_path) INTO missing
  FROM (
    SELECT table_name || '.' || column_name AS required_path
    FROM (VALUES
      ('leave_policies','late_year_monthly_accrual'),
      ('leave_policies','monthly_schedule'),
      ('leave_policies','year_type'),
      ('leave_policy_versions','leave_type'),
      ('leave_policy_versions','snapshot_json'),
      ('people_company_letterhead','logo_key'),
      ('people_offers','letterhead_logo_key'),
      ('people_onboarding_categories','slug'),
      ('people_announcements','media_key'),
      ('people_announcements','audience_ids'),
      ('activity_agent_devices','employee_id'),
      ('activity_agent_devices','app_usage_json'),
      ('pay_manual_payslips','storage_key')
    ) AS required(table_name,column_name)
    WHERE NOT EXISTS (
      SELECT 1 FROM information_schema.columns c
      WHERE c.table_schema='public'
        AND c.table_name=required.table_name
        AND c.column_name=required.column_name
    )
  ) gaps;
  IF missing IS NOT NULL THEN
    RAISE EXCEPTION 'Unapplied reviewed schema migrations: %', missing;
  END IF;
  IF EXISTS (
    SELECT 1 FROM leave_policies p WHERE NOT EXISTS (
      SELECT 1 FROM leave_policy_versions v
      WHERE v.leave_type=p.leave_type AND v.effective_from=DATE '2000-01-01'
    )
  ) THEN
    RAISE EXCEPTION 'Legacy leave policy history baseline missing';
  END IF;
END $schema_gate$;
SQL
  echo "Reviewed migration schema verified; release can continue."
  else
    echo "Schema changes detected; select the matching reviewed migration approval in manual workflow."
    exit 1
  fi
fi
rollback() {
 code=$?
 trap - ERR
 echo "Rollback to $PREVIOUS_SHA attempted"
 git checkout --detach "$PREVIOUS_SHA"
 docker compose build api web leave-email-worker || true
 docker compose up -d --no-deps api web || true
 exit "$code"
}
trap rollback ERR
git checkout --detach "$TARGET_SHA"
docker compose config --quiet
docker compose build api web leave-email-worker
docker compose up -d --no-deps api web
if docker compose ps --services --status running | grep -qx leave-email-worker; then
 docker compose up -d --no-deps leave-email-worker
fi
healthy=false
for attempt in {1..20}; do
 if curl -fsS --max-time 8 http://127.0.0.1:8000/health >/dev/null 2>&1 &&
    curl -fsS --max-time 8 https://api-hrms.jellygit.com/health >/dev/null 2>&1 &&
    curl -fsS --max-time 8 https://hrms.jellygit.com >/dev/null 2>&1; then
  healthy=true; break
 fi
 sleep 3
done
[[ "$healthy" == true ]] || { echo "Post-deploy health failed"; false; }
trap - ERR
echo "Successfully deployed $TARGET_SHA"
