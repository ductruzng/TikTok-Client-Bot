"""Disposable audit-path fixtures; never open actual protected runtime files."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OfflineGuardTests(unittest.TestCase):
    def child(self, code):
        prefix = 'import runpy,sys\ng=runpy.run_path(' + repr(str(ROOT / 'tests/run_offline.py')) + ",run_name='fixture_guard')\n"
        result = subprocess.run([sys.executable, '-B', '-c', prefix + code],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_synthetic_dir_fd_path_is_not_interpreted_relative_to_cwd(self):
        self.child('''from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
import stat,tempfile
with tempfile.TemporaryDirectory() as d:
 with patch.object(g['os'],'fstat',return_value=SimpleNamespace(st_mode=stat.S_IFDIR)),patch.object(g['os'],'readlink',return_value=d):
  path=g['open_path']('state',17)
 assert path==Path(d)/'state' and path!=g['ROOT']/'state'
 token=g['_open_context'].set(('state',path))
 try:g['guard']('open',('state',None,0))
 finally:g['_open_context'].reset(token)
''')

    def test_synthetic_private_relative_and_traversal_paths_are_refused(self):
        self.child('''from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
import stat,tempfile
with tempfile.TemporaryDirectory() as d:
 root=Path(d);private=root/'private';private.mkdir();safe=root/'safe';safe.mkdir()
 g['protected'].append(private)
 for base,raw in [(str(private),'secret.json'),(str(safe),'../private/secret.json')]:
  with patch.object(g['os'],'fstat',return_value=SimpleNamespace(st_mode=stat.S_IFDIR)),patch.object(g['os'],'readlink',return_value=base):
   path=g['open_path'](raw,17)
  token=g['_open_context'].set((raw,path))
  try:
   try:g['guard']('open',(raw,None,0))
   except RuntimeError:pass
   else:raise AssertionError('private path admitted')
  finally:g['_open_context'].reset(token)
 g['protected'].remove(private)
''')

    def test_unresolved_or_deleted_descriptor_fails_closed(self):
        self.child('''from unittest.mock import patch
from types import SimpleNamespace
import stat
for base in [OSError('fixture'),'relative','/fixture (deleted)']:
 with patch.object(g['os'],'fstat',return_value=SimpleNamespace(st_mode=stat.S_IFDIR)),patch.object(g['os'],'readlink',**({'side_effect':base} if isinstance(base,Exception) else {'return_value':base})):
  try:g['open_path']('state',17)
  except RuntimeError:pass
  else:raise AssertionError('unresolved descriptor admitted')
''')

    def test_context_resets_after_open_failure_and_network_stays_blocked(self):
        self.child('''from unittest.mock import patch
import tempfile
from pathlib import Path
with tempfile.TemporaryDirectory() as d:
 try:g['guarded_open'](str(Path(d)/'missing'),0)
 except FileNotFoundError:pass
 else:raise AssertionError('missing opened')
 assert g['_open_context'].get() is None
for event,args in [('socket.getaddrinfo',('fixture.invalid',443)),('socket.connect',(None,('192.0.2.1',443)))]:
 try:g['guard'](event,args)
 except RuntimeError:pass
 else:raise AssertionError('network admitted')
''')

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires native Linux dir_fd and /proc/self/fd')
    def test_native_dir_fd_cleanup_and_private_refusal(self):
        self.child('''import os,tempfile
from pathlib import Path
with tempfile.TemporaryDirectory() as d:
 root=Path(d);(root/'state').mkdir();private=root/'private';private.mkdir()
 g['protected'].append(private)
 fd=os.open(root,os.O_RDONLY)
 try:
  child=os.open('state',os.O_RDONLY,dir_fd=fd);os.close(child)
  try:os.open('private',os.O_RDONLY,dir_fd=fd)
  except RuntimeError:pass
  else:raise AssertionError('private opened')
 finally:os.close(fd)
 g['protected'].remove(private)
# TemporaryDirectory.cleanup uses native descriptor-relative rmtree here.
''')

    def test_ambiguous_cached_low_level_relative_open_is_refused(self):
        self.child('''try:g['guard']('open',('fixture',None,0))
except RuntimeError:pass
else:raise AssertionError('ambiguous low-level path admitted')
''')

    def test_cookie_fixture_preloads_platform_sensitive_stdlib(self):
        self.child('''import shutil,sqlite3,tempfile
from unittest.mock import patch
with patch.object(sys,'platform','win32'):
 import tools.browsercookies
''')

    def test_scheduler_refusal_source_does_not_require_textual(self):
        # Keep core-only static coverage; full fixture additionally executes TUI.
        import ast
        tree = ast.parse((ROOT / 'relttk/application/tui.py').read_text(encoding='utf-8-sig'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'TikTokTUI')
        self.assertFalse(any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == '_check_schedule' for n in cls.body))
        fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_run_send')
        gate = fn.body[0]
        self.assertIsInstance(gate, ast.If)
        self.assertEqual(ast.unparse(gate.test), "source == 'Scheduler'")
        self.assertIsInstance(gate.body[-1], ast.Return)
