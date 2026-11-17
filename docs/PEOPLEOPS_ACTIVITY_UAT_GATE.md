# People Operations + Windows Activity Agent — pre-UAT gate (PR #49)

**Do not merge/deploy while this PR is draft.** This PR is stacked on PR #48 in commit history and temporarily targets `main` to run CI. PR #48 remains a release prerequisite. Do not deploy by a single unreviewed merge.

## Migrations (separate, controlled, tested order)

- `20261117_tiered_leave_accrual.sql` (PR #48)
- `20261117_manual_payslips.sql` (PR #48)
- `20261117_custom_monthly_leave_schedule.sql`
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
- Calendar-year policy semantics and effective-dated policy versioning are **not yet complete**. Do not activate those options or represent these features as finished.
- Activity agent: Windows 10/11 pilot, tray visibility, start, reason-to-exit, heartbeat, forced kill/offline inference, revocation, no screenshots/keystrokes/URLs. Verify status after 100 seconds without heartbeat.
- Activity agent requires one-time HR device enrollment token, HTTPS-only API host and disclosed monitoring policy.
- Test browser dark-mode hover contrast, theme transition, profile Sign out and outside click from PR #48 on Hostinger-staging build.
- No live Hostinger deployment until migration, backups, UAT, security and privacy approvals.
