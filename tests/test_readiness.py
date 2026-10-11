import hashlib
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import circuit_breaker as cb
import ledger_migrations as migrations
import readiness
import services


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name); self.base.chmod(0o700)
        self.db=self.base/'fixture.db'; migrations.initialize(self.db)
        cb.bind_session('111','fixture',db_path=str(self.db))
        self.policy=self.base/'policy.json'
        self.policy.write_text(json.dumps(dict(session='fixture',message='fixture',targets=[dict(conv_id='a',conv_short_id=1,conv_type=1)])))
        self.policy.chmod(0o600)
        (self.base/'sesion'/'ws-auth').mkdir(parents=True,mode=0o700)
        (self.base/'sesion').chmod(0o700)
        self.cookies=self.base/'sesion'/'fixture.json'; self.cookies.write_text('{"sessionid":"synthetic"}'); self.cookies.chmod(0o600)
        self.auth=self.base/'sesion'/'ws-auth'/'fixture.json'
        self.auth.write_text(json.dumps(dict(session='fixture',session_hash=hashlib.sha256(b'synthetic').hexdigest(),ttwid='1|fixture|123|abc',access_key='a'*32))); self.auth.chmod(0o600)

    def run_report(self,**kw): return readiness.report(str(self.base),str(self.db),str(self.policy),**kw)
    def snapshot(self):
        return {str(p.relative_to(self.base)):(p.read_bytes(),p.stat().st_mode,p.stat().st_mtime_ns) for p in self.base.rglob('*') if p.is_file()}

    def test_metadata_and_credentials_have_no_files_or_chmod_side_effects(self):
        before=self.snapshot()
        for check in (False,True):
            with patch('os.chmod',side_effect=AssertionError('chmod')), patch('os.makedirs',side_effect=AssertionError('mkdir')):
                result=self.run_report(check_credentials=check)
            self.assertEqual(result['state'],'UNVERIFIED',result)
            self.assertIn('QUIESCENT_V8_BOUND',[c['code'] for c in result['checks']])
            self.assertNotIn('QUIESCENT_V7_BOUND',[c['code'] for c in result['checks']])
            self.assertEqual(self.snapshot(),before)
        text=json.dumps(result); self.assertNotIn('synthetic',text); self.assertNotIn('a'*32,text)

    def test_metadata_does_not_open_credential_bodies(self):
        with patch('runtime_paths.read_private_json',side_effect=AssertionError('credential read')):
            self.assertEqual(self.run_report()['state'],'UNVERIFIED')

    def test_missing_db_does_not_create_it(self):
        self.db.unlink()
        self.assertEqual(self.run_report()['state'],'BLOCKED')
        self.assertFalse(self.db.exists())

    def test_nonempty_wal_is_blocked_without_mutation_or_checkpoint(self):
        conn=sqlite3.connect(self.db)
        try:
            conn.execute('PRAGMA journal_mode=WAL'); conn.execute('CREATE TABLE fixture_extra(x)'); conn.commit()
            before=self.snapshot()
            self.assertEqual(self.run_report()['state'],'BLOCKED')
            self.assertEqual(self.snapshot(),before)
        finally: conn.close()

    def test_schema_and_unbound_account_are_blocked(self):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('PRAGMA user_version=6'); conn.commit()
        self.assertEqual(self.run_report()['state'],'BLOCKED')
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute('PRAGMA user_version=7'); conn.commit()
        cfg=json.loads(self.policy.read_text()); cfg['session']='unbound'; self.policy.write_text(json.dumps(cfg))
        self.assertEqual(self.run_report()['state'],'BLOCKED')

    def test_pair_mismatch_and_missing_auth_are_blocked(self):
        data=json.loads(self.auth.read_text()); data['session_hash']='wrong'; self.auth.write_text(json.dumps(data))
        self.assertEqual(self.run_report(check_credentials=True)['state'],'BLOCKED')
        self.auth.unlink(); self.assertEqual(self.run_report()['state'],'BLOCKED')

    def test_open_breaker_and_dependency_version_are_blocked(self):
        cb.record_failure(cb.Failure('AUTH','identity','fixture'),db_path=str(self.db),session='fixture')
        self.assertEqual(self.run_report()['state'],'BLOCKED')
        with patch('importlib.metadata.version',return_value='99.0'):
            self.assertEqual(self.run_report()['state'],'BLOCKED')

    def test_conflicting_runtime_root_is_rejected(self):
        with patch.dict(os.environ,{'TIKTOK_RUNTIME_DIR':str(self.base.parent)}):
            self.assertEqual(self.run_report()['state'],'BLOCKED')

    def test_malformed_credential_is_not_read_by_metadata_mode(self):
        self.cookies.write_text('not JSON')
        self.assertEqual(self.run_report()['state'],'UNVERIFIED')
        self.assertEqual(self.run_report(check_credentials=True)['state'],'BLOCKED')

    def test_unresolved_unknown_blocks_readiness_and_circuit_reset(self):
        import ledger_requests as requests
        cfg=json.loads(self.policy.read_text())
        row,_=requests.create_request('111','a','fixture',{'target':cfg['targets'][0],'message':'fixture'},
            db_path=str(self.db),session_name='fixture',policy_reference=str(self.policy),policy_config=cfg)
        requests.start_transmission(row['request_id'],db_path=str(self.db),session_name='fixture',
            policy_reference=str(self.policy),policy_config=cfg,**requests.settings_from_config(cfg))
        current=requests.get_request(row['request_id'],db_path=str(self.db))
        requests.finish('111','a',current['date'],row['client_msg_id'],db_path=str(self.db),
            status='failed_unknown',reason='fixture',failure=cb.Failure('UNKNOWN','send','fixture'))
        for state in cb.inspect(db_path=str(self.db),uid='111',session='fixture'):
            if state['state']=='OPEN':
                import ledger
                with self.assertRaises(ledger.LedgerError):
                    cb.reset(state['scope_type'],state['scope_key'],state,'fixture explicit reset',db_path=str(self.db))
        self.assertEqual(self.run_report()['state'],'BLOCKED')
