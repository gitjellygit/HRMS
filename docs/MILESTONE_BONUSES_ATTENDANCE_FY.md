# Project incentives, attendance status and India financial-year leave

## Project sourcing and 30-day milestone bonus

In **Projects → Add project**, select the sourcing employee, start date and an INR milestone bonus (for example ₹10,000 or ₹15,000).

- A project starting **1 December** reaches 30 completed calendar days on **31 December**.
- The API reconciles due awards on startup and hourly while it runs (the `PROJECT_BONUS_AUTO_SYNC` environment variable defaults to `true`). If the server was offline, the next startup catches up.
- Each project generates **at most one** planned bonus, assigned to the sourcing employee. Database uniqueness plus advisory locks prevent duplicates.
- Employees see bonus amount/status in their **Overview**. HR can see status and manually award already-eligible projects if the scheduler has not yet run.
- Bonuses are **not marked approved or paid automatically**. The existing Bonuses workflow controls approval/payment; actual payroll transfer is not yet implemented.
- Legacy projects remain readable, without fictional start dates, sourcing employees or rates.
- Project source owner is distinct from the assigned project team.

**Production note:** the hourly loop runs in an API process. Move scheduled reconciliation to a dedicated worker/cron with monitoring and audit trails before deploying at scale. Stored project rates are commercially sensitive; a permissions review is still required.

## Attendance

Both Overview and Attendance query `GET /attendance/status` for the authenticated employee.

- Not checked in → **Punch in**
- Currently checked in → **Punch out**
- After action, the current status refreshes immediately.
- Server serializes concurrent toggles per employee; repeated clicks are not interpreted as separate explicit actions.

## India financial-year leave

The leave policy engine now labels financial years **FY YYYY-YY**, from **1 April to 31 March**, rather than the calendar year.

For `annual_days: 12`, joining **1 December 2026** gives approximately **4 days for FY 2026–27**. Joining on 1 April receives 12. Days are prorated for service days from joining date through 31 March, rounded to the nearest **0.5 day**. This rule is a company configuration assumption, not a claim about statutory entitlement.

- HR configures the yearly 12-day leave policy once under **Leave requests → Policies & balances**.
- The **HR overview** displays the calculated financial-year allocations for new and existing employees automatically. HR no longer has to allocate 12 days individually.
- HR can enter an **explicit override** for an employee and FY; it supersedes policy proration.
- If monthly accrual is configured instead, that mode accrues through elapsed months after joining; monthly and annual policy allocations are alternatives, not additive.
- Pending and approved leave reserve balance. Prior-year carry-forward uses the configured cap; review your local HR policy before enabling it.
- Requests must stay within one April–March FY; split across FY boundary. Cross-calendar-year dates within one FY are supported.
- Older manually allocated calendar-year entitlements and legacy `/leaves` data require a reviewed migration/reconciliation before production.

## Local testing

```bash
git fetch origin
git switch --track origin/feature/project-bonus-attendance-fy
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Test one project starting over 30 days ago and a future-starting project; check that only the mature project gets a **planned** bonus. Test punching in and out from both navigation screens. Set a 12-day leave policy and create an employee joining on 1 December, then check the HR overview for FY 2026–27.

GitHub Actions executes backend PostgreSQL smoke tests and Next.js build. Before production: Alembic migrations, financial policy sign-off, payroll approval integration, rate permissions and complete security checks.
