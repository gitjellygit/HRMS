# People Operations + Windows Activity Agent — pre-UAT gate (PR #49)

**Do not merge/deploy while this PR is draft.** This PR is stacked on PR #48 in commit history and temporarily targets `main` to run CI. PR #48 remains a release prerequisite. Do not deploy by a single unreviewed merge.

## Migrations (separate, controlled, tested order)

- `20261117_tiered_leave_accrual.sql` (PR #48)
- `20261117_manual_payslips.sql` (PR #48)
- `20261117_custom_monthly_leave_schedule.sql`
- `20261117_leave_policy_year_and_versions.sql` (after custom monthly schedule)
- `20261117_company_letterhead.sql`
- `20261117_offer_logo_snapshot.sql`
- `20261117_onboarding_categories.sql`
- `20261117_announcement_media_audience.sql`
- `20261117_activity_agent_devices.sql`
- `20261117_activity_agent_app_usage.sql`

Migration scripts are explicit and the existing automatic deployment script is not migration-aware. Validate a restorable database backup and uploads volume backup on a disposable database first.

## Acceptance gates

- Full HRMS checks + isolated Playwright E2E on final head SHA.
- Local Mac compose build plus role-based UAT: HR, Admin, Manager, Employee, Accountant.
- Preview a branded offer PDF, upload company logo, edit/archive templates and preserve sent-document snapshots.
- Validate announcement media file type/size, audience filtering and private access to attachments.
- Onboarding progress scoped by employee, category CRUD/archive, selected assignee notification and task permission.
- Employee resignation does not accept selected notice; HR reviews notice with mandatory audit reason.
- Leave 12-month custom schedule, annual distribution with roundoff, joining-date proration, FY rollover, carry-forward and overlapping requests.
- Calendar-year policy semantics and immutable effective-dated policy versioning are implemented in draft; verify the revised leave engine in backend and browser UAT before enabling them in production.
- Regression coverage must confirm policy-year boundaries, leap year, partial joining months, prospective policy changes, prior-year carry-forward and permissions.
- Activity agent: Windows 10/11 pilot, tray visibility, start, reason-to-exit, heartbeat, forced kill/offline inference, revocation, no screenshots/keystrokes/URLs. Verify status after 100 seconds without heartbeat.
- Activity agent requires one-time HR device enrollment token, HTTPS-only API host and disclosed monitoring policy.
- Test browser dark-mode hover contrast, theme transition, profile Sign out and outside click from PR #48 on Hostinger-staging build.
- No live Hostinger deployment until migration, backups, UAT, security and privacy approvals.

## CI migration smoke rehearsal

`backend/tests/test_peopleops_migrations_rehearsal.py` applies the new migration scripts twice to a disposable legacy PostgreSQL schema, validates the baseline snapshot and confirms idempotence. This does not replace a rehearsal against a sanitized/restored Hostinger snapshot and a backup of the uploads directory.

## v0.6 zero-file self-registration (staged; not released)

See [WINDOWS_COMPANION_AUTO_REGISTRATION.md](WINDOWS_COMPANION_AUTO_REGISTRATION.md). Use `HRMS_ACTIVITY_AUTO_REGISTER_ENABLED=true` only during controlled validation, with an edge rate limit and asset verification. An unassigned hostname is untrusted and receives no activity permissions.
