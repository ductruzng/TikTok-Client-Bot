"""Synthetic UI tests: no real account, session, DB or network."""
import importlib.util
import unittest
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec('textual'), 'optional Textual not installed')
class UsabilityTests(unittest.IsolatedAsyncioTestCase):
    def setup_ui(self, names=('a', 'b'), config=None, inbox=None):
        from relttk.application import tui
        self.tui = tui
        self.addCleanup(patch.stopall)
        patch.object(tui, 'list_sessions', return_value=list(names)).start()
        patch.object(tui, 'read_json_object', return_value=config or {}).start()
        self.fetch = patch.object(tui, 'fetch_inbox', return_value=inbox or []).start()
        from relttk.application import services
        patch.object(services, 'schedule_list', return_value=[]).start()
        return tui.TikTokTUI()

    async def test_approved_main_layout_has_one_navigation_and_no_retired_controls(self):
        from textual.widgets import TextArea
        app=self.setup_ui(names=())
        async with app.run_test(size=(120,40)) as pilot:
            await pilot.pause()
            self.assertEqual(app.query_one('#navigation').region.width,18)
            for retired in ('sidebar','info','send-time','enable-schedule','skip-sent','send-settings','log-card'):
                self.assertFalse(app.query('#'+retired),retired)
            self.assertGreater(app.query_one('#table').size.height,10)
            self.assertEqual(app.query_one('#message',TextArea).parent.id,'message-card')
            for key in ('save-all','send-now','dryrun'):
                self.assertLessEqual(app.query_one('#'+key).region.right,120)
                self.assertLessEqual(app.query_one('#'+key).region.bottom,40)
            self.assertIn('Scheduler: TẮT',str(app.query_one('#statusbar').content))

    async def test_refresh_reloads_all_but_keeps_unsaved_message_and_selection(self):
        from textual.widgets import TextArea
        from relttk.application import services
        row=services.Conversation('c',1,1,'Friend')
        app=self.setup_ui(names=('a',),inbox=[row])
        async with app.run_test(size=(120,40)) as pilot:
            await pilot.pause()
            app.selected_ids={'c'}
            app.query_one('#message',TextArea).load_text(' exact\n draft ')
            self.fetch.reset_mock()
            with patch.object(services,'schedule_list',return_value=[]) as status:
                app.action_refresh();await pilot.pause(0.3)
                status.assert_called_once()
            self.fetch.assert_called_once_with('a')
            self.assertEqual(app.selected_ids,{'c'})
            self.assertEqual(app.query_one('#message',TextArea).text,' exact\n draft ')

    async def test_send_now_shows_saved_content_but_cannot_bypass_identity(self):
        from relttk.application import services
        from relttk.application.tui import SendNowReview
        row=services.Conversation('c',1,1,'Friend')
        cfg={'session':'a','message':'saved exact','targets':[row.target()]}
        app=self.setup_ui(names=('a',),config=cfg,inbox=[row])
        with patch.object(app,'_run_send') as send:
            async with app.run_test(size=(120,40)) as pilot:
                await pilot.pause()
                await pilot.click('#send-now');await pilot.pause()
                self.assertIsInstance(app.screen,SendNowReview)
                self.assertTrue(any(b.disabled for b in app.screen.query('Button')))
                send.assert_not_called()

    async def test_saved_account_auto_syncs_once_and_switch_syncs(self):
        from textual.widgets import Select
        app = self.setup_ui(config={'session': 'b', 'message': 'saved'})
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertEqual(app.loaded_for, 'b')
            self.fetch.assert_called_once_with('b')
            app.query_one('#account', Select).value = 'a'
            await pilot.pause()
            self.assertEqual(app.loaded_for, 'a')
            self.assertEqual(self.fetch.call_count, 2)

    async def test_no_accounts_never_fetches(self):
        app = self.setup_ui(names=())
        async with app.run_test() as pilot:
            await pilot.pause()
            self.fetch.assert_not_called()
            self.assertIn('Chưa có tài khoản', str(app.query_one('#inbox-notice').content))

    async def test_inbox_notice_failure_and_retry_preserve_exact_draft(self):
        from textual.widgets import TextArea
        from relttk.application.services import Conversation
        app = self.setup_ui(names=('a',))
        async with app.run_test(size=(120,40)) as pilot:
            await pilot.pause()
            self.assertIn('Inbox rỗng', str(app.query_one('#inbox-notice').content))
            exact = '  Bản nháp\nkhông đổi  '
            app.query_one('#message',TextArea).load_text(exact)
            self.fetch.side_effect = TimeoutError
            await app._sync_inbox()
            self.assertIn('Lỗi đồng bộ', str(app.query_one('#inbox-notice').content))
            self.assertEqual(app.query_one('#message',TextArea).text, exact)
            self.assertTrue(app.query_one('#inbox-notice').has_class('error'))
            self.fetch.side_effect = None
            self.fetch.return_value = [Conversation('c',1,1,'Bạn An')]
            await app._sync_inbox()
            self.assertFalse(app.query_one('#inbox-notice').has_class('error'))
            self.assertEqual(app.query_one('#message',TextArea).text, exact)
            app.query_one('#search').value = 'absent'
            await pilot.pause()
            self.assertIn('Không tìm thấy', str(app.query_one('#inbox-notice').content))

    async def test_stale_failure_notice_does_not_leak_to_new_account(self):
        from textual.widgets import Select
        app = self.setup_ui(names=('a','b'))
        async with app.run_test(size=(120,40)) as pilot:
            await pilot.pause()
            self.fetch.side_effect = TimeoutError
            await app._sync_inbox()
            self.assertTrue(app.query_one('#inbox-notice').has_class('error'))
            self.fetch.side_effect = None
            app.query_one('#account',Select).value = 'b'
            await pilot.pause()
            self.assertFalse(app.query_one('#inbox-notice').has_class('error'))
            self.assertEqual(app.loaded_for,'b')

    async def test_literal_selection_and_multiline_message_visible_at_80x24(self):
        from textual.widgets import TextArea, DataTable
        from relttk.application.services import Conversation
        row=Conversation('c',1,1,'[red]Bạn An[/red]')
        cfg={'session':'a','message':'Dòng một\nDòng hai','targets':[row.target()]}
        app=self.setup_ui(names=('a',),config=cfg,inbox=[row])
        async with app.run_test(size=(80,24)) as pilot:
            await pilot.pause()
            values=app.query_one('#table',DataTable).get_row('c')
            self.assertEqual(values[0].plain,'[x]')
            self.assertEqual(values[1].plain,row.name)
            self.assertGreaterEqual(app.query_one('#message',TextArea).content_size.height,2)
            svg=app.export_screenshot()
            self.assertIn('Dòng',svg)


    async def test_f2_opens_settings_on_small_terminal_without_sending(self):
        from relttk.application import services
        from relttk.application.settings_ui import SendSettingsScreen
        app = self.setup_ui(names=())
        with patch.object(services,'read_json_object',return_value={}):
            async with app.run_test(size=(80,24)) as pilot:
                await pilot.press('f2'); await pilot.pause()
                self.assertIsInstance(app.screen,SendSettingsScreen)
                self.fetch.assert_not_called()
                app.screen.dismiss(None)

    async def test_failure_has_no_auto_retry_manual_retry_works(self):
        app = self.setup_ui(names=('a',))
        self.fetch.side_effect = TimeoutError
        async with app.run_test() as pilot:
            await pilot.pause()
            self.fetch.assert_called_once_with('a')
            self.assertIsNone(app.loaded_for)
            self.fetch.side_effect = None
            await app._sync_inbox()
            self.assertEqual(app.loaded_for, 'a')
            self.assertEqual(self.fetch.call_count, 2)

    async def test_search_focus_and_filter_do_not_change_layout(self):
        from textual.widgets import Input, DataTable
        from relttk.application.services import Conversation
        app = self.setup_ui(inbox=[Conversation('c1', 1, 1, 'Friend'),
            Conversation('group-id', 2, 2, 'Nhóm')])
        async with app.run_test(size=(140, 45)) as pilot:
            for width, height in [(140,45), (100,35), (80,24)]:
                await pilot.resize_terminal(width,height)
                await pilot.pause()
                regions = {key: app.query_one('#'+key).region
                    for key in ('search','table','navigation','inbox-card')}
                search = app.query_one('#search', Input)
                search.focus()
                search.value = 'group-id'
                await pilot.pause()
                self.assertEqual(regions, {key: app.query_one('#'+key).region for key in regions})
                self.assertEqual(search.region.height, 3)
                self.assertEqual(app.query_one('#navigation').region.width, 18)
                self.assertEqual(app.query_one('#table', DataTable).row_count, 1)
                self.assertGreater(app.query_one('#table').size.height, 2)
                for key in ('select-visible','clear-selection'):
                    self.assertLessEqual(app.query_one('#'+key).region.right, regions['inbox-card'].right)
                search.value = ''
                await pilot.pause()

    async def test_time_rejects_characters_paste_ranges_and_accepts_valid_time(self):
        from textual.widgets import Input
        from textual.app import App
        from relttk.application.time_input import TimeInput
        app = App()
        async with app.run_test(size=(100,35)) as pilot:
            await app.mount(TimeInput(id='schedule-time'))
            time = app.query_one('#schedule-time', Input)
            time.focus()
            await pilot.press('ctrl+a', 'd', 's', 'f')
            self.assertEqual(time.value, '08:00')
            time.replace('26:99', 0, len(time.value))
            self.assertEqual(time.value, '08:00')
            for value in ('00:00','23:59','08:30'):
                time.replace(value,0,len(time.value))
                self.assertEqual(time.value,value)
                self.assertTrue(time.validate(value).is_valid)
            time.value=''
            await pilot.press('0','8',':','3','0')
            self.assertEqual(time.value, '08:30')
            await pilot.press('backspace')
            self.assertFalse(time.validate(time.value).is_valid)


