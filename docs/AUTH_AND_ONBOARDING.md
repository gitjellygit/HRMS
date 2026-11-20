# HRMS login and employee onboarding

## Login and sessions
- Public registration is not implemented; admins and HR create users.
- Login uses an HttpOnly SameSite=Lax cookie. The password is never saved by the app's JavaScript.
- 'Remember me' keeps a session for 30 days; unchecked sessions expire after 8 hours and use a browser-session cookie.
- Browser password managers can save and fill passwords via standard autocomplete fields.
- Configure `COOKIE_SECURE=true` behind HTTPS for deployment; API and frontend should be same-site HTTPS subdomains.
- Password changes revoke old sessions via password-hash-bound tokens. Rate-limiting and audit logs are still required before production use.

## Password reset email
Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `FRONTEND_URL`.
The server sends time-limited, one-use email links with a 30 minute expiry. No reset tokens are logged; only token digests are stored.
When SMTP isn't configured, a registered-user reset request fails with HTTP 503, as intended. Use production SMTP credentials in environment variables, never commit them to Git.

## Documents
HR/admin may upload documents while creating an employee; employees may download only their own documents. Files are limited to 5 MB and PDF, PNG or JPEG and kept in private `hrms_uploads` Docker volume.
Do not store real ID documents until backups, antivirus scanning, encryption/retention controls and an authorization review are complete.

## Local verification
Run `docker compose up --build -d` after pulling the branch. Test login, remember session, reset email, new account creation, role restrictions and document downloads.
`POSTGRES_PASSWORD` may contain URL-reserved characters; if so encode those characters in the `DATABASE_URL` value consumed by the API (the existing compose may override it). See README for hosting cautions.
