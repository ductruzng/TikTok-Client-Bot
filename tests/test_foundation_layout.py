"""Actual G1 canonical modules in fresh guarded processes."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FoundationLayoutTests(unittest.TestCase):
    def child(self, code, env=None):
        prefix = 'import runpy,sys\nrunpy.run_path(' + repr(str(ROOT / 'tests/run_offline.py')) + ",run_name='fixture_guard')\n"
        result = subprocess.run([sys.executable, '-B', '-c', prefix + code],
                                env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_real_legacy_first_modules_and_monkeypatch(self):
        self.child('import config,log,runtime_paths\nfrom relttk import config as c,log as l,runtime_paths as r\nassert config is c and log is l and runtime_paths is r\nassert runtime_paths.UnsafeRuntime is r.UnsafeRuntime\nfrom unittest.mock import patch\nwith patch.object(config,"OWN_USER_ID","fixture"): assert c.OWN_USER_ID=="fixture"\nwith patch.object(log,"_NO_COLOR",False): assert l._NO_COLOR is False\nwith patch.object(runtime_paths,"REPO","fixture"): assert r.REPO=="fixture"\n')

    def test_real_canonical_first_identity_reload_and_exception(self):
        self.child('from relttk import config as c,log as l,runtime_paths as r\nimport config,log,runtime_paths,importlib,pickle\nassert config is c and log is l and runtime_paths is r\nfor module in (c,l,r):\n assert importlib.reload(module) is module\n assert module.__spec__.name.startswith("relttk.")\nassert runtime_paths.UnsafeRuntime is r.UnsafeRuntime\nassert type(pickle.loads(pickle.dumps(r.UnsafeRuntime("fixture")))) is r.UnsafeRuntime\n')

    def test_explicit_bootstrap_is_inert_idempotent_and_conflict_safe(self):
        self.child('from relttk.compat import enable,TARGETS\nfrom pathlib import Path\nimport sys,types\nassert all(t not in sys.modules for t in TARGETS.values())\ncount=len(sys.path);enable();enable();assert len(sys.path)==count\nold=types.ModuleType("config");sys.modules["config"]=old\ntry:enable()\nexcept RuntimeError as exc: assert str(exc)=="LEGACY_IMPORT_CONFLICT"\nelse:raise AssertionError("conflict accepted")\nassert sys.modules["config"] is old\nassert "relttk.config" not in sys.modules\n')

    def test_config_and_log_keep_import_time_environment(self):
        env = dict(os.environ, TIKTOK_WS_AUTH_FILE='fixture-auth-name.json', NO_COLOR='1')
        self.child('from relttk import config,log\nimport os\nassert config.WS_AUTH_FILE=="fixture-auth-name.json"\nassert log._NO_COLOR\nos.environ["TIKTOK_WS_AUTH_FILE"]="later.json"\nos.environ.pop("NO_COLOR",None)\nassert config.WS_AUTH_FILE=="fixture-auth-name.json"\nassert log._NO_COLOR\n', env)

    def test_moved_root_and_private_refusal_with_synthetic_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp);base.chmod(0o700)
            code = 'from relttk import runtime_paths as p\nfrom pathlib import Path\n'
            code += 'assert p.REPO==Path(' + repr(str(ROOT)) + ')\nbase=Path(' + repr(tmp) + ')\nassert p.root(str(base))==base\n'
            code += 'for value in ("relative","",str(base/"..")):\n try:p.root(value)\n except p.UnsafeRuntime:pass\n else:raise AssertionError("unsafe root")\ntry:p.contained(base.parent/"outside.json",base=base,must_exist=False)\nexcept p.UnsafeRuntime:pass\nelse:raise AssertionError("outside root")\n'
            self.child(code)
            self.assertEqual(list(base.iterdir()), [])

    def test_real_canonical_and_alias_files_are_scanned(self):
        sys.path.insert(0, str(ROOT / 'tests'))
        try:
            from source_checks import source_paths
        finally:
            sys.path.pop(0)
        paths = set(source_paths(ROOT))
        for name in ('config', 'log', 'runtime_paths'):
            self.assertIn(ROOT / 'relttk' / (name + '.py'), paths)
            self.assertIn(ROOT / 'relttk/compat/legacy' / (name + '.py'), paths)
            self.assertFalse((ROOT / (name + '.py')).exists())