@unittest.skipUnless(importlib.util.find_spec('textual'), 'optional Textual not installed')
class SettingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_settings_actions_remain_visible_at_supported_sizes(self):
        from textual.app import App
        from relttk.application import services
        from relttk.application.settings_ui import SendSettingsScreen
        app=App()
        with patch.object(services,'read_json_object',return_value={}):
            async with app.run_test(size=(120,40)) as pilot:
                screen=SendSettingsScreen()
                app.push_screen(screen);await pilot.pause()
                for width,height in ((120,40),(80,24)):
                    await pilot.resize_terminal(width,height);await pilot.pause()
                    for key in ('settings-save','settings-cancel'):
                        region=screen.query_one('#'+key).region
                        self.assertLessEqual(region.bottom,height)
                        self.assertLessEqual(region.right,width)
                        self.assertEqual(region.height,3)
                    row=screen.query_one('#settings-max_sends_per_account_per_day').parent
                    self.assertLessEqual(row.query_one('Label').region.right,row.query_one('Input').region.x)

    async def run_settings(self, action):
        from textual.app import App
        from relttk.application import services
        from relttk.application.settings_ui import SendSettingsScreen
        from relttk.storage import ledger
        import tempfile
        from pathlib import Path
        original = {'session':'fixture','message':'unchanged','targets':[]}
        app = App()
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(services, 'read_json_object', return_value=original) as read, \
                patch.object(ledger, '_DEFAULT_LEDGER_PATH',str(Path(tmp)/'missing.db')), \
                patch.object(services, 'save_send_settings', return_value=original) as save:
            async with app.run_test(size=(100,45)) as pilot:
                screen = SendSettingsScreen()
                app.push_screen(screen)
                await pilot.pause()
                await action(screen,pilot,save,read)

    async def test_save_all_six_settings_uses_shared_service(self):
        from textual.widgets import Input, Switch
        async def action(screen,pilot,save,read):
            values = {'max_sends_per_account_per_day':10,
                'max_sends_per_conversation_per_day':2,
                'min_send_interval_seconds':60,'max_sends_per_window':1,'window_seconds':300}
            for key,value in values.items():
                screen.query_one('#settings-'+key,Input).value=str(value)
            screen.query_one('#settings-skip',Switch).value=False
            await pilot.click('#settings-save'); await pilot.pause()
            save.assert_called_once_with(True,2,max_sends_per_account_per_day=10,
                min_send_interval_seconds=60,max_sends_per_window=1,window_seconds=300)
        await self.run_settings(action)


    async def test_invalid_settings_do_not_write(self):
        from textual.widgets import Input
        async def action(screen,pilot,save,read):
            field=screen.query_one('#settings-window_seconds',Input)
            field.value='0'
            await pilot.click('#settings-save'); await pilot.pause()
            save.assert_not_called()
            field.replace('oops',0,1)
            self.assertEqual(field.value,'0')
        await self.run_settings(action)

    async def test_stale_settings_do_not_overwrite(self):
        async def action(screen,pilot,save,read):
            read.return_value={'session':'another'}
            await pilot.click('#settings-save'); await pilot.pause()
            save.assert_not_called()
        await self.run_settings(action)

    async def test_cancel_does_not_write(self):
        async def action(screen,pilot,save,read):
            await pilot.click('#settings-cancel'); await pilot.pause()
            save.assert_not_called()
        await self.run_settings(action)

    async def test_active_grant_blocks_settings_write(self):
        from relttk.application import services
        async def action(screen,pilot,save,read):
            with patch('relttk.application.settings_ui.Path.exists', return_value=True), \
                    patch.object(services,'schedule_list', return_value=[{'event':{'event_type':'ACTIVATED'}}]):
                await pilot.click('#settings-save'); await pilot.pause()
                save.assert_not_called()
        await self.run_settings(action)


