# JellyGit HRMS hardening and UAT release gate (2026-11-09)

Scope: **synthetic-data pilot only until every P0 gate is verified.**
Do not issue real payslips, GST invoices, payout instructions or upload real PAN/Aadhaar/banking records.

## CI quality gates
- Run the entire backend test directory against ephemeral PostgreSQL, with data isolation **per test**.
- Run all Playwright role and workflow suites against fresh isolated application services.
- Require frontend production build and backend syntax/OpenAPI checks.
- Require negative authorization cases for every privileged endpoint.
- No skipped, flaky or known-failing critical tests. Capture test-count/report artifacts.
- Run database migrations on an empty DB and a copy of disposable prior-schema data; test rollback.
- Perform restore drills for PostgreSQL and document volumes.
- Run regression through a release-candidate commit after all PRs merge.

## Phase 1 — access and employee integrity
[x] Privileged lifecycle exit and self-deactivation protection.
[x] Super Admin creation restricted to Super Admin.
[x] Manager-required import and partial updates preserving omitted fields.
[x] Retire legacy employee and leave **write** bypass routes.
[x] Field-level 422 for invalid sensitive change requests.
[x] Case-insensitive login and neutral forgot-password error response.
[ ] Role-specific mandatory MFA enrollment + recovery codes.
[ ] DB-backed login and OTP throttling/lockout with audit.
[ ] Email-only, single-use set-password flow; no HR-visible temporary passwords.
[ ] Retire legacy read/report paths after dependent UI and tests migrate.
[ ] Negative authorization matrix for HR/admin/accountant/manager/employee including hidden endpoint calls.
[ ] Verified session expiration, CSRF/origin handling, upload authorization and sensitive logging.

## Phase 2 — payroll calculation and governance
[x] Working-day, holiday-aware and fractional LOP for the payroll month.
[x] Mid-month joiner gross proration and inclusion of employees exiting during month.
[ ] Legal/payroll policy for statutory deductions on partial-month service.
[ ] No unconfigured employee silently omitted or able to receive zero salary.
[ ] Effective-dated immutable salary/statutory versions, approver segregation, audit and migration.
[ ] No self-edits; payroll admin action boundaries / HR approvals.
[ ] Draft recalculation, clear exceptions and reasoned replacement/void process.
[ ] Golden-amount test matrix: leap year, 28/29/30/31 day month, holidays, half-day,
    overlapping periods, join/exit, payslip rounding and missing configuration.

## Phase 3 — billing accuracy
[x] Approved billing review defaults to configured tax rate.
[x] Voided invoice cannot permanently consume the period; preserve its history (requires migration).
[x] Missed final service period is reviewed after project ending.
[ ] GST invoice legal fields, CGST/SGST/IGST selection, GSTIN, SAC and validated tax rounding.
[ ] Credit notes, payment applications, partial payment and ageing.
[ ] Approved timesheets into units with versioned client approval; reject unapproved quantities.
[ ] Concurrency/uniqueness test under parallel billing requests.
[ ] Reconcile project schedules, reviews, invoices and receipts every day.
[ ] Verify migration on existing DB and restore path before deployment.

## Phase 4 — leave, exits and workflow reliability
[x] HR overview handles inactive staff.
[x] Approval list applies cap after stage-filtering.
[x] HR escalation requires a note and generates approval history.
[x] Pending encashment reservations and approved encashment carry-forward.
[x] Cancellation rejection feedback distinguishes it from fresh leave approval.
[ ] Reassign reporting chains when manager exits; fallback to HOD/HR.
[ ] Consolidate legacy leave reads, financial-year reporting and proration.
[ ] Background retryable notifications, dead-letter review and delivery status.
[ ] Exit checklist tasks linked to the closure/settlement gate; templates editable/deactivatable.
[ ] FY rollover, holidays, leap-day, balance races and long-pending approval tests.

## Local release candidate and Cloudflare pilot
1. Keep the current `hrms` and `hrms-pilot` Compose databases untouched while developing.
2. Merge fully reviewed PRs, apply migrations only to backed-up disposable DB copies.
3. Build a clean local release-candidate Docker stack with separate volumes/ports.
4. Execute complete backend/Playwright suites and manual HR/manager/employee/accountant UAT.
5. Exercise registration-disabled login, access scopes, employee lifecycle, payroll drafts,
   approved leave, void/rebill, uploads/restarts and backup restores.
6. Fix every P0, retest affected module plus full regression, record commit SHA.
7. Only then update Cloudflare pilot to that exact SHA, verify HTTPS/cookies/origin,
   invite approved testers, and record issues with role, steps, expected/actual and screenshots.
8. Never run `docker compose down -v` on development or pilot.
