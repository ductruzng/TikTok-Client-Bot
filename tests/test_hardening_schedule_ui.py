"""Disposable recurring grants and Textual pilots; never live transmission."""
import asyncio
from copy import deepcopy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from relttk.application import services
from relttk.storage import ledger, ledger_requests as requests
from relttk.runtime import scheduling, worker
from relttk.transport import oneshot
import test_scheduling as schedule_fixtures


class ScheduleServiceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = schedule_fixtures.ScheduleTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.f = self.fixture

    def test_authorize_activate_pause_revoke_exact_fresh_actions(self):
        review = self.f.review()
        with self.assertRaises(ValueError):
            services.schedule_confirm('AUTHORIZE', review, 'fixture', 'yes', db_path=self.f.db)
        gid = services.schedule_confirm('AUTHORIZE',review,'fixture',services.schedule_action_challenge('AUTHORIZE',review),db_path=self.f.db)
        self.assertEqual(services.schedule_list('fixture',db_path=self.f.db)[0]['event']['event_type'],'AUTHORIZED')
        for action in ('ACTIVATED','PAUSED','REVOKED'):
            current = services.schedule_status(gid,db_path=self.f.db)
            services.schedule_confirm(action,current,'fixture',services.schedule_action_challenge(action,current),db_path=self.f.db)
        self.assertFalse(self.f.rows())

    def test_stale_preview_after_policy_edit_refused(self):
        review = self.f.review(); self.f.cfg['message']='changed';self.f.save()
        with self.assertRaises(scheduling.ScheduleHeld):
            services.schedule_confirm('AUTHORIZE',review,'fixture',services.schedule_action_challenge('AUTHORIZE',review),db_path=self.f.db)
        self.assertFalse(self.f.sql('SELECT * FROM recurring_grants'))

    def test_blank_reason_creates_no_grant(self):
        review = self.f.review()
        with self.assertRaises(ValueError): services.schedule_confirm('AUTHORIZE',review,' ',services.schedule_action_challenge('AUTHORIZE',review),db_path=self.f.db)
        self.assertFalse(self.f.sql('SELECT * FROM recurring_grants'))

    def test_status_recipient_unknown_not_success_and_quota_not_refunded(self):
        gid,_,out = self.f.batch(); row=self.f.rows()[0]
        self.f.claim(row);self.f.finish(row,'failed_unknown')
        report=services.schedule_status(gid,db_path=self.f.db)
        self.assertEqual(report['usage']['daily_used'],1)
        self.assertEqual(report['recipients'][0]['requests'][0]['status'],'failed_unknown')
        self.assertEqual(report['recipients'][1]['requests'][0]['status'],'queued')

    def test_status_explains_cooldown_without_claiming_or_creating_events(self):
        self.f.cfg['min_send_interval_seconds']=60;self.f.save()
        gid,_,out=self.f.batch();row=self.f.rows()[0];self.f.claim(row);self.f.finish(row)
        before=self.f.sql('SELECT * FROM request_events')
        report=services.schedule_status(gid,db_path=self.f.db)
        reasons=report['recipients'][1]['admission_holds'][0]['blocks']
        self.assertEqual(reasons[0]['code'],'MIN_INTERVAL')
        self.assertEqual(reasons[0]['retry_at_ms'],self.f.clock+60000)
        self.assertEqual(before,self.f.sql('SELECT * FROM request_events'))


class TwoTargetEchoTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_packet_echo_path_two_targets_with_cooldown_releases_resources(self):
        from test_streak import MockWebSocket, _build_synthetic_echo_frame
        fixture=schedule_fixtures.ScheduleTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.cfg['min_send_interval_seconds']=60;fixture.save()
        gid,fp,out=fixture.batch()
        rows=fixture.rows()
        sockets=[MockWebSocket([b'hi',_build_synthetic_echo_frame(r['conv_id'],'111',r['client_msg_id'],'precise text')]) for r in rows]
        waits=[]
        async def wait(stop, seconds):
            with ledger.RunLock(str(Path(fixture.db).parent/'run.lock')):
                self.assertEqual(scheduling.status(gid,db_path=fixture.db)['event']['event_type'],'ACTIVATED')
            waits.append(seconds);fixture.clock+=int(seconds*1000)
        with patch.object(oneshot,'load_session',return_value={'sessionid':'synthetic'}),patch.object(oneshot,'get_own_user_id',return_value='111'),\
             patch.object(oneshot,'load_ws_auth',return_value={'device_id':'0'}),patch.object(oneshot,'validate_against_server_inbox'),\
             patch.object(oneshot,'_prepare_ws',return_value=({},'wss://fixture.invalid')),patch.object(oneshot,'_open_ws',side_effect=sockets):
            result=await worker.run(out['occurrence']['run_id'],out['run_fingerprint'],db_path=fixture.db,wait=wait)
        self.assertEqual(waits,[60]);self.assertEqual(result['state'],'COMPLETE')
        self.assertEqual([r['status'] for r in fixture.rows()],['confirmed','confirmed'])
        self.assertEqual([len(ws.sent_packets) for ws in sockets],[2,2])


