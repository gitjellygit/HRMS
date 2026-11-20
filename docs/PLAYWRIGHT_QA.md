# JellyGit HRMS — Playwright end-to-end QA

## QA accounts

The list in the request totals **seven**, not five: 3 bench sales + 2 software developers + 1 HR + 1 accountant. We seed all seven and **one manager** for hierarchy/approval permissions. All are fake employees in an isolated database, never real HR records.

| Persona | Department | Role | Intended access |
| --- | --- | --- | --- |
| Aarav Sales | Bench Sales | Employee | Own profile, attendance, leave, projects (read), org chart |
| Ishita Sales | Bench Sales | Employee | Same as employee |
| Kabir Sales | Bench Sales | Employee | Same as employee |
| Nisha Developer | Engineering | Employee | Same as employee |
| Rohan Developer | Engineering | Employee | Same as employee |
| Meera Humanresources | Human Resources | HR | Employee directory, HR overview, policies, approvals, organization, bulk |
| Dev Accountant | Finance | Accountant | Employee summary, bonuses (read), own profile, attendance, leave, projects |
| Neha Manager | Bench Sales | Manager | Own profile, team leave approvals, calendar, attendance; no HR policies |

Roles are currently *access roles*, not job titles: **Bench Sales and Software Developer both use the Employee role**. This is intentional until the app has fine-grained job-based permissions.

## 1. Start a separate local QA environment

From the root of the repository:

```bash
git fetch origin
git switch --track origin/test/playwright-role-e2e
docker compose -f docker-compose.e2e.yml up -d --build
docker compose -f docker-compose.e2e.yml ps
```

The QA stack is a distinct Compose project called **jellygit-hrms-e2e**, with its own PostgreSQL volume, uploads and ports:

- QA web UI: **http://127.0.0.1:3100**
- QA API/Swagger: **http://127.0.0.1:8100/docs**
- Regular HRMS dev stack remains at localhost:3000 / localhost:8000

All credentials in `docker-compose.e2e.yml` are explicitly **throwaway local test credentials only**. Never deploy this Compose configuration or reuse its secrets in production.

## 2. Install Playwright locally (Mac)

```bash
cd frontend
npm install
npx playwright install chromium
```

## 3. Run all tests

Run from the `frontend` directory:

```bash
E2E_ALLOW_SEED=isolated \
E2E_ADMIN_EMAIL=qa.admin@example.org \
E2E_ADMIN_PASSWORD='TestAdminOnly!Pass1234' \
npm run test:e2e
```

Playwright's setup step creates the departments and eight accounts in the **isolated QA database**, with unique emails, then runs all scenarios. Tests cover role navigation, frontend forms, server authorization, login/logout, leave, payroll visibility, attendance, policy access and sidebar position.

**The test harness will refuse to create users unless `E2E_ALLOW_SEED=isolated` is set.** The configured URLs must be loopback URLs.

## 4. Watch Chromium interact with the app

**Open a visible browser and watch automation:**

```bash
E2E_ALLOW_SEED=isolated \
E2E_ADMIN_EMAIL=qa.admin@example.org \
E2E_ADMIN_PASSWORD='TestAdminOnly!Pass1234' \
npm run test:e2e:headed
```

**Interactive Playwright UI** (run individual tests, view timelines and debug):

```bash
E2E_ALLOW_SEED=isolated \
E2E_ADMIN_EMAIL=qa.admin@example.org \
E2E_ADMIN_PASSWORD='TestAdminOnly!Pass1234' \
npm run test:e2e:ui
```

**Run only role/menu checks:**

```bash
E2E_ALLOW_SEED=isolated \
E2E_ADMIN_EMAIL=qa.admin@example.org \
E2E_ADMIN_PASSWORD='TestAdminOnly!Pass1234' \
npx playwright test e2e/navigation.spec.ts
```

After a test has seeded accounts once, see generated emails in `frontend/e2e/.auth/users.json` (ignored by Git). All seeded users share the *test-only* password `DemoOnly!Pass1234`. Open **http://127.0.0.1:3100** in your normal browser and sign in as each user to examine the role-specific menus manually.

## 5. Understand the results

```bash
npx playwright show-report
```

On failure, Playwright saves HTML reports, screenshots, video and traces under `frontend/playwright-report/` and `frontend/test-results/`. These folders are ignored by Git. In GitHub Actions download the `hrms-playwright-e2e-report` artifact from the **Playwright E2E (isolated HRMS)** workflow.

The assertions intentionally surface mismatches between intended roles and actual UI/API permissions. **Do not change tests merely to turn red checks green**; investigate actual authorization or navigation defects first.

## 6. Stop / reset ONLY isolated QA data

From the repo root:

```bash
docker compose -f docker-compose.e2e.yml down
```

To discard **only** the QA database/fixtures:

```bash
docker compose -f docker-compose.e2e.yml down -v
```

The second command is safe **only because it references the standalone e2e file and project**. Never run `docker compose down -v` against the normal application stack.

## Further testing needed

Automated tests are a strong baseline but not production certification. Upcoming checks: accessibility across browsers/mobile, full MFA, payroll calculations, leave accrual correctness, document malware scanning, audits, recovery, security scanning and dedicated data migration tests.
