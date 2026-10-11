"""V5->V6 preflight, committed WAL snapshot, rollback and immutable history fixtures."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import ledger
import ledger_migrations as migrations


class QueueMigrationTests(unittest.TestCase):
    def fixture(self, path):
        conn = sqlite3.connect(path, isolation_level=None)
        conn.execute('PRAGMA journal_mode=WAL'); conn.execute('PRAGMA wal_autocheckpoint=0')
        migrations._migrate_v2(conn, path)
        conn.execute('BEGIN IMMEDIATE')
        migrations._apply_v3(conn, None); migrations._apply_v4(conn, None); migrations._apply_v5(conn, None)
        conn.commit()
        for n, status in enumerate(('queued', 'queued', 'failed_unknown', 'pending')):
            transmitted = int(status != 'queued')
            conn.execute('''INSERT INTO send_requests(request_id,canonical_uid,conv_id,idempotency_key,payload_json,
                status,created_at,client_msg_id,transmitted,date,attempt_time,transmission_started_at_ms)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''', (str(n), '111', 'c'+str(n), 'key'+str(n), '{}', status,
                'fixture', 'client'+str(n), transmitted, '2026-10-09' if transmitted else None,
                '2026-10-09T12:00:00+07:00' if transmitted else None, 1791522000000 if transmitted else None))
            conn.execute('INSERT INTO request_events(request_id,event_type,created_at,details_json) VALUES(?,?,?,?)',
                         (str(n), 'FIXTURE', 'fixture', '{}'))
        return conn

    def test_preflight_is_readonly_then_wal_backup_and_migration_preserve_all_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / 'v5.db')
            with closing(self.fixture(path)) as conn:
                before = list(conn.iterdump())
                rows = conn.execute('SELECT * FROM send_requests').fetchall()
                events = conn.execute('SELECT * FROM request_events').fetchall()
                report = migrations.preflight(path)
                self.assertFalse(report['errors'])
                self.assertEqual((report['version'], report['queued_count'], report['unbound_queued_count'], report['unknown_count'], report['pending_count']), (5, 2, 2, 1, 1))
                self.assertEqual(list(conn.iterdump()), before)
                backup = migrations.migrate(path)
                self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0], migrations.VERSION)
                self.assertEqual(conn.execute('SELECT * FROM send_requests').fetchall(), rows)
                self.assertEqual(conn.execute('SELECT * FROM request_events').fetchall(), events)
                self.assertEqual(conn.execute('SELECT enqueue_seq,request_id,session_name FROM queue_entries').fetchall(), [(i+1, str(i), None) for i in range(4)])
                self.assertEqual(conn.execute('SELECT count(*) FROM unknown_resolution_events').fetchone()[0], 0)
                self.assertIsNone(conn.execute('PRAGMA foreign_key_check').fetchone())
                self.assertIsNone(migrations.migrate(path))
                restored_path = str(Path(tmp) / 'restored.db')
                with closing(sqlite3.connect(backup)) as saved, closing(sqlite3.connect(restored_path)) as restored:
                    saved.backup(restored)
                    self.assertEqual(restored.execute('PRAGMA user_version').fetchone()[0], 5)
                    self.assertEqual(restored.execute('SELECT * FROM send_requests').fetchall(), rows)
                    self.assertEqual(restored.execute('SELECT * FROM request_events').fetchall(), events)
                    self.assertEqual(restored.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_fault_after_v6_ddl_rolls_back_every_change_and_can_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / 'v5.db')
            with closing(self.fixture(path)) as conn:
                before = list(conn.iterdump()); original = migrations._apply_v6
                def fail(*args):
                    original(*args)
                    raise RuntimeError('fixture crash before commit')
                with patch.object(migrations, '_apply_v6', side_effect=fail):
                    with self.assertRaises(RuntimeError): migrations.migrate(path)
                self.assertEqual(list(conn.iterdump()), before)
                migrations.migrate(path)
                migrations.validate_schema(conn)

    def test_queue_constraints_and_incomplete_schema_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / 'v5.db')
            with closing(self.fixture(path)) as conn:
                migrations.migrate(path)
                for sql in ('DELETE FROM queue_entries', "UPDATE queue_entries SET request_id='other'", "UPDATE queue_entries SET session_name='partial' WHERE request_id='0'", "UPDATE queue_entries SET session_name='s',policy_reference='p',policy_fingerprint='" + 'a'*64 + "' WHERE request_id='2'"):
                    with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError): conn.execute(sql)
                conn.execute('DROP TRIGGER unknown_resolution_valid')
                with self.assertRaises(ledger.SchemaError): ledger.check_ready(path)

    def test_missing_or_invalid_source_is_never_initialized_or_repaired(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = str(Path(tmp) / 'missing.db')
            self.assertTrue(migrations.preflight(missing)['errors'])
            with self.assertRaises(ValueError): migrations.migrate(missing)
            self.assertFalse(Path(missing).exists())
            with closing(self.fixture(missing)) as conn:
                conn.execute('DROP TRIGGER request_marker_immutable')
                conn.execute('DROP TRIGGER request_marker_valid')
                conn.execute('DROP TRIGGER request_terminal')
                conn.execute("UPDATE send_requests SET transmission_started_at_ms=NULL WHERE transmitted=1")
                before = list(conn.iterdump())
                self.assertTrue(migrations.preflight(missing)['errors'])
                with self.assertRaises(ValueError): migrations.migrate(missing)
                self.assertEqual(list(conn.iterdump()), before)
