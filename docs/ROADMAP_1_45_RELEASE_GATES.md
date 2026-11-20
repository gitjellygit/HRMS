# Jellygit HRMS: checklist 1–45 integration and demo gates

Last reviewed: 2026-11-05. This is an **engineering status**, not production certification.

## Dependency graph

1. PR #13 (role/privacy/password profile) targets main; role/PII and browser tests must pass.
2. PR #14 (attendance/time 23–30) targets PR #13; verify geofence, shift swaps, overtime, timesheets and mobile browser workflows.
3. PR #15 (payroll/people 31–35, 39–45) targets PR #14; audit older divergent implementation branch before retaining latest.
4. PR #16 (performance 36–38) targets PR #15; verify goals, reviews and development UI/role tests.

**Do not merge in reverse order.** Refresh dependent branches after merges and rerun checks on the actual integrated commit.

## Functional acceptance matrix

| Item | Capability | Engineering status | Minimum demo evidence |
| --- | --- | --- | --- |
| 1–10 | Employee core, RBAC, org, documents, lifecycle, bulk import | Merged to main, production security not certified | Add/edit employee; role visibility; protected document; import; deactivate |
| 11–22 | Leave policies, requests, balances, holidays, approvals, delegation | Merged to main, policy signoff outstanding | Employee requests leave, manager/HR approves, FY balance updates |
| 23–30 | Time, shifts, roster, WFH, overtime, GPS, corrections, timesheets | Draft PR #14 | Punch, GPS rejection, roster swap consent, approval, time entries |
| 31 | Salary structure builder | Draft PR #15 | HR defines basic/HRA/allowances/deductions |
| 32 | Controlled payroll run | Draft PR #15 | Time/LOP -> draft -> exception handling -> two-person approval -> publish |
| 33 | Statutory calculations | Draft PR #15, policy-configured not compliance-certified | Reviewed PF/ESI/PT/TDS/gratuity settings and calculation evidence |
| 34 | PDF payslips | Draft PR #15 | Employee downloads own slip, another employee denied |
| 35 | Reimbursements | Draft PR #15 | Attach receipt, HR review and permission check |
| 36 | Employee goals/KRAs | Draft PR #16 | Set goal, update progress, employee isolation |
| 37 | Review cycles and ratings | Draft PR #16 | HR creates cycle, employee self-reviews, manager completes |
| 38 | Growth and development | Draft PR #16, partial | Development plans; learning/catalog and career progression need scope acceptance |
| 39 | Offer letters | Draft PR #15 | HR builds PDF, employee acknowledges; qualified e-sign provider not integrated |
| 40 | Onboarding | Draft PR #15 | HR assigns document/asset tasks, employee completes |
| 41 | Announcements, policies, HR helpdesk | Draft PR #15 | Publish/acknowledge policy; resolve ticket |
| 42 | Exit management | Draft PR #15 | Employee resignation, HR review, clearance and F&F record (no money transfer) |
| 43 | Analytics | Draft PR #15 | Role-protected dashboard and cost/headcount trends validation |
| 44 | Notifications | Draft PR #15 | Configured outbox, event & channel preferences; external SMS/push/WhatsApp providers not connected |
| 45 | Audit/security/integrations | Draft PR #15, partial | Audit events, MFA and permissions; external systems, migration and backup validation remain |

## Critical gaps before final merge

- Resolve the failing PR #13 and #14 browser suites and run Playwright across the fully integrated branch.
- Bring the chosen 31–45 branch up to date with main after preceding PRs merge; compare the alternate divergent branch for unique functionality.
- Confirm the original exact acceptance criteria for 36–38; evaluate multi-rater/360 feedback, manager calibration, learning plans and career progression.
- Implement version-controlled DB migrations; test upgrade/rollback and backup/restore in a disposable environment.
- Review statutory payroll rules with HR/finance/legal for the actual jurisdictions, including pay period, LOP, retro adjustments and F&F.
- Run security tests for all role boundaries, PII, file uploads, session protection, MFA recovery, audit immutability and retention.
- Confirm integrations: SMTP, SMS/WhatsApp/push providers, e-signatures, biometric hardware, accounting and banking are not assumed operational just because endpoints or outboxes exist.
- Test cross-module journeys: hire -> probation -> leave -> attendance -> payroll -> growth -> exit, including corrections/reversals.
- Require green standard CI and Playwright on final exact commit, team code review, data migration rehearsal and product owner approval.

## Two-day demo-run script (synthetic employee data only)

Day 1:
- HR creates employee + manager relationship, tests permission differences across HR, manager, accountant, employee.
- Employee signs in/change password, submits leave, checks in and enters a timesheet.
- Manager approves leave/WFH/time correction; HR reviews overtime, roster and exceptions.
- HR configures salary/statutory values; accountant creates run; separate reviewer approves; employee downloads own payslip.

Day 2:
- HR generates offer and onboarding checklist, publishes policy; employee acknowledges.
- Employee creates goal, submits self-appraisal; manager reviews; development plan progress is tracked.
- Employee opens helpdesk ticket and resignation; HR handles clearances and final settlement.
- HR tests dashboard, notifications, audit history, document expiry, permissions, and negative-access cases.

Record for each scenario: tester, employee role, input record, expected result, actual result, screenshot/log, defect ID, pass/fail and remediation commit.

## Release gate

**Final merge is blocked** until exact acceptance criteria are met, all dependent PRs are green and reviewed, migration/privacy/payroll controls pass, and the two-day demo uses a dedicated non-production test environment. Do not load real employee PII into the demo.
