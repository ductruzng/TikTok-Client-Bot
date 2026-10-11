"""G0 toy compatibility and real pre-move path/output contracts, offline only."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SourceLayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def write(self, name, text):
        p = self.base / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
        return p

    def child(self, code, *, toy=False, env=None, expected=0):
        prefix = 'import runpy,sys\nrunpy.run_path(' + repr(str(ROOT / 'tests/run_offline.py')) + ",run_name='fixture_guard')\n"
        if toy:
            prefix += 'sys.path=[p for p in sys.path if p != ' + repr(str(ROOT)) + ' and p != ' + repr(str(ROOT / 'relttk/compat/legacy')) + ']\n'
            prefix += 'sys.path.insert(0,' + repr(str(self.base)) + ')\n'
        result = subprocess.run([sys.executable, '-B', '-c', prefix + code],
                                cwd=self.base, env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, expected, result.stderr)
        return result

    def package(self):
        # A toy package in a disposable directory, not the production g0_layout_fixture.
        self.write('g0_layout_fixture/__init__.py', '')
        self.write('g0_layout_fixture/application/__init__.py', '')
        self.write('g0_layout_fixture/transport/__init__.py', '')
        self.write('g0_layout_fixture/application/cli.py', 'CONFIG_PATH="initial"\nSTATE=[]\nclass Failure(Exception): pass\ndef current(): return CONFIG_PATH\n')
        self.write('g0_layout_fixture/application/services.py', 'from g0_layout_fixture.application import cli\ndef send_plan(): return cli.current()\n')
        self.write('g0_layout_fixture/transport/oneshot.py', 'from g0_layout_fixture.application import services\ndef send(): return services.send_plan()\n')
        targets = {'cli': 'g0_layout_fixture.application.cli', 'services': 'g0_layout_fixture.application.services', 'oneshot': 'g0_layout_fixture.transport.oneshot'}
        for name, target in targets.items():
            self.write('legacy/' + name + '.py', 'import importlib,sys\nsys.modules[__name__]=importlib.import_module(' + repr(target) + ')\n')
        self.write('fixture_bootstrap.py', 'import sys\nfrom pathlib import Path\nTARGETS=' + repr(targets) + '\ndef enable():\n for name,target in TARGETS.items():\n  old=sys.modules.get(name)\n  if old is not None and old is not sys.modules.get(target): raise RuntimeError("ALIAS_CONFLICT")\n path=str(Path(__file__).parent/"legacy")\n if path not in sys.path: sys.path.insert(0,path)\n')

    def test_alias_first_identity_singleton_and_monkeypatch(self):
        self.package()
        self.child('from fixture_bootstrap import enable\nenable()\nimport cli,services,oneshot\nfrom g0_layout_fixture.application import cli as canonical\nassert cli is canonical\nassert cli.Failure is canonical.Failure\ncli.STATE.append(1)\nassert canonical.STATE==[1]\nfrom unittest.mock import patch\nwith patch.object(cli,"CONFIG_PATH","patched"): assert oneshot.send()=="patched"\nwith patch.object(services,"send_plan",return_value="service-patch"): assert oneshot.send()=="service-patch"\n', toy=True)

    def test_canonical_first_reload_and_class_identity(self):
        self.package()
        self.child('from g0_layout_fixture.application import cli as canonical\nfrom fixture_bootstrap import enable\nenable()\nimport cli,importlib\nassert cli is canonical\nold=cli.Failure\nassert cli.__spec__.name=="g0_layout_fixture.application.cli"\nassert importlib.reload(cli) is canonical\nassert cli.Failure is canonical.Failure and cli.Failure is not old\nassert cli.STATE==[]\n', toy=True)

    def test_no_duplicate_import_execution_for_two_names(self):
        self.package()
        self.write('g0_layout_fixture/application/cli.py', 'from pathlib import Path\np=Path(__file__).parents[2]/"count"\np.write_text(str(int(p.read_text())+1) if p.exists() else "1")\n')
        self.child('from fixture_bootstrap import enable\nenable()\nimport cli\nfrom g0_layout_fixture.application import cli as canonical\nfrom pathlib import Path\nassert cli is canonical\nassert Path("count").read_text()=="1"\n', toy=True)

    def test_explicit_enable_is_required_and_idempotent(self):
        self.package()
        self.child('import importlib.util,sys\nassert importlib.util.find_spec("cli") is None\nfrom fixture_bootstrap import enable\nenable();enable()\nfrom pathlib import Path\nassert sys.path.count(str(Path("legacy").resolve()))==1\nimport cli\nassert cli.__name__=="g0_layout_fixture.application.cli"\n', toy=True)

    def test_conflict_is_not_overwritten(self):
        self.package()
        self.child('import sys,types\nfrom fixture_bootstrap import enable\nold=types.ModuleType("cli");sys.modules["cli"]=old\ntry: enable()\nexcept RuntimeError as exc: assert str(exc)=="ALIAS_CONFLICT"\nelse: raise AssertionError("conflict allowed")\nassert sys.modules["cli"] is old\n', toy=True)

    def test_real_file_roots_and_environment_capture_in_fresh_process(self):
        runtime = self.base / 'runtime'
        runtime.mkdir(mode=0o700)
        env = dict(os.environ, TIKTOK_RUNTIME_DIR=str(runtime))
        code = 'import runtime_paths,services,ledger,qrlogin,client,os\nfrom pathlib import Path\n'
        code += 'root=Path(' + repr(str(ROOT)) + ')\nruntime=Path(' + repr(str(runtime)) + ')\n'
        code += 'assert runtime_paths.REPO==root and services.ROOT==root\nassert services.CONFIG_PATH==runtime/"streak.local.json"\nassert services.PREFS_PATH==runtime/"work"/"tui-settings.local.json"\nassert Path(ledger._DEFAULT_LEDGER_PATH)==runtime/"state"/"streak_ledger.db"\nassert Path(ledger._DEFAULT_LOCK_PATH)==runtime/"state"/"run.lock"\nassert Path(qrlogin._SESSION_DIR)==root/"sesion"\nassert Path(object.__new__(client.LttkClient)._plugins_dir())==root/"plugins"\nos.environ["TIKTOK_RUNTIME_DIR"]=str(runtime/"later")\nassert services.CONFIG_PATH==runtime/"streak.local.json"\nassert Path(ledger._DEFAULT_LEDGER_PATH)==runtime/"state"/"streak_ledger.db"\nassert runtime_paths.root(str(runtime))==runtime\n'
        self.child(code, env=env)
        self.assertEqual(list(runtime.iterdir()), [])

    def test_cwd_dry_run_uses_only_synthetic_configuration(self):
        self.write('streak.json', json.dumps({'session': '', 'targets': [], 'message': 'fixture'}))
        result = self.child('import runpy,sys\nsys.argv=["main.py"]\nrunpy.run_path(' + repr(str(ROOT / 'main.py')) + ',run_name="__main__")\n', expected=1)
        self.assertIn('OFFLINE DRY-RUN', result.stdout)
        self.assertIn(str(self.base / 'streak.json'), result.stdout)
        self.assertFalse((self.base / 'state').exists())

    def test_path_consumers_still_refer_to_root_resources(self):
        # Inspect reviewed source; never open the referenced auth/profile paths.
        client_text = (ROOT / 'relttk/transport/client.py').read_text(encoding='utf-8-sig')
        self.assertIn('config.WS_AUTH_FILE', client_text)
        self.assertIn('os.path.join(str(REPO), "state")', client_text)
        tui = (ROOT / 'relttk/application/tui.py').read_text(encoding='utf-8-sig')
        self.assertIn('ROOT / "main.py"', tui)
        self.assertIn('cwd=str(ROOT)', tui)
        renderer = (ROOT / 'deploy/render_units.py').read_text(encoding='utf-8-sig')
        self.assertIn('Path(__file__).resolve().parents[1]', renderer)
        self.assertIn('operational_entry.py', renderer)

    def test_operational_entry_mutes_corrupt_future_import(self):
        self.write('operational_entry.py', (ROOT / 'operational_entry.py').read_text(encoding='utf-8-sig'))
        self.write('relttk/operations.py', 'print("SYNTHETIC_DIAGNOSTIC")\nfrom g0_layout_fixture.operations import cli_entry\n')
        self.write('g0_layout_fixture/__init__.py', '')
        self.write('g0_layout_fixture/operations.py', 'this is invalid syntax !!!\n')
        result = self.child('import runpy,sys,relttk\nfrom pathlib import Path\nrelttk.__path__.insert(0,str(Path("relttk").resolve()))\nsys.argv=["operational_entry.py","operational-status","--operational-output"]\nrunpy.run_path("operational_entry.py",run_name="__main__")\n', toy=True, expected=3)
        self.assertEqual(result.stdout + result.stderr, '')

    def test_operational_entry_mutes_missing_future_import(self):
        self.write('operational_entry.py', (ROOT / 'operational_entry.py').read_text(encoding='utf-8-sig'))
        self.write('relttk/operations.py', 'print("SYNTHETIC_DIAGNOSTIC")\nfrom g0_layout_fixture.operations import cli_entry\n')
        self.write('g0_layout_fixture/__init__.py', '')
        result = self.child('import runpy,sys,relttk\nfrom pathlib import Path\nrelttk.__path__.insert(0,str(Path("relttk").resolve()))\nsys.argv=["operational_entry.py","operational-status","--operational-output"]\nrunpy.run_path("operational_entry.py",run_name="__main__")\n', toy=True, expected=3)
        self.assertEqual(result.stdout + result.stderr, '')
