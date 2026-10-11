"""V7 -> V8 on disposable WAL fixtures, including backup restore and rollback."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import ledger
import ledger_migrations as migrations
import test_worker_migrations as prior_migration


class SchedulingMigrationTests(unittest.TestCase):
    def fixture(self,path):
        conn=prior_migration.WorkerMigrationTests().fixture(path)
        conn.execute('BEGIN IMMEDIATE');migrations._apply_v7(conn,None);conn.commit()
        conn.execute("INSERT INTO worker_runs VALUES('old',?,'{}',1)",('a'*64,))
        conn.execute("INSERT INTO worker_run_requests VALUES('old',0,'0','{}')")
        conn.execute("INSERT INTO worker_events(run_id,event_type,at_ms,details_json) VALUES('old','APPROVED',1,'{}')")
        return conn

    def snapshot(self,conn):
        tables=[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='sqlite_sequence'")]
        return {name:conn.execute('SELECT * FROM '+name).fetchall() for name in tables if name!='schema_migrations'}

    def test_preflight_wal_backup_preserves_v7_and_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=str(Path(tmp)/'v7.db')
            with closing(self.fixture(db)) as conn:
                before=self.snapshot(conn);dump=list(conn.iterdump())
                report=migrations.preflight(db)
                self.assertEqual(report['version'],7);self.assertFalse(report['errors']);self.assertEqual(dump,list(conn.iterdump()))
                backup=migrations.migrate(db);migrations.validate_schema(conn)
                for table,rows in before.items():self.assertEqual(conn.execute('SELECT * FROM '+table).fetchall(),rows)
                self.assertIsNone(migrations.migrate(db))
                with closing(sqlite3.connect(backup)) as saved:
                    migrations.validate_schema(saved,expected=7);self.assertEqual(before,self.snapshot(saved))
                    with closing(sqlite3.connect(str(Path(tmp)/'restored.db'))) as restored:
                        saved.backup(restored);migrations.validate_schema(restored,expected=7)
                        self.assertEqual(before,self.snapshot(restored))

    def test_v8_failure_rolls_back_and_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=str(Path(tmp)/'v7.db')
            with closing(self.fixture(db)) as conn:
                before=list(conn.iterdump());apply=migrations._apply_v8
                def fail(*args):apply(*args);raise RuntimeError('fixture migration crash')
                with patch.object(migrations,'_apply_v8',side_effect=fail),self.assertRaises(RuntimeError):migrations.migrate(db)
                self.assertEqual(before,list(conn.iterdump()));self.assertEqual(conn.execute('PRAGMA user_version').fetchone()[0],7)
                migrations.migrate(db);migrations.validate_schema(conn)

    def test_append_only_events_transition_and_missing_trigger_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=str(Path(tmp)/'v8.db');migrations.initialize(db)
            with closing(sqlite3.connect(db,isolation_level=None)) as conn:
                conn.execute("INSERT INTO recurring_grants VALUES('g','s',?,'{}',1)",('a'*64,))
                conn.execute("INSERT INTO recurring_events(grant_id,version,event_type,at_ms,details_json) VALUES('g',1,'AUTHORIZED',1,'{}')")
                for sql in ("UPDATE recurring_grants SET schedule_id='new'","DELETE FROM recurring_events", "INSERT INTO recurring_events(grant_id,version,event_type,at_ms,details_json) VALUES('g',2,'ACTIVATED',0,'{}')"):
                    with self.assertRaises(sqlite3.IntegrityError):conn.execute(sql)
                conn.execute("INSERT INTO recurring_events(grant_id,version,event_type,at_ms,details_json) VALUES('g',2,'ACTIVATED',2,'{}')")
                conn.execute("INSERT INTO recurring_events(grant_id,version,event_type,at_ms,details_json) VALUES('g',3,'PAUSED',3,'{}')")
                with self.assertRaises(sqlite3.IntegrityError):conn.execute("INSERT INTO recurring_events(grant_id,version,event_type,at_ms,details_json) VALUES('g',4,'ACTIVATED',4,'{}')")
                conn.execute('DROP TRIGGER recurring_event_valid')
                with self.assertRaises(ledger.SchemaError):ledger.check_ready(db)

    def test_send_rejects_v7_without_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=str(Path(tmp)/'v7.db')
            with closing(self.fixture(db)) as conn:
                before=list(conn.iterdump())
                with self.assertRaises(ledger.SchemaError):ledger.check_ready(db)
                self.assertEqual(before,list(conn.iterdump()))
