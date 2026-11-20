# Phase 4 rollout: persistent pilot database and email outbox

Do not run `docker compose down -v`: that deletes database volumes.

## Before the API upgrade

1. Backup and verify the PostgreSQL database used by the target Compose project.
2. Apply **all outstanding Phase 1–3 SQL migrations** in chronological order as applicable; they are not replaced by this document. In particular, preserve `pay_config_versions`, finance invoice indexes and new billing-ledger tables.
3. Apply `20261110_leave_email_outbox.sql` on the **same database** as the API, before starting the email worker.
4. Check the resulting table exists and the migration does not alter or delete historic leave rows.

Example from a checked-out backend container with an authenticated `DATABASE_URL`:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/migrations/20261110_leave_email_outbox.sql
```

Run the SQL from the host/container where its path exists. The backend image copies `app/` only, so migration SQL may need to be mounted or passed through stdin rather than referenced directly inside that container.

## Email delivery

- `docker-compose.yml` includes a **separate** `leave-email-worker` process. It polls the durable outbox once per minute. It does not block API requests.
- Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, and optionally `SMTP_USER` / `SMTP_PASSWORD` in the environment loaded by the API and worker.
- Without SMTP credentials, leaves/approvals still save and in-app notices still appear. Email attempts become visible as retrying/failed in **HR overview → Leave email delivery**; HR can requeue failed items.
- Check email-worker container logs and successful delivery receipts before assuming that real emails reached recipients.
- The existing quick Cloudflare tunnel does not restrict access to known testers. Keep real employee PII and financial records out until approved access protection is configured.

## Phase 4 smoke test

- Create leave request with a manager, approve/reject/cancel it; test HR override with mandatory reason.
- Verify half-day and encashment reservations, carry-forward and April–March boundaries.
- Deactivate a manager with active direct reports; verify reassignment and pending leave approvals.
- Start exit workflow, verify incomplete employee/HR tasks block F&F; document asset, IT and finance clearance approvals; confirm final settlement and only then mark lifecycle as exited.
- Update and disable an exit template. New exits must use the new configuration, existing cases must retain their assigned tasks.
- Verify HR can see failed email delivery and retry; ensure the API stays responsive if SMTP is down.
- Confirm legacy `/leaves`, `/core/hr-overview` and `/core/leave-entitlements` correctly respond with HTTP 410 and point to the replacement leave APIs.

**Do not mark the pilot production-ready solely from CI.** CI does not prove SMTP deliverability, tenant data migrations, external payroll compliance or actual Cloudflare access controls.
