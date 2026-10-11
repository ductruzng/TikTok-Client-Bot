"""Worker contracts on disposable V7 fixtures; no real credentials or transport."""
import asyncio
from contextlib import closing, redirect_stdout
from copy import deepcopy
import io
import json
import multiprocessing
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

import circuit_breaker as cb
import ledger
import ledger_migrations as migrations
import ledger_requests as requests
import main
import oneshot
import queue_service as queue
import services
import worker


def claim_worker(path, reference, cfg, rid, run_id, fingerprint, barrier, output):
    barrier.wait(timeout=10)
    try:
        ok = requests.start_transmission(rid, db_path=path, session_name=cfg['session'],
            policy_reference=reference, policy_config=cfg, worker_context=worker.RunContext(run_id, fingerprint),
            **requests.settings_from_config(cfg))
        if ok:
            row = requests.get_request(rid, db_path=path)
            requests.finish(row['canonical_uid'], row['conv_id'], row['date'], row['client_msg_id'],
                db_path=path, status='confirmed', reason='fixture', server_id='123', result_date=row['date'])
        output.put('ok' if ok else 'held')
    except ledger.LedgerError:
        output.put('held')


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / 'worker.db')
        self.policy = str(Path(self.tmp.name) / 'policy.json')
        migrations.initialize(self.db)
        self.cfg = dict(session='fixture', message='exact text', allow_repeat_same_day=True,
            max_sends_per_conversation_per_day=10, max_sends_per_account_per_day=20,
            min_send_interval_seconds=0, max_sends_per_window=20,
            targets=[dict(conv_id=c, conv_short_id=1, conv_type=1) for c in ('a', 'b', 'c')])
        Path(self.policy).write_text(json.dumps(self.cfg), encoding='utf-8')
        cb.bind_session('111', 'fixture', db_path=self.db)
        self.clock = int(time.time()*1000)
        self.addCleanup(patch.stopall)
        patch.object(requests, 'utc_now_ms', side_effect=lambda: self.clock).start()
        patch.object(cb, 'now_ms', side_effect=lambda: self.clock).start()

    def create(self, cid='a', key=None):
        t = next(t for t in self.cfg['targets'] if t['conv_id'] == cid)
        return requests.create_request('111', cid, key or cid, {'target': t, 'message': self.cfg.get('message', '')},
            db_path=self.db, rotation_config=self.cfg if 'rotation' in self.cfg else None,
            session_name='fixture', policy_reference=self.policy, policy_config=self.cfg)[0]

    def grant(self, rows, **bounds):
        bounds.setdefault('expires_at_ms', self.clock+86400000)
        review = worker.preview('fixture', [r['request_id'] for r in rows], db_path=self.db, **bounds)
        run_id = worker.authorize(review, 'fixture owner approval', db_path=self.db)
        return run_id, review['fingerprint']

    def start(self, row, context=None):
        return requests.start_transmission(row['request_id'], db_path=self.db, session_name='fixture',
            policy_reference=self.policy, policy_config=self.cfg, worker_context=context, rotation_config=self.cfg,
            **requests.settings_from_config(self.cfg))

    def finish(self, row, status='confirmed'):
        current = requests.get_request(row['request_id'], db_path=self.db)
        requests.finish('111', row['conv_id'], current['date'], row['client_msg_id'], db_path=self.db,
            status=status, reason='fixture', server_id='123' if status == 'confirmed' else None,
            result_date=current['date'], failure=cb.Failure('UNKNOWN', 'send', 'fixture') if status == 'failed_unknown' else None)

    async def send(self, reference, *, request_id, _worker_context, **kwargs):
        row = requests.get_request(request_id, db_path=self.db)
        self.start(row, _worker_context)
        self.finish(row)
        return {'results': [dict(request_id=request_id, status='confirmed')]}

    async def execute(self, run_id, fp, **kwargs):
        with patch.object(oneshot, 'run_oneshot_send', side_effect=self.send):
            return await worker.run(run_id, fp, db_path=self.db, **kwargs)

    def sql(self, query, params=()):
        with closing(sqlite3.connect(self.db)) as conn:
            return conn.execute(query, params).fetchall()

    def test_preview_is_readonly_shows_exact_content_and_validates_bounds(self):
        row = self.create()
        before = self.sql('SELECT * FROM worker_runs')
        result = worker.preview('fixture', [row['request_id']], db_path=self.db)
        self.assertEqual(result['messages'][0]['payload']['message'], 'exact text')
        self.assertEqual(self.sql('SELECT * FROM worker_runs'), before)
        for bounds in ({'max_jobs': True}, {'max_jobs': 0}, {'max_jobs': 101}, {'max_wait': -1}, {'max_wait': True}, {'max_wait': 86401}, {'expires_at_ms': self.clock}):
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                worker.preview('fixture', [row['request_id']], db_path=self.db, **bounds)
        for ids in ([], [row['request_id']]*2):
            with self.assertRaises(ValueError): worker.preview('fixture', ids, db_path=self.db)

    def test_stale_consent_policy_binding_or_cancel_is_rejected(self):
        row = self.create()
        review = worker.preview('fixture', [row['request_id']], db_path=self.db)
        requests.cancel_request(row['request_id'], 'fixture cancellation', db_path=self.db)
        with self.assertRaises(ledger.LedgerError): worker.authorize(review, 'fixture', db_path=self.db)
        self.assertFalse(self.sql('SELECT * FROM worker_runs'))

    def test_consent_atomic_event_failure_rolls_back_everything(self):
        row = self.create()
        review = worker.preview('fixture', [row['request_id']], db_path=self.db)
        with patch.object(worker, '_event', side_effect=RuntimeError('fixture rollback')):
            with self.assertRaises(RuntimeError): worker.authorize(review, 'fixture', db_path=self.db)
        self.assertFalse(self.sql('SELECT * FROM worker_runs'))
        self.assertFalse(self.sql('SELECT * FROM worker_run_requests'))

    async def test_default_budget_is_one_and_manifest_does_not_pick_up_new_requests(self):
        a, b = self.create(), self.create('b')
        rid, fp = self.grant([a, b])
        new = self.create('c')
        result = await self.execute(rid, fp)
        self.assertEqual(result['state'], 'COMPLETE')
        self.assertEqual(worker.status(rid, db_path=self.db)['transmitted'], 1)
        self.assertEqual(requests.get_request(b['request_id'], db_path=self.db)['status'], 'queued')
        self.assertEqual(requests.get_request(new['request_id'], db_path=self.db)['status'], 'queued')
        self.assertEqual((await self.execute(rid, fp))['results'], [])

    async def test_wait_releases_runlock_sql_writer_and_rechecks_admission(self):
        a, b = self.create(), self.create('b')
        self.cfg['min_send_interval_seconds'] = 60
        Path(self.policy).write_text(json.dumps(self.cfg), encoding='utf-8')
        for row in (a, b):
            review = queue.preview_bind(row['request_id'], self.cfg, self.policy, db_path=self.db)
            queue.bind_request(row['request_id'], self.cfg, self.policy, review, 'fixture limit', db_path=self.db)
        rid, fp = self.grant([a, b], max_jobs=2)
        waits = []
        async def wait(stop, seconds):
            waits.append(seconds)
            with ledger.RunLock(str(Path(self.db).parent/'run.lock')):
                with requests.transaction(self.db) as conn:
                    self.assertEqual(conn.execute("SELECT count(*) FROM send_requests WHERE status='pending'").fetchone()[0], 0)
            self.clock += int(seconds*1000)
        result = await self.execute(rid, fp, wait=wait)
        self.assertEqual(result['state'], 'COMPLETE')
        self.assertEqual(waits, [60])
        self.assertEqual(worker.status(rid, db_path=self.db)['transmitted'], 2)

    async def test_wait_limit_persists_original_deadline_across_clean_restart(self):
        a, b = self.create(), self.create('b')
        self.start(a); self.finish(a)
        self.cfg['min_send_interval_seconds'] = 60
        Path(self.policy).write_text(json.dumps(self.cfg), encoding='utf-8')
        queue.bind_request(b['request_id'], self.cfg, self.policy,
            queue.preview_bind(b['request_id'], self.cfg, self.policy, db_path=self.db), 'fixture cooldown', db_path=self.db)
        rid, fp = self.grant([b], max_wait=30)
        stop = asyncio.Event()
        async def interrupted(stop, seconds):
            self.clock += 10000
            stop.set()
        first = await self.execute(rid, fp, stop_event=stop, wait=interrupted)
        self.assertEqual(first['state'], 'STOPPED')
        async def resume_wait(stop, seconds):
            self.assertLessEqual(seconds, 20)
            self.clock += int(seconds*1000)
        second = await self.execute(rid, fp, wait=resume_wait)
        self.assertEqual(second['state'], 'WAIT_LIMIT')
        self.assertEqual(len(self.sql("SELECT * FROM worker_events WHERE event_type='RUN_STARTED'")), 1)
        self.assertEqual(requests.get_request(b['request_id'], db_path=self.db)['transmitted'], 0)

    async def test_zero_wait_returns_without_sleep_or_transmission(self):
        a, b = self.create(), self.create('b')
        self.start(a); self.finish(a)
        self.cfg['max_sends_per_account_per_day'] = 1
        Path(self.policy).write_text(json.dumps(self.cfg), encoding='utf-8')
        queue.bind_request(b['request_id'], self.cfg, self.policy,
            queue.preview_bind(b['request_id'], self.cfg, self.policy, db_path=self.db), 'fixture quota', db_path=self.db)
        rid, fp = self.grant([b], max_wait=0)
        wait = AsyncMock()
        self.assertEqual((await self.execute(rid, fp, wait=wait))['state'], 'WAIT_LIMIT')
        wait.assert_not_called()

    async def test_default_midnight_expiry_does_not_renew_on_next_day(self):
        row = self.create()
        review = worker.preview('fixture', [row['request_id']], db_path=self.db)
        rid = worker.authorize(review, 'fixture', db_path=self.db)
        self.clock = review['consent']['expires_at_ms']
        result = await self.execute(rid, review['fingerprint'])
        self.assertEqual(result['state'], 'WAIT_LIMIT')
        self.assertEqual(requests.get_request(row['request_id'], db_path=self.db)['transmitted'], 0)

    async def test_manual_transmission_counts_budget_before_worker_start(self):
        a, b = self.create(), self.create('b')
        rid, fp = self.grant([a, b])
        self.start(a); self.finish(a)
        result = await self.execute(rid, fp)
        self.assertEqual(result['state'], 'COMPLETE')
        self.assertEqual(requests.get_request(b['request_id'], db_path=self.db)['transmitted'], 0)

    async def test_unknown_counts_budget_and_prevents_auto_resume_after_reset(self):
        a, b = self.create(), self.create('b')
        rid, fp = self.grant([a, b], max_jobs=2)
        self.start(a); self.finish(a, 'failed_unknown')
        result = await self.execute(rid, fp)
        self.assertEqual(result['state'], 'NEEDS_OWNER_REVIEW')
        self.assertEqual(worker.status(rid, db_path=self.db)['transmitted'], 1)
        self.assertEqual(requests.get_request(b['request_id'], db_path=self.db)['transmitted'], 0)

    async def test_both_account_and_session_open_reset_aba_invalidate_consent(self):
        for kind, key in (('account', '111'), ('session', 'fixture')):
            with self.subTest(kind=kind):
                row = self.create(key=kind)
                rid, fp = self.grant([row])
                cb.record_failure(cb.Failure('RATE_LIMIT', 'identity', 'http429'), db_path=self.db,
                                  uid='111' if kind == 'account' else None, session='fixture')
                current = cb.inspect(db_path=self.db, uid='111' if kind == 'account' else None,
                                     session='fixture' if kind == 'session' else None)[0]
                cb.reset(kind, key, current, 'fixture explicit owner reset', db_path=self.db)
                result = await self.execute(rid, fp)
                self.assertEqual(result['state'], 'NEEDS_OWNER_REVIEW')
                self.assertEqual(result['reason'], 'CIRCUIT_CHANGED')

    async def test_scope_route_aba_holds_that_conversation_and_continues_independent(self):
        a, b = self.create(), self.create('b')
        rid, fp = self.grant([a, b])
        review = queue.preview_bind(a['request_id'], self.cfg, self.policy, db_path=self.db)
        queue.bind_request(a['request_id'], self.cfg, self.policy, review, 'fixture identical rebind changes audit version', db_path=self.db)
        result = await self.execute(rid, fp)
        self.assertEqual(result['state'], 'COMPLETE')
        self.assertEqual(requests.get_request(a['request_id'], db_path=self.db)['transmitted'], 0)
        self.assertEqual(requests.get_request(b['request_id'], db_path=self.db)['transmitted'], 1)

    async def test_fifo_cannot_overtake_an_older_request_outside_manifest(self):
        old, new, b = self.create(key='old'), self.create(key='new'), self.create('b')
        rid, fp = self.grant([new, b])
        result = await self.execute(rid, fp)
        self.assertEqual(result['state'], 'COMPLETE')
        self.assertEqual(requests.get_request(old['request_id'], db_path=self.db)['transmitted'], 0)
        self.assertEqual(requests.get_request(new['request_id'], db_path=self.db)['transmitted'], 0)
        self.assertEqual(requests.get_request(b['request_id'], db_path=self.db)['transmitted'], 1)

    async def test_shutdown_during_echo_drains_result_and_never_retransmits(self):
        row = self.create()
        rid, fp = self.grant([row])
        stop = asyncio.Event()
        async def drain(reference, *, request_id, _worker_context, **kwargs):
            self.start(row, _worker_context)
            stop.set()
            await asyncio.sleep(0)
            self.finish(row)
            return {'results': [dict(request_id=request_id, status='confirmed')]}
        with patch.object(oneshot, 'run_oneshot_send', side_effect=drain):
            result = await worker.run(rid, fp, db_path=self.db, stop_event=stop)
        self.assertEqual(result['state'], 'STOPPED')
        self.assertEqual(requests.get_request(row['request_id'], db_path=self.db)['status'], 'confirmed')
        await self.execute(rid, fp)
        self.assertEqual(worker.status(rid, db_path=self.db)['transmitted'], 1)

    async def test_crash_pending_recovers_unknown_and_aborts_without_send(self):
        row = self.create()
        rid, fp = self.grant([row])
        context = worker.RunContext(rid, fp)
        worker._start(context, self.db)
        self.start(row, context)
        result = await self.execute(rid, fp)
        self.assertEqual(result['state'], 'NEEDS_OWNER_REVIEW')
        self.assertEqual(requests.get_request(row['request_id'], db_path=self.db)['status'], 'failed_unknown')
        self.assertEqual(worker.status(rid, db_path=self.db)['transmitted'], 1)

    async def test_revocation_while_waiting_is_final_and_prevents_send(self):
        a, b = self.create(), self.create('b')
        self.start(a); self.finish(a)
        self.cfg['min_send_interval_seconds'] = 60
        Path(self.policy).write_text(json.dumps(self.cfg), encoding='utf-8')
        queue.bind_request(b['request_id'], self.cfg, self.policy,
            queue.preview_bind(b['request_id'], self.cfg, self.policy, db_path=self.db), 'fixture', db_path=self.db)
        rid, fp = self.grant([b])
        async def revoke(stop, seconds):
            current = worker.status(rid, db_path=self.db)
            worker.revoke(rid, current, 'fixture revoke during released wait', db_path=self.db)
            self.clock += int(seconds*1000)
        result = await self.execute(rid, fp, wait=revoke)
        self.assertEqual(worker.status(rid, db_path=self.db)['state'], 'REVOKED')
        self.assertEqual(requests.get_request(b['request_id'], db_path=self.db)['transmitted'], 0)

    def test_atomic_claim_rechecks_revocation_budget_membership_and_stop(self):
        a, b = self.create(), self.create('b')
        rid, fp = self.grant([a])
        context = worker.RunContext(rid, fp)
        worker._start(context, self.db)
        with self.assertRaisesRegex(worker.WorkerHeld, 'SCOPE_CHANGED'): self.start(b, context)
        stop = asyncio.Event(); stop.set()
        with self.assertRaisesRegex(worker.WorkerHeld, 'WORKER_STOPPED'):
            self.start(a, worker.RunContext(rid, fp, stop_event=stop))
        current = worker.status(rid, db_path=self.db)
        worker.revoke(rid, current, 'fixture', db_path=self.db)
        with self.assertRaises(ledger.LedgerError): self.start(a, context)
        self.assertFalse(self.sql("SELECT * FROM send_requests WHERE transmitted=1"))

    async def test_wrong_hash_or_missing_schema_does_not_write_or_load_credentials(self):
        row = self.create(); rid, fp = self.grant([row])
        before = self.sql('SELECT * FROM worker_events')
        with self.assertRaises(worker.WorkerHeld): await worker.run(rid, '0'*64, db_path=self.db)
        self.assertEqual(self.sql('SELECT * FROM worker_events'), before)
        missing = str(Path(self.tmp.name)/'missing.db')
        with self.assertRaises(ledger.LedgerError): await worker.run(rid, fp, db_path=missing)
        self.assertFalse(Path(missing).exists())

    async def test_clock_rollback_and_future_jump_fail_closed(self):
        row = self.create(); rid, fp = self.grant([row])
        self.clock -= 1000
        result = await self.execute(rid, fp)
        self.assertEqual(result['reason'], 'CLOCK_SKEW')
        self.assertEqual(requests.get_request(row['request_id'], db_path=self.db)['transmitted'], 0)

    def test_two_processes_cannot_exceed_same_manifest_budget(self):
        a, b = self.create(), self.create('b')
        rid, fp = self.grant([a, b])
        worker._start(worker.RunContext(rid, fp), self.db)
        ctx = multiprocessing.get_context('spawn')
        barrier, output = ctx.Barrier(2), ctx.Queue()
        processes = [ctx.Process(target=claim_worker, args=(self.db, self.policy, self.cfg,
            row['request_id'], rid, fp, barrier, output)) for row in (a, b)]
        for p in processes: p.start()
        for p in processes:
            p.join(timeout=20)
            self.assertEqual(p.exitcode, 0)
        self.assertEqual(sorted([output.get(timeout=3), output.get(timeout=3)]), ['held', 'ok'])
        self.assertEqual(worker.status(rid, db_path=self.db)['transmitted'], 1)

    def test_cli_authorization_cannot_be_granted_noninteractively(self):
        row = self.create()
        args = ['main.py', 'worker-authorize', '--db', self.db, '--session', 'fixture', '--request-id', row['request_id'], '--apply']
        with patch('sys.argv', args), patch('sys.stdin.isatty', return_value=False), redirect_stdout(io.StringIO()):
            self.assertEqual(main.main(), 3)
        self.assertFalse(self.sql('SELECT * FROM worker_runs'))

    async def test_real_managed_transport_uses_worker_snapshot_and_correlated_echo(self):
        from test_streak import MockWebSocket, _build_synthetic_echo_frame
        row = self.create(); rid, fp = self.grant([row])
        echo = _build_synthetic_echo_frame('a', '111', row['client_msg_id'], 'exact text')
        ws = MockWebSocket([b'hi', echo])
        with patch.object(oneshot, 'load_session', return_value={'sessionid': 'synthetic'}), \
             patch.object(oneshot, 'get_own_user_id', return_value='111'), \
             patch.object(oneshot, 'load_ws_auth', return_value={'device_id': '0'}), \
             patch.object(oneshot, 'validate_against_server_inbox'), \
             patch.object(oneshot, '_prepare_ws', return_value=({}, 'wss://fixture.invalid')), \
             patch.object(oneshot, '_open_ws', AsyncMock(return_value=ws)):
            result = await services.worker_run(rid, fp, db_path=self.db)
        self.assertEqual(result['state'], 'COMPLETE')
        self.assertEqual(len(ws.sent_packets), 2)
        self.assertEqual(requests.get_request(row['request_id'], db_path=self.db)['status'], 'confirmed')

    def settings(self, **values):
        self.cfg.update(values)
        Path(self.policy).write_text(json.dumps(self.cfg), encoding='utf-8')
        for row in queue.list_queue(db_path=self.db):
            if row['status'] == 'queued':
                queue.bind_request(row['request_id'], self.cfg, self.policy,
                    queue.preview_bind(row['request_id'], self.cfg, self.policy, db_path=self.db), 'fixture reviewed Settings', db_path=self.db)

    async def test_daily_quota_wait_can_cross_midnight_only_with_explicit_valid_consent(self):
        local = requests.local_time(self.clock).replace(hour=23, minute=59, second=30, microsecond=0)
        self.clock = int(local.timestamp()*1000)
        a, b = self.create(), self.create('b')
        self.start(a); self.finish(a)
        self.settings(max_sends_per_account_per_day=1)
        rid, fp = self.grant([b], max_wait=60, expires_at_ms=self.clock+120000)
        waits = []
        async def wait(stop, seconds):
            waits.append(seconds)
            self.clock += int(seconds*1000)
        result = await self.execute(rid, fp, wait=wait)
        self.assertEqual(result['state'], 'COMPLETE')
        self.assertEqual(waits, [30])
        self.assertNotEqual(requests.get_request(a['request_id'], db_path=self.db)['date'],
                            requests.get_request(b['request_id'], db_path=self.db)['date'])

    async def test_sliding_window_wait_uses_latest_blocker_and_exact_boundary(self):
        a, b = self.create(), self.create('b')
        self.start(a); self.finish(a)
        self.settings(min_send_interval_seconds=10, max_sends_per_window=1, window_seconds=30)
        rid, fp = self.grant([b])
        waits = []
        async def wait(stop, seconds):
            waits.append(seconds)
            self.clock += int(seconds*1000)
        self.assertEqual((await self.execute(rid, fp, wait=wait))['state'], 'COMPLETE')
        self.assertEqual(waits, [30])

    async def test_policy_drift_and_cooldown_are_held_without_waiting(self):
        a, b = self.create(), self.create('b')
        self.start(a); self.finish(a)
        self.settings(min_send_interval_seconds=60)
        rid, fp = self.grant([b])
        self.cfg['message'] = 'changed after approval'
        Path(self.policy).write_text(json.dumps(self.cfg), encoding='utf-8')
        wait = AsyncMock()
        result = await self.execute(rid, fp, wait=wait)
        self.assertEqual(result['state'], 'HELD')
        wait.assert_not_called()
        self.assertEqual(requests.get_request(b['request_id'], db_path=self.db)['transmitted'], 0)

    async def test_open_circuit_with_rate_limit_never_waits_or_resumes(self):
        a, b = self.create(), self.create('b')
        self.start(a); self.finish(a)
        self.settings(min_send_interval_seconds=60)
        rid, fp = self.grant([b])
        cb.record_failure(cb.Failure('RATE_LIMIT', 'identity', 'http429'), db_path=self.db, uid='111')
        wait = AsyncMock()
        result = await self.execute(rid, fp, wait=wait)
        self.assertEqual(result['state'], 'NEEDS_OWNER_REVIEW')
        wait.assert_not_called()
        self.assertEqual(requests.get_request(b['request_id'], db_path=self.db)['transmitted'], 0)

    async def test_interrupted_wait_before_transmission_is_immediate_and_uncharged(self):
        a, b = self.create(), self.create('b')
        self.start(a); self.finish(a)
        self.settings(min_send_interval_seconds=60)
        rid, fp = self.grant([b])
        stop = asyncio.Event()
        async def stop_wait(event, seconds):
            event.set()
        result = await self.execute(rid, fp, stop_event=stop, wait=stop_wait)
        self.assertEqual(result['state'], 'STOPPED')
        self.assertEqual(worker.status(rid, db_path=self.db)['transmitted'], 0)

    async def test_expiry_during_inflight_echo_finishes_confirmed_without_retransmit(self):
        row = self.create(); rid, fp = self.grant([row], expires_at_ms=self.clock+1000)
        async def finish_after_expiry(reference, *, request_id, _worker_context, **kwargs):
            self.start(row, _worker_context)
            self.clock += 2000
            self.finish(row)
            return {'results': [dict(request_id=request_id, status='confirmed')]}
        with patch.object(oneshot, 'run_oneshot_send', side_effect=finish_after_expiry):
            await worker.run(rid, fp, db_path=self.db)
        self.assertEqual(requests.get_request(row['request_id'], db_path=self.db)['status'], 'confirmed')
        await self.execute(rid, fp)
        self.assertEqual(worker.status(rid, db_path=self.db)['transmitted'], 1)

    async def test_cleanup_error_after_marker_is_not_retried_or_refunded(self):
        row = self.create(); rid, fp = self.grant([row])
        async def cleanup_error(reference, *, request_id, _worker_context, **kwargs):
            self.start(row, _worker_context)
            self.finish(row)
            raise RuntimeError('fixture cleanup failed')
        with patch.object(oneshot, 'run_oneshot_send', side_effect=cleanup_error):
            result = await worker.run(rid, fp, db_path=self.db)
        self.assertEqual(result['state'], 'NEEDS_OWNER_REVIEW')
        self.assertEqual(worker.status(rid, db_path=self.db)['transmitted'], 1)
        self.assertEqual((await self.execute(rid, fp))['results'], [])

    async def test_terminal_cancelled_member_is_not_executed(self):
        row = self.create(); rid, fp = self.grant([row])
        requests.cancel_request(row['request_id'], 'fixture owner cancel', db_path=self.db)
        with patch.object(oneshot, 'run_oneshot_send', AsyncMock()) as send:
            result = await worker.run(rid, fp, db_path=self.db)
        self.assertEqual(result['state'], 'COMPLETE')
        send.assert_not_called()
        self.assertEqual(worker.status(rid, db_path=self.db)['transmitted'], 0)

    def test_claim_rollback_never_charges_worker_or_quota(self):
        row = self.create(); rid, fp = self.grant([row])
        context = worker.RunContext(rid, fp)
        worker._start(context, self.db)
        with patch.object(requests, 'event', side_effect=RuntimeError('fixture commit failure')):
            with self.assertRaises(RuntimeError): self.start(row, context)
        self.assertEqual(worker.status(rid, db_path=self.db)['transmitted'], 0)
        self.assertEqual(requests.get_request(row['request_id'], db_path=self.db)['status'], 'queued')

    async def test_random_and_round_robin_snapshots_only_advance_on_success(self):
        for mode in ('round_robin', 'random_no_immediate_repeat'):
            self.cfg.pop('message', None)
            self.cfg.update(campaign_id=mode, rotation={'mode': mode, 'templates': [dict(id='a', text='one'), dict(id='b', text='two')]})
            Path(self.policy).write_text(json.dumps(self.cfg), encoding='utf-8')
            row = self.create(key=mode)
            snapshot = row['snapshot_json']
            rid, fp = self.grant([row])
            await self.execute(rid, fp)
            current = requests.get_request(row['request_id'], db_path=self.db)
            self.assertEqual(current['snapshot_json'], snapshot)
            self.assertEqual(self.sql('SELECT success_seq FROM rotation_state WHERE campaign_id=?', (mode,)), [(1,)])
            await self.execute(rid, fp)
            self.assertEqual(self.sql('SELECT success_seq FROM rotation_state WHERE campaign_id=?', (mode,)), [(1,)])

    async def test_backward_or_past_retry_does_not_busy_loop(self):
        row = self.create(); rid, fp = self.grant([row], max_wait=3)
        delays = []
        def blocked(conn, request, settings, **kwargs):
            raise requests.RateLimitError(row['request_id'], [dict(code='MIN_INTERVAL', scope='account',
                used=0, limit=60, retry_at_ms=self.clock-1000, detail='fixture stale retry time')])
        async def wait(stop, seconds):
            delays.append(seconds)
            self.clock += int(seconds*1000)
        with patch.object(requests, 'check_admission', side_effect=blocked):
            result = await self.execute(rid, fp, wait=wait)
        self.assertEqual(result['state'], 'WAIT_LIMIT')
        self.assertEqual(delays, [1, 1, 1])

    async def test_forward_clock_jump_expires_instead_of_extending_consent(self):
        row = self.create(); rid, fp = self.grant([row], expires_at_ms=self.clock+1000)
        self.clock += 86400000
        self.assertEqual((await self.execute(rid, fp))['state'], 'WAIT_LIMIT')
        self.assertEqual(requests.get_request(row['request_id'], db_path=self.db)['transmitted'], 0)

    def test_cli_preview_status_and_run_default_are_readonly_and_execute_requires_hash(self):
        row = self.create(); rid, fp = self.grant([row])
        before = self.sql('SELECT * FROM worker_events')
        for command in (['worker-preview', '--session', 'fixture', '--request-id', row['request_id']],
                        ['worker-status', '--run-id', rid], ['worker-run', '--run-id', rid]):
            with patch('sys.argv', ['main.py', *command, '--db', self.db]), redirect_stdout(io.StringIO()):
                self.assertEqual(main.main(), 0)
        with patch('sys.argv', ['main.py', 'worker-run', '--run-id', rid, '--db', self.db, '--yes', '--execute']), redirect_stdout(io.StringIO()):
            self.assertEqual(main.main(), 3)
        self.assertEqual(self.sql('SELECT * FROM worker_events'), before)

    async def test_late_runner_progress_cannot_reopen_closed_consent(self):
        row = self.create(); rid, fp = self.grant([row])
        worker._start(worker.RunContext(rid, fp), self.db)
        worker._record(rid, 'HELD', db_path=self.db)
        before = self.sql('SELECT * FROM worker_events')
        for state in ('RUNNING', 'WAITING_RATE_LIMIT', 'STOPPED', 'COMPLETE'):
            worker._record(rid, state, db_path=self.db)
        self.assertEqual(self.sql('SELECT * FROM worker_events'), before)
        with requests.transaction(self.db) as conn:
            with self.assertRaises(worker.WorkerHeld):
                worker.check_authorization(conn, None, worker.RunContext(rid, fp), claim=True)
        self.assertEqual((await self.execute(rid, fp))['state'], 'HELD')
        self.assertEqual(requests.get_request(row['request_id'], db_path=self.db)['transmitted'], 0)

    async def test_manual_unknown_exhausting_budget_during_wait_requires_owner_review(self):
        prior = self.create('c'); self.start(prior); self.finish(prior)
        row = self.create()
        self.cfg['min_send_interval_seconds'] = 60
        Path(self.policy).write_text(json.dumps(self.cfg), encoding='utf-8')
        queue.bind_request(row['request_id'], self.cfg, self.policy,
            queue.preview_bind(row['request_id'], self.cfg, self.policy, db_path=self.db),
            'fixture cooldown', db_path=self.db)
        rid, fp = self.grant([row], max_jobs=1)
        async def wait(stop, seconds):
            self.clock += int(seconds*1000)
            self.start(row); self.finish(row, 'failed_unknown')
        result = await self.execute(rid, fp, wait=wait)
        self.assertEqual(result['state'], 'NEEDS_OWNER_REVIEW')
        self.assertEqual(worker.status(rid, db_path=self.db)['transmitted'], 1)
        self.assertEqual((await self.execute(rid, fp))['results'], [])
