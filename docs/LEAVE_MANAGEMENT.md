# Leave Management — roadmap 11–22

This module lives in **feature/leave-management-11-22**, PR into **feature/employee-core-1-10**. It depends on the existing employee hierarchy and does not merge the earlier PRs into main.

## Features

- **11 Apply leave:** full-day, half-day (0.5), short leave (0.25) with reason, overlap validation and leave policy checks.
- **12 Balance dashboard:** employee/HR balances, pending and approved reservations, carried balance and approved encashment.
- **13 Leave types:** casual, sick, earned/privilege, maternity, paternity, comp-off, loss of pay.
- **14 Policy:** HR-configured annual allocation, monthly accrual, capped previous-year carry-forward, probation restriction, encashment eligibility and approval stages. These are simplified company rules; statutory/legal policy is not inferred.
- **15 Reporting manager approval:** manager ID is snapshotted from Employee Core on submission.
- **16 Multilevel approval:** configurable ordered manager, HR and admin stages; each reviewer acts on their own step.
- **17 Notices:** durable in-app notification inbox and best-effort SMTP emails. **SMS, mobile push and WhatsApp are not wired to providers**; these need separate credentials, delivery receipts, opt-in and provider integration.
- **18 Withdrawal/cancellation:** pending leave may be withdrawn; approved leave requires HR cancellation approval before balances return.
- **19 Team calendar:** approved leave for direct reports (HR has full visibility).
- **20 Holidays:** public and optional holidays configured by location and date; mandatory holidays are excluded from counted leave days.
- **21 HR reports:** year and department filters, JSON aggregates and CSV exports.
- **22 Delegation:** time-bounded alternate manager approver, 90-day cap, revocation.

## Local test

```bash
git fetch origin
git switch --track origin/feature/leave-management-11-22
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Unlike Employee Core, this PR does not add new runtime dependencies, so **no image rebuild is needed** after switching from a fully built Employee Core dev environment. Uvicorn reload watches your source.

Use **Policies & balances** (HR) first to activate a leave type and configure its approval stages. For example: `casual`, 12 annual days, Manager → HR. Assign a reporting manager to the employee in Employee Core. Without a manager, a policy requiring manager approval will prevent submission.

Once the leave policy and manager are set up, employees can apply in **Leave requests**. Manager and HR users can approve their assigned stage. The same module exposes the calendar, holiday configuration, notifications and delegation.

## Important business rules and limitations

1. Dates are inclusive and requests cannot cross a year; split year-end leave into separate requests.
2. Saturdays/Sundays and configured non-optional holidays are excluded by default. Weekly offs and shift-specific work schedules will need feature 25.
3. Half-day or short leave is accepted for a single working date only.
4. Annual entitlement is set by either explicit HR allocation or the configured annual policy. If monthly accrual is non-zero **and no explicit allocation exists**, earned balance equals monthly accrual multiplied by elapsed months of the year. This is a simplified model, not daily proration, and should be validated against actual employment policies.
5. Carry-forward uses prior-year explicitly allocated balance (capped by policy), and does not currently carry forward purely monthly-generated balances.
6. Pending and approved leave reserve balance. Rejected/cancelled leave is excluded.
7. Encashment requests have HR approve/reject endpoints. Actual financial payment and salary calculations are reserved for Payroll features.
8. Existing legacy `/leaves` APIs and HR overview leave allocations are retained for compatibility; new policies and workflows use `/leave/*` and lowercase leave type IDs. Plan a migration before production.
9. For a single quarter-day short leave, duration is 0.25 day; configurable short-leave time limits and hourly balance rules can follow with attendance integration.
10. Notification email is best-effort and not queued/retried; in-app notices remain visible even when SMTP is unconfigured.
11. Leave balances are not financially authoritative until leave policy details, approval edge cases, concurrency, compliance and audit coverage pass user acceptance.
12. `Base.metadata.create_all` is still used for new tables on startup; **Alembic migrations are required** before real production use.

## CI and security

GitHub Actions runs backend syntax/OpenAPI validation, PostgreSQL integration tests for multi-level approvals, half-day balances and approved cancellation, plus the Next.js production build.

Do not use the draft HRMS with real employee data until proper migrations, backups, audit logs, strict permissions, notification delivery controls and security testing are complete.
