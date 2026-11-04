# Employee lifecycle & usability — HRMS PR #12

## 1. IDs and manual overrides

**Employee ID:** `JG-001`, `JG-002`…  
**Project number:** `JG-P-0001`, `JG-P-0002`…

The **Generate** button allocates a new candidate from a PostgreSQL sequence; each click advances the sequence. The input is editable for an HR-approved manual override, subject to its required prefix, digit width, and unique constraint. When someone sets a higher code, the sequence advances accordingly. Unused candidates leave gaps; no existing code is reused.

The existing legacy project/employee records remain intact.

## 2. Dropdowns

The app now uses unified native dropdown styling, consistent type, spacing, chevrons, and visible keyboard focus. Native option-popup rendering is owned by Chrome/Safari/OS; a custom accessible listbox is future work if full menu visual control is required.

## 3. Company policy register

Go to **Policies → Add policy**. The form stores a title, category, effective date and policy description, while the existing sourcing bonus and leave-policy settings remain separate. Currently this is a simple HR policy register, not full document version control or acknowledgments.

## 4. Attendance

Under **Attendance**, each local calendar day appears as a single expandable header showing the session count and daily total hours. Expand for every individual punch-in/out. Sessions spanning midnight are grouped by punch-in date.

## 5. Full employee detail and probation

Click an employee name in **Employees**. The profile header now includes name, employee ID, department, designation, work email, mobile, joining date, and the 90-day probation completion date. The system automatically confirms active employees after 90 full calendar days from date of joining. A lifecycle history event is recorded.

## 6. Access deactivation

On the Employee directory, HR/Admin can **Deactivate** an active employee. Enter a reason of at least ten characters. This keeps records intact but immediately prevents login and invalidates currently authenticated sessions because the backend checks status for each protected request. Employees cannot deactivate themselves; elevated accounts have additional restrictions.

## 7. Temporary password reset

HR/Admin can choose **Reset password**, enter a reason, and issue a cryptographically generated temporary password. It is returned once to the authorized HR user and not stored in plaintext; the previous password and existing sessions are invalidated.

**Important:** Enforced password change on first sign-in, secure delivery to employees, notification controls, and independent security audit remain **pre-production follow-ups**. Don't send temporary passwords through public chat or unencrypted email.

## 8. Indian mobile validation

A new employee's optional Indian mobile must be ten digits starting with 6–9, optionally prefixed with 91 or +91. Values normalize to `+91XXXXXXXXXX`. Other countries' numbers and fixed-line numbers are not currently accepted for the employee mobile field; expanding country support will require a country-code selector.

## Run locally with hot reload

```bash
git fetch origin
git switch --track origin/feature/hrms-employee-lifecycle-ux
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Visit **http://localhost:3000**. For automatic browser validation, see `docs/PLAYWRIGHT_QA.md`; the isolated E2E environment is intentionally separate from your real dev DB.

## Before production

- Perform Alembic schema migrations and backups; application still uses runtime `create_all`.
- Add mandatory password change at first login, comprehensive security audits, and approved secure credential delivery.
- Enforce and audit future edit/delete/archive policy workflows.
- Use a formal policy versioning/employee acknowledgment model rather than plain-text policy records for regulatory compliance.
- Extend country-specific phone validation if international employees are hired.
- Move probation reconciliation to a monitored worker and verify idempotent audit logs when multiple API workers are running.
