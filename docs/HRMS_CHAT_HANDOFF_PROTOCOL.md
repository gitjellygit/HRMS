# HRMS chat handoff protocol

**Chats are sessions, not the engineering system of record.** These committed documents make a fresh conversation possible without copying earlier chats.

## On starting every session
1. Read `docs/HRMS_MASTER_CONTEXT.md`.
2. Read `docs/HRMS_CURRENT_STATE.md`.
3. Read `docs/HRMS_ARCHITECTURE_DECISIONS.md` and the appropriate release gate (`HARDENING_UAT_GATE.md`, `PEOPLEOPS_ACTIVITY_UAT_GATE.md`, `HRMS_UAT_150_CASES.md`, migration or deployment playbook).
4. Verify `main` SHA, **all open PRs** (including draft), commits, changed files, reviews and CI live in GitHub.
5. Check which features actually exist on `main` versus an unmerged branch. For deployment questions, check the **actual hosted SHA, migration ledger, backups and smoke tests**, not GitHub alone.
6. Reconcile discrepancies: GitHub wins for code/PR/CI; deployment evidence wins for the running environment. Update stale handoff docs in an appropriate PR.

## Before implementing
- Define scope and acceptance criteria; search existing code/tests first.
- Maintain small focused PRs, avoid giant unrelated changes or hidden behavior.
- Add API authorization, validation and regression tests where appropriate.
- For schema changes: append-only migration, correct `ORDER.txt`, disposable PostgreSQL rehearsal, tested backup/restore path.
- Review financial correctness, HR visibility, employee privacy and audit requirements when relevant.
- Never merge a draft or ship an executable because CI alone is green; honor explicit release blocks and verify real-device integration.

## After each meaningful merge, test or release
Update `HRMS_CURRENT_STATE.md` with:
- date, main SHA, PR URLs and whether open/draft/merged;
- what changed (separate implemented / tests passed / merged / deployed / hosted verified);
- remaining failures, P0 blockers, backup/migration requirements;
- exact next steps and any retained unmerged branch;
- hosted environment verification (date/SHA/evidence) only when observed.
Update architecture decisions only when a **durable decision** changes. Update the relevant UAT gate after verified work, not merely code changes.

## Do not store
Secrets, staff names or PII, database snapshots, access tokens, private URLs with credentials, employee monitoring telemetry, or full conversation transcripts in these files.

## Canonical new-session prompt
> Continue the JellyGit HRMS project from GitHub, not from chat memory. Read HRMS_MASTER_CONTEXT, HRMS_CURRENT_STATE, HRMS_CHAT_HANDOFF_PROTOCOL, HRMS_ARCHITECTURE_DECISIONS and the relevant UAT gates. Verify live main, open PRs, checks and the deployed release. Explain what's implemented versus merged versus deployed, and work from the next verified blocker. Update handoff documentation in a focused PR.

## Reference map
| What | Authority |
|---|---|
| Code behavior | live `main` + tests |
| Open PR and CI | GitHub live |
| Database migrations | `backend/migrations/ORDER.txt` + `HRMS_VERSIONED_MIGRATIONS.md` |
| Operational readiness | `HARDENING_UAT_GATE.md`, `PEOPLEOPS_ACTIVITY_UAT_GATE.md` |
| Hosted state | verified VPS deployment SHA, ledger and release evidence |
| Stable decisions | `HRMS_ARCHITECTURE_DECISIONS.md` |
| Latest summary | `HRMS_CURRENT_STATE.md` (dated snapshot) |
