"""Behavioral and AST inventory checks for legacy DM mutation entry points."""
import ast
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

import client
from source_checks import client_implementation
from client import LttkClient, UnsupportedSafetyOperation

LEGACY = ('send_message', 'send_video', 'send_reaction', 'delete_message',
          'delete_message_everyone', 'remove_reaction', 'run')


class LegacyClosureTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_legacy_entry_rejects_before_any_attribute_or_effect(self):
        # An uninitialized client proves the guards run before cookies/auth/plugin/socket access.
        bot = object.__new__(LttkClient)
        for method in LEGACY:
            with self.subTest(method=method), patch.object(client, 'build_ws_packet') as packet, \
                    patch.object(client, 'get_item_detail') as video, patch('websockets.connect', AsyncMock()) as connect:
                args = ('c', 'item') if method == 'send_video' else ()
                with self.assertRaises(UnsupportedSafetyOperation):
                    await getattr(bot, method)(*args)
                packet.assert_not_called(); video.assert_not_called(); connect.assert_not_called()

    async def test_socket_and_legacy_callbacks_cannot_be_used_through_mutations(self):
        bot = object.__new__(LttkClient)
        bot.websocket = AsyncMock()
        bot._load_session = AsyncMock()
        bot._load_plugins = AsyncMock()
        for name in LEGACY:
            with self.assertRaises(UnsupportedSafetyOperation):
                await getattr(bot, name)(*(['c', 'item'] if name == 'send_video' else []))
        bot.websocket.send.assert_not_called()
        bot._load_session.assert_not_called(); bot._load_plugins.assert_not_called()

    async def test_ast_inventory_keeps_all_legacy_sink_methods_guarded(self):
        source = client_implementation(Path(__file__).resolve().parents[1], client)
        tree = ast.parse(source.read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'LttkClient')
        methods = {n.name: n for n in cls.body if isinstance(n, ast.AsyncFunctionDef)}
        for name in LEGACY:
            first = methods[name].body[0]
            self.assertIsInstance(first, ast.Raise, name)
            self.assertEqual(first.exc.func.id, 'UnsupportedSafetyOperation')
        raw_sinks = []
        for name, method in methods.items():
            for call in ast.walk(method):
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == 'send':
                    raw_sinks.append(name)
        # Remaining private heartbeat is a control-frame loop reached from guarded run().
        self.assertEqual(set(raw_sinks), set(LEGACY) | {'_heartbeat'})

    async def test_pure_packet_builder_remains_available_to_managed_transport(self):
        from core.proto import build_ws_packet
        self.assertTrue(callable(build_ws_packet))
        self.assertTrue(callable(LttkClient.decode_echo_frame))
