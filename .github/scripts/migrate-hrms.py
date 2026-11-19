#!/usr/bin/env python3
"""Versioned PostgreSQL migrations for HRMS running on a Docker Compose VPS.

Use only with a verified Git commit. Scripts are loaded from Git, not from the
mutable host working tree; each successfully applied script is recorded with a
SHA-256 checksum in PostgreSQL. Future changes to applied scripts fail closed.

First-time installations that predate this ledger must do a ONE-TIME reviewed
--bootstrap-legacy. No schema approval options are needed after that.
"""
import argparse
import hashlib
import re
import subprocess
import sys

MANIFEST = "backend/migrations/ORDER.txt"
BASELINE_LAST = "20261117_activity_agent_app_usage.sql"
SQL_NAME = re.compile(r"^[0-9]{8}_[a-z0-9_]+\.sql$")
SHA = re.compile(r"^[0-9a-f]{40}$")
PSQL = ["docker", "compose", "exec", "-T", "db", "sh", "-c",
        'psql -X -At -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"']
LOCK = "SELECT pg_advisory_xact_lock(72517, 20261119);"
LEDGER = """
CREATE TABLE IF NOT EXISTS public.hrms_schema_migrations (
 name text PRIMARY KEY,
 checksum_sha256 char(64) NOT NULL,
 applied_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT hrms_migration_hash_check CHECK (checksum_sha256 ~ '^[a-f0-9]{64}$')
);
"""
# Legacy baseline is accepted only when all key schema artifacts are present;
# historical migration SQL is never blindly rerun on an existing production DB.
LEGACY_CHECK = """
DO $legacy_check$
DECLARE absent text;
BEGIN
 SELECT string_agg(t.n, ', ') INTO absent
 FROM (VALUES
  ('leave_policies'),('leave_policy_versions'),('people_company_letterhead'),
  ('people_onboarding_categories'),('people_announcements'),('people_offers'),
  ('activity_agent_devices'),('pay_manual_payslips'),('leave_email_outbox'),
  ('finance_invoices'),('time_timesheets'),('sec_login_failures')
 ) t(n) WHERE to_regclass('public.' || t.n) IS NULL;
 IF absent IS NOT NULL THEN
   RAISE EXCEPTION 'Legacy HRMS schema incomplete; missing: %', absent;
 END IF;
 SELECT string_agg(t.tbl || '.' || t.col, ', ') INTO absent
 FROM (VALUES
   ('leave_policies','year_type'),('leave_policies','monthly_schedule'),
   ('leave_policies','late_year_monthly_accrual'),
   ('people_offers','letterhead_logo_key'),
   ('people_announcements','audience_ids'),
   ('activity_agent_devices','app_usage_json')
 ) t(tbl,col) WHERE NOT EXISTS (
   SELECT 1 FROM information_schema.columns c
   WHERE c.table_schema='public' AND c.table_name=t.tbl
     AND c.column_name=t.col);
 IF absent IS NOT NULL THEN
   RAISE EXCEPTION 'Legacy HRMS columns incomplete: %', absent;
 END IF;
 IF EXISTS (
   SELECT 1 FROM leave_policies p WHERE NOT EXISTS (
     SELECT 1 FROM leave_policy_versions v
     WHERE v.leave_type=p.leave_type AND v.effective_from=DATE '2000-01-01'
   )
 ) THEN RAISE EXCEPTION 'Legacy leave-policy baseline missing'; END IF;
END
$legacy_check$;
"""


def run(args, *, data=None):
    return subprocess.run(args, input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True)


def git_text(sha, path):
    return run(["git", "show", f"{sha}:{path}"]).stdout


def manifest(sha):
    names = [
        row.strip() for row in git_text(sha, MANIFEST).decode().splitlines()
        if row.strip() and not row.lstrip().startswith("#")
    ]
    if not names or len(set(names)) != len(names):
        raise ValueError("Migration manifest is missing or has duplicate entries")
    if any(not SQL_NAME.fullmatch(n) for n in names):
        raise ValueError("Migration filenames must be YYYYMMDD_name.sql")
    if BASELINE_LAST not in names:
        raise ValueError("Legacy baseline boundary missing from manifest")
    repo_files = run(["git", "ls-tree", "-r", "--name-only", sha,
                      "backend/migrations"]).stdout.decode().splitlines()
    listed = {p.rsplit("/", 1)[-1] for p in repo_files if p.endswith(".sql")}
    if listed != set(names):
        raise ValueError(
            "Every SQL migration must appear exactly once in ORDER.txt; "
            f"unlisted={sorted(listed - set(names))}, "
            f"missing={sorted(set(names) - listed)}"
        )
    files = [(n, git_text(sha, f"backend/migrations/{n}")) for n in names]
    for name, raw in files:
        if not raw.strip():
            raise ValueError(f"Empty migration: {name}")
    return files


