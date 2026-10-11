"""Edit the existing send policy; never creates recurring consent or sends."""
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import VerticalScroll, Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, Switch

from relttk.application import services
from relttk.storage import ledger, ledger_requests


LIMIT_LABELS = {
    'max_sends_per_account_per_day': 'Lượt truyền / tài khoản / ngày',
    'max_sends_per_conversation_per_day': 'Lượt truyền / hội thoại / ngày',
    'min_send_interval_seconds': 'Khoảng nghỉ tối thiểu (giây)',
    'max_sends_per_window': 'Lượt truyền tối đa trong cửa sổ',
    'window_seconds': 'Độ dài cửa sổ (giây)',
}


class SendSettingsScreen(ModalScreen):
    DEFAULT_CSS = '''SendSettingsScreen { align: center middle; }
    #settings-panel { width: 80; max-width: 95%; height: 95%; border: round $accent;
        background: $surface; padding: 0 1; }
    #settings-body { height: 1fr; }
    #settings-panel .limit-row { height: 3; }
    #settings-panel .limit-row Label { width: 1fr; padding: 1 0; }
    #settings-panel Input { height: 3; width: 14; }
    #settings-panel Switch { width: 14; }
    #settings-actions { height: 3; }
    #settings-panel Button { width: 1fr; height: 3; }
    #settings-error { height: auto; color: $error; }'''

    def compose(self) -> ComposeResult:
        error = ''
        self.original = None
        try:
            self.original = services.read_json_object(services.CONFIG_PATH)
            settings = ledger_requests.settings_from_config(self.original)
        except (ValueError, OSError):
            settings = dict(ledger_requests.DEFAULT_SETTINGS)
            error = 'Cấu hình không hợp lệ. Đang hiển thị mặc định; chưa ghi thay đổi.'
        with Vertical(id='settings-panel'):
            yield Label('CÀI ĐẶT GIỚI HẠN GỬI', classes='panel-title')
            with VerticalScroll(id='settings-body'):
                yield Static('Giới hạn nội bộ; không bảo đảm tránh phát hiện bot. UNKNOWN vẫn tính quota. Không tự retry.', classes='ui-muted')
                with Horizontal(classes='limit-row'):
                    yield Label('Bỏ qua nếu đã gửi hôm nay')
                    yield Switch(not settings['allow_repeat_same_day'], id='settings-skip')
                yield Static('Bỏ tích để cho phép gửi lặp; cần tăng hạn mức hội thoại tương ứng.', classes='ui-muted')
                for name, label in LIMIT_LABELS.items():
                    with Horizontal(classes='limit-row'):
                        yield Label(label)
                        yield Input(value=str(settings[name]), restrict=r'[0-9]*', max_length=10,
                            id='settings-'+name)
                yield Static('Khoảng nghỉ có thể bằng 0. Các hạn mức và độ dài cửa sổ phải lớn hơn 0.', classes='ui-muted')
                yield Static(error, id='settings-error')
            with Horizontal(id='settings-actions'):
                yield Button('LƯU GIỚI HẠN', id='settings-save', variant='primary')
                yield Button('HỦY', id='settings-cancel')

    def on_button_pressed(self, event):
        if event.button.id == 'settings-cancel':
            self.dismiss(None)
        elif event.button.id == 'settings-save':
            try:
                if self.original is None:
                    raise ValueError('Không đọc được cấu hình. Sửa file cấu hình rồi mở lại cài đặt.')
                if services.read_json_object(services.CONFIG_PATH) != self.original:
                    raise ValueError('Cấu hình đã đổi. Đóng và mở lại cài đặt.')
                db = ledger._DEFAULT_LEDGER_PATH
                session = self.original.get('session', '')
                if Path(db).exists() and any(r['event']['event_type'] == 'ACTIVATED'
                        for r in services.schedule_list(session, db_path=db)):
                    raise ValueError('Pause/revoke lịch đang hoạt động trước khi sửa giới hạn; cần authorize lại.')
                limits = {name: int(self.query_one('#settings-'+name, Input).value)
                    for name in LIMIT_LABELS}
                repeat = not self.query_one('#settings-skip', Switch).value
                ledger_requests.validate_settings(allow_repeat_same_day=repeat, **limits)
                settings = services.save_send_settings(repeat,
                    limits.pop('max_sends_per_conversation_per_day'), **limits)
            except (ValueError, OSError, ledger.LedgerError) as exc:
                self.query_one('#settings-error', Static).update(str(exc))
            else:
                self.dismiss(settings)
