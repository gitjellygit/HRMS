# Automatic Windows companion registration — staged rollout

This feature is a **controlled pilot**, not an invitation for arbitrary public devices to begin activity monitoring.

## Installer and API
- Windows companion v0.6 has a built-in HTTPS API URL and creates its own local configuration when missing.
- On first run it detects the Windows hostname and POSTs `{"device_label":"HOSTNAME"}` to `/activity-agent/register-auto`.
- The API creates a **pending** device, issues a device-only bearer token, and does not accept activity heartbeats while unassigned.
- HR/Admin sees and assigns the device in People Operations -> Analytics. Assignment requires an active employee.
- The API must be deployed, and pending enrollment tested against Hostinger, before the EXE works. A GitHub merge is not a server deployment.

## Explicit enablement
The endpoint returns HTTP 503 unless `HRMS_ACTIVITY_AUTO_REGISTER_ENABLED=true` is set on the FastAPI deployment. This must not be enabled until a controlled pilot is approved.

Pilot protections: registration limit 10/hour per API process and max 50 globally pending devices. These are defense in depth, **not** a production anti-abuse system: enforce public endpoint rate limiting at the edge/reverse proxy, monitor pending volume, and consider enterprise device attestation/management before broad rollout.

## Asset identity and employee privacy
Windows hostname can be spoofed and is not proof of ownership or physical asset identity. Never auto-assign by hostname. HR/IT must independently verify the actual laptop before assigning. Provide clear notice and authorization for workplace monitoring before activation. Do not rely on an EXE-embedded permanent secret.

## Verification / release gates
1. Review and merge pending-device migration and API PR only after migration backup/restore rehearsal.
2. Verify zero-file launch and automatic pending registration on a real Windows 10/11 machine over HTTPS.
3. Verify offline retry, duplicate install, assignment, revocation, 403 heartbeat while pending and no telemetry before assignment.
4. Verify monitored activity categories, exit UX and role-scoped HRMS visibility.
5. Code sign the EXE, scan it, and commit reviewed Windows source before distributing it to staff.
