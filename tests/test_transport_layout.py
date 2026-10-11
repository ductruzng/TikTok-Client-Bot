"""Actual G3 transport contracts in fresh guarded processes; fixtures only."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TransportLayoutTests(unittest.TestCase):
    def child(self, code):
        prefix = 'import runpy,sys\nrunpy.run_path(' + repr(str(ROOT / 'tests/run_offline.py')) + ",run_name='fixture_guard')\n"
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-B', '-c', prefix + code],
                                    cwd=directory, capture_output=True, text=True,
                                    encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_legacy_first_modules_class_and_exception_identity(self):
        self.child('''import client,oneshot,qrlogin,ws_auth_capture
from relttk.transport import client as c,oneshot as o,qrlogin as q,ws_auth_capture as w
import pickle
assert client is c and oneshot is o and qrlogin is q and ws_auth_capture is w
assert o.LttkClient is c.LttkClient
for name in ("UnsupportedSafetyOperation","_BotStop","_BotRestart"):
 exception=getattr(c,name)
 assert getattr(client,name) is exception
 assert type(pickle.loads(pickle.dumps(exception("fixture")))) is exception
assert qrlogin._stop_event is q._stop_event
''')

    def test_canonical_first_identity_and_public_export(self):
        self.child('''from relttk.transport import client as c,oneshot as o,qrlogin as q,ws_auth_capture as w
import client,oneshot,qrlogin,ws_auth_capture,__init__ as public
assert client is c and oneshot is o and qrlogin is q and ws_auth_capture is w
assert public.LttkClient is c.LttkClient is o.LttkClient
assert client.UnsupportedSafetyOperation is c.UnsupportedSafetyOperation
assert all(m.__spec__.name.startswith("relttk.transport.") for m in (c,o,q,w))
''')

    def test_each_transport_initializes_once_and_bootstrap_is_inert(self):
        self.child('''import relttk.transport,sys
from pathlib import Path
from relttk.compat import TARGETS,enable
assert all(name not in sys.modules for name in TARGETS.values())
count=[]
def profile(frame,event,arg):
 if event=="call" and frame.f_code.co_name=="<module>" and "/relttk/transport/" in Path(frame.f_code.co_filename).as_posix():count.append(Path(frame.f_code.co_filename).name)
sys.setprofile(profile)
import oneshot,client,qrlogin,ws_auth_capture
from relttk.transport import oneshot as o,client as c,qrlogin as q,ws_auth_capture as w
enable();enable()
sys.setprofile(None)
assert sorted(count)==["client.py","oneshot.py","qrlogin.py","ws_auth_capture.py"]
''')

    def test_auth_patch_and_missing_auth_never_open_socket(self):
        self.child('''import oneshot,client,asyncio,hashlib
from relttk.transport import oneshot as o,client as c
from unittest.mock import patch,AsyncMock
cookies={"sessionid":"synthetic","ttwid":"1|old|1|aa"}
auth=c.validate_ws_auth({"session":"fixture","session_hash":hashlib.sha256(b"synthetic").hexdigest(),"ttwid":"1|fixture|1|aa","access_key":"a"*32},session_name="fixture",cookies=cookies)
with patch.object(oneshot,"load_ws_auth",return_value=auth) as load:
 paired,url=o._prepare_ws(cookies,"fixture")
 load.assert_called_once_with(session_name="fixture",cookies=cookies)
 assert paired["ttwid"]==auth["ttwid"] and cookies["ttwid"]=="1|old|1|aa"
 assert "synthetic" not in url
for value in ({},{"ttwid":"1|fixture|1|aa","access_key":"bad"}):
 with patch.object(oneshot,"load_ws_auth",return_value=value),patch.object(o._log,"error"),patch("websockets.connect",AsyncMock()) as opened:
  try:o._prepare_ws(cookies,"fixture")
  except ValueError:pass
  else:raise AssertionError("invalid auth accepted")
  opened.assert_not_called()
with patch.object(client,"build_ws_packet",return_value="fixture") as packet:
 assert c.build_ws_packet()=="fixture";packet.assert_called_once()
with patch.object(oneshot,"build_ws_packet",return_value="fixture") as packet:
 assert o.build_ws_packet()=="fixture";packet.assert_called_once()
''')

    def test_qr_session_patch_reaches_client_consumer(self):
        self.child('''import qrlogin,client
from relttk.transport import qrlogin as q,client as c
from unittest.mock import patch
with patch.object(qrlogin,"load_session",return_value={"sessionid":"synthetic"}) as load:
 bot=c.LttkClient(username="fixture",managed=True)
 load.assert_called_once_with("fixture")
 assert bot._cookies=={"sessionid":"synthetic"} and bot._active_session=="fixture"
 assert bot._msg_db is None and not bot._enable_plugins
''')

    def test_repository_and_synthetic_private_paths_from_other_cwd(self):
        code = '''from relttk.transport import client as c,qrlogin as q
from pathlib import Path
from unittest.mock import patch
import os
root=Path(ROOT_VALUE)
assert c.REPO==root and q.REPO==root
assert Path(object.__new__(c.LttkClient)._plugins_dir())==root/"plugins"
assert Path(q._SESSION_DIR)==root/"sesion"
runtime=Path.cwd();runtime.chmod(0o700)
with patch.dict(os.environ,{"TIKTOK_RUNTIME_DIR":str(runtime)}):
 session=q._get_session_path("fixture")
 auth=q.ws_auth_path("fixture")
 assert Path(session)==runtime/"sesion"/"fixture.json"
 assert Path(auth)==runtime/"sesion"/"ws-auth"/"fixture.json"
 assert c.load_ws_auth(session_name="fixture",cookies={"sessionid":"synthetic"})=={}
 try:c.load_ws_auth()
 except ValueError:pass
 else:raise AssertionError("global auth fallback")
assert sorted(p.name for p in runtime.iterdir())==["sesion"]
assert list((runtime/"sesion").iterdir())==[]
'''.replace('ROOT_VALUE', repr(str(ROOT)))
        self.child(code)

    def test_legacy_auth_and_message_db_anchors_without_runtime_io(self):
        code = '''from relttk.transport import client as c
from unittest.mock import patch,Mock
from pathlib import Path
import os,sqlite3
root=Path(ROOT_VALUE)
with patch.dict(os.environ,{},clear=True),patch.object(c.os.path,"islink",return_value=False),patch.object(c.os.path,"exists",return_value=False) as exists:
 assert c.load_ws_auth()=={}
 exists.assert_called_once_with(str(root/c.config.WS_AUTH_FILE))
bot=object.__new__(c.LttkClient)
with patch.object(c.os,"makedirs") as mkdir,patch.object(sqlite3,"connect",return_value=Mock()) as connect:
 bot._init_msg_db()
 mkdir.assert_called_once_with(str(root/"state"),mode=0o700,exist_ok=True)
 connect.assert_called_once_with(str(root/"state"/"messages.db"),check_same_thread=False)
'''.replace('ROOT_VALUE', repr(str(ROOT)))
        self.child(code)

    def test_optional_websockets_and_browser_dependencies_fail_before_effects(self):
        self.child('''from unittest.mock import patch
import sys
with patch.dict(sys.modules,{"websockets":None}):
 try:import client
 except ModuleNotFoundError:pass
 else:raise AssertionError("missing websockets accepted")
 assert "client" not in sys.modules and "relttk.transport.client" not in sys.modules
from relttk.transport import ws_auth_capture as w,qrlogin as q
with patch.object(w.sys,"platform","win32"),patch.dict(sys.modules,{"playwright.sync_api":None}):
 try:w.capture_for_cookies({})
 except ModuleNotFoundError:pass
 else:raise AssertionError("missing browser dependency accepted")
with patch.object(q.sys.stdout,"isatty",return_value=True),patch.dict(sys.modules,{"qrcode":None}),patch.object(q._log,"warn") as warn:
 q._print_qr("https://fixture.invalid/")
 warn.assert_called_once()
''')

    def test_legacy_live_paths_refuse_before_attributes_auth_and_websocket(self):
        self.child('''from relttk.transport import client as c
import client,asyncio
from unittest.mock import patch,AsyncMock
bot=object.__new__(client.LttkClient)
with patch.object(client,"load_ws_auth") as auth,patch("websockets.connect",AsyncMock()) as opened,patch.object(c,"build_ws_packet") as packet:
 for name in ("send_message","send_video","send_reaction","delete_message","delete_message_everyone","remove_reaction","run"):
  try:asyncio.run(getattr(bot,name)(*(["fixture","item"] if name=="send_video" else [])))
  except client.UnsupportedSafetyOperation:pass
  else:raise AssertionError("legacy path accepted")
 auth.assert_not_called();opened.assert_not_called();packet.assert_not_called()
''')

    def test_scanner_reaches_actual_class_and_all_aliases(self):
        from source_checks import source_paths, client_implementation
        import client
        paths = set(source_paths(ROOT))
        self.assertEqual(client_implementation(ROOT, client), ROOT / 'relttk/transport/client.py')
        for name in ('client', 'oneshot', 'qrlogin', 'ws_auth_capture'):
            self.assertIn(ROOT / 'relttk/transport' / (name + '.py'), paths)
            self.assertIn(ROOT / 'relttk/compat/legacy' / (name + '.py'), paths)
            self.assertFalse((ROOT / (name + '.py')).exists())
