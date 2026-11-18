# JellyGit HRMS — Pre-pilot verification & migration runbook

**Status: NOT approved for production.** This work is PR #48, layered on PR #47.
PR #46 (manual Hostinger release) is already merged. Do **not** enable `HRMS_DEPLOY_ENABLED`.

## Business policy sign-off

- India FY: 1 April–31 March, not calendar year.
- Configured earned-leave rates: April–November **1.5 days/month**, December–March **2.5 days/month**.
- Full FY total: **22 days**. Leave is credited month by month (including the current calendar month), *not* allotted as 22 days at FY opening.
- Employee's first joining month is prorated for days employed, rounded to nearest half-day.
- Unused credits accumulate across months inside the FY; with carry-forward limit **0**, unused leave expires after 31 March.
- The above assumes rates follow **FY months**; confirm this exact interpretation with the HR policy owner before making it active. Existing legacy leave policy values are **not** changed by migration.
- WFH: at most **two calendar days per employee per calendar month**, counting pending/approved requests. Rejected/withdrawn do not count. No monthly carry-over.
- Attendance gap between completed sessions is **inferred**, not independently captured break-start/break-end events.

## Isolated local validation on Mac

Do not point your local QA `DATABASE_URL`, `NEXT_PUBLIC_API_URL` or Docker environment to live Hostinger. Confirm you have no uncommitted work to lose.

```bash
git fetch origin
git switch -c qa/hrms-prepilot origin/feature/prepilot-hr-attendance-leave-wfh-bonus-payslip-20261117

docker compose -p hrms_qa \
 -f docker-compose.yml -f docker-compose.dev.yml \
 up -d --build
docker compose -p hrms_qa \
 -f docker-compose.yml -f docker-compose.dev.yml ps
```

Use synthetic employees. Test with distinct logins for HR, Admin, Manager, Employee, Accountant.
For an **existing** local QA database, ensure the database schema has both migrations before starting the new API:

```bash
docker compose -p hrms_qa -f docker-compose.yml -f docker-compose.dev.yml up -d db

for migration in backend/migrations/20261117_tiered_leave_accrual.sql backend/migrations/20261117_manual_payslips.sql; do
  docker compose -p hrms_qa -f docker-compose.yml -f docker-compose.dev.yml exec -T db sh -c \
    'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$migration" || exit 1
done
```

For an **empty** QA database, let the normal app bootstrap initialize tables before applying idempotent migrations; never run ALTER on tables that do not yet exist.

Use the separate **HR Pilot Acceptance Checklist** workbook and save screenshots/defect URLs.

## Migration and production safeguards

1. Do not change production until PR #47 and PR #48 both pass full CI, independent HR pilot UAT, and approval.
2. Confirm tested, restorable PostgreSQL backup and secure off-host copy; back up the **uploads Docker volume** (manual payslip PDFs live there).
3. Test both SQL scripts on a copy of the production database; compare leave balances for representative employees before/after, including April/December boundary.
4. Both migration files **must be applied before the new API starts against the existing production DB**, or the new model will query missing columns/tables.
5. The existing `.github/scripts/deploy-hrms.sh` intentionally rejects new migration files. **Do not bypass this guard** without a separately reviewed, migration-aware release procedure.
6. Confirm DB migration success, image build, API health, user login, WFH quota, leave accrual, attendance audit, bonus visibility and payslip authorization.
7. Do not expose real salary or private PDF documents in GitHub issues, screenshots or chat logs.

## Release criteria

- Every P0 checklist test Pass; zero open critical/blocker defects.
- Full HRMS checks + Playwright E2E green on the **final** head SHA.
- Backups and restoration of both database and employee files verified.
- HR confirms FY accrual dates, probation rules, WFH counts and manual payslip publication controls.
- HR lead signs off explicitly, then one controlled/manual Hostinger release is authorized.
