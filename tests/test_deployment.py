"""Unit text on Windows is simulation, never a claim of installed systemd."""
from copy import deepcopy
import os
from pathlib import Path
import sys
import unittest

from deploy import render_units as renderer


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.consent=dict(policy={'targets':[{'conv_id':'fixture'}]},daily_budget=1,
                          max_wait=300,window_minutes=60,time='08:00')
        self.args=dict(grant_id='a'*32,fingerprint='b'*64,python='/opt/relttk/releases/r1/venv/bin/python',
                       entry='/opt/relttk/releases/r1/operational_entry.py',runtime='/var/lib/relttk',
                       db='/var/lib/relttk/state/ledger.db')

    def test_exact_unit_oneshot_and_timer_no_retry_no_activation(self):
        result=renderer.unit_text(self.consent,**self.args)
        self.assertEqual(len(result),2)
        service=result['relttk-'+'a'*32+'.service'];timer=result['relttk-'+'a'*32+'.timer']
        for text in ('Type=oneshot','Restart=no','TimeoutStartSec=600','TimeoutStopSec=90',
                     'User=relttk','UMask=0077','StandardError=null','--execute --yes --operational-output',
                     'NoNewPrivileges=yes','ReadWritePaths=/var/lib/relttk'):
            self.assertIn(text,service)
        self.assertIn('Persistent=false',timer)
        self.assertIn('Asia/Ho_Chi_Minh',timer)
        self.assertNotIn('ExecStartPre=',service);self.assertNotIn('ExecStop=',service)
        self.assertNotIn('%',service+timer);self.assertNotIn('$',service+timer)
        self.assertNotIn('fixture',service+timer)

    def test_path_and_selector_injection_specifier_escape_rejected(self):
        for key in self.args:
            for value in ('../x','/safe/../x','/tmp/x\nExecStart=/bad','/tmp/%i','/tmp/$VAR',
                          '/tmp/"x"','/tmp/a b','/tmp/x\x00','/tmp//x','/tmp/./x','/tmp/x\\y'):
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                    renderer.unit_text(self.consent,**{**self.args,key:value})
        with self.assertRaises(ValueError):
            renderer.unit_text(self.consent,**{**self.args,'db':'/other/state.db'})

    def test_workload_recipient_wait_window_midnight_bounds(self):
        self.assertEqual(renderer.workload(self.consent)['profile_seconds'],540)
        for updates in ({'policy':{'targets':[]}}, {'policy':{'targets':[{},{}]}},
                        {'daily_budget':2},{'max_wait':301},{'max_wait':True},
                        {'window_minutes':1},{'time':'23:59'},{'time':'unsafe'}):
            with self.subTest(updates=updates),self.assertRaisesRegex(ValueError,'UNSUPPORTED_WORKLOAD'):
                renderer.workload({**self.consent,**updates})
        self.assertEqual(renderer.workload({**self.consent,'time':'23:50'})['recipients'],1)

    @unittest.skipIf(os.name=='posix','Windows renderer refusal only')
    def test_renderer_refuses_windows_actual_artifacts(self):
        with self.assertRaisesRegex(ValueError,'POSIX'):
            renderer.render(db='x',grant_id='a'*32,fingerprint='b'*64,python='x',entry='x',runtime='x',output='x')

    def test_templates_are_only_files_no_host_commands(self):
        source=Path(renderer.__file__).read_text(encoding='utf-8')
        self.assertNotIn('subprocess',source)
        self.assertNotIn('os.system',source)
        self.assertNotIn('systemctl',source)
