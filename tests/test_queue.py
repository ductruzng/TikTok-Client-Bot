"""3D queue contracts through production services, using disposable verified fixtures."""
import asyncio
from contextlib import closing, redirect_stdout
from copy import deepcopy
import io
import json
import multiprocessing
from pathlib import Path
import sqlite3
import tempfile
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


def claim_race(path, config, reference, request_id, barrier, output, action='claim'):
    barrier.wait(timeout=10)
    try:
        if action == 'cancel':
            requests.cancel_request(request_id, 'race fixture', db_path=path)
        else:
            requests.start_transmission(request_id, db_path=path, session_name=config['session'],
                policy_reference=reference, policy_config=config, **requests.settings_from_config(config))
        output.put('ok')
    except ledger.LedgerError:
        output.put('held')


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / 'queue.db')
        self.plan = Path(self.tmp.name) / 'policy.json'
        migrations.initialize(self.path)
        self.cfg = dict(session='fixture', message='hello', allow_repeat_same_day=True,
            max_sends_per_conversation_per_day=10, min_send_interval_seconds=0, max_sends_per_window=20,
            targets=[dict(conv_id=c, conv_short_id=1, conv_type=1) for c in ('a', 'b')])
        self.save()
        cb.bind_session('111', 'fixture', db_path=self.path)

    def save(self):
        self.plan.write_text(json.dumps(self.cfg), encoding='utf-8')

    def create(self, key='key', cid='a', cfg=None):
        cfg = dict(cfg or self.cfg)
        if 'rotation' in cfg:
            cfg.pop('message', None)
        target = next(t for t in cfg['targets'] if t['conv_id'] == cid)
        return requests.create_request('111', cid, key, {'target': target, 'message': cfg.get('message', '')},
            db_path=self.path, rotation_config=cfg if 'rotation' in cfg else None,
            session_name='fixture', policy_reference=str(self.plan), policy_config=cfg)[0]

    def start(self, row, cfg=None):
        cfg = dict(cfg or self.cfg)
        if 'rotation' in cfg:
            cfg.pop('message', None)
        return requests.start_transmission(row['request_id'], db_path=self.path, session_name='fixture',
            policy_reference=str(self.plan), policy_config=cfg, rotation_config=cfg,
            **requests.settings_from_config(cfg))

    def finish(self, row, status='confirmed'):
        current = requests.get_request(row['request_id'], db_path=self.path)
        requests.finish('111', row['conv_id'], current['date'], row['client_msg_id'], db_path=self.path,
            status=status, reason='fixture', server_id='123' if status == 'confirmed' else None)

    def query(self, sql):
        with closing(sqlite3.connect(self.path)) as conn:
            return conn.execute(sql).fetchall()

    def test_fifo_prevents_all_direct_claims_from_overtaking(self):
        old = self.create('old')
        new = self.create('new')
        with self.assertRaisesRegex(queue.QueueHeld, 'FIFO_BLOCKED'):
            self.start(new)
        self.assertTrue(self.start(old))
        self.finish(old)
        self.assertTrue(self.start(new))

    def test_fifo_is_shared_across_campaigns(self):
        cfg = dict(self.cfg, campaign_id='first', rotation={'mode': 'round_robin', 'templates': [{'id': 'x', 'text': 'x'}]})
        old = self.create('old', cfg=cfg)
        other = deepcopy(cfg); other['campaign_id'] = 'second'
        new = self.create('new', cfg=other)
        with self.assertRaisesRegex(queue.QueueHeld, 'FIFO_BLOCKED'):
            self.start(new, other)
        requests.cancel_request(old['request_id'], 'retire fixture', db_path=self.path)
        self.assertTrue(self.start(new, other))

    def test_blocked_head_holds_its_conversation_but_not_others(self):
        old = self.create('old')
        later = self.create('later')
        other = self.create('other', 'b')
        changed = deepcopy(self.cfg); changed['max_sends_per_window'] = 19
        with self.assertRaisesRegex(queue.QueueHeld, 'POLICY_CHANGED'):
            self.start(old, changed)
        with self.assertRaisesRegex(queue.QueueHeld, 'FIFO_BLOCKED'):
            self.start(later)
        self.assertTrue(self.start(other))

    def test_unbound_request_is_durable_but_never_eligible(self):
        row, _ = requests.create_request('111', 'a', 'unbound', {'message': 'hello', 'target': self.cfg['targets'][0]}, db_path=self.path)
        with self.assertRaisesRegex(queue.QueueHeld, 'ROUTE_UNBOUND'):
            self.start(row)
        self.assertEqual(self.query('SELECT status,transmitted FROM send_requests'), [('queued', 0)])
        preview = queue.preview_bind(row['request_id'], self.cfg, str(self.plan), db_path=self.path)
        queue.bind_request(row['request_id'], self.cfg, str(self.plan), preview, 'review fixture', db_path=self.path)
        self.assertTrue(self.start(row))

    def test_config_drift_requires_stale_checked_rebind(self):
        row = self.create()
        changed = deepcopy(self.cfg); changed['max_sends_per_conversation_per_day'] = 11
        with self.assertRaisesRegex(queue.QueueHeld, 'POLICY_CHANGED'):
            self.start(row, changed)
        preview = queue.preview_bind(row['request_id'], changed, str(self.plan), db_path=self.path)
        queue.bind_request(row['request_id'], changed, str(self.plan), preview, 'raise configured limit', db_path=self.path)
        with self.assertRaisesRegex(queue.QueueHeld, 'STALE_PREVIEW'):
            queue.bind_request(row['request_id'], changed, str(self.plan), preview, 'duplicate', db_path=self.path)
        self.assertTrue(self.start(row, changed))

    def test_bind_rejects_fixed_content_target_and_identity_changes(self):
        row = self.create()
        for field, value in [('message', 'new'), ('targets', self.cfg['targets'][1:]), ('session', 'unbound')]:
            cfg = dict(self.cfg, **{field: value})
            with self.subTest(field=field), self.assertRaises(ledger.LedgerError):
                queue.preview_bind(row['request_id'], cfg, str(self.plan), db_path=self.path)

    def test_bind_cannot_race_with_claim_or_cancel(self):
        for terminal in ('claim', 'cancel'):
            with self.subTest(terminal=terminal):
                row = self.create(terminal, cid='a' if terminal == 'claim' else 'b')
                view = queue.preview_bind(row['request_id'], self.cfg, str(self.plan), db_path=self.path)
                if terminal == 'claim':
                    self.start(row)
                    self.finish(row)
                else:
                    requests.cancel_request(row['request_id'], 'fixture', db_path=self.path)
                with self.assertRaises(ledger.LedgerError):
                    queue.bind_request(row['request_id'], self.cfg, str(self.plan), view, 'stale', db_path=self.path)

    def test_enqueue_and_dry_preview_idempotency_survive_restart(self):
        dump = self.query('SELECT * FROM send_requests')
        view = services.queue_enqueue(str(self.plan), 'task', db_path=self.path)
        self.assertTrue(view['preview_only'])
        self.assertEqual(self.query('SELECT * FROM send_requests'), dump)
        rows = services.queue_enqueue(str(self.plan), 'task', db_path=self.path, apply=True)
        again = services.queue_enqueue(str(self.plan), 'task', db_path=self.path, apply=True)
        self.assertEqual([r['request_id'] for r in rows], [r['request_id'] for r in again])
        self.assertEqual(len(queue.list_queue(db_path=self.path)), 2)
        with self.assertRaises(requests.IdempotencyConflict):
            self.create(rows[0]['idempotency_key'], cid='b')

    def test_account_session_without_binding_fails_before_auth(self):
        self.cfg['session'] = 'unbound'; self.save()
        with patch.object(oneshot, 'load_session') as auth, patch.object(oneshot, '_open_ws', AsyncMock()) as connect:
            with self.assertRaisesRegex(queue.QueueHeld, 'IDENTITY_UNBOUND'):
                asyncio.run(oneshot.run_oneshot_send(str(self.plan), db_path=self.path))
            auth.assert_not_called(); connect.assert_not_called()
        self.assertEqual(self.query('SELECT count(*) FROM send_requests'), [(0,)])

    def test_old_send_is_held_before_network_if_it_overtakes_queue(self):
        old = self.create('old')
        with patch.object(oneshot, 'load_session') as auth, patch.object(oneshot, '_open_ws', AsyncMock()) as connect:
            # Restrict this send to the blocked conversation.
            self.cfg['targets'] = self.cfg['targets'][:1]; self.save()
            output = asyncio.run(services.send_plan(str(self.plan), db_path=self.path, idempotency_key='new'))
            self.assertEqual(output['results'][0]['reason'], 'FIFO_BLOCKED')
            auth.assert_not_called(); connect.assert_not_called()
        self.assertEqual(requests.get_request(old['request_id'], db_path=self.path)['transmitted'], 0)

    def test_terminal_replay_returns_before_credentials_and_network(self):
        rows = queue.enqueue(self.cfg, str(self.plan), 'task', db_path=self.path)
        for row in rows:
            self.start(row); self.finish(row)
        cb.record_failure(cb.Failure('AUTH', 'fixture', 'http', 401), db_path=self.path, session='fixture')
        with patch.object(oneshot, 'load_session') as auth, patch.object(oneshot, '_open_ws', AsyncMock()) as connect:
            result = asyncio.run(services.send_plan(str(self.plan), db_path=self.path, idempotency_key='task'))
            self.assertTrue(all(r['existing_status'] == 'confirmed' for r in result['results']))
            auth.assert_not_called(); connect.assert_not_called()

    def test_preview_does_not_change_any_tables_or_create_database(self):
        self.create()
        with closing(sqlite3.connect(self.path)) as conn:
            before = list(conn.iterdump())
        self.assertTrue(queue.preview_run(db_path=self.path, session='fixture')[0]['eligible'])
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertEqual(list(conn.iterdump()), before)
        missing = str(Path(self.tmp.name) / 'missing.db')
        with self.assertRaises(ledger.LedgerError): queue.preview_run(db_path=missing, session='fixture')
        self.assertFalse(Path(missing).exists())

    def test_enqueue_event_failure_rolls_back_queue_and_request_together(self):
        with patch.object(requests, 'event', side_effect=RuntimeError('fixture crash')):
            with self.assertRaises(RuntimeError): self.create()
        self.assertEqual(self.query('SELECT count(*) FROM send_requests'), [(0,)])
        self.assertEqual(self.query('SELECT count(*) FROM queue_entries'), [(0,)])

    def compete(self, ids, actions):
        ctx = multiprocessing.get_context('spawn')
        barrier, output = ctx.Barrier(2), ctx.Queue()
        jobs = [ctx.Process(target=claim_race, args=(self.path, self.cfg, str(self.plan), rid, barrier, output, action)) for rid, action in zip(ids, actions)]
        try:
            for job in jobs: job.start()
            result = [output.get(timeout=20) for _ in jobs]
            for job in jobs:
                job.join(20); self.assertEqual(job.exitcode, 0)
            return result
        finally:
            for job in jobs:
                if job.is_alive(): job.terminate(); job.join()
            output.close()

    def test_two_processes_claim_cannot_overtake_or_double_transmit(self):
        old, new = self.create('old'), self.create('new')
        self.assertEqual(sorted(self.compete([old['request_id'], new['request_id']], ['claim', 'claim'])), ['held', 'ok'])
        self.assertEqual(self.query('SELECT sum(transmitted) FROM send_requests'), [(1,)])
        self.assertEqual(requests.get_request(new['request_id'], db_path=self.path)['status'], 'queued')

    def test_two_processes_cancel_claim_are_mutually_exclusive(self):
        row = self.create()
        outcomes = self.compete([row['request_id']] * 2, ['cancel', 'claim'])
        current = requests.get_request(row['request_id'], db_path=self.path)
        self.assertIn(current['status'], ('pending', 'cancelled'))
        self.assertEqual(current['transmitted'], int(current['status'] == 'pending'))
        self.assertIn('ok', outcomes)

    def test_cli_preview_and_interactive_only_execution(self):
        self.create()
        for execute in (False, True):
            argv = ['main.py', '--yes', 'queue-run-once', '--db', self.path, '--session', 'fixture'] + (['--execute'] if execute else [])
            with patch('sys.argv', argv), redirect_stdout(io.StringIO()) as output, patch.object(services, 'queue_run_once', AsyncMock()) as run:
                self.assertEqual(main.main(), int(execute))
                run.assert_not_called()
                self.assertIn('eligible', output.getvalue())


    def test_bounded_snapshot_excludes_newly_enqueued_jobs(self):
        first = self.create('first')
        calls = []
        async def execute(*args, request_id, **kwargs):
            calls.append(request_id)
            self.create('new-during-run', 'b')
            row = requests.get_request(request_id, db_path=self.path)
            self.start(row); self.finish(row)
            return {'results': [{'request_id': request_id, 'status': 'confirmed'}]}
        with patch.object(oneshot, 'run_oneshot_send', side_effect=execute):
            asyncio.run(queue.run_once(db_path=self.path, session='fixture', max_jobs=100, confirm_request=lambda _: True))
        self.assertEqual(calls, [first['request_id']])

    def test_default_max_one_and_consider_each_candidate_at_most_once(self):
        first = self.create('first')
        self.create('later', 'b')
        calls = []
        async def execute(*args, request_id, **kwargs):
            calls.append(request_id)
            row = requests.get_request(request_id, db_path=self.path)
            self.start(row); self.finish(row)
            return {'results': [{'request_id': request_id, 'status': 'confirmed'}]}
        with patch.object(oneshot, 'run_oneshot_send', side_effect=execute):
            asyncio.run(queue.run_once(db_path=self.path, session='fixture', confirm_request=lambda _: True))
        self.assertEqual(calls, [first['request_id']])

    def test_blocked_head_does_not_prevent_other_conversation_execution(self):
        first = self.create('first'); later = self.create('later'); other = self.create('other', 'b')
        calls = []
        async def execute(*args, request_id, **kwargs):
            calls.append(request_id)
            if request_id == other['request_id']:
                self.start(other); self.finish(other)
            return {'results': [{'request_id': request_id, 'status': 'skipped' if request_id != other['request_id'] else 'confirmed'}]}
        with patch.object(oneshot, 'run_oneshot_send', side_effect=execute):
            asyncio.run(queue.run_once(db_path=self.path, session='fixture', confirm_request=lambda _: True))
        self.assertEqual(calls, [first['request_id'], later['request_id'], other['request_id']])

    def test_invalid_batch_limit_or_noninteractive_service_is_refused(self):
        for limit in (0, 101, True):
            with self.assertRaises(ValueError):
                asyncio.run(queue.run_once(db_path=self.path, session='fixture', max_jobs=limit, confirm_request=lambda _: True))
        with self.assertRaises(ValueError):
            asyncio.run(queue.run_once(db_path=self.path, session='fixture'))

    def test_cleanup_error_after_commit_still_counts_against_run_bound(self):
        row = self.create('first'); self.create('later', 'b')
        calls = []
        async def execute(*args, request_id, **kwargs):
            calls.append(request_id)
            stored = requests.get_request(request_id, db_path=self.path)
            self.start(stored); self.finish(stored)
            raise OSError('synthetic close failure')
        with patch.object(oneshot, 'run_oneshot_send', side_effect=execute):
            result = asyncio.run(queue.run_once(db_path=self.path, session='fixture', confirm_request=lambda _: True))
        self.assertEqual(calls, [row['request_id']])
        self.assertEqual(result['results'][0]['existing_status'], 'confirmed')

    def test_policy_settings_cannot_be_overridden_at_atomic_claim(self):
        row = self.create()
        with self.assertRaisesRegex(queue.QueueHeld, 'POLICY_SETTINGS_MISMATCH'):
            requests.start_transmission(row['request_id'], db_path=self.path, session_name='fixture',
                policy_reference=str(self.plan), policy_config=self.cfg,
                **dict(requests.settings_from_config(self.cfg), max_sends_per_account_per_day=999))
        self.assertEqual(requests.get_request(row['request_id'], db_path=self.path)['transmitted'], 0)

    def test_run_cannot_switch_to_rebound_alias_of_same_account(self):
        row = self.create()
        cb.bind_session('111', 'other_alias', db_path=self.path)
        cfg = dict(self.cfg, session='other_alias')
        view = queue.preview_bind(row['request_id'], cfg, str(self.plan), db_path=self.path)
        queue.bind_request(row['request_id'], cfg, str(self.plan), view, 'review alias fixture', db_path=self.path)
        self.plan.write_text(json.dumps(cfg), encoding='utf-8')
        with patch.object(oneshot, 'load_session') as auth:
            with self.assertRaisesRegex(queue.QueueHeld, 'SESSION_ROUTE_CHANGED'):
                asyncio.run(oneshot.run_oneshot_send(str(self.plan), db_path=self.path,
                    request_id=row['request_id'], _expected_session='fixture'))
            auth.assert_not_called()

    def test_binding_preview_rejects_aba_change_in_audit_version(self):
        row = self.create()
        view = queue.preview_bind(row['request_id'], self.cfg, str(self.plan), db_path=self.path)
        queue.bind_request(row['request_id'], self.cfg, str(self.plan), view, 'record identical review', db_path=self.path)
        with self.assertRaisesRegex(queue.QueueHeld, 'STALE_PREVIEW'):
            queue.bind_request(row['request_id'], self.cfg, str(self.plan), view, 'stale identical review', db_path=self.path)

    def test_end_to_end_queue_and_service_send_use_same_durable_request_and_echo(self):
        from test_streak import MockWebSocket, _build_synthetic_echo_frame
        rows = queue.enqueue(self.cfg, str(self.plan), 'task', db_path=self.path)
        for row in rows:
            echo = _build_synthetic_echo_frame(row['conv_id'], '111', row['client_msg_id'], 'hello')
            ws = MockWebSocket([b'hi', echo])
            with patch.object(oneshot, 'load_session', return_value={'sessionid': 'synthetic'}), \
                 patch.object(oneshot, 'get_own_user_id', return_value='111'), \
                 patch.object(oneshot, 'load_ws_auth', return_value={'device_id': '0'}), \
                 patch.object(oneshot, 'validate_against_server_inbox') as inbox, \
                 patch.object(oneshot, '_prepare_ws', return_value=({}, 'wss://fixture.invalid')), \
                 patch.object(oneshot, '_open_ws', AsyncMock(return_value=ws)):
                result = asyncio.run(services.queue_run_once(db_path=self.path, session='fixture', confirm_request=lambda _: True))
                self.assertEqual(result['results'][0]['request_id'], row['request_id'])
                self.assertEqual(result['results'][0]['status'], 'confirmed')
                inbox.assert_called_once()
                self.assertEqual(len(ws.sent_packets), 2)  # Control hi + exactly one managed packet.
        self.assertEqual(self.query('SELECT count(*) FROM send_requests'), [(2,)])

    def test_verified_binding_is_checked_against_fresh_server_identity(self):
        row = self.create()
        with patch.object(oneshot, 'load_session', return_value={'sessionid': 'synthetic'}), \
             patch.object(oneshot, 'get_own_user_id', return_value='222'), \
             patch.object(oneshot, '_open_ws', AsyncMock()) as connect:
            with self.assertRaises(cb.CircuitOpen):
                asyncio.run(services.send_plan(str(self.plan), db_path=self.path, request_id=row['request_id']))
            connect.assert_not_called()
        self.assertEqual(requests.get_request(row['request_id'], db_path=self.path)['transmitted'], 0)