@unittest.skipUnless(importlib.util.find_spec('textual'), 'optional Textual not installed')
class ScheduleUsabilityTests(unittest.IsolatedAsyncioTestCase):
    def setup_screen(self):
        from relttk.application import services
        from relttk.application.schedule_ui import ScheduleScreen
        self.addCleanup(patch.stopall)
        patch.object(services,'read_json_object',return_value={'session':'fixture'}).start()
        self.review = {'consent': {'schedule_id':'daily','session':'fixture',
            'time':'08:30','valid_from':'2026-10-11','valid_through':'2026-10-17',
            'daily_budget':1,'total_budget':7,'window_minutes':60,'max_wait':300,
            'policy':{'message':' exact\ntext ', 'targets':[{'conv_id':'friend'}]}}, 'fingerprint':'a'*64}
        self.preview = patch.object(services,'schedule_preview',return_value=self.review).start()
        self.confirm = patch.object(services,'schedule_confirm').start()
        return ScheduleScreen('fixture',lambda:'fixture',send_time='08:30')

    async def test_labeled_fields_visible_without_overlap_and_fixed_actions(self):
        from textual.app import App
        from textual.widgets import Input
        app=App();screen=self.setup_screen()
        async with app.run_test(size=(140,45)) as pilot:
            app.push_screen(screen);await pilot.pause()
            for width,height in ((140,45),(100,35),(80,24)):
                await pilot.resize_terminal(width,height);await pilot.pause()
                for left,right in (('name','time'),('first','last')):
                    a=screen.query_one('#schedule-'+left).region
                    b=screen.query_one('#schedule-'+right).region
                    self.assertEqual(a.height,3);self.assertEqual(b.height,3)
                    self.assertLessEqual(a.right,b.x)
                    self.assertLessEqual(b.right,screen.query_one('#schedule-panel').region.right)
                for key in ('schedule-preview','schedule-authorize','schedule-close'):
                    region=screen.query_one('#'+key).region
                    self.assertGreater(region.width,7)
                    self.assertLessEqual(region.bottom,height)
                    self.assertLessEqual(region.right,screen.query_one('#schedule-panel').region.right)
                self.assertEqual(screen.query_one('#schedule-time',Input).value,'08:30')
                self.assertTrue(any(not parent.display for parent in screen.query_one('#schedule-db').ancestors))
            self.preview.assert_not_called();self.confirm.assert_not_called()

    async def test_preview_summary_and_input_change_invalidates_authorize(self):
        from textual.app import App
        from textual.widgets import Button,Input,Static
        app=App();screen=self.setup_screen()
        async with app.run_test(size=(100,35)) as pilot:
            app.push_screen(screen);await pilot.pause()
            self.assertTrue(screen.query_one('#schedule-authorize',Button).disabled)
            await pilot.click('#schedule-preview');await pilot.pause()
            self.assertFalse(screen.query_one('#schedule-authorize',Button).disabled)
            self.assertIn(' exact\ntext ',str(screen.query_one('#schedule-summary',Static).content))
            self.confirm.assert_not_called()
            screen.query_one('#schedule-time',Input).value='09:30';await pilot.pause(0.2)
            self.assertTrue(screen.query_one('#schedule-authorize',Button).disabled)
            self.assertIsNone(screen.preview)

    async def test_duration_presets_use_start_date_without_writes(self):
        from datetime import date,timedelta
        from textual.app import App
        from textual.widgets import Input
        app=App();screen=self.setup_screen()
        async with app.run_test(size=(100,35)) as pilot:
            app.push_screen(screen);await pilot.pause()
            first=date.fromisoformat(screen.value('first'))
            for button,days in (('schedule-thirty',29),('schedule-seven',6)):
                await pilot.click('#'+button);await pilot.pause()
                self.assertEqual(screen.query_one('#schedule-last',Input).value,(first+timedelta(days=days)).isoformat())
            self.preview.assert_not_called();self.confirm.assert_not_called()

    async def test_changed_inputs_reject_open_confirmation(self):
        from textual.app import App
        from textual.widgets import Input
        app=App();screen=self.setup_screen()
        async with app.run_test(size=(120,60)) as pilot:
            app.push_screen(screen);await pilot.pause()
            await pilot.click('#schedule-preview');await pilot.pause()
            await pilot.click('#schedule-authorize');await pilot.pause()
            screen.query_one('#schedule-time',Input).value='09:30';await pilot.pause()
            app.screen.query_one('#reason',Input).value='fixture owner'
            app.screen.query_one('#challenge',Input).value='AUTHORIZE'
            await pilot.click('#confirm-action');await pilot.pause()
            self.confirm.assert_not_called()

