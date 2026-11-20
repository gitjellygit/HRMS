# HRMS architecture decisions

Durable rationale for future engineers and ChatGPT sessions; do not maintain live CI or PR state in this document.

## ADR-001 — GitHub and committed documentation are the persistent project memory
**Status: Accepted (2026-11-19).**
Use current GitHub `main`, tests, dated current-state handoff, release gates and decision log. Chats may end and are not an authoritative record. Verify live status at the beginning of every session.

## ADR-002 — Strict separation of code, CI, migration and deployment readiness
**Status: Accepted (2026-11-19).**
A feature may be implemented or CI-green while still unmerged, unmigrated or unverified on Hostinger. Maintain distinct states: implemented, automated tested, merged, migration rehearsed, deployed, hosted verified. A passed pipeline is never evidence that a Windows executable connected successfully to a VPS.

## ADR-003 — HRMS employee and finance changes require backend governance
**Status: Existing intended control, verify each module before release.**
Role-specific permissions must be enforced in backend routes. Payroll, statutory, salary, invoice and lifecycle edits need appropriate approvals, audit evidence and explicit errors. The UI should make missing actions and validation conditions clear.

## ADR-004 — Device monitoring is disclosed, authorized and assignment-gated
**Status: Proposed design under PR #57; not merged at snapshot.**
HR/IT can register a company-authorized device before employee creation using an expiring single-use invitation. The device is pending and must not send or store activity telemetry until HR assigns it to an active employee and disclosure/authorization gates are satisfied. Avoid covert surveillance, screenshots, keystrokes and visited-URL collection. Review applicable employee notice, privacy and retention requirements before activation.

## ADR-005 — Migrations and production data are protected
**Status: Existing release rule.**
Versioned PostgreSQL migrations are applied in manifest order, with backup and rehearsal before deployment. No destructive volume resets, manual rewriting of applied migrations or production data experiments. Deployment from main requires a separately verified release gate.

## ADR-006 — Focused PRs and evidence-driven handoffs
**Status: Accepted (2026-11-19).**
Keep documentation changes isolated from runtime features, and record verified outcomes with exact PRs/SHAs. Future sessions should reconcile the snapshot with live GitHub rather than reimplement work already merged.
