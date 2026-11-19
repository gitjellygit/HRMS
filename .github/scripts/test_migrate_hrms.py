"""Offline CI checks for immutable, transactional migration runner."""
import importlib.util
from pathlib import Path
from unittest.mock import patch
import hashlib
import subprocess
import unittest

SCRIPT=Path(__file__).with_name("migrate-hrms.py")
spec=importlib.util.spec_from_file_location("hrms_migrator",SCRIPT)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class MigratorTests(unittest.TestCase):
    def test_ledger_query_uses_real_newline_not_literal_psql_backslash_command(self):
        # Regression: the literal characters \\n after SQL are interpreted by
        # psql as an invalid client-side command, preventing legacy bootstrap.
        captured=[]
        def fake_psql(statement, **kwargs):
            captured.append(statement)
            return ""
        with patch.object(m,"psql",side_effect=fake_psql):
            self.assertEqual(m.ledger_entries(),{})
        self.assertEqual(len(captured),1)
        self.assertTrue(captured[0].endswith(";\n"))
        self.assertNotIn(";\\\\n",captured[0])

    def test_git_manifest_covers_all_sql_files_once_and_in_dependency_order(self):
        sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
        names=[n for n,_ in m.manifest(sha)]
        self.assertEqual(len(names),22)
        self.assertLess(names.index("20261117_activity_agent_devices.sql"),
                        names.index("20261117_activity_agent_app_usage.sql"))
        self.assertEqual(names[-1],"20261119_leave_probation_months.sql")

    def test_verify_rejects_checksum_mutation_and_out_of_order_ledger(self):
        files=[("20261101_a.sql",b"SELECT 1;"),("20261102_b.sql",b"SELECT 2;"),
               ("20261103_c.sql",b"SELECT 3;")]
        h=lambda x:hashlib.sha256(x).hexdigest()
        self.assertEqual(m.verify_entries(files,{"20261101_a.sql":h(files[0][1])}),
                         {n:h(raw) for n,raw in files})
        with self.assertRaisesRegex(RuntimeError,"checksum mismatch"):
            m.verify_entries(files,{"20261101_a.sql":h(b"modified")})
        with self.assertRaisesRegex(RuntimeError,"gap"):
            m.verify_entries(files,{"20261102_b.sql":h(files[1][1])})
        with self.assertRaisesRegex(RuntimeError,"absent"):
            m.verify_entries(files,{"20261101_a.sql":h(files[0][1]),
                                    "20261104_unknown.sql":h(b"SELECT 4;")})

    def test_apply_is_atomic_and_skips_already_recorded_sql(self):
        files=[("20261101_a.sql",b"CREATE TABLE a(id integer);"),
               ("20261102_b.sql",b"ALTER TABLE a ADD COLUMN b text;")]
        calls=[]
        recorded={"20261101_a.sql":m.hash_of(files[0][1])}
        with patch.object(m,"ledger_entries",return_value=recorded),\
             patch.object(m,"psql",side_effect=lambda sql,**kw:calls.append((sql,kw)) or ""):
            m.migrate(files)
        self.assertEqual(len(calls),1)
        script,kwargs=calls[0]
        self.assertTrue(kwargs["single_transaction"])
        self.assertIn("pg_advisory_xact_lock",script)
        self.assertIn("ALTER TABLE a ADD COLUMN b text;",script)
        self.assertIn("INSERT INTO public.hrms_schema_migrations",script)
        self.assertNotIn("CREATE TABLE a(",script)

    def test_bootstrap_writes_only_ledger_not_legacy_ddl(self):
        # The baseline must never execute historical migration SQL.
        fake=[("20261117_activity_agent_app_usage.sql",b"DROP TABLE employees;")]
        with patch.object(m,"ledger_entries",return_value={}),\
             patch.object(m,"psql",return_value="") as sql:
            m.bootstrap(fake)
        data=sql.call_args.args[0]
        self.assertNotIn("DROP TABLE employees;",data)
        self.assertIn("Legacy HRMS schema incomplete",data)
        self.assertIn("INSERT INTO public.hrms_schema_migrations",data)
        self.assertTrue(sql.call_args.kwargs["single_transaction"])


if __name__=="__main__":
    unittest.main()
