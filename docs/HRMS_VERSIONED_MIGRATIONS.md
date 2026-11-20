# HRMS database migrations — ongoing deployment procedure

## Why

The previous production workflow had a dated schema approval option for each release. This does not scale and does not track whether a migration was applied.

The replacement uses `backend/migrations/ORDER.txt` and PostgreSQL table `public.hrms_schema_migrations` with a SHA-256 checksum. **Every newly added SQL migration must be a new, append-only manifest entry**. Never edit or reorder historical migrations once applied. The runner detects missing/changed scripts, rejects ledger gaps, applies pending scripts transactionally, and records their checksum with the DDL.

The existing manual production workflow still requires `DEPLOY`, exact main-commit CI success, database/uploads backups, and health checks. It no longer has a date-specific schema-approval dropdown. A Compose file change remains blocked pending infrastructure review.

## One-time production bootstrap (existing Hostinger VPS)

This is needed **once only** because the VPS already contains SQL migrations through November 17 but has no migration ledger. Do not repeat the historical migrations.

1. Verify the deployed VPS has completed the old November 17 schema: `leave_policy_versions`, `activity_agent_devices`, `people_onboarding_categories`, and the required columns in `leave_policies`.
2. Ensure PostgreSQL and employee uploads both have current, validated backups.
3. After the migration-runner PR has passed CI and merged to main, SSH into the Hostinger VPS as `deploy`:

```bash
set -euo pipefail
cd /opt/jellygit/hrms
git fetch --no-tags origin main
TARGET_SHA="$(git rev-parse origin/main)"
MIGRATION_RUNNER="$(mktemp)"
trap 'rm -f "$MIGRATION_RUNNER"' EXIT
git show "$TARGET_SHA:.github/scripts/migrate-hrms.py" > "$MIGRATION_RUNNER"
python3 "$MIGRATION_RUNNER" "$TARGET_SHA" --bootstrap-legacy
python3 "$MIGRATION_RUNNER" "$TARGET_SHA" --check
```

The bootstrap checks historical schema markers, then records checksums for all 21 existing migrations without re-running their SQL. `--check` should report the Nov 19 probation migration as pending if it has not yet been recorded.

**Never bootstrap if the schema checks fail**. Investigate missing migrations and verify a rollback plan first.

4. In GitHub Actions, run `Hostinger HRMS manual release` from `main`, type `DEPLOY`. No schema option. The pipeline checks main CI, backs up DB and uploads, applies pending migrations, then rebuilds/restarts services and checks their endpoints.
5. Confirm deployed commit and new column:

```bash
cd /opt/jellygit/hrms
git rev-parse --short HEAD
docker compose exec -T db sh -c 'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT name, applied_at FROM public.hrms_schema_migrations ORDER BY applied_at, name"'
docker compose exec -T db sh -c 'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT probation_months FROM leave_policies"'
```

## Every subsequent release

1. Add a new, uniquely named `YYYYMMDD_description.sql` under `backend/migrations`.
2. Append its filename to the end of `ORDER.txt`. Existing entries and SQL content are immutable.
3. Use **additive/backward-compatible** migrations; for destructive column removals use a separately reviewed expand/backfill/contract sequence.
4. Open a PR. CI checks Python release-runner syntax, migration manifest consistency, backend tests (including disposable PostgreSQL rehearsal), and frontend tests.
5. Merge once verified. Trigger manual workflow with `DEPLOY`. Database changes are applied automatically; no new approval input is introduced.

## Operational safety

- Single SQL migration and its ledger row use one PostgreSQL transaction and an advisory transaction lock. Failed SQL is rolled back for that script, and application checkout is not started.
- Earlier successful migrations in the same release are **not** automatically rolled back if a later script fails; investigate and rerun after fixing the issue with new SQL rather than deleting ledger entries.
- App rollback does not reverse migrations. Always use backward-compatible schema changes and preserve database backups. Real production restores require an explicit data-loss assessment.
- Scripts requiring nontransactional SQL (e.g. CREATE INDEX CONCURRENTLY), irreversible data changes, database extensions or deployment topology changes need their own separately reviewed rollout; the generic runner intentionally fails rather than bypassing transaction safety.
- The production workflow still requires a human to authorize each release with `DEPLOY` (and can use GitHub Environment required reviewers). This is one approval for **deployment**, not a new menu option for every migration.
- Hostinger is the current target. A future Heroku deployment can reuse the same manifest/ledger semantics with a different database transport.
