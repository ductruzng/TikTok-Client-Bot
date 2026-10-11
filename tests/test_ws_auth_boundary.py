"""Synthetic-only authentication boundary regressions; no credential files."""
import ast
import asyncio
import hashlib
from pathlib import Path
import re
import unittest
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

import client
import config
import oneshot


class WSAuthBoundaryTests(unittest.TestCase):
    def test_no_implicit_upstream_default(self):
        self.assertFalse(hasattr(config, 'WS_ACCESS_KEY'))
        with patch.object(config, 'WS_ACCESS_KEY', 'a' * 32, create=True):
            with self.assertRaises(ValueError):
                client.build_ws_url({'ttwid': '1|fixture|1|aa'})

    def test_missing_empty_and_invalid_key_refused_without_echoing_input(self):
        for key in (None, '', False, 123, b'a' * 32, 'a' * 31, 'g' * 32,
                    'a' * 33, 'a' * 32 + '\n', ' ' + 'a' * 32, 'a&ttwid=x'):
            with self.subTest(type=type(key).__name__), self.assertRaises(ValueError) as caught:
                client.build_ws_url({'ttwid': '1|fixture|1|aa'}, access_key=key)
            self.assertEqual(str(caught.exception), 'Explicit browser-issued 32-hex WS access key required')

    def test_session_bound_pair_produces_expected_url_and_cookie(self):
        cookies = {'sessionid': 'synthetic-session', 'ttwid': '1|old|1|aa'}
        auth = client.validate_ws_auth({
            'session': 'fixture',
            'session_hash': hashlib.sha256(cookies['sessionid'].encode()).hexdigest(),
            'ttwid': '1%7Cfixture%7C123%7Cab', 'access_key': 'AB' * 16,
        }, session_name='fixture', cookies=cookies)
        with patch.object(oneshot, 'load_ws_auth', return_value=auth) as load:
            ws_cookies, url = oneshot._prepare_ws(cookies, 'fixture')
        load.assert_called_once_with(session_name='fixture', cookies=cookies)
        self.assertEqual(ws_cookies['ttwid'], '1|fixture|123|ab')
        params = parse_qs(urlsplit(url).query)
        self.assertEqual(params['access_key'], ['ab' * 16])
        self.assertEqual(params['ttwid'], [ws_cookies['ttwid']])
        self.assertNotIn('synthetic-session', url)
        self.assertEqual(cookies['ttwid'], '1|old|1|aa')

    def test_wrong_session_binding_refused(self):
        with self.assertRaises(ValueError):
            client.validate_ws_auth({'session': 'other', 'session_hash': 'a' * 64,
                                     'ttwid': '1|fixture|1|aa', 'access_key': 'a' * 32},
                                    session_name='fixture', cookies={'sessionid': 'synthetic'})

    def test_missing_or_invalid_ttwid_refused(self):
        for ttwid in (None, '', 123, 'bad', '1|fixture|1|aa\n', '1|fixture|1|aa&extra=bad'):
            with self.subTest(type=type(ttwid).__name__), self.assertRaises(ValueError):
                client.build_ws_url({'ttwid': ttwid}, access_key='a' * 32)

    def test_url_and_extra_params_cannot_supply_or_override_auth(self):
        for query in ('access_key=', 'access_key=' + 'b' * 32,
                      'access%5Fkey=' + 'b' * 32, 'ACCESS_KEY=x', 'ttwid=x',
                      'TTWID=x', 'access_key=x&access_key=y'):
            with self.subTest(query_name=query.split('=')[0]):
                with self.assertRaises(ValueError):
                    client.build_ws_url({'ttwid': '1|fixture|1|aa'},
                                        'wss://im-ws-sg.tiktok.com/ws/v2?' + query, 'a' * 32)
                with patch.object(config, 'WS_EXTRA_PARAMS', query), self.assertRaises(ValueError):
                    client.build_ws_url({'ttwid': '1|fixture|1|aa'}, access_key='a' * 32)

    def test_no_websocket_opened_without_valid_auth(self):
        async def connect_after_prepare():
            cookies, url = oneshot._prepare_ws({'ttwid': '1|fixture|1|aa'}, 'fixture')
            await oneshot._open_ws(cookies, url)
        for auth in ({}, {'ttwid': '1|fixture|1|aa', 'access_key': ''},
                     {'ttwid': '1|fixture|1|aa', 'access_key': 'bad'}):
            with patch.object(oneshot, 'load_ws_auth', return_value=auth), \
                    patch('websockets.connect', AsyncMock()) as connect, \
                    patch.object(oneshot._log, 'error'):
                with self.assertRaises(ValueError):
                    asyncio.run(connect_after_prepare())
                connect.assert_not_called()

    def test_unrelated_query_values_cannot_suppress_explicit_auth(self):
        url = client.build_ws_url({'ttwid': '1|fixture|1|aa'},
                                  'wss://im-ws-sg.tiktok.com/ws/v2?note=access_key=&other=ttwid=',
                                  'a' * 32)
        params = parse_qs(urlsplit(url).query)
        self.assertEqual(params['access_key'], ['a' * 32])
        self.assertEqual(params['ttwid'], ['1|fixture|1|aa'])

    def test_legacy_run_still_refuses_before_auth_or_socket(self):
        with patch.object(client, 'load_ws_auth') as load, \
                patch('websockets.connect', AsyncMock()) as connect:
            with self.assertRaises(client.UnsupportedSafetyOperation):
                asyncio.run(object.__new__(client.LttkClient).run())
            load.assert_not_called()
            connect.assert_not_called()

    def test_static_source_has_no_embedded_ws_key(self):
        root = Path(__file__).resolve().parents[1]
        paths = list(root.glob('*.py'))
        for directory in ('core', 'signers', 'plugins', 'deploy', 'tests'):
            paths.extend((root / directory).rglob('*.py'))
        for path in paths:
            tree = ast.parse(path.read_text(encoding='utf-8-sig'))
            for node in ast.walk(tree):
                names = []
                value = None
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    names = [t.id for t in targets if isinstance(t, ast.Name)]
                    value = node.value
                if any(n.upper() == 'WS_ACCESS_KEY' for n in names):
                    self.fail(f'Forbidden WS default assignment: {path.name}:{node.lineno}')
                if path.parent.name != 'tests' and any(n.lower() == 'access_key' for n in names) and isinstance(value, ast.Constant):
                    self.assertFalse(bool(value.value), f'Embedded key: {path.name}:{node.lineno}')
                if path.parent.name != 'tests' and isinstance(node, ast.Dict):
                    for k, v in zip(node.keys, node.values):
                        if isinstance(k, ast.Constant) and k.value == 'access_key' and isinstance(v, ast.Constant):
                            self.assertFalse(bool(v.value), f'Embedded key: {path.name}:{node.lineno}')
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    self.assertIsNone(re.search(r'access_key=[0-9a-fA-F]{32}(?:&|$)', node.value),
                                      f'Embedded URL key: {path.name}:{node.lineno}')
