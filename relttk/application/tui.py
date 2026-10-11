"""TikTok Streak Manager - Modern Dashboard TUI v0.3.

Run: python -B main.py tui
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from rich.text import Text

from textual.app import App, ComposeResult
from textual.screen import ModalScreen
from textual.theme import Theme
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual import work
from textual.widgets import (
    Button, DataTable, Footer, Input, RichLog,
    Select, Static, TextArea, ContentSwitcher,
)

from relttk.application.services import (
    CONFIG_PATH, PREFS_PATH, ROOT, Conversation,
    fetch_inbox, list_sessions, matching_selected_ids,
    read_json_object, save_plan,
)


class SendNowReview(ModalScreen):
    DEFAULT_CSS = '''SendNowReview { align: center middle; }
    #send-review { width: 90%; max-width: 90; height: 80%; border: round $accent; background: $surface; padding: 1; }
    #send-review Static { height: auto; }'''

    def __init__(self, policy):
        super().__init__()
        self.policy = policy

    def compose(self):
        with VerticalScroll(id='send-review'):
            yield Static('Kiểm tra trước khi gửi', classes='panel-title')
            yield Static('Tài khoản: '+str(self.policy.get('session', '')), markup=False)
            yield Static('Người nhận:\n'+'\n'.join(str(t['conv_id']) for t in self.policy.get('targets', [])), markup=False)
            yield Static(str(self.policy.get('message', '')), markup=False)
            yield Static('CHƯA THỂ GỬI: danh tính tài khoản chưa được xác minh. Không gửi tin, không tạo request hay bỏ qua hạn mức.', classes='ui-warning')
            yield Static('Server xác nhận không có nghĩa người nhận đã đọc hoặc tin được tính streak.', classes='ui-muted')
            yield Button('Xác nhận gửi (đang bị chặn)', disabled=True)
            yield Button('Đóng', id='send-review-close')

    def on_button_pressed(self, event):
        if event.button.id == 'send-review-close':
            self.dismiss()


class Dashboard(Horizontal):
    def on_resize(self, event) -> None:
        self.set_class(event.size.height < 28, 'short')
        self.app.call_after_refresh(self.app._fit_table)


class TikTokTUI(App):
    TITLE = "TikTok Streak Manager"
    CSS = """
    Screen { background: #0e1116; color: #e6e9ef; }
    .panel-title { height: auto; text-style: bold; color: #4fb8c9; }
    .ui-muted { height: auto; color: #8b95a5; }
    .ui-warning { height: auto; color: #e0b050; }
    Button { background: #161b22; }
    Button.-primary { background: #4fb8c9; color: #0e1116; }
    #topbar { height: 3; background: #161b22; }
    #brand { width: 1fr; padding: 1 1; height: 3; }
    #account { width: 22; border: none; }
    #topbar Button { min-width: 5; height: 3; padding: 0 1; }
    #settings-open { width: 15; }
    #main-container { height: 1fr; }
    #navigation { width: 18; border-right: solid #2a313c; padding: 1 0; background: #161b22; }
    #navigation Button { width: 100%; min-width: 10; height: 3; border: none; }
    #pages { width: 1fr; height: 1fr; }
    #conversations-page { padding: 0 1; }
    #inbox-card { height: 1fr; }
    #search-row { height: 3; }
    #search { width: 1fr; }
    #filter { width: 20; border: none; }
    Input { height: 3; border: tall #2a313c; background: #0e1116; }
    Input:focus { border: tall #4fb8c9; }
    #table-toolbar { height: 3; }
    #table-toolbar Button { min-width: 10; height: 3; padding: 0 1; }
    #inbox-counter { width: 1fr; padding: 1 1; }
    #inbox-notice { height: 2; color: #8b95a5; }
    .short #inbox-notice { height: 1; }
    #inbox-notice.error { color: #e0676a; }
    #table { height: 1fr; border: tall #2a313c; background: #0e1116; }
    DataTable > .datatable--header { background: #161b22; color: #e6e9ef; text-style: bold; }
    #message-card { height: 9; padding-top: 1; }
    .short #message-card { height: 5; padding-top: 0; }
    .short #message-caption { display: none; }
    .short #message { height: 2; border: none; }
    .short #table-toolbar { height: 1; }
    .short #table-toolbar Button { height: 1; border: none; }
    .short #inbox-counter { padding: 0 1; }
    #message { height: 4; border: tall #2a313c; background: #0e1116; }
    #message:focus { border: tall #4fb8c9; }
    #message-caption { height: 1; color: #4fb8c9; text-style: bold; }
    #message-state { width: 1fr; padding: 1 0; }
    #message-state.saved { color: #5fbf7a; }
    #message-state.draft { color: #e0b050; }
    #message-save-row, #main-actions { height: 3; }
    #save-all { height: 3; min-width: 23; }
    #main-actions Button { height: 3; min-width: 14; }
    #schedule-page { padding: 1 2; }
    #schedule-overview, #schedule-message, #schedule-status { height: auto; }
    #schedule-message { border: tall #2a313c; padding: 0 1; }
    #schedule-manager { width: 100%; height: 3; }
    #logs-page { padding: 1; }
    #activity { height: 1fr; border: tall #2a313c; background: #0e1116; }
    #statusbar { height: 2; background: #161b22; padding: 0 1; }
    Footer { height: 1; background: #161b22; }
    """

    BINDINGS = [
        ("f2", "settings", "Cài đặt"),
        ("ctrl+r", "refresh", "Làm mới tất cả"),
        ("ctrl+s", "sync", "Đồng bộ Inbox"),
        ("ctrl+q", "quit", "Thoát"),
    ]

    def __init__(self):
        super().__init__()
        self.register_theme(Theme(name='streak', primary='#4fb8c9', accent='#4fb8c9',
            secondary='#8b95a5', foreground='#e6e9ef', background='#0e1116',
            surface='#161b22', panel='#161b22', success='#5fbf7a',
            warning='#e0b050', error='#e0676a'))
        self.theme = 'streak'
        self.conversations: list[Conversation] = []
        self.selected_ids: set[str] = set()
        self.loaded_for: str | None = None
        self._initialized = False
        self._fetching = False
        self._generation = 0
        self._draft_session = ''
        self._drafts = {}
        self._sync_requested = False
        self._sync_context = None
        self._inbox_error = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="topbar"):
            yield Static("TikTok Streak Manager", id="brand")
            yield Select([], prompt="Chọn tài khoản", allow_blank=True, id="account")
            yield Button("↻", id="refresh", tooltip="Làm mới toàn bộ; giữ bản nháp")
            yield Button("QR", id="login")
            yield Button("Cài đặt F2", id="settings-open")
        with Dashboard(id="main-container"):
            with Vertical(id="navigation"):
                yield Button("Hội thoại", id="nav-conversations", variant="primary")
                yield Button("Lịch gửi", id="nav-schedule")
                yield Button("Nhật ký", id="nav-logs")
            with ContentSwitcher(initial="conversations-page", id="pages"):
                with Vertical(id="conversations-page"):
                    with Vertical(id="inbox-card"):
                        with Horizontal(id="search-row"):
                            yield Input(placeholder="Tìm tên, nhóm, ID…", id="search")
                            yield Select([("Tất cả", "all"), ("Cá nhân", "direct"), ("Nhóm", "group")],
                                value="all", allow_blank=False, id="filter")
                        with Horizontal(id="table-toolbar"):
                            yield Button("Chọn hết", id="select-visible")
                            yield Button("Bỏ chọn", id="clear-selection")
                            yield Static("Chưa đồng bộ", id="inbox-counter")
                        yield Static('', id='inbox-notice', markup=False)
                        yield DataTable(id="table", cursor_type="row", zebra_stripes=True)
                    with Vertical(id="message-card"):
                        yield Static("TIN NHẮN STREAK", id="message-caption")
                        yield TextArea(id="message")
                        with Horizontal(id="message-save-row"):
                            yield Static("Chưa lưu", id="message-state")
                            yield Button("Lưu tin & người nhận", id="save-all")
                    with Horizontal(id="main-actions"):
                        yield Button("Gửi ngay", id="send-now", variant="primary")
                        yield Button("Chạy thử", id="dryrun")
                with VerticalScroll(id="schedule-page"):
                    yield Static("LỊCH GỬI", classes="panel-title")
                    yield Static("", id="schedule-overview", markup=False)
                    yield Static("TIN NHẮN ĐÃ LƯU", classes='panel-title')
                    yield Static("Chưa có nội dung đã lưu", id="schedule-message", markup=False)
                    yield Static("Chỉnh nội dung và người nhận tại Hội thoại, rồi lưu trước khi tạo lịch.", classes='ui-muted')
                    yield Button("Cấu hình / quản lý lịch gửi", id="schedule-manager")
                    yield Static("Chưa tải trạng thái lịch", id="schedule-status", markup=False)
                with Vertical(id="logs-page"):
                    yield Static("NHẬT KÝ HOẠT ĐỘNG", classes='panel-title')
                    yield Static('Nhật ký trong phiên này. Lưu cấu hình không phải xác nhận gửi thành công.', classes='ui-muted')
                    yield RichLog(id="activity", markup=False, wrap=True, auto_scroll=True)
        yield Static("Scheduler: TẮT · cần recurring consent", id="statusbar", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#table", DataTable)
        table.add_column("✓", width=3)
        table.add_column("Tên hiển thị", key="name", width=22)
        table.add_column("Loại", width=7)
        self.refresh_sessions(initial=True)
        self._initialized = True
        self._activity("🚀 TikTok Streak Manager v0.3 Dashboard đã sẵn sàng.")
        self.call_after_refresh(self._account_changed)
        self.call_after_refresh(self._fit_table)

    def _fit_table(self) -> None:
        table = self.query_one('#table', DataTable)
        if table.columns:
            column = next(c for k, c in table.columns.items() if k.value == 'name')
            column.width = max(10, table.size.width - 18)
            table.refresh(layout=True)

    def _activity(self, text: str) -> None:
        self.query_one("#activity", RichLog).write(text)

    def _session(self) -> str:
        selected = self.query_one("#account", Select).value
        return selected if isinstance(selected, str) else ""

    def _saved_plan(self) -> dict:
        return read_json_object(CONFIG_PATH)

    def refresh_sessions(self, initial: bool = False) -> None:
        try:
            names = list_sessions()
            options = [(name, name) for name in names]
            account = self.query_one("#account", Select)
            previous = self._session()
            saved = self._saved_plan()
            preferred = previous if previous in names else saved.get("session", "")
            if preferred not in names:
                preferred = names[0] if names else ""
            account.set_options(options)
            account.value = preferred if preferred else Select.NULL
            if initial:
                self.query_one("#message", TextArea).load_text(str(saved.get("message", "")))
            self._update_summary()
            if not initial:
                self.notify(f"Tìm thấy {len(names)} tài khoản đã lưu")
        except (OSError, ValueError) as exc:
            self.notify(f"Không thể đọc cấu hình: {type(exc).__name__}", severity="error")

    def _update_summary(self) -> None:
        try:
            config = self._saved_plan()
        except (OSError, ValueError):
            config = {}
        account_name = self._session() or "(Chưa chọn)"
        targets_count = (len(config.get('targets', [])) if config.get('session') == self._session()
            and isinstance(config.get('targets'), list) else 0)
        
        self.query_one("#statusbar", Static).update(
            f"{account_name} · Đã lưu: {targets_count} người nhận | Scheduler: TẮT · cần recurring consent")
        self.query_one('#schedule-overview', Static).update(
            f"Tài khoản: {account_name} · Đã lưu: {targets_count} người nhận\nScheduler: TẮT · cần recurring consent. TUI không chạy lịch nền.")
        self.query_one('#schedule-message', Static).update(
            str(config.get('message', '')) if config.get('session') == self._session() else 'Chưa có nội dung đã lưu cho tài khoản này')
        saved_ids = matching_selected_ids(config.get('targets', []), self.conversations) if config.get('session') == self._session() else set()
        saved = (config.get('session') == self._session() and config.get('message', '') == self.query_one('#message', TextArea).text
            and saved_ids == self.selected_ids and len(config.get('targets', [])) == len(saved_ids)
            and self.loaded_for == self._session())
        message_state = self.query_one('#message-state', Static)
        message_state.update('Đã lưu' if saved else 'Bản nháp · chưa lưu')
        message_state.set_class(saved, 'saved')
        message_state.set_class(not saved, 'draft')

        visible_count = len(self._visible()) if self.loaded_for == self._session() else 0
        total_count = len(self.conversations) if self.loaded_for == self._session() else 0
        selected_count = len(self.selected_ids)
        
        if self.loaded_for != self._session():
            self.query_one("#inbox-counter", Static).update("Chưa đồng bộ tài khoản này")
        else:
            self.query_one("#inbox-counter", Static).update(
                f"Đã chọn: {selected_count} | Hiển thị: {visible_count}/{total_count}"
            )
        notice = self.query_one('#inbox-notice', Static)
        context = (self._session(), self._generation)
        failed = self._inbox_error == context
        notice.set_class(failed, 'error')
        if not self._session():
            text = 'Chưa có tài khoản · chọn tài khoản hoặc đăng nhập QR.'
        elif self._fetching and self._sync_context == context:
            text = 'Đang tải inbox… Bản nháp được giữ nguyên.'
        elif failed:
            text = 'Lỗi đồng bộ · bấm ↻ để thử lại. Bản nháp được giữ nguyên.'
        elif self.loaded_for != self._session():
            text = 'Chưa tải inbox · bấm ↻ để làm mới.'
        elif not total_count:
            text = 'Inbox rỗng · có thể bấm ↻ để kiểm tra lại.'
        elif not visible_count:
            text = 'Không tìm thấy kết quả · đổi từ khóa hoặc bộ lọc.'
        else:
            text = 'Chọn người nhận và lưu nội dung trước khi gửi hoặc tạo lịch.'
        notice.update(text)

    def _reset_inbox(self) -> None:
        self.loaded_for = None
        self.conversations = []
        self.selected_ids.clear()
        self.query_one("#table", DataTable).clear()
        self._update_summary()

    def on_select_changed(self, event: Select.Changed) -> None:
        if self._initialized and event.select.id == "account":
            self._account_changed()
        elif self._initialized and event.select.id == 'filter':
            self._render_table()

    def _account_changed(self) -> None:
        if self._session() != self._draft_session:
            self._generation += 1
            if self._draft_session:
                self._drafts[self._draft_session] = (self.conversations, set(self.selected_ids),
                    self.query_one('#message', TextArea).text, self.loaded_for)
            self._reset_inbox()
            session = self._session()
            self._draft_session = session
            if session in self._drafts:
                self.conversations, self.selected_ids, text, self.loaded_for = self._drafts[session]
            else:
                saved = self._saved_plan()
                text = str(saved.get('message', '')) if saved.get('session') == session else ''
            self.query_one('#message', TextArea).load_text(text)
            self._render_table()
            self._activity(f"Đã chọn tài khoản: {session or '(Không chọn)' }.")
            if session:
                self.action_sync()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self._render_table()
    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if self._initialized:
            self._update_summary()

    def _visible(self) -> list[Conversation]:
        keyword = self.query_one("#search", Input).value.strip().casefold()
        kind = self.query_one('#filter', Select).value
        return [c for c in self.conversations
            if (kind == 'all' or (kind == 'group' and c.conv_type == 2) or (kind == 'direct' and c.conv_type == 1))
            and (not keyword or keyword in c.name.casefold() or keyword in c.conv_id.casefold()
                or keyword in str(c.conv_short_id))]

    def _render_table(self) -> None:
        table = self.query_one("#table", DataTable)
        table.clear()
        if self.loaded_for != self._session():
            return
        visible = self._visible()
        for c in visible:
            is_selected = c.conv_id in self.selected_ids
            check_box = "[x]" if is_selected else "[ ]"
            conv_kind = "Nhóm" if c.conv_type == 2 else "Cá nhân"
            table.add_row(
                Text(check_box),
                Text(c.name),
                conv_kind,
                key=c.conv_id,
            )
        self._update_summary()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "table" or self.loaded_for != self._session():
            return
        conv_id = str(event.row_key.value)
        if conv_id in self.selected_ids:
            self.selected_ids.remove(conv_id)
        else:
            self.selected_ids.add(conv_id)
        self._render_table()

    async def _sync_inbox(self) -> None:
        session = self._session()
        if not session:
            self.notify("Vui lòng chọn một tài khoản TikTok trước khi đồng bộ!", severity="warning")
            return
        if self._fetching:
            self._sync_requested = True
            return
        self._sync_requested = False
        self._fetching = True
        generation = self._generation
        self._sync_context = (session, generation)
        self._inbox_error = None
        self._update_summary()
        previous = [c.target() for c in self.conversations if c.conv_id in self.selected_ids] if self.loaded_for == session else None
        self.query_one("#refresh", Button).disabled = True
        self._activity(f"⏳ Đang kết nối máy chủ TikTok đồng bộ hội thoại cho '{session}'...")
        try:
            conversations = await asyncio.to_thread(fetch_inbox, session)
            if session != self._session() or generation != self._generation:
                self._activity("Tài khoản đã đổi trong lúc tải; đã hủy kết quả cũ.")
                return
            config = self._saved_plan()
            old = previous if previous is not None else (config.get("targets", []) if config.get("session") == session else [])
            if self.loaded_for == session:
                old = [c.target() for c in self.conversations if c.conv_id in self.selected_ids]
            self.conversations = conversations
            self.loaded_for = session
            self.selected_ids = matching_selected_ids(old, conversations)
            self._render_table()
            self._activity(f"✅ Đồng bộ thành công: Tìm thấy {len(conversations)} hội thoại (Đã tích chọn lại {len(self.selected_ids)} trước đó).")
            self.notify(f"Đã đồng bộ {len(conversations)} hội thoại!", severity="information")
        except Exception as exc:
            if session == self._session() and generation == self._generation:
                self._inbox_error = (session, generation)
            self._activity(f"❌ Không thể đồng bộ inbox: {type(exc).__name__}.")
            self.notify("Đồng bộ thất bại; kiểm tra kết nối mạng hoặc đăng nhập lại!", severity="error")
        finally:
            self._fetching = False
            self.query_one("#refresh", Button).disabled = False
            self._update_summary()
            if self._sync_requested and self.is_running:
                self.action_sync()

    def _save_all(self) -> None:
        session = self._session()
        if not session or self.loaded_for != session:
            self.notify("Vui lòng đồng bộ Inbox của tài khoản trước khi lưu!", severity="warning")
            return
        
        chosen = [c for c in self.conversations if c.conv_id in self.selected_ids]
        if not chosen:
            self.notify("Vui lòng tích chọn ít nhất 1 người nhận!", severity="warning")
            return

        message = self.query_one("#message", TextArea).text
        if not message.strip():
            self.notify("Vui lòng nhập nội dung tin nhắn!", severity="warning")
            return

        try:
            from relttk.application.services import schedule_list
            from relttk.storage import ledger
            db = ledger._DEFAULT_LEDGER_PATH
            if Path(db).exists() and any(r['event']['event_type'] == 'ACTIVATED' for r in schedule_list(session, db_path=db)):
                raise ValueError('Pause/revoke active grants before editing; authorize a new preview afterwards')
            save_plan(session, message, chosen)
            self._activity(f"Đã lưu tin nhắn và {len(chosen)} người nhận; chưa cấp quyền lịch.")
            self.notify(f"Đã lưu {len(chosen)} người nhận và cấu hình; chưa kích hoạt lịch CLI.", severity="information")
            self._update_summary()
        except (ValueError, OSError) as exc:
            self.notify(f"Lỗi khi lưu cấu hình: {exc}", severity="error")
            self._activity(f"❌ Lỗi lưu cấu hình: {exc}")

    def _launch_terminal(self, *args: str) -> None:
        if os.name != "nt":
            self.notify("Đóng TUI và chạy python -B main.py login trong terminal này; mở lại sau đăng nhập.", severity="information")
            return
        try:
            subprocess.Popen(
                [sys.executable, "-B", str(ROOT / "main.py"), *args],
                cwd=str(ROOT), creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            self._activity("📷 Đã mở cửa sổ QR Login. Hãy quét mã bằng ứng dụng TikTok trên điện thoại.")
            self.notify("Đã mở cửa sổ QR Login!", severity="information")
        except OSError:
            self.notify("Không mở được terminal đăng nhập", severity="error")

    async def _dryrun(self) -> None:
        if not CONFIG_PATH.exists():
            self.notify("Chưa có cấu hình. Hãy chọn người nhận và bấm Lưu trước.", severity="warning")
            return
        self._activity("🧪 Đang kiểm tra chạy thử (Offline Dry-run)...")
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-B", str(ROOT / "main.py"),
                "--config", str(CONFIG_PATH), "--dry-run",
                cwd=str(ROOT), stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=25)
            content = out.decode("utf-8", errors="replace")
            for line in content.splitlines():
                if any(marker in line for marker in (
                    "Planned Targets (", "DRY-RUN COMPLETE", "Zero network calls",
                    "Config Validation Issues", "Dry-run stopped",
                )):
                    self._activity(line.strip())
            self.notify("Dry-run hoàn tất!", severity="information" if proc.returncode == 0 else "warning")
        except (OSError, asyncio.TimeoutError):
            self._activity("❌ Dry-run không hoàn thành.")
            self.notify("Không chạy được dry-run", severity="error")

    def action_refresh(self) -> None:
        self.refresh_sessions()
        self._refresh_schedule_status()
        self._update_summary()
        self._activity('Đang làm mới toàn bộ; giữ tin nhắn và lựa chọn chưa lưu.')
        if self._session():
            self.action_sync()

    def _refresh_schedule_status(self) -> None:
        try:
            from relttk.application.services import schedule_list
            from relttk.application.schedule_ui import STATE_LABELS
            from relttk.storage import ledger
            rows = schedule_list(self._session(), db_path=ledger._DEFAULT_LEDGER_PATH) if self._session() else []
            text = '\n'.join(r['consent']['schedule_id']+' · '+STATE_LABELS.get(r['event']['event_type'], r['event']['event_type']) for r in rows)
            self.query_one('#schedule-status', Static).update(text or 'Chưa có lịch đã cấp quyền.')
        except Exception as exc:
            self.query_one('#schedule-status', Static).update('Không tải được trạng thái lịch: '+type(exc).__name__)
            self._activity('Làm mới trạng thái lịch thất bại: '+type(exc).__name__)


    def action_sync(self) -> None:
        self.run_worker(self._sync_inbox(), group='inbox')

    def action_settings(self) -> None:
        from relttk.application.settings_ui import SendSettingsScreen
        self.push_screen(SendSettingsScreen(), self._settings_saved)

    @work(thread=True, group="send")
    def _run_send(self, source: str) -> None:
        if source == 'Scheduler':
            self.call_from_thread(self._activity, 'Legacy scheduler disabled. Review schedule consent through CLI.')
            return
        from relttk.transport import oneshot
        from relttk.application.services import summarize_results
        try:
            from relttk.application.services import send_plan
            import uuid
            key = "manual:" + str(uuid.uuid4())
            def preview_only(row):
                self.call_from_thread(self._activity, f"Preview request={row['request_id']}: {row['payload_json']}")
                self.call_from_thread(self._activity, "Request held. Use CLI --send --request-id with this request's stored idempotency key to review and confirm.")
                return False
            result = asyncio.run(send_plan(CONFIG_PATH, idempotency_key=key,
                confirm_request=preview_only))
            confirmed, skipped, failed = summarize_results(result)
            text = (f"[{source}] ✅ Kết quả: {confirmed} xác nhận thành công | {skipped} bỏ qua | {failed} thất bại.")
            self.call_from_thread(self._activity, text)
            self.call_from_thread(self.notify, text, severity="warning" if failed else "information")
            for r in result.get("results", []):
                cid = r.get('conv_id', '')
                st = r.get('status', '')
                rs = r.get('reason', '')
                self.call_from_thread(self._activity, f"   ↳ {cid}: {st} {r.get('detail') or rs} | request={r.get('request_id', '')}")
        except Exception as exc:
            text = f"[{source}] ❌ Quá trình gửi gặp lỗi: {type(exc).__name__}."
            self.call_from_thread(self._activity, text)
            self.call_from_thread(self.notify, text, severity="error")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        action = event.button.id
        if action == "refresh":
            self.action_refresh()
        elif action == "login":
            self._launch_terminal("login")
        elif action == "sync":
            self.action_sync()
        elif action == "dryrun":
            await self._dryrun()
        elif action == "select-visible":
            if self.loaded_for == self._session():
                self.selected_ids.update(c.conv_id for c in self._visible())
                self._render_table()
        elif action == "clear-selection":
            self.selected_ids.clear()
            self._render_table()
        elif action == "save-all":
            self._save_all()
        elif action == 'schedule-manager':
            from relttk.application.schedule_ui import ScheduleScreen
            self.push_screen(ScheduleScreen(self._session(), lambda: (self._session(), self._generation)),
                lambda _: self._refresh_schedule_status())
        elif action == 'settings-open':
            self.action_settings()
        elif action in ('nav-conversations', 'nav-schedule', 'nav-logs'):
            page = {'nav-conversations':'conversations-page', 'nav-schedule':'schedule-page', 'nav-logs':'logs-page'}[action]
            self.query_one('#pages', ContentSwitcher).current = page
            for button in self.query('#navigation Button'):
                button.variant = 'primary' if button.id == action else 'default'
            if action == 'nav-schedule':
                self._update_summary()
                self._refresh_schedule_status()
        elif action == "send-now":
            saved = self._saved_plan()
            chosen = [c.target() for c in self.conversations if c.conv_id in self.selected_ids]
            if (saved.get('session') != self._session() or saved.get('message') != self.query_one('#message', TextArea).text
                    or sorted(chosen, key=lambda t:t['conv_id']) != sorted(saved.get('targets', []), key=lambda t:t['conv_id'])):
                self.notify('Lưu tin và người nhận trước khi gửi.', severity='warning')
            elif not chosen:
                self.notify('Chọn ít nhất một người nhận.', severity='warning')
            else:
                self.push_screen(SendNowReview(saved))

    def _settings_saved(self, settings) -> None:
        if settings is not None:
            self._update_summary()
            self.notify('Đã lưu giới hạn gửi; chưa kích hoạt lịch hay gửi tin.')


if __name__ == "__main__":
    TikTokTUI().run()
