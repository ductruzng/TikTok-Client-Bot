"""Owner resolutions never alter UNKNOWN, quota, rotation or circuit state."""
import asyncio
from contextlib import closing, redirect_stdout
from copy import deepcopy
import io
import json
import multiprocessing
import sqlite3
import unittest
from unittest.mock import patch

import circuit_breaker as cb
import ledger
import ledger_requests as requests
import main
import queue_service as queue
import services
import unknown_resolution as unknown
import test_queue


def resolve_race(path, rid, preview, action, barrier, output):
    barrier.wait(timeout=10)
    try:
        if action == 'RESET':
            cb.reset('account', '111', preview, 'explicit fixture reset', db_path=path)
        else:
            unknown.resolve(rid, action, preview, 'fixture decision', 'fixture manual observation', db_path=path)
        output.put('ok')
    except ledger.LedgerError:
        output.put('stale')


class ResolutionTests(unittest.TestCase):
    setUp = test_queue.QueueTests.setUp
    create = test_queue.QueueTests.create
    start = test_queue.QueueTests.start
    finish = test_queue.QueueTests.finish
    query = test_queue.QueueTests.query
    save = test_queue.QueueTests.save

    def uncertain(self, cfg=None):
        row = self.create(cfg=cfg)
        self.start(row, cfg)
        self.finish(row, 'failed_unknown')
        return row

    def resolve(self, row, action, preview=None):
        return unknown.resolve(row['request_id'], action, preview or unknown.preview(row['request_id'], db_path=self.path),
            'reviewed by fixture owner', 'manual observation fixture', db_path=self.path)

    def reset(self):
        state = cb.inspect(db_path=self.path, uid='111')[0]
        cb.reset('account', '111', state, 'Owner reset fixture', db_path=self.path)

    def test_keep_blocked_is_append_only_review_and_stales_preview(self):
        row = self.uncertain(); preview = unknown.preview(row['request_id'], db_path=self.path)
        self.resolve(row, 'KEEP_BLOCKED', preview)
        with self.assertRaisesRegex(ledger.LedgerError, 'Stale'):
            self.resolve(row, 'CLOSE_WITHOUT_RESEND', preview)
        current = unknown.preview(row['request_id'], db_path=self.path)
        self.assertFalse(current['resolved'])
        self.assertEqual(current['outstanding_unknown'], [row['request_id']])
        with self.assertRaisesRegex(ledger.LedgerError, 'UNKNOWN'):
            self.reset()

    def test_close_preserves_row_marker_quota_history_and_requires_separate_reset(self):
        row = self.uncertain()
        before = self.query('SELECT * FROM send_requests')
        circuit = cb.inspect(db_path=self.path, uid='111')
        old_events = self.query('SELECT * FROM request_events')
        self.resolve(row, 'CLOSE_WITHOUT_RESEND')
        self.assertEqual(self.query('SELECT * FROM send_requests'), before)
        self.assertEqual(cb.inspect(db_path=self.path, uid='111'), circuit)
        self.assertEqual(self.query('SELECT * FROM request_events')[:len(old_events)], old_events)
        self.assertEqual(self.query('SELECT sum(transmitted) FROM send_requests'), [(1,)])
        self.assertTrue(unknown.preview(row['request_id'], db_path=self.path)['resolved'])
        self.reset()
        next_row = self.create('new', 'b')
        self.assertTrue(self.start(next_row))

    def test_replacement_has_new_id_key_client_id_and_exact_snapshot(self):
        cfg = dict(self.cfg, campaign_id='daily', rotation={'mode': 'random_no_immediate_repeat', 'templates': [
            {'id': 'a', 'text': ' hello 🌞 '}, {'id': 'b', 'text': ' world '}]})
        row = self.uncertain(cfg)
        result = self.resolve(row, 'AUTHORIZE_REPLACEMENT')
        new = requests.get_request(result['replacement_request_id'], db_path=self.path)
        for field in ('request_id', 'idempotency_key', 'client_msg_id'):
            self.assertNotEqual(new[field], row[field])
        for field in ('payload_json', 'snapshot_json', 'campaign_id', 'rotation_seq', 'selection_generation', 'intent_json'):
            self.assertEqual(new[field], row[field])
        self.assertEqual((new['status'], new['transmitted']), ('queued', 0))
        self.assertEqual(self.query('SELECT success_seq,selection_generation FROM rotation_state'), [(0, 0)])
        self.assertEqual(cb.inspect(db_path=self.path, uid='111')[0]['state'], 'OPEN')
        self.assertEqual(self.query('SELECT sum(transmitted) FROM send_requests'), [(1,)])
        with self.assertRaises(ledger.LedgerError): self.resolve(row, 'AUTHORIZE_REPLACEMENT')

    def test_same_day_replacement_shows_limit_and_does_not_refund_unknown(self):
        self.cfg.update(allow_repeat_same_day=False, max_sends_per_conversation_per_day=1)
        self.save()
        row = self.uncertain()
        view = services.unknown_preview(row['request_id'], db_path=self.path)
        self.assertEqual(view['conversation_transmitted_today'], 1)
        self.assertEqual(view['current_settings']['max_sends_per_conversation_per_day'], 1)
        result = self.resolve(row, 'AUTHORIZE_REPLACEMENT')
        new = requests.get_request(result['replacement_request_id'], db_path=self.path)
        with self.assertRaises(requests.RateLimitError) as held: self.start(new)
        codes = [r['code'] for r in held.exception.reasons]
        self.assertIn('CONVERSATION_DAILY_LIMIT', codes); self.assertIn('REPEAT_DISABLED', codes)
        self.assertNotIn('UNKNOWN', codes)
        self.assertEqual(self.query('SELECT sum(transmitted) FROM send_requests'), [(1,)])
        self.reset()
        changed = dict(self.cfg, allow_repeat_same_day=True, max_sends_per_conversation_per_day=2)
        with self.assertRaisesRegex(queue.QueueHeld, 'POLICY_CHANGED'):
            self.start(new, changed)
        view = queue.preview_bind(new['request_id'], changed, str(self.plan), db_path=self.path)
        queue.bind_request(new['request_id'], changed, str(self.plan), view, 'Owner adjusts limits explicitly', db_path=self.path)
        self.assertTrue(self.start(new, changed))
        self.assertEqual(self.query('SELECT sum(transmitted) FROM send_requests'), [(2,)])

    def test_resolved_old_key_never_reexecutes(self):
        row = self.uncertain(); self.resolve(row, 'CLOSE_WITHOUT_RESEND'); self.reset()
        replay = self.create()
        self.assertEqual(replay['request_id'], row['request_id'])
        self.assertFalse(self.start(replay))
        self.assertEqual(self.query('SELECT sum(transmitted) FROM send_requests'), [(1,)])

    def test_resolution_and_replacement_roll_back_together(self):
        row = self.uncertain(); preview = unknown.preview(row['request_id'], db_path=self.path)
        before = self.query('SELECT * FROM send_requests')
        with patch.object(requests, 'event', side_effect=RuntimeError('fixture crash')):
            with self.assertRaises(RuntimeError): self.resolve(row, 'AUTHORIZE_REPLACEMENT', preview)
        self.assertEqual(self.query('SELECT * FROM send_requests'), before)
        self.assertEqual(self.query('SELECT count(*) FROM unknown_resolution_events'), [(0,)])
        self.assertEqual(self.query('SELECT count(*) FROM queue_entries'), [(1,)])
        self.assertEqual(unknown.preview(row['request_id'], db_path=self.path), preview)

    def test_decisions_and_unknown_rows_cannot_be_deleted_or_rewritten(self):
        row = self.uncertain(); self.resolve(row, 'CLOSE_WITHOUT_RESEND')
        for sql in ('DELETE FROM unknown_resolution_events', "UPDATE unknown_resolution_events SET action='KEEP_BLOCKED'",
                    "UPDATE send_requests SET transmitted=0", 'DELETE FROM send_requests'):
            with self.subTest(sql=sql), closing(sqlite3.connect(self.path)) as conn:
                with self.assertRaises(sqlite3.IntegrityError): conn.execute(sql)

    def test_two_processes_cannot_finalize_twice_or_make_two_replacements(self):
        row = self.uncertain(); preview = unknown.preview(row['request_id'], db_path=self.path)
        ctx = multiprocessing.get_context('spawn'); barrier, output = ctx.Barrier(2), ctx.Queue()
        jobs = [ctx.Process(target=resolve_race, args=(self.path, row['request_id'], preview, 'AUTHORIZE_REPLACEMENT', barrier, output)) for _ in range(2)]
        try:
            for job in jobs: job.start()
            self.assertEqual(sorted(output.get(timeout=20) for _ in jobs), ['ok', 'stale'])
            for job in jobs: job.join(20); self.assertEqual(job.exitcode, 0)
        finally:
            for job in jobs:
                if job.is_alive(): job.terminate(); job.join()
            output.close()
        self.assertEqual(self.query('SELECT count(*) FROM unknown_resolution_events'), [(1,)])
        self.assertEqual(self.query('SELECT count(*) FROM send_requests'), [(2,)])

    def test_rotation_skip_uses_same_unresolved_predicate(self):
        cfg = dict(self.cfg, campaign_id='daily', rotation={'mode': 'round_robin', 'templates': [{'id': 'a', 'text': 'a'}]})
        row = self.uncertain(cfg)
        scope = ('111', 'a', 'daily')
        with self.assertRaises(ledger.LedgerError): requests.preview_skip(scope, db_path=self.path)
        self.resolve(row, 'CLOSE_WITHOUT_RESEND')
        view = requests.preview_skip(scope, db_path=self.path)
        requests.skip_selection(scope, view, 'retire unused selection', db_path=self.path)
        self.assertEqual(self.query('SELECT success_seq,selection_generation FROM rotation_state'), [(0, 1)])
        self.assertEqual(self.query('SELECT sum(transmitted) FROM send_requests'), [(1,)])

    def test_active_rotation_request_prevents_replacement_without_changing_unknown(self):
        cfg = dict(self.cfg, campaign_id='daily', rotation={'mode': 'round_robin', 'templates': [{'id': 'a', 'text': 'a'}]})
        row = self.uncertain(cfg)
        self.create('active', cfg=cfg)
        with self.assertRaisesRegex(ledger.LedgerError, 'active request'):
            self.resolve(row, 'AUTHORIZE_REPLACEMENT')
        self.assertFalse(unknown.preview(row['request_id'], db_path=self.path)['resolved'])

    def test_resolve_requires_unknown_reason_evidence_and_safe_notes(self):
        row = self.create()
        with self.assertRaises(ledger.LedgerError): unknown.preview(row['request_id'], db_path=self.path)
        self.start(row); self.finish(row, 'failed_unknown')
        for note in ('', 'cookie=SECRET', 'https://example.invalid/?token=SECRET', 'raw\nlog'):
            with self.subTest(note=note), self.assertRaises(ValueError):
                unknown.resolve(row['request_id'], 'CLOSE_WITHOUT_RESEND', unknown.preview(row['request_id'], db_path=self.path), note, 'observed', db_path=self.path)

    def test_preview_and_cli_do_not_send_or_resolve_noninteractively(self):
        row = self.uncertain()
        for command in ('unknown-show', 'unknown-resolve'):
            argv = ['main.py', '--yes', command, '--db', self.path, '--request-id', row['request_id']]
            with patch('sys.argv', argv), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main.main(), int(command == 'unknown-resolve'))
                self.assertIn('conversation_transmitted_today', output.getvalue())
        self.assertEqual(self.query('SELECT count(*) FROM unknown_resolution_events'), [(0,)])

    def test_interactive_confirmation_binds_action_request_and_fingerprint(self):
        row = self.uncertain(); view = services.unknown_preview(row['request_id'], db_path=self.path)
        challenge = 'CLOSE_WITHOUT_RESEND ' + row['request_id'] + ' ' + view['fingerprint']
        argv = ['main.py', 'unknown-resolve', '--db', self.path, '--request-id', row['request_id'], '--action', 'CLOSE_WITHOUT_RESEND']
        with patch('sys.argv', argv), redirect_stdout(io.StringIO()), patch('sys.stdin.isatty', return_value=True), \
             patch('builtins.input', side_effect=['fixture review', 'manual observation', challenge]):
            import sys
            with patch.object(sys.stdout, 'isatty', return_value=True): self.assertEqual(main.main(), 0)
        self.assertTrue(unknown.preview(row['request_id'], db_path=self.path)['resolved'])

    def test_resolution_racing_explicit_reset_never_erases_quota_or_history(self):
        row = self.uncertain()
        ctx = multiprocessing.get_context('spawn'); barrier, output = ctx.Barrier(2), ctx.Queue()
        decision = unknown.preview(row['request_id'], db_path=self.path)
        circuit = cb.inspect(db_path=self.path, uid='111')[0]
        jobs = [ctx.Process(target=resolve_race, args=(self.path, row['request_id'], view, action, barrier, output))
                for action, view in [('CLOSE_WITHOUT_RESEND', decision), ('RESET', circuit)]]
        try:
            for job in jobs: job.start()
            results = [output.get(timeout=20) for _ in jobs]
            for job in jobs: job.join(20); self.assertEqual(job.exitcode, 0)
            self.assertIn('ok', results)
        finally:
            for job in jobs:
                if job.is_alive(): job.terminate(); job.join()
            output.close()
        self.assertEqual(self.query('SELECT status,transmitted FROM send_requests'), [('failed_unknown', 1)])
        self.assertEqual(self.query("SELECT count(*) FROM unknown_resolution_events WHERE action='CLOSE_WITHOUT_RESEND'"), [(1,)])
        if cb.inspect(db_path=self.path, uid='111')[0]['state'] == 'CLOSED':
            history = cb.inspect(db_path=self.path, uid='111', history=True)
            self.assertEqual(history[-1]['event_type'], 'RESET')

    def test_breaker_change_invalidates_unknown_review(self):
        row = self.uncertain(); view = unknown.preview(row['request_id'], db_path=self.path)
        cb.record_failure(cb.Failure('NETWORK', 'fixture', 'transport'), db_path=self.path, uid='111')
        with self.assertRaisesRegex(ledger.LedgerError, 'Stale'):
            self.resolve(row, 'CLOSE_WITHOUT_RESEND', view)

    def test_unbound_legacy_payload_cannot_be_authorized_for_replacement(self):
        row, _ = requests.create_request('111', 'a', 'legacy', {}, db_path=self.path)
        # Build a historical UNKNOWN fixture without invoking any transport.
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("UPDATE send_requests SET status='failed_unknown',transmitted=1,date='2026-10-09',attempt_time='2026-10-09T12:00:00+07:00',transmission_started_at_ms=1791522000000 WHERE request_id=?", (row['request_id'],))
            conn.commit()
        with self.assertRaisesRegex(ledger.LedgerError, 'verified queue binding'):
            self.resolve(row, 'AUTHORIZE_REPLACEMENT')
        self.resolve(row, 'CLOSE_WITHOUT_RESEND')
        self.assertEqual(self.query('SELECT count(*) FROM send_requests'), [(1,)])
