import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import runtime_paths as paths
import qrlogin
import services
import client


class RuntimePathsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name); self.base.chmod(0o700)
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {'TIKTOK_RUNTIME_DIR':str(self.base)}).start()

    def test_explicit_root_never_falls_back_to_legacy_session_or_global_auth(self):
        self.assertEqual(qrlogin.load_session('fixture'), {})
        self.assertEqual(services.list_sessions(), [])
        self.assertEqual(client.load_ws_auth(session_name='fixture',cookies={'sessionid':'fixture'}), {})
        with self.assertRaises(ValueError): client.load_ws_auth()

    def test_relative_empty_and_outside_paths_rejected(self):
        for value in ('relative', '', str(self.base/'..')):
            with self.subTest(value=value), self.assertRaises(ValueError): paths.root(value)
        with self.assertRaises(ValueError): paths.contained('relative', must_exist=False)
        with self.assertRaises(ValueError): paths.contained(self.base.parent/'outside.json',must_exist=False)

    def test_traversal_aliases_and_private_read(self):
        directory = self.base/'sesion'; directory.mkdir(mode=0o700)
        p=directory/'fixture.json'; p.write_text(json.dumps({'sessionid':'synthetic'})); p.chmod(0o600)
        for alias in ('..','../fixture','a/b','a\\b','', '.'): 
            with self.subTest(alias=alias), self.assertRaises(ValueError): paths.credential_path(alias)
        with patch('os.chmod',side_effect=AssertionError('chmod forbidden')):
            self.assertEqual(paths.read_private_json(p)['sessionid'],'synthetic')

    def test_root_is_independent_of_cwd(self):
        prior=os.getcwd()
        try:
            os.chdir(self.base.parent)
            self.assertEqual(paths.session_dir(),self.base/'sesion')
        finally: os.chdir(prior)

    def test_symlink_ancestor_rejected(self):
        link=self.base/'alias'
        try: link.symlink_to(self.base, target_is_directory=True)
        except OSError: self.skipTest('Symlink creation not available')
        with self.assertRaises(ValueError): paths.inspect_path(link/'missing',must_exist=False)

    def test_legacy_path_is_preserved_when_opt_in_is_unset(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(paths.session_dir(self.base),self.base)

    @unittest.skipUnless(os.name=='posix','Requires actual POSIX permissions')
    def test_posix_private_permissions_rejected_without_repair(self):
        self.base.chmod(0o755)
        with self.assertRaises(ValueError): paths.root()
        self.assertEqual(self.base.stat().st_mode & 0o777,0o755)
