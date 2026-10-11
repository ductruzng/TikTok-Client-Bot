"""Export actual 120x40 Textual screens using guarded synthetic data only."""
import asyncio
from pathlib import Path
import runpy
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
runpy.run_path(str(ROOT / 'tests/run_offline.py'), run_name='guard')

from relttk.application import services, tui
from relttk.storage import ledger


async def render(output):
    rows = [services.Conversation('fixture-friend-a', 1, 1, 'Bạn An'),
        services.Conversation('fixture-group-b', 2, 2, 'Nhóm bạn bè'),
        services.Conversation('fixture-friend-c', 3, 1, 'Bạn Bình')]
    policy = {'session': 'tai-khoan-mau', 'message': 'Chào bạn 👋\nGiữ streak cùng nhau nhé!',
        'targets': [r.target() for r in rows[:2]]}
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp, \
            patch.object(tui, 'list_sessions', return_value=['tai-khoan-mau']), \
            patch.object(tui, 'fetch_inbox', return_value=rows), \
            patch.object(tui, 'read_json_object', return_value=policy), \
            patch.object(services, 'read_json_object', return_value=policy), \
            patch.object(services, 'schedule_list', return_value=[]), \
            patch.object(ledger, '_DEFAULT_LEDGER_PATH', str(Path(tmp)/'fixture.db')):
        app = tui.TikTokTUI()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.3)
            app.save_screenshot('hoi-thoai.svg', path=str(output))
            await pilot.click('#send-now'); await pilot.pause()
            app.save_screenshot('kiem-tra-gui.svg', path=str(output))
            app.screen.dismiss(None); await pilot.pause()
            await pilot.press('f2'); await pilot.pause(0.3)
            app.save_screenshot('cai-dat.svg', path=str(output))
            app.screen.dismiss(None); await pilot.pause()
            await pilot.click('#nav-schedule'); await pilot.pause()
            app.save_screenshot('lich-gui.svg', path=str(output))
            await pilot.click('#schedule-manager'); await pilot.pause(0.3)
            app.save_screenshot('tao-lich.svg', path=str(output))
            app.screen.dismiss(None); await pilot.pause()
            await pilot.click('#nav-logs'); await pilot.pause()
            app.save_screenshot('nhat-ky.svg', path=str(output))
            await pilot.click('#nav-conversations'); await pilot.pause()
            await pilot.resize_terminal(80, 24); await pilot.pause()
            app.save_screenshot('hoi-thoai-80x24.svg', path=str(output))
    labels = [('hoi-thoai','Hội thoại'), ('cai-dat','Cài đặt F2'),
        ('lich-gui','Lịch gửi'), ('tao-lich','Tạo / quản lý lịch'),
        ('kiem-tra-gui','Kiểm tra gửi · bị chặn'), ('nhat-ky','Nhật ký'),
        ('hoi-thoai-80x24','Hội thoại · 80×24')]
    html = ['<!doctype html><meta charset="utf-8"><title>Mẫu TUI 120×40</title>',
        '<style>body{background:#0e1116;color:#e6e9ef;font:16px system-ui;margin:24px}a{color:#4fb8c9;margin-right:24px}section{margin:32px 0}svg{width:100%;height:auto}h2{font-size:20px}</style>',
        '<h1>Mẫu giao diện 120×40</h1><p>Dữ liệu giả. Không đăng nhập, không gửi tin, không truy cập database thật.</p>',
        '<nav>'+''.join(f'<a href="#{name}">{label}</a>' for name,label in labels)+'</nav>']
    for name,label in labels:
        html.append(f'<section id="{name}"><h2>{label}</h2>'+ (output/(name+'.svg')).read_text(encoding='utf-8')+'</section>')
    (output/'index.html').write_text('\n'.join(html), encoding='utf-8')
    print(str(output/'index.html'))


if __name__ == '__main__':
    asyncio.run(render(ROOT/'work/ui-preview'))
