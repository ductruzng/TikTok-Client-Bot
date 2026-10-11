"""G5 canonical operations identity and guarded offline administration fixtures."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OperationsLayoutTests(unittest.TestCase):
    def child(self, code):
        prefix = 'import runpy,sys\nrunpy.run_path(' + repr(str(ROOT / 'tests/run_offline.py')) + ",run_name='fixture_guard')\n"
        prefix += 'sys.path.insert(0,' + repr(str(ROOT / 'tests')) + ')\n'
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-B', '-c', prefix + code],
                                    cwd=directory, capture_output=True, text=True,
                                    encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_legacy_first_shared_identity(self):
        self.child('''import operations
import relttk.operations as canonical
assert operations is canonical and operations.__spec__.name=='relttk.operations'
from pathlib import Path
assert Path(operations.__file__).parent.name=='relttk'
''')

    def test_canonical_first_and_single_initialization(self):
        self.child('''calls=[]
def trace(frame,event,arg):
 if event=='call' and frame.f_code.co_name=='<module>' and frame.f_globals.get('__name__')=='relttk.operations':calls.append(1)
sys.setprofile(trace)
import relttk.operations as canonical
import operations
sys.setprofile(None)
assert canonical is operations and calls==[1]
''')

    def test_monkeypatch_and_metadata_state_shared_with_services(self):
        self.child('''from unittest.mock import patch
import operations
from relttk.application import services
import relttk.operations as canonical
with patch.object(operations,'status',return_value={'state':'BLOCKED'}) as mocked:
 assert services.operational_status('fixture',db_path='synthetic.db')=={'state':'BLOCKED'}
 mocked.assert_called_once()
operations.note({'state':'COMPLETE','cookie':'SYNTHETIC_PRIVATE_SENTINEL'})
assert canonical._result=={'state':'COMPLETE','identity':'IDENTITY_CONTRACT_BLOCKED'}
''')

    def test_conflicting_legacy_module_is_refused(self):
        self.child('''import types
from relttk.compat import enable
sys.modules['operations']=types.ModuleType('operations')
try:enable()
except RuntimeError as exc:assert str(exc)=='LEGACY_IMPORT_CONFLICT'
else:raise AssertionError('conflict accepted')
''')

    def test_canonical_import_error_is_silent_after_entry_mute(self):
        self.child('''from pathlib import Path
import subprocess,tempfile
with tempfile.TemporaryDirectory() as d:
 stage=Path(d);pkg=stage/'relttk';pkg.mkdir();(pkg/'__init__.py').write_text('')
 compat=pkg/'compat';compat.mkdir();(compat/'__init__.py').write_text('def enable():pass\\n')
 entry=Path(sys.path[1])/'operational_entry.py'
 # Locate the reviewed entry through the runner's unchanged repository anchor.
 import source_checks
 entry=Path(source_checks.__file__).parents[1]/'operational_entry.py'
 (stage/'operational_entry.py').write_bytes(entry.read_bytes())
 for body in (None,'print("SYNTHETIC_PRIVATE_SENTINEL")\\nraise RuntimeError("SYNTHETIC_PRIVATE_SENTINEL")\\n','invalid syntax !!!\\n'):
  p=pkg/'operations.py'
  if body is not None:p.write_text(body)
  env={k:v for k,v in __import__('os').environ.items() if k!='PYTHONPATH'}
  guard='import runpy;runpy.run_path('+repr(str(entry.parent/'tests/run_offline.py'))+',run_name="fixture_guard");'
  guard+='import sys;[sys.modules.pop(k) for k in list(sys.modules) if k=="relttk" or k.startswith("relttk.")];sys.path.insert(0,'+repr(str(stage))+');'
  guard+='sys.argv=["operational_entry.py","operational-status","--operational-output"];runpy.run_path('+repr(str(stage/'operational_entry.py'))+',run_name="__main__")'
  result=subprocess.run([sys.executable,'-B','-c',guard],cwd=stage,env=env,capture_output=True,timeout=10)
  assert result.returncode==3 and result.stdout+result.stderr==b'',result
''')

    def test_status_absent_fixture_and_alternate_cwd_no_creation(self):
        self.child('''from pathlib import Path
import relttk.operations as operations
from relttk.runtime_paths import REPO
assert (REPO/'main.py').is_file()
missing=Path.cwd()/'missing.db'
assert operations.status('fixture',db_path=missing)=={'state':'UNKNOWN','reason':'LOCAL_CHECK_FAILED'}
assert not missing.exists()
''')

    def test_explicit_backup_fixture_preserves_history_and_source(self):
        self.child('''from pathlib import Path
from contextlib import closing
import sqlite3
import operations
import relttk.operations as canonical
from relttk.storage import ledger_migrations as migrations
db=Path.cwd()/'fixture.db';dest=Path.cwd()/'copy.db'
migrations.initialize(db)
with closing(sqlite3.connect(db)) as conn:conn.execute('PRAGMA journal_mode=DELETE')
before=db.read_bytes()
assert operations.backup(db,dest)['state']=='BACKUP_COMPLETE'
assert db.read_bytes()==before
with closing(sqlite3.connect(db)) as source,closing(sqlite3.connect(dest)) as target:
 assert canonical._history_counts(source)==operations._history_counts(target)
 assert target.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
 migrations.validate_schema(target)
try:canonical.backup(db,dest)
except ValueError:pass
else:raise AssertionError('destination overwrite accepted')
''')

    def test_scanner_finds_canonical_and_alias_without_root_copy(self):
        self.child('''from pathlib import Path
from source_checks import source_paths
root=Path(__import__('source_checks').__file__).parents[1]
paths=source_paths(root)
assert root/'relttk/operations.py' in paths
assert root/'relttk/compat/legacy/operations.py' in paths
assert not (root/'operations.py').exists()
''')
