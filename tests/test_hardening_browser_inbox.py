"""Fake browser lifecycle and disposable bounded children; no real auth/network."""
import json
import multiprocessing
from pathlib import Path
import sys
import tempfile
import time
import types
from urllib.parse import urlencode
import unittest
from unittest.mock import MagicMock, patch

from relttk.transport import ws_auth_capture as capture, bounded_inbox as inbox
from deploy import render_units


def slow_child(output, cookies, device_id):
    time.sleep(30)


def successful_child(output, cookies, device_id):
    output.send_bytes(json.dumps([{'conv_id':'fixture'}]).encode())
    output.close()


class BrowserInboxTests(unittest.TestCase):
    def browser(self):
        playwright = MagicMock()
        browser = playwright.chromium.launch.return_value
        context = browser.new_context.return_value
        context.pages = []
        module = types.ModuleType('playwright.sync_api')
        factory = MagicMock()
        factory.return_value.__enter__.return_value = playwright
        module.sync_playwright = factory
        return module, playwright, browser, context

    def test_context_creation_failure_closes_browser_without_cookie_output(self):
        module, playwright, browser, context = self.browser()
        browser.new_context.side_effect = RuntimeError('synthetic')
        with patch.dict(sys.modules, {'playwright.sync_api':module}), self.assertRaises(RuntimeError):
            capture.capture_for_cookies({'sessionid':'synthetic'})
        browser.close.assert_called_once()
        playwright.chromium.launch.assert_called_once_with(headless=True, timeout=15_000)

    def test_cookie_injection_failure_closes_context_and_browser(self):
        module, _, browser, context = self.browser()
        context.add_cookies.side_effect = RuntimeError('synthetic')
        with patch.dict(sys.modules, {'playwright.sync_api':module}), self.assertRaises(RuntimeError):
            capture.capture_for_cookies({'sessionid':'synthetic'})
        context.close.assert_called_once(); browser.close.assert_called_once()

    def test_navigation_failure_and_timeout_close_every_resource(self):
        module, _, browser, context = self.browser()
        context.new_page.return_value.goto.side_effect = TimeoutError('synthetic')
        with patch.dict(sys.modules, {'playwright.sync_api':module}), self.assertRaises(TimeoutError):
            capture.capture_for_cookies({'sessionid':'synthetic'})
        context.close.assert_called_once(); browser.close.assert_called_once()

    def test_cdp_pair_requires_101_frames_and_no_conflicting_candidate(self):
        for mode in ('valid', 'no-handshake', 'no-frames', 'error', 'conflict', 'malformed'):
            with self.subTest(mode=mode):
                module, _, browser, context = self.browser()
                page=MagicMock(); context.pages=[page]
                callbacks={}
                context.new_cdp_session.return_value.on.side_effect=lambda event,fn:callbacks.setdefault(event,fn)
                def events(_):
                    for rid,key in [('one','a'*32)]+([('two','b'*32)] if mode=='conflict' else []):
                        query=urlencode({'ttwid':'1|fixture|1|aa','access_key':key if mode!='malformed' else 'bad'})
                        callbacks['Network.webSocketCreated']({'requestId':rid,'url':'wss://im-ws-sg.tiktok.com/ws/v2?'+query})
                        callbacks['Network.webSocketHandshakeResponseReceived']({'requestId':rid,'response':{'status':400 if mode=='no-handshake' else 101}})
                        if mode!='no-frames':
                            for event in ('Network.webSocketFrameSent','Network.webSocketFrameReceived'):
                                callbacks[event]({'requestId':rid})
                        if mode=='error': callbacks['Network.webSocketFrameError']({'requestId':rid})
                page.wait_for_timeout.side_effect=events
                with patch.dict(sys.modules,{'playwright.sync_api':module}):
                    result=capture.capture_for_cookies({'sessionid':'synthetic'})
                self.assertEqual(result,('1|fixture|1|aa','a'*32) if mode=='valid' else None)
                context.close.assert_called_once();browser.close.assert_called_once()

    def test_preflight_never_launches_browser(self):
        module, playwright, browser, context = self.browser()
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp)/'fixture-executable'; executable.touch()
            playwright.chromium.executable_path = str(executable)
            with patch.dict(sys.modules, {'playwright.sync_api':module}):
                self.assertEqual(capture.browser_preflight()['state'], 'LOCAL_READY')
            playwright.chromium.launch.assert_not_called(); context.add_cookies.assert_not_called()

    def test_missing_optional_dependency_is_sanitized(self):
        with patch.dict(sys.modules, {'playwright.sync_api':None}):
            self.assertEqual(capture.browser_preflight()['reason'], 'PLAYWRIGHT_NOT_INSTALLED')

    def test_inbox_child_deadline_terminates_and_reaps(self):
        before = {p.pid for p in multiprocessing.active_children()}
        started = time.monotonic()
        with patch.object(inbox, '_collect', slow_child), self.assertRaises(TimeoutError):
            inbox.fetch({'sessionid':'synthetic'}, timeout=0.5)
        self.assertLess(time.monotonic()-started, 5)
        self.assertEqual(before, {p.pid for p in multiprocessing.active_children()})

    def test_inbox_child_exact_result_no_credentials_on_disk_or_output(self):
        with patch.object(inbox, '_collect', successful_child):
            self.assertEqual(inbox.fetch({'sessionid':'synthetic'}, timeout=10), [{'conv_id':'fixture'}])

    def test_missing_auth_and_invalid_deadline_start_no_process(self):
        with patch.object(inbox.multiprocessing, 'get_context') as ctx:
            for cookies in ({}, None, {'sessionid':123}):
                with self.assertRaises(ValueError): inbox.fetch(cookies)
            for timeout in (0, -1, True, 46):
                with self.assertRaises(ValueError): inbox.fetch({'sessionid':'synthetic'},timeout=timeout)
            ctx.assert_not_called()

    def test_two_target_profile_matches_explicit_budget_and_cooldown(self):
        consent = dict(policy={'targets':[{},{}]}, daily_budget=2, max_wait=300,window_minutes=60,time='08:00')
        profile = render_units.workload(consent)
        self.assertEqual(profile['recipients'], 2)
        self.assertLess(profile['profile_seconds'], profile['startup_seconds'])
        for update in ({'daily_budget':1}, {'window_minutes':10}, {'time':'23:50'}, {'max_wait':30},
                       {'policy':{'targets':[{},{}], 'min_send_interval_seconds':301}}):
            with self.subTest(update=update),self.assertRaises(ValueError):
                render_units.workload({**consent, **update})

    def test_two_target_unit_does_not_enable_service_or_retry(self):
        consent = dict(policy={'targets':[{},{}]}, daily_budget=2,max_wait=300,window_minutes=60,time='08:00')
        units = render_units.unit_text(consent, grant_id='a'*32,fingerprint='b'*64,
            python='/opt/relttk/python',entry='/opt/relttk/operational_entry.py',runtime='/var/lib/relttk',db='/var/lib/relttk/state/db')
        service = units['relttk-'+'a'*32+'.service']
        self.assertIn('TimeoutStartSec=900', service)
        self.assertIn('Restart=no', service)
