"""Synthetic streams and disposable grants only; no live credentials or transport."""
from contextlib import closing
from datetime import datetime
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import main
from relttk.application import terminal
from relttk.identity import circuit_breaker as cb
from relttk.runtime import scheduling
from relttk.storage import ledger, ledger_migrations, ledger_requests


class TTY(io.StringIO):
    def isatty(self):
        return True


class TerminalStreamTests(unittest.TestCase):
    def test_utf8_input_and_output_keep_vietnamese_emoji_and_whitespace(self):
        text = '  lý do 🇻🇳\n'
        with patch('sys.stdin', TTY(text)), patch('sys.stdout', TTY()) as out:
            self.assertEqual(terminal.read('Reason: '), text[:-1])
            terminal.write(text)
            self.assertTrue(out.getvalue().endswith(text + '\n'))

    def test_ascii_output_escapes_presentation_without_changing_value(self):
        raw = io.BytesIO()
        out = io.TextIOWrapper(raw, encoding='ascii', errors='strict')
        with patch('sys.stdout', out):
            text = 'lý do ✅'
            terminal.write(text)
            out.flush()
            self.assertIn(b'\\u2705', raw.getvalue())
            self.assertEqual(text, 'lý do ✅')

    def test_undecodable_bytes_refused_in_strict_and_posix_surrogateescape(self):
        for errors in ('strict', 'surrogateescape'):
            with self.subTest(errors=errors):
                stream = io.TextIOWrapper(io.BytesIO(b'bad\xff\n'), encoding='utf-8', errors=errors)
                with patch('sys.stdin', stream), patch('sys.stdout', TTY()):
                    with self.assertRaises(terminal.TerminalInputError) as raised:
                        terminal.read('Reason: ')
                self.assertTrue(raised.exception.code.startswith('TERMINAL_INPUT_ENCODING'))

    def test_lossy_decoder_refused_without_reading(self):
        stream = SimpleNamespace(errors='replace')
        with patch('sys.stdin', stream), patch('builtins.input', side_effect=AssertionError('read')):
            with self.assertRaises(terminal.TerminalInputError):
                terminal.read('Reason: ')

    def test_valid_posix_surrogateescape_input_is_preserved(self):
        stream = io.TextIOWrapper(io.BytesIO('lý do ✅\n'.encode()), encoding='utf-8', errors='surrogateescape')
        with patch('sys.stdin', stream), patch('sys.stdout', TTY()):
            self.assertEqual(terminal.read('Reason: '), 'lý do ✅')

    def test_eof_cancel_and_prompt_encoding_are_sanitized(self):
        failures = [(EOFError(), 'TERMINAL_INPUT_EOF'),
                    (KeyboardInterrupt(), 'TERMINAL_INPUT_CANCELLED'),
                    (UnicodeEncodeError('ascii', 'é', 0, 1, 'fixture'), 'TERMINAL_PROMPT_ENCODING')]
        for error, code in failures:
            with self.subTest(code=code), patch('builtins.input', side_effect=error):
                with self.assertRaises(terminal.TerminalInputError) as raised:
                    terminal.read('ASCII challenge: ')
                self.assertTrue(raised.exception.code.startswith(code))


class ScheduleTerminalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.base.chmod(0o700)
        self.db = self.base / 'fixture.db'
        self.policy = self.base / 'policy.json'
        self.cfg = dict(session='fixture', message='  tin nhắn\n✅  ',
                        targets=[dict(conv_id='fixture-conversation', conv_short_id=1, conv_type=1)])
        self.policy.write_text(json.dumps(self.cfg), encoding='utf-8')
        self.policy.chmod(0o600)
        ledger_migrations.initialize(self.db)
        clock = int(datetime(2026, 10, 11, 8, tzinfo=ledger.TZ_HO_CHI_MINH).timestamp() * 1000)
        for target in (patch.object(ledger_requests, 'utc_now_ms', return_value=clock),
                       patch.object(cb, 'now_ms', return_value=clock),
                       patch.dict(os.environ, {'TIKTOK_RUNTIME_DIR': str(self.base)})):
            target.start()
            self.addCleanup(target.stop)
        cb.bind_session('111', 'fixture', db_path=self.db)

    def args(self, command, gid=None):
        return SimpleNamespace(command=command, db=str(self.db), config=str(self.policy),
                               schedule_id='fixture', time='08:00', valid_from=None,
                               valid_through=None, window_minutes=60, daily_budget=None,
                               total_budget=None, max_wait=300, apply=True, grant_id=gid)

    def counts(self):
        with closing(sqlite3.connect(self.db)) as conn:
            return tuple(conn.execute('SELECT count(*) FROM ' + table).fetchone()[0]
                         for table in ('recurring_grants', 'recurring_events'))

    def invoke(self, args, answers, *, tty=True):
        out = TTY()
        with patch('sys.stdin', TTY() if tty else io.StringIO()), patch('sys.stdout', out), \
                patch('builtins.input', side_effect=answers):
            code = main.cmd_schedule_admin(args)
        return code, out.getvalue()

    def authorized(self):
        review = scheduling.preview(self.policy, 'fixture', db_path=self.db)
        return scheduling.authorize(review, 'fixture setup', db_path=self.db)

    def test_authorize_utf8_reason_exact_content_and_confirmation(self):
        review = scheduling.preview(self.policy, 'fixture', db_path=self.db)
        code, _ = self.invoke(self.args('schedule-authorize'), ['  lý do ✅  ', 'AUTHORIZE ' + review['fingerprint']])
        self.assertEqual(code, 0)
        self.assertEqual(self.counts(), (1, 1))
        with closing(sqlite3.connect(self.db)) as conn:
            reason = json.loads(conn.execute('SELECT details_json FROM recurring_events').fetchone()[0])['reason']
            consent = json.loads(conn.execute('SELECT consent_json FROM recurring_grants').fetchone()[0])
        self.assertEqual(reason, '  lý do ✅  ')
        self.assertEqual(consent['policy']['message'], self.cfg['message'])

    def test_decode_eof_cancel_and_non_tty_create_no_grants_or_events(self):
        for error in (UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'fixture'), EOFError(), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                before = self.counts()
                code, text = self.invoke(self.args('schedule-authorize'), error)
                self.assertEqual(code, 3)
                self.assertIn('TERMINAL_INPUT_', text)
                self.assertEqual(self.counts(), before)
        before = self.counts()
        code, _ = self.invoke(self.args('schedule-authorize'), AssertionError('input'), tty=False)
        self.assertEqual(code, 3)
        self.assertEqual(self.counts(), before)

    def test_wrong_or_whitespace_modified_authorize_challenge_never_writes(self):
        review = scheduling.preview(self.policy, 'fixture', db_path=self.db)
        for challenge in ('AUTHORIZE', 'AUTHORIZE ' + review['fingerprint'] + ' ', 'authorize ' + review['fingerprint']):
            with self.subTest(challenge=challenge):
                self.assertEqual(self.invoke(self.args('schedule-authorize'), ['fixture', challenge])[0], 1)
                self.assertEqual(self.counts(), (0, 0))

    def test_activate_pause_revoke_use_exact_versioned_challenges(self):
        gid = self.authorized()
        for command in ('schedule-activate', 'schedule-pause', 'schedule-revoke'):
            current = scheduling.status(gid, db_path=self.db)
            challenge = command.removeprefix('schedule-').upper() + ' ' + gid + ' ' + current['fingerprint'] + ' ' + str(current['event']['version'])
            before = self.counts()
            self.assertEqual(self.invoke(self.args(command, gid), ['fixture', challenge + ' '])[0], 1)
            self.assertEqual(self.counts(), before)
            code, _ = self.invoke(self.args(command, gid), ['lý do ✅', challenge])
            self.assertEqual(code, 0)
            self.assertEqual(self.counts()[1], before[1] + 1)

    def test_decode_error_on_each_action_keeps_existing_history(self):
        gid = self.authorized()
        for command in ('schedule-activate', 'schedule-pause', 'schedule-revoke'):
            with self.subTest(command=command):
                before = self.counts()
                code, _ = self.invoke(self.args(command, gid), ['fixture', UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'fixture')])
                self.assertEqual(code, 3)
                self.assertEqual(self.counts(), before)

    def test_stale_policy_after_exact_confirmation_does_not_authorize(self):
        review = scheduling.preview(self.policy, 'fixture', db_path=self.db)
        def answer(prompt):
            if prompt.startswith('Required'):
                return 'fixture'
            changed = {**self.cfg, 'message': 'changed'}
            self.policy.write_text(json.dumps(changed), encoding='utf-8')
            return 'AUTHORIZE ' + review['fingerprint']
        code, _ = self.invoke(self.args('schedule-authorize'), answer)
        self.assertEqual(code, 3)
        self.assertEqual(self.counts(), (0, 0))

    def test_ascii_stdout_failure_diagnostic_is_readable_and_no_writes(self):
        raw = io.BytesIO()
        output = io.TextIOWrapper(raw, encoding='ascii', errors='strict')
        error = scheduling.ScheduleHeld('Lỗi ✅')
        with patch('sys.stdout', output), patch('relttk.application.services.schedule_preview', side_effect=error):
            code = main.cmd_schedule_admin(self.args('schedule-authorize'))
            output.flush()
        self.assertEqual(code, 3)
        self.assertIn(b'\\u2705', raw.getvalue())
        self.assertEqual(self.counts(), (0, 0))
