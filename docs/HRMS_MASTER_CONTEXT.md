# HRMS master context

This is the stable orientation for JellyGit HRMS. For active PRs/CI and hosted status, consult `HRMS_CURRENT_STATE.md` and verify GitHub live. Do not use chat history as the source of truth.

## Identity and architecture
- Repository: `gitjellygit/HRMS`; default branch `main`.
- Internal HRMS for a small JellyGit team; pilot target up to approximately 50 employees.
- Frontend: Next.js 15 / TypeScript; backend: Python FastAPI / SQLAlchemy; database: PostgreSQL 16.
- Docker Compose for local development and Hostinger VPS; Caddy/HTTPS reverse proxy for hosted pilot.
- Existing `README.md` has early-MVP descriptions and is not a reliable feature inventory. Confirm each claim in the current source, migrations and tests.

## Functional scope to verify against current code
- Employees, reporting managers, departments, organization, role-specific HR/manager/employee/accountant access.
- Attendance and leave policies, entitlements, approvals, carry-forward and year boundaries.
- Projects, project billing, invoice schedules/ledger, timesheets, bonuses and performance.
- Salary, statutory deductions, payroll approval, payslips, employee documents.
- Onboarding, policy acknowledgements, announcements, notifications, helpdesk and exit lifecycle.
- People Operations and company-authorized Windows activity companion.
The list describes product domains, not a claim that each is production-complete.

## Core invariants
1. Never infer a feature is merged from an old chat, branch or PR. Check live `main`, tests and deployed SHA.
2. Keep payroll, billing and statutory finance outputs in draft/pilot until financial, approval, audit and legal checks are verified.
3. Enforce role and ownership authorization in backend endpoints; frontend visibility alone is not access control.
4. Sensitive employee information and document uploads require deliberate privacy, retention, access and security review.
5. Require explicit human approval and an audit reason for privileged lifecycle, payroll and financial changes as applicable.
6. Treat employee activity as sensitive: company-authorized, disclosed, scoped to enrolled devices, no covert collection; pending/unassigned devices cannot send activity telemetry.
7. Never silently overwrite migrations or alter existing VPS volumes. Apply the versioned migration manifest to a backed-up, rehearsed database.
8. Make employee/HR/accountant UI errors specific and actionable; never substitute generic validation messages.
9. Distinguish **implemented**, **tested**, **merged**, **deployed**, and **hosted verified**.

## Deployment references
- `docs/HOSTINGER_DEPLOYMENT.md` — protected VPS deployment and deploy opt-in.
- `docs/HRMS_VERSIONED_MIGRATIONS.md` — database migration ledger and procedures.
- `docs/HARDENING_UAT_GATE.md` — cross-module security/payroll/billing release checklist.
- `docs/PEOPLEOPS_ACTIVITY_UAT_GATE.md` — People Operations and Windows companion UAT.
- `docs/HRMS_UAT_150_CASES.md` and `docs/PLAYWRIGHT_QA.md` — testing inventory.
- `docs/LOCAL_DEVELOPMENT.md` — local Compose commands.

## Source-of-truth order
1. Live GitHub `main` SHA, PRs, workflows, code, migrations, and tests for implementation state.
2. Verified environment release SHA, backup/restoration, migration ledger and acceptance evidence for deployed state.
3. Module-specific UAT gates/checklists for required work.
4. `docs/HRMS_CURRENT_STATE.md` as an explicitly dated handoff snapshot.
5. `docs/HRMS_ARCHITECTURE_DECISIONS.md` for stable rationale.
6. Earlier conversations and memory only as supporting context.

## Development rule
Read this file, current state, decisions and relevant UAT gate; refresh GitHub main/PR/CI; inspect implementation; write a small reviewed PR with focused tests; update the current-state snapshot following meaningful changes. Do not merge a draft or deploy based on passing CI alone when release gates are outstanding.
