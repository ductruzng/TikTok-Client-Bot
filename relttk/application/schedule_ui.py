"""Explicit recurring authority UI. No tick, worker, auth or timer invocation."""
import json
from datetime import date, timedelta
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import VerticalScroll, Horizontal, Vertical
from textual.widgets import Button, Input, Label, Select, RichLog, Static, Collapsible, TabbedContent, TabPane

from relttk.application import services
from relttk.application.time_input import TimeInput
from relttk.storage import ledger, ledger_requests as requests


ACTION_LABELS = {'AUTHORIZE': 'Cấp quyền lịch', 'ACTIVATED': 'Bật quyền lịch',
    'PAUSED': 'Tạm dừng', 'REVOKED': 'Thu hồi quyền'}
STATE_LABELS = {'AUTHORIZED': 'Đã cấp quyền, chưa bật', 'ACTIVATED': 'Đã bật quyền lịch',
    'PAUSED': 'Đã tạm dừng', 'REVOKED': 'Đã thu hồi'}


def review_text(review):
    """Human summary of the exact backend consent; details remain available."""
    consent = review.get('consent', {})
    if not consent:
        return 'Xem chi tiết bên dưới.'
    policy = consent.get('policy', {})
    targets = policy.get('targets', [])
    lines = [f"Lịch: {consent.get('schedule_id', '')} · Tài khoản: {consent.get('session', '')}",
        f"Mỗi ngày lúc {consent.get('time', '')} (giờ Việt Nam)",
        f"Từ {consent.get('valid_from', '')} đến hết {consent.get('valid_through', '')}",
        f"Người nhận: {len(targets)} hội thoại · Tối đa {consent.get('daily_budget', '')} lượt/ngày, {consent.get('total_budget', '')} lượt cả lịch",
        f"Cửa sổ gửi: {consent.get('window_minutes', '')} phút · Chờ hạn mức tối đa: {consent.get('max_wait', '')} giây"]
    if 'message' in policy:
        lines.append('Nội dung đã lưu:\n' + str(policy['message']))
    else:
        lines.append('Dùng các template đã lưu; xem nội dung trong chi tiết.')
    lines.extend('• '+str(t.get('conv_id', '')) for t in targets)
    event = review.get('event', {})
    if event:
        lines.append('Trạng thái: '+STATE_LABELS.get(event.get('event_type'), event.get('event_type', '')))
    usage = review.get('usage', {})
    if usage:
        lines.append(f"Đã truyền: {usage.get('daily_used', 0)} lượt hôm nay / {usage.get('total_used', 0)} lượt cả lịch (kể cả UNKNOWN)")
    lines.append('TUI không chạy lịch nền. Bật quyền không khởi động dịch vụ hay gửi ngay.')
    return '\n'.join(lines)


class ConfirmSchedule(ModalScreen):
    DEFAULT_CSS = '''ConfirmSchedule { align: center middle; }
    #confirmation { width: 90%; max-width: 100; height: 90%; border: round $accent; background: $surface; padding: 0 1; }
    #confirmation Input { height: 3; } #confirmation Button { width: 100%; }
    #review { height: 12; } #confirmation-error { color: $error; height: auto; }'''

    def __init__(self, action, review, apply):
        super().__init__()
        self.action, self.review, self.apply = action, review, apply
        self.word = services.schedule_action_challenge(action, review).split(' ')[0]

    def compose(self) -> ComposeResult:
        with VerticalScroll(id='confirmation'):
            yield Label('XÁC NHẬN: '+ACTION_LABELS.get(self.action, self.word), classes='panel-title')
            yield Static(review_text(self.review), markup=False)
            with Collapsible(title='Chi tiết kỹ thuật của bản xác nhận', collapsed=True):
                yield RichLog(id='review', wrap=True, markup=False)
            yield Label('Lý do cho thao tác này (bắt buộc)')
            yield Input(placeholder='Lý do bắt buộc, không nhập credentials', id='reason')
            yield Label('Gõ '+self.word+' để xác nhận riêng thao tác này')
            yield Input(placeholder='Gõ chính xác '+self.word, id='challenge')
            yield Static('', id='confirmation-error')
            yield Button('XÁC NHẬN', id='confirm-action', variant='warning')
            yield Button('HỦY', id='cancel-action')

    def on_mount(self):
        self.query_one('#review', RichLog).write(json.dumps(self.review, ensure_ascii=False, indent=2))

    def on_button_pressed(self, event):
        if event.button.id == 'cancel-action':
            self.dismiss()
        elif event.button.id == 'confirm-action':
            if self.query_one('#challenge', Input).value != self.word:
                self.query_one('#confirmation-error', Static).update('Gõ chính xác '+self.word+' để xác nhận.')
                return
            reason = self.query_one('#reason', Input).value
            if not reason.strip():
                self.query_one('#confirmation-error', Static).update('Nhập lý do trước khi xác nhận.')
                return
            try:
                self.apply(reason)
            except Exception as exc:
                self.notify('Bị chặn: '+getattr(exc, 'code', type(exc).__name__), severity='error')
                self.dismiss()
            else:
                self.dismiss()


