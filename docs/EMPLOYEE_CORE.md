# Employee Core — roadmap features 1–10

This change lives in **PR #6** targeting `feature/hrms-mvp`; merge the MVP first, then PR #6. Do not use real employee identity or bank documents until encryption, backups, migrations, access review and audit trails have been verified.

## Local setup (development hot reload)

```bash
git fetch origin
git switch feature/employee-core-1-10
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```

The new Python packages `cryptography` and `openpyxl` make **one development image rebuild** necessary. Afterwards ordinary edits hot reload.

Create a **new, private, permanent** Fernet key (inside the API image, after build):

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm --no-deps api python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Add the result to your local `.env` as `HRMS_PII_KEY=...`; keep the key backed up securely outside Git. **Do not rotate it by simply generating a new value:** existing PAN/Aadhaar/UAN and banking values would become unreadable.

Recreate the API container once to read the new environment variable:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --force-recreate api
```

Then open http://localhost:3000.

## What is available in the UI

- Employees → Add: reporting manager, HOD, company department/designation/grade/branch/cost center; admin role controls
- Employees → click a name: employee master record, sensitive identifiers (HR only), protected documents, status history
- Organization: create departments, designations, grades, branches, cost centers
- Org chart: visual tree of reporting relationships
- My profile: view personal profile and request an HR-reviewed edit
- Profile approvals: HR approval queue or employee request history
- Bulk data & expiries: CSV/XLSX import and export, document expiry alerts

### Roles

| Role | Employee master data | HR administration |
| --- | --- | --- |
| Super Admin (and legacy Admin) | All employees, including encrypted fields | Organization, accounts, approvals, import/export |
| HR | All employees, including encrypted fields | Accounts excluding Super Admin, organization, approvals, import/export |
| Manager | Own record and basic direct-report details | Cannot view other employees' PAN/bank fields |
| Employee | Own profile and HR change requests | None |
| Accountant | Existing directory fields only (legacy) | No sensitive core-data access |

The existing `admin` role remains for backward compatibility. Do not grant manager/HR roles to a user without appropriate review. Password-reset SMTP must be configured for bulk imported accounts to become usable.

## Import template

Supported CSV and XLSX columns:

```csv
name,email,designation,department,role,joining_date,phone,manager_email
Aarav Sharma,aarav.sharma@example.org,Software Engineer,Engineering,employee,2026-11-03,+919876543210,morgan.manager@example.org
```

Manager must already exist and have Manager/HR/Admin role before assignment. Import is limited to 500 rows/2 MB per run, validates entire file first, and supports dry-run preview. Imported accounts receive random, unknown passwords. Users must use password-reset email before sign-in. No sensitive bank/PAN/Aadhaar/UAN fields are imported/exported.

## Known limitations before merge

- No Alembic schema migrations yet; startup creates new tables. Do not use `Base.metadata.create_all` as a production migration strategy.
- Leave balances, leave policies, manager-routed leave approval, employee document expiry emails, document encryption-at-rest, multi-factor authentication, and password-reset delivery are **not** complete here.
- The document store has authorization checks and private Docker volume, but still needs malware scanning, encryption-at-rest policy, retention, backups and access audits.
- Some old endpoints still use legacy role checks and are being kept for compatibility; permissions and field-level exposure need a separate production security review.
- Aadhaar storage and identity document processing require a clear business purpose and lawful privacy/compliance review, even with encryption.
- CI integration smoke tests run against disposable PostgreSQL. They are not a substitute for an end-to-end/UAT security pass.

## Tests

GitHub Actions runs Python compile, FastAPI OpenAPI registration, PostgreSQL integration workflow, and Next.js build. All changes remain in a **draft** PR until accepted.
