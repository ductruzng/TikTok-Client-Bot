"""Actual G2 application identities, paths and consumers under the offline guard."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ApplicationLayoutTests(unittest.TestCase):
    def child(self, code):
        prefix = 'import runpy,sys\nrunpy.run_path(' + repr(str(ROOT / 'tests/run_offline.py')) + ",run_name='fixture_guard')\n"
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-B', '-c', prefix + code],
                                    cwd=directory, capture_output=True, text=True,
                                    encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_legacy_first_identity_and_cli_config_patch(self):
        self.child('''import cli,services
from relttk.application import cli as c,services as s
assert cli is c and services is s
assert cli.Conversation is s.Conversation
from unittest.mock import patch
from pathlib import Path
with patch.object(cli,"CONFIG_PATH",Path("fixture.json")),patch.object(cli.main_cli,"cmd_dry_run") as dry,patch("builtins.input",return_value=""):
 c.menu_dry_run()
 dry.assert_called_once_with("fixture.json")
''')

    def test_canonical_first_service_globals_functions_and_class(self):
        self.child('''from relttk.application import services as s,cli as c
import services,cli,importlib,pickle
from unittest.mock import patch
assert services is s and cli is c
with patch.object(services,"SESSION_PATTERN",None):assert s.SESSION_PATTERN is None
with patch.object(services,"save_fixed_message") as save,patch.object(c,"read_json_object",return_value={}),patch("builtins.input",side_effect=["fixture",""]):
 c.menu_config_message()
 save.assert_called_once_with("fixture",c.CONFIG_PATH)
value=s.Conversation("fixture",1,1,"Fixture")
assert type(pickle.loads(pickle.dumps(value))) is services.Conversation
assert importlib.reload(services) is s
assert services.Conversation is s.Conversation
''')

    def test_package_bootstrap_is_inert_and_application_conflicts_refused(self):
        self.child('''import relttk.application,sys,types
from relttk.compat import enable,TARGETS
assert all(name not in sys.modules for name in TARGETS.values())
before=list(sys.path);enable();enable();assert sys.path==before
old=types.ModuleType("services");sys.modules["services"]=old
try:enable()
except RuntimeError as exc:assert str(exc)=="LEGACY_IMPORT_CONFLICT"
else:raise AssertionError("conflict allowed")
assert sys.modules["services"] is old
assert "relttk.application.services" not in sys.modules
''')

    def test_service_initializes_once_across_both_import_names(self):
        self.child('''import sys
from pathlib import Path
initializations=[]
def profile(frame,event,arg):
 if event=="call" and frame.f_code.co_name=="<module>" and Path(frame.f_code.co_filename).as_posix().endswith("/relttk/application/services.py"):
  initializations.append(frame.f_code.co_filename)
sys.setprofile(profile)
import services
from relttk.application import services as canonical
import cli
from relttk.application import cli as canonical_cli
sys.setprofile(None)
assert len(initializations)==1
assert services is canonical and cli is canonical_cli
assert cli.Conversation is services.Conversation
''')

    def test_cli_dispatch_and_help_without_textual(self):
        result = self.child('''from unittest.mock import patch
import sys
sys.modules["textual"]=None
from relttk.application import cli
import main
from pathlib import Path
with patch.object(cli,"CONFIG_PATH",Path("fixture.json")),patch.object(sys,"argv",["cli","dry-run"]),patch.object(main,"cmd_dry_run") as dry:
 cli.main();dry.assert_called_once_with("fixture.json")
with patch.object(sys,"argv",["cli","--help"]):
 try:cli.main()
 except SystemExit as exc:assert exc.code==0
 else:raise AssertionError("help did not exit")
with patch.object(sys,"argv",["main.py","tui"]):assert main.main()==1
assert "relttk.application.tui" not in sys.modules
''')
        self.assertIn('Optional TUI dependencies missing', result.stdout)

    def test_real_cli_dry_run_from_other_cwd_has_no_state(self):
        result = self.child('''from relttk.application import cli
from unittest.mock import patch
from pathlib import Path
import json
cfg=Path("fixture.json");cfg.write_text(json.dumps({"session":"","targets":[],"message":"fixture"}))
with patch.object(cli,"CONFIG_PATH",cfg),patch("sys.argv",["cli","dry-run"]):cli.main()
assert not Path("state").exists()
assert sorted(p.name for p in Path.cwd().iterdir())==["fixture.json"]
''')
        self.assertIn('OFFLINE DRY-RUN', result.stdout)

    @unittest.skipUnless(importlib.util.find_spec('textual'), 'optional Textual not installed')
    def test_tui_legacy_first_identity_and_consumer_patch(self):
        self.child('''import tiktok_tui,services
from relttk.application import tui,services as s
from unittest.mock import patch
assert tiktok_tui is tui and services is s
assert tiktok_tui.TikTokTUI is tui.TikTokTUI
assert tui.Conversation is s.Conversation
with patch.object(tiktok_tui,"CONFIG_PATH","fixture"),patch.object(tui,"read_json_object",return_value={}) as read:
 tui.TikTokTUI._saved_plan(object())
 read.assert_called_once_with("fixture")
''')

    @unittest.skipUnless(importlib.util.find_spec('textual'), 'optional Textual not installed')
    def test_tui_canonical_first_subprocess_argv_and_cwd(self):
        code = '''from relttk.application import tui
import tiktok_tui,asyncio
from unittest.mock import patch,Mock,AsyncMock
from pathlib import Path
assert tui is tiktok_tui
assert tui.ROOT==Path(ROOT_VALUE)
fake=Mock()
with patch.object(tui.os,"name","nt"),patch.object(tui.subprocess,"CREATE_NEW_CONSOLE",16,create=True),patch.object(tiktok_tui.subprocess,"Popen") as opened:
 tui.TikTokTUI._launch_terminal(fake,"login")
 assert opened.call_args.args[0]==[sys.executable,"-B",str(tui.ROOT/"main.py"),"login"]
 assert opened.call_args.kwargs["cwd"]==str(tui.ROOT)
proc=Mock(returncode=0);proc.communicate=AsyncMock(return_value=(b"DRY-RUN COMPLETE",None))
with patch.object(tui,"CONFIG_PATH",Path("fixture.json")),patch.object(Path,"exists",return_value=True),patch.object(tui.asyncio,"create_subprocess_exec",new_callable=AsyncMock,return_value=proc) as opened:
 asyncio.run(tui.TikTokTUI._dryrun(fake))
 assert opened.call_args.args==(sys.executable,"-B",str(tui.ROOT/"main.py"),"--config","fixture.json","--dry-run")
 assert opened.call_args.kwargs["cwd"]==str(tui.ROOT)
'''.replace('ROOT_VALUE', repr(str(ROOT)))
        self.child(code)

    def test_actual_implementations_and_aliases_have_scanner_coverage(self):
        from source_checks import source_paths
        paths = set(source_paths(ROOT))
        for old, new in (('cli', 'cli'), ('services', 'services'), ('tiktok_tui', 'tui')):
            self.assertIn(ROOT / 'relttk/application' / (new + '.py'), paths)
            self.assertIn(ROOT / 'relttk/compat/legacy' / (old + '.py'), paths)
            self.assertFalse((ROOT / (old + '.py')).exists())
        self.child('''from relttk.application import cli,services
from pathlib import Path
assert Path(cli.__file__).parent==Path(services.__file__).parent
assert Path(cli.__file__).parent.name=="application"
assert cli.__spec__.name=="relttk.application.cli"
assert services.__spec__.name=="relttk.application.services"
''')
