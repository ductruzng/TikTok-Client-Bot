"""V6 to V7 fixture migration, WAL backup, rollback and read-only validation."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import ledger
import ledger_migrations as migrations


class WorkerMigrationTests(unittest.TestCase):
    def fixture(self, path):
        conn = sqlite3.connect(path, isolation_level=None)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA wal_autocheckpoint=0')
        migrations._migrate_v2(conn, path)
        conn.execute('BEGIN IMMEDIATE')
        for apply in (migrations._apply_v3, migrations._apply_v4, migrations._apply_v5, migrations._apply_v6):
            apply(conn, None)
        conn.commit()
        for n, status in enumerate(('queued', 'pending', 'failed_unknown', 'confirmed')):
            transmitted = int(status != 'queued')
            conn.execute('''INSERT INTO send_requests(request_id,canonical_uid,conv_id,idempotency_key,payload_json,
                status,created_at,client_msg_id,transmitted,date,attempt_time,transmission_started_at_ms)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''', (str(n), '111', str(n), str(n), '{}', status,
                'fixture', str(n), transmitted, '2026-10-09' if transmitted else None,
                '2026-10-09T12:00:00+07:00' if transmitted else None, 1791522000000 if transmitted else None))
            conn.execute('INSERT INTO queue_entries(request_id) VALUES(?)', (str(n),))
        return conn

    def test_v6_preflight_readonly_wal_backup_preservation_and_repeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp)/'v6.db')
            with closing(self.fixture(path)) as conn:
                before = list(conn.iterdump())
                report = migrations.preflight(path)
                self.assertEqual(report['version'], 6)
                self.assertFalse(report['errors'])
                self.assertEqual(list(conn.iterdump()), before)
                rows = conn.execute('SELECT * FROM send_requests').fetchall()
                queue = conn.execute('SELECT * FROM queue_entries').fetchall()
                backup = migrations.migrate(path)
                migrations.validate_schema(conn)
                self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], migrations.VERSION)
                self.assertEqual(conn.execute('SELECT * FROM send_requests').fetchall(), rows)
                self.assertEqual(conn.execute('SELECT * FROM queue_entries').fetchall(), queue)
                self.assertEqual(conn.execute('SELECT count(*) FROM worker_runs').fetchone()[0], 0)
                self.assertIsNone(migrations.migrate(path))
                with closing(sqlite3.connect(backup)) as saved:
                    self.assertEqual(saved.execute('PRAGMA user_version').fetchone()[0], 6)
                    self.assertEqual(saved.execute('SELECT * FROM send_requests').fetchall(), rows)
                    restored_path = str(Path(tmp)/'restored.db')
                    with closing(sqlite3.connect(restored_path)) as restored:
                        saved.backup(restored)
                        self.assertEqual(restored.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                        migrations.validate_schema(restored, expected=6)

    def test_v7_failure_rolls_back_and_can_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp)/'v6.db')
            with closing(self.fixture(path)) as conn:
                before = list(conn.iterdump())
                apply = migrations._apply_v7
                def fail(*args):
                    apply(*args)
                    raise RuntimeError('fixture before commit')
                with patch.object(migrations, '_apply_v7', side_effect=fail):
                    with self.assertRaises(RuntimeError): migrations.migrate(path)
                self.assertEqual(list(conn.iterdump()), before)
                migrations.migrate(path)
                migrations.validate_schema(conn)

    def test_worker_history_constraints_and_missing_trigger_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp)/'v6.db')
            with closing(self.fixture(path)) as conn:
                migrations.migrate(path)
                conn.execute("INSERT INTO worker_runs VALUES('r',?,'{}',1)", ('a'*64,))
                conn.execute("INSERT INTO worker_run_requests VALUES('r',0,'0','{}')")
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute("INSERT INTO worker_run_requests VALUES('r',1,'1','{}')")
                conn.execute("INSERT INTO worker_events(run_id,event_type,at_ms,details_json) VALUES('r','RUN_STARTED',2,'{}')")
                for sql in ("UPDATE worker_runs SET consent_json='{}'", 'DELETE FROM worker_run_requests',
                    'DELETE FROM worker_events', "INSERT INTO worker_events(run_id,event_type,at_ms,details_json) VALUES('r','RUN_STARTED',3,'{}')",
                    "INSERT INTO worker_events(run_id,event_type,at_ms,details_json) VALUES('r','STOPPED',1,'{}')"):
                    with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError): conn.execute(sql)
                conn.execute('DROP TRIGGER worker_event_valid')
                with self.assertRaises(ledger.SchemaError): ledger.check_ready(path)

    def test_v6_send_opener_never_migrates_and_missing_database_never_creates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp)/'v6.db')
            with closing(self.fixture(path)) as conn:
                before = list(conn.iterdump())
                with self.assertRaises(ledger.SchemaError): ledger.check_ready(path)
                self.assertEqual(list(conn.iterdump()), before)
            missing = str(Path(tmp)/'missing.db')
            with self.assertRaises(ledger.LedgerError): ledger.check_ready(missing)
            self.assertFalse(Path(missing).exists())
