"""All inputs are disposable fixtures; operational output never captures raw logs."""
from contextlib import closing
import json
import os
import signal
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import ledger_migrations as migrations
import operations

ROOT = Path(__file__).resolve().parents[1]
HAS_NO_CKPT = hasattr(sqlite3.Connection, 'setconfig') and hasattr(sqlite3, 'SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE')


class OperationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.db = self.base/'fixture.db'
        migrations.initialize(self.db)
        # DELETE-journal fixtures exercise native backup on Python 3.10. WAL
        # acceptance additionally requires the actual no-checkpoint capability.
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('PRAGMA journal_mode=DELETE')

    def test_metadata_nested_sentinels_and_nonfinite_values(self):
        secret = 'SENTINEL message UID cookie token https://private.invalid/?secret=x'
        for key in ('state','reason','usage','policy','worker','requests','retry_at_ms','consent','results'):
            with self.subTest(key=key):
                text = json.dumps(operations.metadata({key: secret, 'nested': {'cookie':secret}}))
                self.assertNotIn('SENTINEL', text)
                self.assertLess(len(text), 2048)
        self.assertNotIn('requests', operations.metadata({'requests':True}))
        self.assertNotIn('retry_at_ms', operations.metadata({'retry_at_ms':2**1000}))
        self.assertEqual(operations.metadata({'worker':{'state':'COMPLETE','uid':secret}})['state'],'COMPLETE')

    def test_sink_mutes_python_native_and_libraries_with_bounded_metadata(self):
        with tempfile.TemporaryFile() as output:
            def invoke():
                print('COOKIE_MESSAGE_SENTINEL'*10000)
                sys.stderr.write('UID_SENTINEL')
                os.write(1, b'NATIVE_SECRET_SENTINEL')
                os.write(2, b'URL_SENTINEL')
                operations.note({'state':'COMPLETE','usage':{'daily_used':1}, 'policy':{'message':'SENTINEL'}})
                return 0
            self.assertEqual(operations.cli_entry(invoke, output_fd=output.fileno()),0)
            output.seek(0); data=output.read()
        self.assertNotIn(b'SENTINEL',data)
        self.assertLess(len(data),2048)
        self.assertEqual(json.loads(data)['daily_used'],1)

    def test_sink_exception_parse_exit_and_unavailable_fd(self):
        for exception in (ValueError('SESSION_TOKEN_SENTINEL'), SystemExit('MESSAGE_SENTINEL'), KeyboardInterrupt()):
            with self.subTest(exception=type(exception).__name__), tempfile.TemporaryFile() as output:
                def fail(): raise exception
                self.assertEqual(operations.cli_entry(fail,output_fd=output.fileno()),3)
                output.seek(0); self.assertNotIn(b'SENTINEL',output.read())
        invoked=[]
        with patch.object(os,'dup',side_effect=OSError('SENTINEL')):
            self.assertEqual(operations.cli_entry(lambda:invoked.append(1)),3)
        self.assertEqual(invoked,[])

    def test_bootstrap_parser_errors_do_not_leak_even_without_modules(self):
        for script in ('main.py','operational_entry.py'):
            result=subprocess.run([sys.executable,'-B',str(ROOT/script),'schedule-tick','--operational-output',
                                   '--UNKNOWN_UID_TOKEN_SENTINEL'],capture_output=True)
            self.assertNotIn(b'SENTINEL',result.stdout+result.stderr)
            self.assertEqual(result.stderr,b'')
            self.assertIn(result.returncode,(2,3))
        stage=self.base/'bootstrap';stage.mkdir()
        (stage/'operational_entry.py').write_bytes((ROOT/'operational_entry.py').read_bytes())
        result=subprocess.run([sys.executable,'-B',str(stage/'operational_entry.py'),
                               'operational-status','--operational-output'],cwd=stage,capture_output=True,
                              env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'})
        self.assertEqual(result.returncode,3)
        self.assertEqual(result.stdout+result.stderr,b'')

    def test_readonly_health_absent_wrong_and_nonquiescent(self):
        missing=self.base/'missing.db'
        self.assertEqual(operations.status('fixture',db_path=missing)['state'],'UNKNOWN')
        self.assertFalse(missing.exists())
        before=self.db.read_bytes()
        self.assertEqual(operations.status('fixture',db_path=self.db)['state'],'UNKNOWN')
        self.assertEqual(before,self.db.read_bytes())
        sidecar=Path(str(self.db)+'-wal');sidecar.write_bytes(b'nonquiescent');os.chmod(sidecar,0o600)
        result=operations.status('fixture',db_path=self.db)
        self.assertEqual(result['reason'],'DATABASE_NOT_QUIESCENT')
        self.assertEqual(sidecar.read_bytes(),b'nonquiescent')

    def test_valid_grant_health_remains_blocked_with_no_credentials_or_mutation(self):
        import circuit_breaker as cb
        import ledger
        import ledger_requests as requests
        import scheduling
        from datetime import datetime
        policy=self.base/'policy.json'
        cfg=dict(session='fixture',message='SECRET_SENTINEL',targets=[dict(conv_id='a',conv_short_id=1,conv_type=1)])
        policy.write_text(json.dumps(cfg),encoding='utf-8');os.chmod(policy,0o600)
        clock=int(datetime(2026,10,11,8,tzinfo=ledger.TZ_HO_CHI_MINH).timestamp()*1000)
        with patch.object(requests,'utc_now_ms',return_value=clock),patch.object(cb,'now_ms',return_value=clock):
            cb.bind_session('111','fixture',db_path=self.db)
            review=scheduling.preview(policy,'fixture',db_path=self.db)
            gid=scheduling.authorize(review,'fixture',db_path=self.db)
            before={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in self.base.iterdir() if p.is_file()}
            result=operations.status(gid,db_path=self.db)
            self.assertEqual(result['state'],'BLOCKED');self.assertEqual(result['requests'],0)
            self.assertNotIn('SENTINEL',json.dumps(result))
            after={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in self.base.iterdir() if p.is_file()}
            self.assertEqual(before,after)

    def test_backup_process_collision_does_not_overwrite_or_change_history(self):
        import multiprocessing
        ctx=multiprocessing.get_context('spawn');out=ctx.Queue();barrier=ctx.Barrier(2)
        destination=str(self.base/'race.db');before=self.db.read_bytes()
        children=[ctx.Process(target=competing_backup,args=(str(self.db),destination,barrier,out)) for _ in range(2)]
        for child in children:child.start()
        for child in children:child.join(15);self.assertFalse(child.is_alive());self.assertEqual(child.exitcode,0)
        results=[out.get(timeout=3) for _ in children]
        self.assertEqual(results.count('BACKUP_COMPLETE'),1)
        self.assertEqual(before,self.db.read_bytes())
        with closing(sqlite3.connect(destination)) as conn:migrations.validate_schema(conn)
        out.close();out.join_thread()

    def test_backup_validates_preserves_all_tables_and_no_overwrite(self):
        out=self.base/'backup.db';before=self.db.read_bytes()
        self.assertEqual(operations.backup(self.db,out)['state'],'BACKUP_COMPLETE')
        self.assertEqual(before,self.db.read_bytes())
        with closing(sqlite3.connect(self.db)) as src,closing(sqlite3.connect(out)) as dest:
            self.assertEqual(operations._history_counts(src),operations._history_counts(dest))
            migrations.validate_schema(dest)
        self.assertTrue(Path(str(out)+'.manifest.json').exists())
        with self.assertRaises(ValueError): operations.backup(self.db,out)
        self.assertFalse(Path(str(out)+'.incomplete').exists())

    def test_backup_missing_wrong_schema_alias_and_destination_collision(self):
        with self.assertRaises(ValueError):operations.backup(self.db,self.db)
        for destination in (Path(str(self.db)+'-wal'),self.base/'nonexisting'/'out.db'):
            with self.subTest(destination=destination),self.assertRaises((ValueError,OSError)):
                operations.backup(self.db,destination)
        wrong=self.base/'wrong.db';wrong.write_bytes(b'bad');os.chmod(wrong,0o600)
        with self.assertRaises(sqlite3.Error):operations.backup(wrong,self.base/'no.db')
        self.assertFalse((self.base/'no.db').exists())

    def test_backup_failure_and_deadline_leave_source_and_incomplete_evidence(self):
        before=self.db.read_bytes();out=self.base/'failed.db'
        with patch.object(os,'link',side_effect=OSError('fixture disk failure')):
            with self.assertRaises(OSError): operations.backup(self.db,out)
        self.assertFalse(out.exists())
        self.assertTrue(Path(str(out)+'.incomplete').exists())
        self.assertEqual(self.db.read_bytes(),before)
        with patch.object(operations.time,'monotonic',side_effect=[0,100]):
            with self.assertRaises(TimeoutError):operations.backup(self.db,self.base/'expired.db')
        self.assertFalse((self.base/'expired.db').exists())
        self.assertEqual(self.db.read_bytes(),before)

    def test_wal_without_no_checkpoint_capability_fails_before_open(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
        before=self.db.read_bytes()
        with patch.object(operations.sqlite3,'SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE',None,create=True):
            with self.assertRaisesRegex(ValueError,'NO_CKPT_ON_CLOSE'):
                operations.backup(self.db,self.base/'refused.db')
        self.assertEqual(before,self.db.read_bytes())
        self.assertFalse((self.base/'refused.db').exists())

    @unittest.skipUnless(HAS_NO_CKPT,'Actual WAL no-checkpoint backup requires Python sqlite3 setconfig capability')
    def test_actual_wal_commits_included_uncommitted_excluded_no_sidecar_changes(self):
        with closing(sqlite3.connect(self.db,isolation_level=None)) as live:
            live.execute('PRAGMA journal_mode=WAL');live.execute('PRAGMA wal_autocheckpoint=0')
            live.execute('CREATE TABLE fixture_history(value TEXT)')
            live.execute("INSERT INTO fixture_history VALUES('committed')")
            wal=Path(str(self.db)+'-wal');os.chmod(wal,0o600);os.chmod(Path(str(self.db)+'-shm'),0o600)
            live.execute('BEGIN IMMEDIATE');live.execute("INSERT INTO fixture_history VALUES('uncommitted')")
            with self.assertRaises(sqlite3.OperationalError):
                operations.backup(self.db,self.base/'busy.db',timeout=0.05)
            self.assertFalse((self.base/'busy.db').exists())
            live.rollback()
            before=wal.read_bytes()
            out=self.base/'wal-copy.db';operations.backup(self.db,out)
            self.assertEqual(before,wal.read_bytes())
            live.execute('BEGIN');live.execute("INSERT INTO fixture_history VALUES('uncommitted')");live.rollback()
            with closing(sqlite3.connect(out)) as dest:
                self.assertEqual(dest.execute('SELECT * FROM fixture_history').fetchall(),[('committed',)])

    @unittest.skipUnless(HAS_NO_CKPT,'Actual persistent WAL requires Python sqlite3 setconfig capability')
    def test_persistent_wal_backup_last_connection_close_never_checkpoints(self):
        with closing(sqlite3.connect(self.db,isolation_level=None)) as live:
            live.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE,True)
            live.execute('PRAGMA journal_mode=WAL');live.execute('PRAGMA wal_autocheckpoint=0')
            live.execute('CREATE TABLE fixture_history(value TEXT)')
            live.execute("INSERT INTO fixture_history VALUES('persistent committed')")
        wal=Path(str(self.db)+'-wal');shm=Path(str(self.db)+'-shm')
        os.chmod(wal,0o600);os.chmod(shm,0o600)
        before={p:p.read_bytes() for p in (self.db,wal,shm)}
        out=self.base/'persistent-copy.db';operations.backup(self.db,out)
        # SHM reader bookkeeping may change; source main/WAL must not checkpoint
        # or be deleted even when the backup owns the last source connections.
        self.assertTrue(shm.exists())
        self.assertEqual(self.db.read_bytes(),before[self.db]);self.assertEqual(wal.read_bytes(),before[wal])
        with closing(sqlite3.connect(out)) as dest:
            self.assertEqual(dest.execute('SELECT * FROM fixture_history').fetchall(),[('persistent committed',)])

    def test_backup_cli_metadata_and_status_never_create_missing_db(self):
        result=subprocess.run([sys.executable,'-B',str(ROOT/'operational_entry.py'),'ledger-backup','--db',str(self.db),
                              '--destination',str(self.base/'cli.db'),'--operational-output'],capture_output=True)
        self.assertEqual(result.returncode,0,result.stdout)
        self.assertEqual(json.loads(result.stdout)['state'],'BACKUP_COMPLETE')
        self.assertEqual(result.stderr,b'')
        missing=self.base/'absent.db'
        result=subprocess.run([sys.executable,'-B',str(ROOT/'operational_entry.py'),'operational-status','--db',str(missing),
                              '--grant-id','UID_SENTINEL','--operational-output'],capture_output=True)
        self.assertEqual(result.returncode,2,result.stdout)
        self.assertNotIn(b'SENTINEL',result.stdout+result.stderr)
        self.assertFalse(missing.exists())

    def test_cli_sigterm_before_after_marker_and_timeout_never_retransmit(self):
        import circuit_breaker as cb
        import ledger
        import ledger_requests as requests
        import main
        import oneshot
        import scheduling
        import time
        from test_streak import MockWebSocket, _build_synthetic_echo_frame
        for stage in ('before','after','timeout'):
            with self.subTest(stage=stage),tempfile.TemporaryDirectory() as directory:
                db=Path(directory)/'fixture.db';migrations.initialize(db)
                policy=Path(directory)/'policy.json'
                cfg=dict(session='fixture',message='MESSAGE_SENTINEL',targets=[dict(conv_id='a',conv_short_id=1,conv_type=1)],min_send_interval_seconds=0)
                policy.write_text(json.dumps(cfg),encoding='utf-8');os.chmod(policy,0o600)
                clock=int(__import__('datetime').datetime(2026,10,11,8,tzinfo=ledger.TZ_HO_CHI_MINH).timestamp()*1000)
                with patch.object(requests,'utc_now_ms',return_value=clock),patch.object(cb,'now_ms',return_value=clock):
                    cb.bind_session('111','fixture',db_path=db)
                    review=scheduling.preview(policy,'fixture',db_path=db)
                    gid=scheduling.authorize(review,'fixture',db_path=db)
                    scheduling.change(gid,scheduling.status(gid,db_path=db),'ACTIVATED','fixture',db_path=db)
                    ws=MockWebSocket()
                    def rows():
                        with closing(sqlite3.connect(db)) as conn:
                            rid=conn.execute('SELECT request_id FROM send_requests').fetchone()[0]
                        return requests.get_request(rid,db_path=db)
                    def opened(*_):
                        row=rows()
                        ws.incoming_frames=[b'hi']+([] if stage=='timeout' else [_build_synthetic_echo_frame('a','111',row['client_msg_id'],'MESSAGE_SENTINEL')])
                        return ws
                    def sent(_):
                        row=rows()
                        if (stage=='before' and not row['transmitted']) or (stage!='before' and row['transmitted']):
                            # Windows signal.raise_signal simulation of installed CLI
                            # handler; not an external POSIX/systemd signal assertion.
                            signal.raise_signal(signal.SIGTERM)
                    ws.on_send=sent
                    argv=['main.py','schedule-tick','--db',str(db),'--grant-id',gid,
                          '--grant-fingerprint',review['fingerprint'],'--execute','--yes','--operational-output']
                    old=signal.getsignal(signal.SIGTERM)
                    started=time.monotonic()
                    with patch.object(sys,'argv',argv),patch.object(oneshot,'load_session',return_value={'sessionid':'TOKEN_SENTINEL'}),\
                         patch.object(oneshot,'get_own_user_id',return_value='111'),patch.object(oneshot,'load_ws_auth',return_value={'device_id':'0'}),\
                         patch.object(oneshot,'validate_against_server_inbox'),patch.object(oneshot,'_prepare_ws',return_value=({},'wss://fixture.invalid')),\
                         patch.object(oneshot,'_open_ws',side_effect=opened),tempfile.TemporaryFile() as output:
                        operations.cli_entry(main.main,output_fd=output.fileno())
                        output.seek(0);self.assertNotIn(b'SENTINEL',output.read())
                    self.assertLess(time.monotonic()-started,90)
                    self.assertEqual(signal.getsignal(signal.SIGTERM),old)
                    row=rows()
                    self.assertEqual(row['transmitted'],0 if stage=='before' else 1)
                    if stage=='after':self.assertEqual(row['status'],'confirmed')
                    if stage=='timeout':self.assertEqual(row['status'],'failed_unknown')
                    packets=len(ws.sent_packets)
                    # Read-only/replay does not create another request/marker.
                    if stage=='timeout':
                        with self.assertRaises(scheduling.ScheduleHeld):scheduling.enqueue(gid,review['fingerprint'],db_path=db)
                    else:
                        scheduling.enqueue(gid,review['fingerprint'],db_path=db)
                    self.assertEqual(len(ws.sent_packets),packets)

    def test_forced_process_exit_after_marker_recovers_unknown(self):
        import multiprocessing
        import ledger
        import ledger_requests as requests
        from ledger_fixtures import fixture_create
        row,_=fixture_create('111','a','crash',{'message':'fixture'},db_path=self.db)
        ctx=multiprocessing.get_context('spawn')
        child=ctx.Process(target=crash_marker,args=(str(self.db),row['request_id']))
        child.start();child.join(15)
        self.assertFalse(child.is_alive());self.assertEqual(child.exitcode,9)
        with ledger.RunLock(str(self.db.parent/'run.lock')) as lock:
            requests.recover_pending(db_path=self.db,run_lock=lock)
        recovered=requests.get_request(row['request_id'],db_path=self.db)
        self.assertEqual(recovered['status'],'failed_unknown');self.assertEqual(recovered['transmitted'],1)


def crash_marker(db,rid):
    from ledger_fixtures import fixture_start
    fixture_start(rid,db_path=db)
    os._exit(9)


def competing_backup(db,destination,barrier,out):
    barrier.wait(timeout=10)
    try:out.put(operations.backup(db,destination)['state'])
    except Exception:out.put('REFUSED')
