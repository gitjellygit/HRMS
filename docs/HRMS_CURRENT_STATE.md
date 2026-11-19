# HRMS current state — handoff snapshot

> Snapshot: **2026-11-19**, from GitHub. **Never treat this file as a live PR/CI feed.** At the beginning of every session, re-check `main`, open PRs, CI, branch diffs, and actual hosted release.

## Snapshot of main
- Repository: `gitjellygit/HRMS`
- `main` SHA at snapshot: `2ec1d170804b7289e46b396534b0fcd3b96aac92`
- Latest main change at snapshot: merge #56, PostgreSQL migration runner newline fix.
- Hostinger migration baseline and deployment were explicitly left separate in #56. **No hosted upgrade is confirmed by this snapshot.**

## Active feature PR at snapshot
### PR #57 — pending activity-device registration and HR assignment
- URL: https://github.com/gitjellygit/HRMS/pull/57
- Head: `feature/activity-pending-device-enrollment-20261119`
- Target: `main`
- Head SHA at snapshot: `467b623fbc3a64027dfc5112c8f9f7e819f7eca8`
- State: **open draft, not merged**, mergeable at snapshot.
- CI at snapshot: `HRMS checks` run 44616225536 **success**; `Playwright E2E (isolated HRMS)` run 44616224826 **success**.
- Changes: one-use HR-created 7-day invitation, company workstation registration without employee, pending-device list, HR assignment, hard heartbeat rejection until assigned, nullable device employee FK migration and backend tests.
- Release blockers documented on PR: migration/backup review; source-control the companion Windows v0.5 build **source** before production distribution; real Windows 10/11-to-Hostinger end-to-end test; monitoring notice/authorization and security/privacy approval. The companion build is currently described as a separate pilot artifact, **not** as merged source.
- **Action: keep draft and unmerged until gates have evidence; automated CI is necessary but insufficient.** Do not conflate pending device connectivity with permission to collect telemetry.

## Handoff-system work
- This documentation-only branch is `docs/hrms-durable-handoff-20261119`.
- The four canonical docs and README discoverability are proposed independently of PR #57.
- After this docs PR is merged, update this file in a later focused PR whenever active PR, release or deployed state materially changes.

## Existing release gates still requiring verification
- `docs/HARDENING_UAT_GATE.md`: MFA/recovery, rate limits, negative authorization matrix, effective-dated payroll settings, billing and leave controls (check exact current state before asserting any item incomplete).
- `docs/PEOPLEOPS_ACTIVITY_UAT_GATE.md`: Windows pilot, disclosure, role UAT, migrations and backup/restore rehearsal.
- `docs/HOSTINGER_DEPLOYMENT.md`: deployment disabled by default, protected environment and manual checks for migration changes.
- `docs/HRMS_VERSIONED_MIGRATIONS.md`: append-only versioned migrations, rehearsal and ledger checks.
- `README.md` has historical early-MVP feature claims; verify against current code before editing claims.

## Recommended next actions
1. Merge this handoff-only PR after confirming its diff is documentation-only.
2. For #57, verify current head and CI again; source-control/audit Windows companion source, validate migration and backups, run live device-to-hosted pilot, assess privacy/notice/authorization, then mark ready and merge if checks pass.
3. Reconcile current hardening UAT checklist with actual code. Prioritize failing P0 security, payroll, billing and leave gates.
4. Follow backup-first release process and verify hosted deployment by exact SHA; record evidence and date.
5. Update this file with fresh main SHA, open PRs, resolved blockers, deployment outcome, and next action. Do not claim hosted success without direct validation.

## Starting a new chat
> Continue JellyGit HRMS. Read docs/HRMS_MASTER_CONTEXT.md, docs/HRMS_CURRENT_STATE.md, docs/HRMS_CHAT_HANDOFF_PROTOCOL.md, docs/HRMS_ARCHITECTURE_DECISIONS.md and relevant UAT gates. Verify live GitHub main SHA, open PRs, checks, release and affected code. GitHub wins over stale notes. Continue from outstanding acceptance gates; keep PRs focused and update the handoff after meaningful changes.
