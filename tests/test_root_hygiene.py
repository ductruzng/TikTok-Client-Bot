"""Phase5E manual-tool imports use synthetic SDKs and no credential access."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RootHygieneTests(unittest.TestCase):
    def child(self, code):
        prefix = 'import runpy,sys\nrunpy.run_path(' + repr(str(ROOT / 'tests/run_offline.py')) + ",run_name='fixture_guard')\n"
        prefix += 'sys.path.insert(0,' + repr(str(ROOT / 'tests')) + ')\n'
        with tempfile.TemporaryDirectory() as cwd:
            result = subprocess.run([sys.executable, '-B', '-c', prefix + code],
                                    cwd=cwd, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_tools_initializer_has_no_side_effect_imports(self):
        self.child('''import tools
assert 'tools.browsercookies' not in sys.modules
assert 'tools.test_ws_capture' not in sys.modules
''')

    def test_capture_script_import_preserves_profile_without_execution(self):
        self.child('''import types
from pathlib import Path
sdk=types.ModuleType('playwright.sync_api')
def forbidden():raise AssertionError('browser must not run')
sdk.sync_playwright=forbidden
sys.modules['playwright']=types.ModuleType('playwright')
sys.modules['playwright.sync_api']=sdk
import tools.test_ws_capture as tool
from relttk.runtime_paths import REPO
assert tool.ROOT==REPO and tool.PROFILE_DIR==REPO/'work/tiktok-browser-profile'
assert tool.has_cookie('fixture=a; ttwid=synthetic','ttwid')
assert not tool.has_cookie('fixture=a','ttwid')
script=runpy.run_path(str(REPO/'tools/test_ws_capture.py'),run_name='manual_import_fixture')
assert script['ROOT']==REPO
''')

    def test_cookie_helper_import_with_windows_platform_only(self):
        self.child('''from unittest.mock import patch
with patch.object(sys,'platform','win32'):
 import tools.browsercookies as tool
assert callable(tool.get_tiktok_cookies)
assert callable(tool._read_firefox)
# No extraction function is called; importing has no filesystem read.
''')

    def test_scanner_covers_tools_and_rejects_nested_key_canary(self):
        self.child('''import tempfile
from pathlib import Path
from source_checks import source_paths,assert_ws_sources
import unittest
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'tools/nested/canary.py';p.parent.mkdir(parents=True)
 p.write_text('WS_ACCESS_KEY = None\\n')
 assert p in source_paths(d)
 try:assert_ws_sources(unittest.TestCase(),source_paths(d))
 except AssertionError:pass
 else:raise AssertionError('scanner missed canary')
''')

    def test_dependency_files_and_diagnostic_paths(self):
        for name in ('tui', 'auth-windows', 'windows'):
            self.assertTrue((ROOT / 'requirements' / (name + '.txt')).is_file())
            self.assertFalse((ROOT / ('requirements-' + name + '.txt')).exists())
        self.assertTrue((ROOT / 'requirements.txt').is_file())
        main = (ROOT / 'main.py').read_text(encoding='utf-8-sig')
        self.assertIn('requirements/tui.txt', main)
        self.assertIn('requirements/auth-windows.txt', main)
        self.assertFalse((ROOT / 'browsercookies.py').exists())
        self.assertFalse((ROOT / 'test_ws_capture.py').exists())

    def test_ignore_rules_cover_synthetic_private_artifact_names(self):
        # Verify literal coverage without Git commands or real private paths.
        rules = set((ROOT / '.gitignore').read_text(encoding='utf-8').splitlines())
        for rule in ('work/', 'state/', 'sesion/', 'sessions/', '*.local.json',
                     '.env', '.env.*', '.uid_cache.json', 'ws_auth*.json',
                     'auth*.json', 'credentials*.json', 'cookies*.json',
                     'browser-profiles/', '/browser-profile/', '*.sqlite3',
                     '*.sqlite3-wal', '*.sqlite3-shm', '*.db', '*.db-wal', '*.db-shm'):
            self.assertIn(rule, rules)