class ScheduleScreen(ModalScreen):
    DEFAULT_CSS = '''ScheduleScreen { align: center middle; }
    #schedule-panel { width: 95%; max-width: 110; height: 95%; border: round $accent; padding: 0 1; background: $surface; }
    #schedule-tabs { height: 1fr; }
    #schedule-panel TabPane { padding: 0; }
    #schedule-panel Input { height: 3; width: 100%; }
    #schedule-panel .fields { height: 4; }
    #schedule-panel .field { width: 1fr; height: 4; margin-right: 1; }
    #schedule-panel .field Label { height: 1; }
    #schedule-panel .actions { height: 3; }
    #schedule-panel .actions Button { width: 1fr; min-width: 8; padding: 0 1; }
    #schedule-panel Select { height: 3; border: none; }
    #schedule-review, #schedule-manage-review { height: 12; }
    #schedule-summary, #schedule-status-summary { height: auto; }
    #schedule-error { height: auto; color: $error; }
    #schedule-close { height: 3; }'''

    def __init__(self, session, current_session, *, send_time='08:00'):
        super().__init__()
        self.session, self.current_session = session, current_session
        self.initial_context = current_session()
        self.grants = {}
        self.send_time = send_time
        self.preview = None
        self.preview_inputs = None

    def compose(self) -> ComposeResult:
        day = requests.local_time(requests.utc_now_ms()).date()
        with Vertical(id='schedule-panel'):
            yield Label('LỊCH GỬI · '+(self.session or 'Chưa chọn tài khoản'), classes='panel-title')
            yield Static('Gửi thật đang bị chặn: chưa xác minh danh tính tài khoản. TUI không chạy nền.', markup=False, classes='ui-warning')
            with TabbedContent(id='schedule-tabs'):
                with TabPane('Tạo lịch', id='schedule-create'):
                    with VerticalScroll():
                        yield Label('1. Chọn giờ và thời hạn · dùng người nhận / nội dung đã lưu')
                        with Horizontal(classes='fields'):
                            with Vertical(classes='field'):
                                yield Label('ID lịch · chữ, số, _ . -')
                                yield Input(value='daily', restrict=r'[A-Za-z0-9_.-]*', max_length=64, id='schedule-name')
                            with Vertical(classes='field'):
                                yield Label('Giờ gửi · HH:MM (Việt Nam)')
                                yield TimeInput(value=self.send_time, id='schedule-time')
                        with Horizontal(classes='fields'):
                            with Vertical(classes='field'):
                                yield Label('Bắt đầu · YYYY-MM-DD')
                                yield Input(value=day.isoformat(), restrict=r'[0-9-]*', max_length=10, id='schedule-first')
                            with Vertical(classes='field'):
                                yield Label('Kết thúc · YYYY-MM-DD')
                                yield Input(value=(day+timedelta(days=6)).isoformat(), restrict=r'[0-9-]*', max_length=10, id='schedule-last')
                        with Horizontal(classes='actions'):
                            yield Button('7 ngày', id='schedule-seven')
                            yield Button('14 ngày', id='schedule-fourteen')
                            yield Button('30 ngày', id='schedule-thirty')
                        yield Static('', id='schedule-saved-policy', markup=False)
                        with Collapsible(title='Nâng cao · giới hạn và đường dẫn', collapsed=True):
                            for name, label, value in (
                                ('window','Cửa sổ gửi sau giờ hẹn (phút)','60'),
                                ('daily','Hạn mức mỗi ngày (trống = số người nhận)',''),
                                ('total','Hạn mức cả lịch (trống = người nhận × số ngày)',''),
                                ('wait','Chờ hạn mức tối đa (giây)','300')):
                                yield Label(label)
                                yield Input(value=value, restrict=r'[0-9]*', max_length=10, id='schedule-'+name)
                            yield Label('Database đã khởi tạo (không tự tạo / nâng cấp)')
                            yield Input(value=ledger._DEFAULT_LEDGER_PATH, id='schedule-db')
                            yield Label('File cấu hình đã lưu')
                            yield Input(value=str(services.CONFIG_PATH), id='schedule-config')
                        yield Label('2. Xem trước → 3. Cấp quyền (chưa bật lịch)', classes='panel-title')
                        yield Static('Chưa xem trước. Không có thay đổi nào được ghi.', id='schedule-summary', markup=False)
                        with Collapsible(title='Chi tiết kỹ thuật của bản xem trước', collapsed=True):
                            yield RichLog(id='schedule-review', wrap=True, markup=False)
                with TabPane('Lịch đã lưu', id='schedule-manage'):
                    with VerticalScroll():
                        yield Static('Tải danh sách, chọn lịch rồi xem trạng thái. Bật / tạm dừng / thu hồi cần xác nhận riêng.')
                        yield Button('Tải lại danh sách', id='schedule-list')
                        yield Select([], id='schedule-grant', prompt='Chọn lịch đã cấp quyền')
                        with Horizontal(classes='actions'):
                            yield Button('Trạng thái', id='schedule-status')
                            yield Button('Bật quyền', id='schedule-activate')
                        with Horizontal(classes='actions'):
                            yield Button('Tạm dừng', id='schedule-pause')
                            yield Button('Thu hồi', id='schedule-revoke')
                        yield Static('Chưa chọn lịch.', id='schedule-status-summary', markup=False)
                        with Collapsible(title='Chi tiết kỹ thuật và trạng thái', collapsed=True):
                            yield RichLog(id='schedule-manage-review', wrap=True, markup=False)
            yield Static('', id='schedule-error', markup=False)
            with Horizontal(classes='actions'):
                yield Button('Xem trước', id='schedule-preview', variant='primary')
                yield Button('Cấp quyền', id='schedule-authorize', disabled=True)
                yield Button('ĐÓNG', id='schedule-close')

    def value(self, name):
        return self.query_one('#schedule-'+name, Input).value

    def on_mount(self):
        try:
            config = services.read_json_object(Path(self.value('config')))
            if config.get('session') != self.session:
                raise ValueError('Chưa có cấu hình đã lưu cho tài khoản này.')
            targets = config.get('targets', [])
            self.query_one('#schedule-saved-policy', Static).update(
                f"NGƯỜI NHẬN ĐÃ LƯU: {len(targets)} hội thoại\nTIN NHẮN ĐÃ LƯU:\n"
                +str(config.get('message', ''))+'\nChỉnh và lưu tại Hội thoại trước khi tạo lịch.')
        except (OSError, ValueError) as exc:
            self.query_one('#schedule-saved-policy', Static).update('Chưa đọc được cấu hình đã lưu: '+type(exc).__name__)

    def show(self, result):
        manage = self.query_one('#schedule-tabs', TabbedContent).active == 'schedule-manage'
        self.query_one('#schedule-status-summary' if manage else '#schedule-summary', Static).update(review_text(result))
        log = self.query_one('#schedule-manage-review' if manage else '#schedule-review', RichLog)
        log.clear()
        log.write(json.dumps(result, ensure_ascii=False, indent=2))

    def input_snapshot(self):
        return tuple(self.value(name) for name in ('db','config','name','time','first','last','window','daily','total','wait'))

    def on_tabbed_content_tab_activated(self, event):
        if event.tabbed_content.id == 'schedule-tabs':
            create = event.pane.id == 'schedule-create'
            self.query_one('#schedule-preview', Button).display = create
            self.query_one('#schedule-authorize', Button).display = create

    def on_input_changed(self, event):
        if self.preview is not None:
            self.preview = None
            self.query_one('#schedule-authorize', Button).disabled = True
            self.query_one('#schedule-summary', Static).update('Cấu hình đã đổi. Bấm Xem trước lại trước khi cấp quyền.')

    def reload_grants(self):
        rows = services.schedule_list(self.session, db_path=self.value('db'))
        self.grants = {r['grant_id']: r for r in rows}
        self.query_one('#schedule-grant', Select).set_options([
            (r['consent']['schedule_id']+' · '+STATE_LABELS.get(r['event']['event_type'], r['event']['event_type'])+' · '+r['grant_id'][:8], r['grant_id']) for r in rows])

    def on_button_pressed(self, event):
        action = event.button.id
        if action == 'schedule-close':
            self.dismiss()
            return
        try:
            self.query_one('#schedule-error', Static).update('')
            if self.current_session() != self.initial_context or not self.session:
                raise ValueError('ACCOUNT_CHANGED')
            db = self.value('db')
            if action in ('schedule-seven', 'schedule-fourteen', 'schedule-thirty'):
                first = date.fromisoformat(self.value('first'))
                self.query_one('#schedule-last', Input).value = (first+timedelta(days={'schedule-seven':6, 'schedule-fourteen':13, 'schedule-thirty':29}[action])).isoformat()
                return
            if action == 'schedule-list':
                self.reload_grants()
                self.query_one('#schedule-status-summary', Static).update(f'{len(self.grants)} lịch đã lưu. Chọn lịch để xem trạng thái.')
                return
            if action in ('schedule-preview', 'schedule-authorize'):
                # Always use the saved exact policy; unsaved widgets cannot authorize.
                config = Path(self.value('config'))
                if services.read_json_object(config).get('session') != self.session:
                    raise ValueError('POLICY_SESSION_MISMATCH')
                if action == 'schedule-authorize':
                    if self.preview is None or self.preview_inputs != self.input_snapshot():
                        raise ValueError('Xem trước lại trước khi cấp quyền.')
                    review = self.preview
                else:
                    review = services.schedule_preview(config, self.value('name'), db_path=db,
                        time=self.value('time'), valid_from=self.value('first'), valid_through=self.value('last'),
                        window_minutes=int(self.value('window')), max_wait=int(self.value('wait')),
                        daily_budget=int(self.value('daily')) if self.value('daily') else None,
                        total_budget=int(self.value('total')) if self.value('total') else None)
                    self.preview = review
                    self.preview_inputs = self.input_snapshot()
                    self.query_one('#schedule-authorize', Button).disabled = False
                operation = 'AUTHORIZE'
            else:
                gid = self.query_one('#schedule-grant', Select).value
                if not isinstance(gid, str) or gid not in self.grants:
                    raise ValueError('SELECT_GRANT')
                review = services.schedule_status(gid, db_path=db)
                operation = {'schedule-activate':'ACTIVATED', 'schedule-pause':'PAUSED', 'schedule-revoke':'REVOKED'}.get(action)
            self.show(review)
            if action in ('schedule-preview', 'schedule-status'):
                return
            if operation is None:
                return
            # db, action, preview/fingerprint/version and account are frozen in this dialog.
            def apply(reason):
                if (self.current_session() != self.initial_context or self.value('db') != db
                        or (operation == 'AUTHORIZE' and (self.preview is not review
                            or self.input_snapshot() != self.preview_inputs))):
                    raise ValueError('STALE_UI_CONTEXT')
                result = services.schedule_confirm(operation, review, reason,
                    services.schedule_action_challenge(operation, review), db_path=db)
                self.preview = None
                self.query_one('#schedule-authorize', Button).disabled = True
                self.query_one('#schedule-tabs', TabbedContent).active = 'schedule-manage'
                self.query_one('#schedule-status-summary', Static).update(ACTION_LABELS[operation]+': đã ghi nhận. Chưa gửi tin; chưa khởi động dịch vụ.')
                try:
                    self.reload_grants()
                except Exception:
                    self.notify('Thao tác đã ghi nhận; tải lại status thất bại. Kiểm tra status trước khi thao tác lại.', severity='warning')
            self.app.push_screen(ConfirmSchedule(operation, review, apply))
        except Exception as exc:
            code = getattr(exc, 'code', None)
            message = code or (str(exc) if isinstance(exc, ValueError) else type(exc).__name__)
            self.query_one('#schedule-error', Static).update('Chưa thực hiện: '+message)
