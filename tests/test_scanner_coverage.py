"""Synthetic scanner canaries; absence of real relttk never skips coverage."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import source_checks


class ScannerCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, name, text='pass\n'):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
        return p

    def test_nested_canonical_canary_is_found_and_rejected(self):
        p = self.write('relttk/transport/deep/client.py', 'WS_ACCESS_KEY = None\n')
        self.assertIn(p, source_checks.source_paths(self.root))
        with self.assertRaisesRegex(AssertionError, 'Forbidden WS default'):
            source_checks.assert_ws_sources(self, source_checks.source_paths(self.root))

    def test_nested_alias_canary_is_found_and_rejected(self):
        p = self.write('relttk/compat/legacy/client.py', 'WS_ACCESS_KEY = None\n')
        self.assertIn(p, source_checks.source_paths(self.root))
        with self.assertRaisesRegex(AssertionError, 'Forbidden WS default'):
            source_checks.assert_ws_sources(self, source_checks.source_paths(self.root))

    def test_existing_allowlisted_roots_and_missing_future_root(self):
        expected = {self.write('main.py')}
        expected.update(self.write(name + '/nested/source.py') for name in source_checks.SOURCE_ROOTS if name != 'relttk')
        self.assertFalse((self.root / 'relttk').exists())
        self.assertEqual(set(source_checks.source_paths(self.root)), expected)
        source_checks.assert_ws_sources(self, expected)

    def test_private_and_unknown_roots_never_read(self):
        allowed = self.write('relttk/application/cli.py')
        for name in ('work/private.py', 'sesion/private.py', 'state/private.py',
                     'unknown/private.py', 'relttk/work/private.py',
                     'relttk/state/private.py', 'relttk/browser-profile/private.py'):
            self.write(name, 'this is not valid Python; must never be parsed')
        self.assertEqual(source_checks.source_paths(self.root), [allowed])
        source_checks.assert_ws_sources(self, source_checks.source_paths(self.root))

    def load_client(self, name):
        p = self.write(name, 'class LttkClient:\n    pass\n')
        spec = importlib.util.spec_from_file_location('g0_synthetic_client', p)
        module = importlib.util.module_from_spec(spec)
        prior = sys.modules.get(spec.name)
        sys.modules[spec.name] = module
        def restore():
            if prior is None:
                sys.modules.pop(spec.name, None)
            else:
                sys.modules[spec.name] = prior
        self.addCleanup(restore)
        spec.loader.exec_module(module)
        return p, module

    def test_future_implementation_not_root_alias_is_inspected(self):
        self.write('client.py', '# alias only\n')
        p, module = self.load_client('relttk/transport/client.py')
        self.assertEqual(source_checks.client_implementation(self.root, module), p)

    def test_wrapper_file_cannot_substitute_for_canonical_class(self):
        wrapper = self.write('client.py', '# alias only\n')
        _, module = self.load_client('relttk/transport/client.py')
        module.__file__ = str(wrapper)
        with self.assertRaisesRegex(AssertionError, 'canonical implementation'):
            source_checks.client_implementation(self.root, module)

    def test_missing_canonical_source_is_rejected(self):
        p, module = self.load_client('relttk/transport/client.py')
        p.unlink()
        with self.assertRaises(AssertionError):
            source_checks.client_implementation(self.root, module)

    def test_excluded_canonical_source_is_rejected(self):
        _, module = self.load_client('relttk/transport/client.py')
        with patch.object(source_checks, 'source_paths', return_value=[]):
            with self.assertRaisesRegex(AssertionError, 'excluded'):
                source_checks.client_implementation(self.root, module)
