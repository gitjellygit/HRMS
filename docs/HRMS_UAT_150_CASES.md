# HRMS release UAT — 150 explicit business acceptance scenarios

Source: business requirements review, 2026-11-05. These are acceptance cases, **not a claim all cases are automated or passed**. Prioritize P0 auth/privacy/financial cutoffs; record test owner, fixture, execution date, actual result, screenshot/log and defect link. CI runs live suites with PostgreSQL and Playwright; deployment/provider checks require manual evidence.

## Authentication / account

| ID | Scenario | Expected acceptance outcome | Execution |
|---|---|---|---|
| UAT-001 | new employee receives credentials | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-002 | first login requires password update | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-003 | wrong password rejected | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-004 | inactive employee login rejected | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-005 | logout invalidates cookie | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-006 | employee can change own password | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-007 | employee can change profile photo | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-008 | profile photo type restricted | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-009 | profile photo size restricted | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-010 | forgot-password token expires | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-011 | reused reset token rejected | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-012 | HR session cannot view admin-only inbox | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-013 | manager session isolated from employee | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-014 | cross-origin write blocked | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-015 | expired session redirected to sign-in | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |

## Employee / orientation

| ID | Scenario | Expected acceptance outcome | Execution |
|---|---|---|---|
| UAT-016 | HR creates employee with valid start date | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-017 | duplicate employee email rejected | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-018 | employee ID uniqueness enforced | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-019 | new employee joins during financial year | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-020 | HR assigns reporting manager | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-021 | manager can view own report | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-022 | peer cannot view another profile | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-023 | HR generates seven orientation tasks | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-024 | orientation generation idempotent | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-025 | employee views own orientation | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-026 | other employee orientation forbidden | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-027 | assigned employee completes task | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-028 | progress percentage advances | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-029 | HR can see pending steps | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-030 | inactive employee cannot begin orientation | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |

## Leave eligibility and balances

| ID | Scenario | Expected acceptance outcome | Execution |
|---|---|---|---|
| UAT-031 | annual allowance prorated for April joiner | Calculated value matches policy, date boundaries and persisted source data | Pending scenario-level evidence |
| UAT-032 | annual allowance prorated for July joiner | Calculated value matches policy, date boundaries and persisted source data | Pending scenario-level evidence |
| UAT-033 | annual allowance prorated for December joiner | Calculated value matches policy, date boundaries and persisted source data | Pending scenario-level evidence |
| UAT-034 | leap-year financial-year rounding | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-035 | join before FY receives full allowance | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-036 | join after FY receives zero allowance | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-037 | manual override remains pending before admin approval | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-038 | approved override changes balance | Calculated value matches policy, date boundaries and persisted source data | Pending scenario-level evidence |
| UAT-039 | rejected override does not change balance | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-040 | monthly accrual accumulates months | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-041 | carry forward capped by policy | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-042 | encashment reduces available balance | Calculated value matches policy, date boundaries and persisted source data | Pending scenario-level evidence |
| UAT-043 | pending leave reserves days | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-044 | approved leave deducts days | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-045 | rejected leave releases balance | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-046 | half-day leave deducts 0.5 | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-047 | short leave deducts 0.25 | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-048 | weekend excluded from working days | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-049 | location holiday excluded | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-050 | overlapping leave rejected | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-051 | insufficient balance rejected | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-052 | probation leave policy enforced | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-053 | cross-year leave correctly split or rejected | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-054 | employee sees own balance only | Calculated value matches policy, date boundaries and persisted source data | Pending scenario-level evidence |
| UAT-055 | HR sees authorized other-employee balance | Calculated value matches policy, date boundaries and persisted source data | Pending scenario-level evidence |

## Leave approvals / governance

| ID | Scenario | Expected acceptance outcome | Execution |
|---|---|---|---|
| UAT-056 | employee submits leave request | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-057 | reporting manager receives request | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-058 | manager approves first stage | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-059 | HR approves second stage | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-060 | self-approval denied | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-061 | wrong manager cannot approve | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-062 | delegate approves during valid period | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-063 | expired delegation rejected | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-064 | employee withdraws pending request | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-065 | approved cancellation requires approval | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-066 | HR creates material leave policy proposal | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-067 | proposal requires business reason | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-068 | HR cannot directly publish leave policy | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-069 | admin approves leave policy | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-070 | HR cannot self-approve proposal | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-071 | admin rejects proposed policy | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-072 | rejected proposal remains unapplied | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-073 | double approval rejected | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-074 | admin approval writes reviewer audit | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-075 | ordinary profile edits need no admin | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |

## Project placements