def psql(statement, *, single_transaction=False):
    args = PSQL[:]
    if single_transaction:
        args[-1] += " -1"
    return run(args, data=statement.encode()).stdout.decode()


def ledger_entries():
    output = psql(
        "SELECT name || E'\\t' || trim(checksum_sha256) "
        "FROM public.hrms_schema_migrations ORDER BY applied_at, name;\\n"
    )
    entries = {}
    for row in output.splitlines():
        if "\t" not in row:
            raise RuntimeError("Malformed migration ledger row")
        k, v = row.split("\t", 1)
        if not SQL_NAME.fullmatch(k) or not re.fullmatch("[a-f0-9]{64}", v):
            raise RuntimeError("Invalid migration ledger row")
        entries[k] = v
    return entries


def hash_of(raw):
    return hashlib.sha256(raw).hexdigest()


def ledger_insert(name, digest):
    if not SQL_NAME.fullmatch(name) or not re.fullmatch("[a-f0-9]{64}", digest):
        raise ValueError("Unsafe migration name/checksum")
    return (
        "INSERT INTO public.hrms_schema_migrations(name,checksum_sha256) "
        f"VALUES ('{name}','{digest}');\n"
    )


def verify_entries(files, recorded):
    expected = {name: hash_of(raw) for name, raw in files}
    unknown = set(recorded) - set(expected)
    if unknown:
        raise RuntimeError(f"Database has migrations absent from target: {sorted(unknown)}")
    changed = [n for n, digest in recorded.items() if digest != expected[n]]
    if changed:
        raise RuntimeError(f"Applied migration checksum mismatch: {changed}. "
                           "Never edit an applied SQL script; add a new migration.")
    ordered = [n for n, _ in files]
    # Prevent deploying an older software commit over a database whose
    # schema already includes newer migrations not present in that commit.
    applied_indices = sorted(ordered.index(n) for n in recorded)
    if applied_indices and applied_indices != list(range(applied_indices[-1] + 1)):
        raise RuntimeError("Migration ledger contains a gap. Manual review required.")
    return expected


def bootstrap(files):
    names = [name for name, _ in files]
    boundary = names.index(BASELINE_LAST)
    recorded = ledger_entries()
    if recorded:
        raise RuntimeError("Ledger already contains migration records; bootstrap refused")
    # Initial baseline may not include newer migrations. This is intentional.
    block = LOCK + "\n" + LEGACY_CHECK + "\n"
    for name, raw in files[:boundary+1]:
        block += ledger_insert(name, hash_of(raw))
    psql(block, single_transaction=True)
    print(f"Baselined {boundary+1} reviewed historical migrations. "
          "No historical SQL was rerun.")


def migrate(files, dry_run=False):
    recorded = ledger_entries()
    if not recorded:
        raise RuntimeError(
            "No migration ledger entries. For a pre-existing VPS, first perform "
            "the one-time reviewed --bootstrap-legacy after backups; new databases "
            "must use the initial schema bootstrap procedure."
        )
    verify_entries(files, recorded)
    pending = [(name, raw) for name, raw in files if name not in recorded]
    print(f"{len(recorded)} applied; {len(pending)} pending.")
    for name, raw in pending:
        print(f"{'PENDING' if dry_run else 'APPLYING'} {name}", flush=True)
        if dry_run:
            continue
        # Single PostgreSQL transaction per migration. DDL plus its checksum
        # ledger row either both commit or both roll back.
        sql = (LOCK + "\n").encode() + raw.rstrip() + b"\n" + (
            ledger_insert(name, hash_of(raw))
        ).encode()
        psql(sql.decode(), single_transaction=True)
        recorded[name] = hash_of(raw)
        verify_entries(files, recorded)
    print("Migration validation complete.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sha", help="Full, verified, 40-character git SHA")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--bootstrap-legacy", action="store_true",
                       help="One-time manual legacy baseline; never runs old SQL")
    group.add_argument("--check", action="store_true",
                       help="Show pending migrations without applying them")
    opts = parser.parse_args()
    if not SHA.fullmatch(opts.sha):
        parser.error("Expected a full verified Git commit SHA")
    try:
        files = manifest(opts.sha)
        psql(LEDGER)
        if opts.bootstrap_legacy:
            bootstrap(files)
        else:
            migrate(files, dry_run=opts.check)
    except (subprocess.CalledProcessError, ValueError, RuntimeError) as exc:
        if isinstance(exc, subprocess.CalledProcessError):
            message = (exc.stderr or b"").decode(errors="replace").strip()
            print(f"Migration command failed: {message}", file=sys.stderr)
        else:
            print(f"Migration check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
