from contextlib import closing
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import circuit_breaker as cb
from core import api
from core.self_identity import verify_authenticated_self
import identity_service as identity
import ledger
import ledger_migrations as migrations
import main
import readiness


def competing_bind(db, uid, versions, barrier, output):
    barrier.wait(timeout=10)
    try:
        cb.bind_session(uid,'fixture',db_path=db,expected_versions=versions,reason='fixture concurrent')
        output.put('bound')
    except ledger.LedgerError:
        output.put('held')


class IdentityBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name); self.base.chmod(0o700)
        self.db=self.base/'fixture.db'; migrations.initialize(self.db)
        (self.base/'sesion').mkdir(mode=0o700)
        self.cookies=self.base/'sesion'/'fixture.json'
        self.cookies.write_text('{"sessionid":"synthetic"}'); self.cookies.chmod(0o600)
        self.addCleanup(patch.stopall)
        patch.dict(os.environ,{'TIKTOK_RUNTIME_DIR':str(self.base)}).start()

    def verified_fixture(self):
        # Synthetic provider only. No real response contract is claimed by this test.
        with patch.object(api,'get_own_user_id',return_value='111') as call:
            result=identity.verify('fixture',db_path=str(self.db))
        call.assert_called_once_with(cookies={'sessionid':'synthetic'},use_cache=False)
        return result

    def count(self):
        with closing(readiness.open_quiescent(self.db)) as conn:
            return conn.execute('SELECT count(*) FROM breaker_events').fetchone()[0]

    def test_default_preview_never_reads_credentials_or_network(self):
        with patch('runtime_paths.read_private_json',side_effect=AssertionError('credentials')), patch.object(api,'get_own_user_id',side_effect=AssertionError('network')):
            result=identity.preview('fixture',db_path=str(self.db))
        self.assertFalse(result['verified']); self.assertEqual(self.count(),0)

    def test_generic_odin_id_or_guessed_authenticated_shape_is_rejected(self):
        for html in ('{"odinId":"111"}', '{"isLogin":true,"user":{"uid":"111"}}','no evidence'):
            with self.subTest(html=html), self.assertRaises(cb.ProtocolFailure): verify_authenticated_self(html)

    def test_fresh_shared_api_does_not_fall_back_to_cache(self):
        response=MagicMock(); response.__enter__.return_value.read.return_value=b'{"odinId":"111"}'
        with patch.object(api.urllib.request,'urlopen',return_value=response), patch('builtins.open',side_effect=AssertionError('cache')):
            with self.assertRaises(cb.ProtocolFailure): api.get_own_user_id({'sessionid':'synthetic'},use_cache=False)

    def test_synthetic_verified_binding_and_same_uid_are_idempotent(self):
        review=self.verified_fixture()
        self.assertNotIn('generation',review.public()); self.assertNotIn('synthetic',json.dumps(review.public()))
        identity.apply(review,'fixture owner reason',db_path=str(self.db))
        self.assertEqual(self.count(),1)
        identity.apply(self.verified_fixture(),'fixture repeated verification',db_path=str(self.db))
        self.assertEqual(self.count(),1)

    def test_raw_dict_uid_is_not_an_accepted_verified_result(self):
        with self.assertRaises(ValueError): identity.apply({'uid':'111','verified':True},'fixture',db_path=str(self.db))
        self.assertEqual(self.count(),0)

    def test_changed_credential_generation_fails_without_binding(self):
        review=self.verified_fixture(); self.cookies.write_text('{"sessionid":"changed"}')
        with self.assertRaises(ValueError): identity.apply(review,'fixture',db_path=str(self.db))
        self.assertEqual(self.count(),0)

    def test_session_and_account_aba_invalidate_confirmation(self):
        for kind in ('session','account'):
            review=self.verified_fixture()
            cb.record_failure(cb.Failure('AUTH','identity','fixture'),db_path=str(self.db),
                              session='fixture' if kind=='session' else None,uid='111' if kind=='account' else None)
            current=cb.inspect(db_path=str(self.db),session='fixture' if kind=='session' else None,uid='111' if kind=='account' else None)[0]
            cb.reset(kind,'fixture' if kind=='session' else '111',current,'fixture explicit reset',db_path=str(self.db))
            with self.assertRaises(ledger.LedgerError): identity.apply(review,'fixture',db_path=str(self.db))

    def test_conflicting_concurrent_bind_and_event_failure_rollback(self):
        review=self.verified_fixture()
        cb.bind_session('222','fixture',db_path=str(self.db))
        with self.assertRaises(ledger.LedgerError): identity.apply(review,'fixture',db_path=str(self.db))
        with self.assertRaises(ledger.LedgerError): cb.bind_session('111','fixture',db_path=str(self.db))
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("CREATE TRIGGER fixture_abort BEFORE INSERT ON breaker_events BEGIN SELECT RAISE(ABORT,'fixture'); END")
            conn.commit()
        with self.assertRaises(sqlite3.Error): cb.bind_session('333','other',db_path=str(self.db))
        with closing(readiness.open_quiescent(self.db)) as conn:
            self.assertFalse(conn.execute("SELECT 1 FROM breaker_state WHERE scope_key='other'").fetchone())

    def test_missing_or_old_db_stops_before_credentials_and_transport(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('PRAGMA user_version=6'); conn.commit()
        with patch('runtime_paths.read_private_json',side_effect=AssertionError('credentials')):
            with self.assertRaises(ValueError): identity.verify('fixture',db_path=str(self.db))

    def test_live_protocol_failure_does_not_bind_and_preserves_failure_history(self):
        with patch.object(api,'get_own_user_id',side_effect=cb.ProtocolFailure('fixture')):
            with self.assertRaises(cb.ProtocolFailure): identity.verify('fixture',db_path=str(self.db))
        self.assertEqual(cb.inspect(db_path=str(self.db),session='fixture')[0]['state'],'OPEN')
        with closing(readiness.open_quiescent(self.db)) as conn:
            self.assertIsNone(conn.execute("SELECT canonical_uid FROM breaker_state WHERE scope_key='fixture'").fetchone()[0])

    def test_cli_apply_requires_live_and_interactive_confirmation(self):
        from contextlib import redirect_stdout
        import io
        with patch('sys.argv',['main.py','identity-verify','--db',str(self.db),'--session','fixture','--apply']), redirect_stdout(io.StringIO()):
            self.assertEqual(main.main(),2)
        review=self.verified_fixture()
        with patch('services.identity_verify',return_value=review),patch('sys.stdin.isatty',return_value=False),patch('sys.argv',['main.py','identity-verify','--db',str(self.db),'--session','fixture','--live','--apply']),redirect_stdout(io.StringIO()):
            self.assertEqual(main.main(),2)
        self.assertEqual(self.count(),0)

    def test_two_processes_cannot_apply_same_stale_identity_preview(self):
        versions=dict(uid=None,session_version=0,account_version=0,verified_account_version=0)
        ctx=multiprocessing.get_context('spawn'); barrier=ctx.Barrier(2); output=ctx.Queue()
        processes=[ctx.Process(target=competing_bind,args=(str(self.db),uid,versions,barrier,output)) for uid in ('111','222')]
        try:
            for process in processes: process.start()
            for process in processes:
                process.join(15); self.assertEqual(process.exitcode,0)
            self.assertEqual(sorted([output.get(timeout=2),output.get(timeout=2)]),['bound','held'])
            self.assertEqual(self.count(),1)
        finally:
            for process in processes:
                if process.is_alive(): process.terminate(); process.join()
            output.close(); output.join_thread()
