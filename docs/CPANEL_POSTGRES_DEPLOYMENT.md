# Jellygit HRMS: cPanel + PostgreSQL deployment runbook (2026-11-05)

**Status: planning only — no live deployment performed.** Confirm hosting features before uploading employee data.

## Stack and compatibility

Frontend: Next.js (Node.js 22). API: FastAPI (ASGI/Uvicorn, Python 3.12). Database: PostgreSQL. Storage: private upload volume. Jobs: daily billing, bonus and probation housekeeping.

- cPanel's Application Manager/Passenger or Meridian Web Apps can host Node.js if your hosting package enables it.
- Python WSGI support in cPanel **does not automatically support FastAPI ASGI**. For FastAPI require a persistent Uvicorn process, proxy routing, SSL and process supervision; standard shared cPanel may not offer these. A VPS/container host is preferable.
- cPanel *can* offer PostgreSQL Databases / Database Wizard, **only if PostgreSQL is installed and configured by the provider in WHM**. If missing, use managed PostgreSQL accessible to the API host.
- Do **not** swap PostgreSQL for MySQL, or place SQL dumps and secrets under `public_html`.

References:
- https://docs.cpanel.net/cpanel/software/application-manager/
- https://docs.cpanel.net/cpanel/meridian/websites/deploy-a-website-with-nodejs/
- https://docs.cpanel.net/cpanel/databases/postgresql-databases/
- https://docs.cpanel.net/cpanel/files/git-version-control/
- https://nextjs.org/docs/app/getting-started/deploying

## Recommended architecture

```
https://hrms.example.com  -> cPanel Node app or managed Next.js host
https://api.hrms.example.com -> VPS/container FastAPI (Uvicorn)
                                     |
                              PostgreSQL 16+
                                     |
                             encrypted backups
```

## Prerequisites

1. A staging domain and PostgreSQL database; backup/restore tested. Never move actual PII to unprotected staging.
2. Version-controlled Alembic migrations for all tables. Current `Base.metadata.create_all()` is **not** production schema migration; release remains gated on migration rehearsal.
3. HTTPS, restricted DB network, least-privilege roles, firewall and security updates.
4. Real secrets set outside repository: `DATABASE_URL`, 32+ byte `JWT_SECRET`, `HRMS_PII_KEY`, `CORS_ORIGINS=https://hrms.example.com`, `COOKIE_SECURE=true`, and a private persistent `UPLOAD_DIR`.
5. Frontend: set `NEXT_PUBLIC_API_URL=https://api.hrms.example.com` at **build time**, then `npm install && npm run build`, and use the provider's supported Node process manager.
6. API: Python 3.12, install `backend/requirements.txt`, run `uvicorn app.main:app` under supervisor/systemd or a suitable managed ASGI service.
7. Data migration: restore an approved PostgreSQL dump using `pg_restore` or `psql` into the provisioned DB, apply tested migrations, verify row counts and permissions.
8. Daily scheduler on backend host (server-local 02:00; review business timezone):
   `0 2 * * * cd /srv/hrms/backend && /srv/hrms/.venv/bin/python -m app.billing_job >> /var/log/hrms-billing.log 2>&1`.
   Draft generation is **not email delivery**. Require reviewed billable units for hourly projects.
9. Test new employee login/logout and password reset, role permissions, leave-year proration, HR approval queue, invoicing periods, contract end cutoff, report downloads, upload privacy, and recovery.
10. Complete developer review, financial/statutory review, two-day synthetic-data UAT and restore/rollback rehearsal **before** production enablement.

## Provider questions

Can they supply Node.js 22, Python 3.12 long-running ASGI, PostgreSQL 16, cron, SSH, SSL, process supervision, secret environment variables, private file storage and backups? If any critical capability is missing, place API/DB on a VPS or managed service rather than forcing the full HRMS into generic shared hosting.
