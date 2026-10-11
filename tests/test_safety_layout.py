"""G4 actual storage/runtime/identity compatibility under the offline guard."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    'ledger': 'relttk.storage.ledger',
    'ledger_requests': 'relttk.storage.ledger_requests',
    'ledger_migrations': 'relttk.storage.ledger_migrations',
    'queue_service': 'relttk.storage.queue_service',
    'worker': 'relttk.runtime.worker',
    'scheduling': 'relttk.runtime.scheduling',
    'rotation': 'relttk.runtime.rotation',
    'unknown_resolution': 'relttk.runtime.unknown_resolution',
    'circuit_breaker': 'relttk.identity.circuit_breaker',
    'identity_service': 'relttk.identity.identity_service',
    'readiness': 'relttk.identity.readiness',
}


class SafetyLayoutTests(unittest.TestCase):
    def child(self, code):
        prefix = 'import runpy,sys\nrunpy.run_path(' + repr(str(ROOT / 'tests/run_offline.py')) + ",run_name='fixture_guard')\n"
        prefix += 'sys.path.insert(0,' + repr(str(ROOT / 'tests')) + ')\n'
        prefix += 'TARGETS=' + repr(TARGETS) + '\n'
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-B', '-c', prefix + code],
                                    cwd=directory, capture_output=True, text=True,
                                    encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_all_eleven_legacy_first_identities(self):
        self.child('''import importlib
for legacy,target in TARGETS.items():
 old=importlib.import_module(legacy);canonical=importlib.import_module(target)
 assert old is canonical and old.__spec__.name==target
import ledger,ledger_requests,queue_service,worker,scheduling,identity_service,circuit_breaker
assert ledger_requests.ledger is ledger and queue_service.ledger is ledger
assert worker.requests is ledger_requests and scheduling.worker is worker
assert identity_service.cb is circuit_breaker
assert issubclass(scheduling.ScheduleHeld,worker.WorkerHeld)
assert issubclass(worker.WorkerHeld,queue_service.QueueHeld)
assert issubclass(queue_service.QueueHeld,ledger.LedgerError)
''')

    def test_all_eleven_canonical_first_identities(self):
        self.child('''import importlib
for legacy,target in TARGETS.items():
 canonical=importlib.import_module(target);old=importlib.import_module(legacy)
 assert old is canonical and old.__file__==canonical.__file__
from relttk.runtime import scheduling,worker
from relttk.storage import ledger_requests,queue_service
assert scheduling.requests is worker.requests is ledger_requests
assert scheduling.queue is worker.queue is queue_service
''')

    def test_inert_packages_and_single_initialization_for_all_eleven(self):
        self.child('''import relttk.storage,relttk.runtime,relttk.identity,sys,importlib
from pathlib import Path
assert all(target not in sys.modules for target in TARGETS.values())
executions=[]
def profile(frame,event,arg):
 name=Path(frame.f_code.co_filename).as_posix()
 if event=="call" and frame.f_code.co_name=="<module>" and any("/relttk/"+group+"/" in name for group in ("storage","runtime","identity")):
  executions.append(Path(name).stem)
sys.setprofile(profile)
for legacy,target in TARGETS.items():importlib.import_module(legacy);importlib.import_module(target)
sys.setprofile(None)
assert sorted(executions)==sorted(TARGETS)
''')

    def test_exception_identity_and_serialization_across_consumers(self):
        self.child('''import ledger,ledger_requests,queue_service,worker,pickle
from relttk.storage import ledger as l,ledger_requests as r,queue_service as q
from relttk.runtime import worker as w
for old,canonical,name,args in ((ledger,l,"SchemaError",("fixture",)),(ledger_requests,r,"IdempotencyConflict",("fixture",)),(queue_service,q,"QueueHeld",("HELD","fixture")),(worker,w,"WorkerHeld",("HELD","fixture"))):
 cls=getattr(old,name);assert cls is getattr(canonical,name)
 assert type(pickle.loads(pickle.dumps(cls(*args)))) is cls
assert w.ledger.LockError is l.LockError
''')

    def test_function_and_global_patches_reach_canonical_consumers(self):
        self.child('''import ledger,ledger_migrations,worker,ledger_requests,asyncio
from relttk.storage import ledger_requests as r
from relttk.application import services
from relttk.runtime import scheduling
from unittest.mock import patch
with patch.object(ledger,"_get_readwrite_connection",side_effect=ledger.SchemaError("fixture")) as opened:
 try:
  with r.transaction("fixture.db"):raise AssertionError("opened")
 except ledger.SchemaError:pass
 opened.assert_called_once_with("fixture.db")
with patch.object(worker,"TERMINAL",{"fixture"}):assert scheduling.worker.TERMINAL=={"fixture"}
with patch.object(ledger_requests,"DEFAULT_SETTINGS",{"fixture":1}):assert scheduling.requests.DEFAULT_SETTINGS=={"fixture":1}
with patch.object(worker,"status",return_value={"state":"fixture"}) as status:
 assert services.worker_status("fixture",db_path="fixture.db")=={"state":"fixture"}
 status.assert_called_once_with("fixture",db_path="fixture.db")
''')

    def test_repository_and_import_time_default_paths_from_other_cwd(self):
        code = '''import os
from pathlib import Path
root=Path(ROOT_VALUE)
runtime=Path.cwd()
os.environ["TIKTOK_RUNTIME_DIR"]=str(runtime)
import ledger
from relttk.storage import ledger as l
assert Path(l._REPO_DIR)==root
assert Path(l._DEFAULT_LEDGER_PATH)==runtime/"state"/"streak_ledger.db"
assert Path(l._DEFAULT_LOCK_PATH)==runtime/"state"/"run.lock"
os.environ["TIKTOK_RUNTIME_DIR"]=str(runtime/"later")
assert ledger is l
assert Path(l.RunLock().lock_path)==runtime/"state"/"run.lock"
assert Path(l.check_ready.__defaults__[0])==runtime/"state"/"streak_ledger.db"
assert not list(runtime.iterdir())
'''.replace('ROOT_VALUE', repr(str(ROOT)))
        self.child(code)

    def test_sqlite_wal_transaction_commit_and_rollback_via_aliases(self):
        self.child('''from pathlib import Path
from contextlib import closing
import sqlite3,ledger_migrations,ledger_requests
from relttk.storage import ledger as l,ledger_requests as r
db=Path.cwd()/"fixture.db"
ledger_migrations.initialize(db)
with closing(sqlite3.connect(db)) as conn:assert conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]=="wal"
try:
 with r.transaction(db) as conn:
  conn.execute("INSERT INTO rotation_state(canonical_uid,conv_id,campaign_id) VALUES('fixture','c','campaign')")
  raise RuntimeError("fixture rollback")
except RuntimeError:pass
with ledger_requests.transaction(db) as conn:
 assert conn.execute("SELECT count(*) FROM rotation_state").fetchone()[0]==0
 assert conn.execute("PRAGMA journal_mode").fetchone()[0]=="wal"
 conn.execute("INSERT INTO rotation_state(canonical_uid,conv_id,campaign_id) VALUES('fixture','c','campaign')")
with closing(sqlite3.connect(db)) as conn:
 assert conn.execute("SELECT count(*) FROM rotation_state").fetchone()[0]==1
 assert conn.execute("PRAGMA user_version").fetchone()[0]==ledger_migrations.VERSION
l.check_ready(db)
''')

    def test_shared_runlock_crash_unknown_and_idempotency(self):
        self.child('''from pathlib import Path
from ledger_fixtures import initialize_fixture,fixture_create,start_at
import ledger,ledger_requests
from relttk.storage import ledger as l,ledger_requests as r
db=Path.cwd()/"fixture.db";initialize_fixture(db)
row,created=fixture_create("fixture","c","key",{"message":"fixture"},db_path=db)
assert created
replay,created=fixture_create("fixture","c","key",{"message":"fixture"},db_path=db)
assert not created and replay["request_id"]==row["request_id"]
assert start_at(row["request_id"],db_path=db)
with ledger.RunLock(str(Path.cwd()/"run.lock")) as lock:
 assert isinstance(lock,l.RunLock)
 assert r.recover_pending(db_path=db,run_lock=lock)==1
 assert ledger_requests.recover_pending(db_path=db,run_lock=lock)==0
unknown=r.get_request(row["request_id"],db_path=db)
assert unknown["status"]=="failed_unknown" and unknown["transmission_started_at_ms"] is not None
replay,created=fixture_create("fixture","c","key",{"message":"fixture"},db_path=db)
assert not created and replay["status"]=="failed_unknown"
assert not start_at(row["request_id"],db_path=db)
''')

    def test_missing_database_readiness_never_initializes(self):
        self.child('''from relttk.storage import ledger,ledger_requests
from pathlib import Path
from unittest.mock import patch
import sqlite3
db=Path.cwd()/"missing.db"
with patch.object(sqlite3,"connect") as opened:
 try:ledger.check_ready(db)
 except ledger.LedgerError:pass
 else:raise AssertionError("missing DB accepted")
 opened.assert_not_called()
assert not db.exists() and not list(Path.cwd().iterdir())
''')

    def test_canonical_sources_and_all_eleven_aliases_are_scanned(self):
        from source_checks import source_paths
        paths = set(source_paths(ROOT))
        for name, target in TARGETS.items():
            self.assertIn(ROOT / (target.replace('.', '/') + '.py'), paths)
            self.assertIn(ROOT / 'relttk/compat/legacy' / (name + '.py'), paths)
            self.assertFalse((ROOT / (name + '.py')).exists())
