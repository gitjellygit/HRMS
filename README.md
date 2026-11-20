# JellyGit HRMS

Lightweight internal HRMS for a small team. **Early MVP foundation — not yet production-ready.**

## Stack
- Next.js 15 + TypeScript frontend
- FastAPI + SQLAlchemy backend
- PostgreSQL 16
- Docker Compose for local development and compatible VPS hosting

## Initial features
- Employee accounts with role-based access: admin, HR, accountant, employee
- Employees and dashboard
- Self-service punch-in / punch-out; attendance history
- Leave requests and HR approval
- Projects, project-team assignment API
- Bonuses (planned → approved → paid), restricted to HR/accountant/admin as appropriate
- Appraisals with manager/HR-visible records
- API documentation at `/docs`

**Not built yet:** actual protected document uploads, salary/payroll processing, leave balances and holidays, full employee edit/delete, password reset, timezone/location policy, audit log, account lockout/rate limits, project assignment UI, database migrations, automated test suite, backup/restore automation. Do not put real employee personal documents in this MVP.

## Local setup
1. Copy `.env.example` to `.env` and set strong unique `POSTGRES_PASSWORD`, `JWT_SECRET` (32+ chars), `ADMIN_EMAIL`, `ADMIN_PASSWORD` (12+ chars).
2. Run `docker compose up --build -d`.
3. Open `http://localhost:3000`. The API is at `http://localhost:8000/docs`.
4. Log in with your configured admin credentials (created only at first startup).
5. Backend schema creation uses SQLAlchemy `create_all` temporarily; use Alembic before production or schema changes.

**Browser API URL:** `NEXT_PUBLIC_API_URL` is built into the frontend image at build time. Use a browser-reachable HTTPS URL on hosted deployments, not `localhost`. Rebuild frontend after changing it.

## Hostinger / cPanel deployment
Hostinger hosting products differ. **Do not assume that shared cPanel hosting supports Docker, persistent Python/ASGI, Node.js services, or PostgreSQL.** First verify the plan's SSH/root access, Python ASGI/Passenger support, Node.js app availability, PostgreSQL database access, process management, and reverse proxy control.

Preferred deployment: Hostinger VPS with Docker Compose, HTTPS reverse proxy (Nginx/Caddy), managed backups, firewall, DNS `hrms.example.com` for frontend and `api.example.com` for backend. Keep PostgreSQL private; expose only HTTPS. Set `NEXT_PUBLIC_API_URL=https://api.example.com` and `CORS_ORIGINS=https://hrms.example.com`, rebuild and deploy behind TLS. Configure proxy requests to frontend port 3000 and API 8000. The compose binds both to 127.0.0.1, suitable for a host reverse proxy.

If you have **shared cPanel only** without persistent FastAPI/Node processes and PostgreSQL, this exact stack cannot be deployed there as-is. You may host frontend/backend on a VPS and use the cPanel-managed domain/DNS.

## Security before real data
- Implement Alembic migrations, HTTP-only secure session cookies / BFF (current MVP stores short-lived tokens in sessionStorage), login rate limits, password resets and account deactivation.
- Add change/audit logs and stricter accountant field-level access (currently accountants can view employee contact details), leave and bonus approval rules.
- Add protected document storage, authorization on each document, encrypted backups, key rotation, retention policy, and India employee-data/privacy review.
- Add testing/CI and verify restore procedures before production use.