@unittest.skipUnless(importlib.util.find_spec('textual'), 'optional Textual not installed')
class DraftPilotTests(unittest.IsolatedAsyncioTestCase):
    def setup_ui(self):
        from relttk.application import tui
        self.tui=tui
        self.addCleanup(patch.stopall)
        patch.object(tui,'list_sessions',return_value=['a','b']).start()
        patch.object(tui,'read_json_object',return_value={}).start()
        patch.object(tui,'fetch_inbox',return_value=[services.Conversation('c',1,1,'Friend')]).start()
        return tui.TikTokTUI()

    async def test_multiline_text_and_account_draft_roundtrip(self):
        from textual.widgets import Select,TextArea
        app=self.setup_ui()
        async with app.run_test(size=(100,35)) as pilot:
            account=app.query_one('#account',Select);account.value='a';await pilot.pause()
            app.loaded_for='a';app.conversations=[services.Conversation('c',1,1,'Friend')];app.selected_ids={'c'}
            text='  Xin chào 👋\nDòng hai\n '
            app.query_one('#message',TextArea).load_text(text)
            account.value='b';await pilot.pause();account.value='a';await pilot.pause()
            self.assertEqual(app.query_one('#message',TextArea).text,text)
            self.assertEqual(app.selected_ids,{'c'});self.assertEqual(app.loaded_for,'a')

    async def test_empty_message_never_writes_plan_or_preferences(self):
        from textual.widgets import Select,TextArea,Input
        app=self.setup_ui()
        async with app.run_test() as pilot:
            app.query_one('#account',Select).value='a';await pilot.pause()
            app.loaded_for='a';app.conversations=[services.Conversation('c',1,1,'Friend')];app.selected_ids={'c'}
            app.query_one('#message',TextArea).load_text('   ')
            with patch.object(self.tui,'save_plan') as plan,patch('relttk.application.services.save_preferences') as prefs:
                app._save_all();plan.assert_not_called();prefs.assert_not_called()

    async def test_refresh_preserves_unsaved_selection_and_text(self):
        from textual.widgets import Select,TextArea
        app=self.setup_ui()
        async with app.run_test() as pilot:
            app.query_one('#account',Select).value='a';await pilot.pause()
            row=services.Conversation('c',1,1,'Friend');app.loaded_for='a';app.conversations=[row];app.selected_ids={'c'}
            app.query_one('#message',TextArea).load_text(' \ntext ')
            with patch.object(self.tui,'fetch_inbox',return_value=[row]): await app._sync_inbox()
            self.assertEqual(app.selected_ids,{'c'});self.assertEqual(app.query_one('#message',TextArea).text,' \ntext ')
            with patch.object(self.tui,'fetch_inbox',side_effect=TimeoutError): await app._sync_inbox()
            self.assertEqual(app.selected_ids,{'c'})

    async def test_account_aba_discards_stale_inbox_result(self):
        from textual.widgets import Select
        import threading
        app=self.setup_ui();ready=threading.Event();release=threading.Event()
        calls=[]
        def fetch(session):
            calls.append(session)
            if len(calls)>1:
                return [services.Conversation('fresh',1,1,'Fresh')]
            ready.set();release.wait(5)
            return [services.Conversation('stale',1,1,'Stale')]
        async with app.run_test() as pilot:
            account=app.query_one('#account',Select);account.value='a';await pilot.pause()
            with patch.object(self.tui,'fetch_inbox',side_effect=fetch):
                task=asyncio.create_task(app._sync_inbox());await asyncio.to_thread(ready.wait,2)
                account.value='b';await pilot.pause();account.value='a';await pilot.pause()
                release.set();await task
            await pilot.pause()
            self.assertNotIn('stale', [c.conv_id for c in app.conversations])
            self.assertEqual(calls,['a','a'])

    async def test_confirmation_cancel_and_wrong_word_never_apply(self):
        from relttk.application.schedule_ui import ConfirmSchedule
        from textual.widgets import Input
        app=self.setup_ui()
        with patch('relttk.application.schedule_ui.services.schedule_confirm') as confirm:
            async with app.run_test() as pilot:
                callback=lambda reason:confirm(reason)
                app.push_screen(ConfirmSchedule('AUTHORIZE',{'fingerprint':'a'*64},callback));await pilot.pause()
                app.screen.query_one('#challenge',Input).value='yes'
                await pilot.click('#confirm-action');await pilot.pause();confirm.assert_not_called()
                await pilot.click('#cancel-action');await pilot.pause();confirm.assert_not_called()

    async def test_dropdown_opens_on_small_and_normal_terminals(self):
        from textual.widgets import Select
        app=self.setup_ui()
        async with app.run_test(size=(80,24)) as pilot:
            await pilot.pause()
            await pilot.click('#account');await pilot.pause()
            self.assertTrue(app.query_one('#account',Select).expanded)
            await pilot.press('end');await pilot.pause()
            await pilot.press('enter');await pilot.pause()
            self.assertIn(app.query_one('#account',Select).value,('a','b'))
            await pilot.resize_terminal(140,45);await pilot.pause()
            await pilot.click('#account');await pilot.pause()
            self.assertTrue(app.query_one('#account',Select).expanded)

    async def test_real_ui_authority_lifecycle_uses_fixture_and_never_ticks(self):
        from relttk.application.schedule_ui import ScheduleScreen
        from textual.widgets import Input,Select
        from textual.app import App
        f=schedule_fixtures.ScheduleTests();f.setUp();self.addCleanup(f.doCleanups)
        app=App()
        with patch.object(ledger,'_DEFAULT_LEDGER_PATH',f.db),patch.object(services,'CONFIG_PATH',Path(f.policy)),\
             patch.object(services,'schedule_tick',side_effect=AssertionError('no tick')):
            async with app.run_test(size=(120,60)) as pilot:
                app.push_screen(ScheduleScreen('fixture',lambda:'fixture'));await pilot.pause()
                await pilot.click('#schedule-preview');await pilot.pause()
                await pilot.click('#schedule-authorize');await pilot.pause()
                app.screen.query_one('#reason',Input).value='fixture owner'
                app.screen.query_one('#challenge',Input).value='AUTHORIZE'
                await pilot.click('#confirm-action');await pilot.pause()
                gid=services.schedule_list('fixture',db_path=f.db)[0]['grant_id']
                for button,word in [('schedule-activate','ACTIVATE'),('schedule-pause','PAUSE'),('schedule-revoke','REVOKE')]:
                    app.screen.query_one('#schedule-grant',Select).value=gid;await pilot.pause()
                    await pilot.click('#'+button);await pilot.pause()
                    app.screen.query_one('#reason',Input).value='fixture owner'
                    app.screen.query_one('#challenge',Input).value=word
                    await pilot.click('#confirm-action');await pilot.pause()
                self.assertEqual(services.schedule_status(gid,db_path=f.db)['event']['event_type'],'REVOKED')
                self.assertFalse(f.rows())

    async def test_account_generation_change_invalidates_confirmation(self):
        from relttk.application.schedule_ui import ScheduleScreen
        from textual.widgets import Input
        from textual.app import App
        f=schedule_fixtures.ScheduleTests();f.setUp();self.addCleanup(f.doCleanups)
        app=App();generation=[0]
        with patch.object(ledger,'_DEFAULT_LEDGER_PATH',f.db),patch.object(services,'CONFIG_PATH',Path(f.policy)):
            async with app.run_test(size=(120,60)) as pilot:
                app.push_screen(ScheduleScreen('fixture',lambda:('fixture',generation[0])));await pilot.pause()
                await pilot.click('#schedule-preview');await pilot.pause()
                await pilot.click('#schedule-authorize');await pilot.pause()
                generation[0]+=2  # A -> B -> A, same name but a new UI generation.
                app.screen.query_one('#reason',Input).value='fixture owner'
                app.screen.query_one('#challenge',Input).value='AUTHORIZE'
                await pilot.click('#confirm-action');await pilot.pause()
                self.assertFalse(services.schedule_list('fixture',db_path=f.db))