| ID | Scenario | Expected acceptance outcome | Execution |
|---|---|---|---|
| UAT-076 | HR creates project for sourced candidate | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-077 | project includes sourcer employee ID | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-078 | project includes candidate name | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-079 | project includes client name | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-080 | project includes vendor name | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-081 | project includes prime vendor | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-082 | rate and currency recorded | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-083 | invalid negative rate rejected | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-084 | project number unique | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-085 | employee sees only sourced projects | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-086 | accountant sees all project placements | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-087 | accountant cannot create project | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-088 | HR activates/deactivates project | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-089 | accountant cannot change project status | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-090 | inactive project bonus prevented | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |

## Invoices and schedules

| ID | Scenario | Expected acceptance outcome | Execution |
|---|---|---|---|
| UAT-091 | configure client recipient | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-092 | configure vendor recipient | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-093 | configure candidate recipient | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-094 | record billing email | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-095 | record billing phone | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-096 | record billing address | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-097 | reject malformed email | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-098 | configure monthly 15th | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-099 | configure monthly 18th | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-100 | configure invoice payment terms | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-101 | invoice starts no earlier than project | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-102 | invoice ends no later than today | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-103 | invoice cannot exceed contract end | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-104 | invoice quantity required | Calculated value matches policy, date boundaries and persisted source data | Pending scenario-level evidence |
| UAT-105 | invoice amount uses Decimal rounding | Calculated value matches policy, date boundaries and persisted source data | Pending scenario-level evidence |
| UAT-106 | tax percentage range validated | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-107 | duplicate invoice window rejected | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-108 | invoice PDF protected by finance role | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-109 | draft cannot be marked paid directly | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-110 | draft can be marked sent | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-111 | sent invoice can be marked paid | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-112 | paid invoice cannot be edited | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-113 | overdue sent invoice marked overdue | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-114 | invoice tied to specific project | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-115 | inactive project manual invoice forbidden | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-116 | inactive project schedule skipped | Only the due, authorized and active project period is processed; repeat runs are safe | Pending scenario-level evidence |
| UAT-117 | contract end date stops future billing | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-118 | schedule retry is idempotent | Only the due, authorized and active project period is processed; repeat runs are safe | Pending scenario-level evidence |
| UAT-119 | hourly schedule requires approved units | Only the due, authorized and active project period is processed; repeat runs are safe | Pending scenario-level evidence |
| UAT-120 | reviewed units produce correct draft | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |

## Authorization / data privacy

| ID | Scenario | Expected acceptance outcome | Execution |
|---|---|---|---|
| UAT-121 | employee cannot read finance project list | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-122 | employee cannot download invoice PDF | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-123 | employee cannot create invoice | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-124 | accountant cannot deactivate project | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-125 | accountant cannot approve HR policy | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-126 | HR cannot self-approve material change | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-127 | HR can propose policy | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-128 | admin can inspect approval reason | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-129 | admin can approve policy | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-130 | peer cannot view private leave balance | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-131 | employee cannot see other person's review | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-132 | peer reviewer identity withheld in aggregate | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-133 | employee cannot view finance audit | Operation is blocked with an explicit error and no unauthorized mutation | Pending scenario-level evidence |
| UAT-134 | protected upload requires login | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-135 | payroll payslip restricted to owner | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |

## Operations / deployment

| ID | Scenario | Expected acceptance outcome | Execution |
|---|---|---|---|
| UAT-136 | staging database isolated | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-137 | production credentials excluded from code | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-138 | database backup created and restored | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-139 | schema migration rehearsal succeeds | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-140 | rollback migration rehearsed | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-141 | frontend builds on supported Node | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-142 | backend starts on supported ASGI host | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-143 | database SSL connectivity verified | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-144 | secure cookie flag enabled | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-145 | uploads stored outside public_html | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-146 | billing cron runs once daily | Only the due, authorized and active project period is processed; repeat runs are safe | Pending scenario-level evidence |
| UAT-147 | missed cron triggers alert | Only the due, authorized and active project period is processed; repeat runs are safe | Pending scenario-level evidence |
| UAT-148 | failed cron replay safe | Only the due, authorized and active project period is processed; repeat runs are safe | Pending scenario-level evidence |
| UAT-149 | cross-module hire to exit UAT | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |
| UAT-150 | two-day demo uses synthetic employee data | Correct role-scoped state is persisted and visible to authorized users | Pending scenario-level evidence |

**Release rule:** do not count a parametrized test as business-process certification unless the actual scenario and assertions are mapped here. Require source code review, UAT evidence, and legal/finance review of invoice formats and withholding/tax rules.
