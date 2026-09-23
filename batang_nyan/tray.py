"""시스템 트레이: 보이기/숨기기, 크기 프리셋, 모니터 선택, 재시작, 종료."""

import subprocess
import sys

import pystray
from PIL import Image

from .constants import ICON_PATH, SIZE_LABELS


def setup_tray(root, set_size_cb=None, initial_size='medium',
               set_monitor_cb=None, monitors=None, initial_monitor=None):
    """트레이 아이콘을 띄우고 블로킹 루프를 돈다 (별도 데몬 스레드에서 호출)."""
    visible = True
    current_size = initial_size
    current_monitor = initial_monitor
    icon_img = Image.open(ICON_PATH).resize((32, 32), Image.LANCZOS)

    def toggle(icon, item):
        nonlocal visible
        visible = not visible
        if visible:
            root.after(0, root.deiconify)
        else:
            root.after(0, root.withdraw)

    def quit_app(icon, item):
        root.after(0, root.destroy)
        icon.stop()

    def restart_app(icon, item):
        def do_restart():
            if getattr(sys, 'frozen', False):
                args = [sys.executable] + sys.argv[1:]
                # 부모 프로세스 종료 시 자식이 함께 죽지 않도록 완전 분리
                flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                args = [sys.executable] + sys.argv
                flags = 0
            subprocess.Popen(args, creationflags=flags)
            root.destroy()
        root.after(0, do_restart)
        icon.stop()

    def on_size(name):
        def handler(icon, item):
            nonlocal current_size
            current_size = name
            if set_size_cb:
                root.after(0, lambda: set_size_cb(name))
        return handler

    size_menu = pystray.Menu(
        pystray.MenuItem(
            SIZE_LABELS['small'], on_size('small'),
            checked=lambda item: current_size == 'small', radio=True,
        ),
        pystray.MenuItem(
            SIZE_LABELS['medium'], on_size('medium'),
            checked=lambda item: current_size == 'medium', radio=True,
        ),
        pystray.MenuItem(
            SIZE_LABELS['large'], on_size('large'),
            checked=lambda item: current_size == 'large', radio=True,
        ),
    )

    def on_monitor(idx):
        def handler(icon, item):
            nonlocal current_monitor
            current_monitor = idx
            if set_monitor_cb:
                root.after(0, lambda: set_monitor_cb(idx))
        return handler

    monitor_items = [
        pystray.MenuItem(
            '전체', on_monitor(None),
            checked=lambda item: current_monitor is None, radio=True,
        ),
    ]
    for i, (mx, my, mw, mh) in enumerate(monitors or []):
        label = f'모니터 {i + 1} ({mw}×{mh})'
        monitor_items.append(
            pystray.MenuItem(
                label, on_monitor(i),
                checked=lambda item, i=i: current_monitor == i, radio=True,
            )
        )
    monitor_menu = pystray.Menu(*monitor_items)

    menu = pystray.Menu(
        pystray.MenuItem('보이기/숨기기', toggle),
        pystray.MenuItem('크기', size_menu),
        pystray.MenuItem('모니터', monitor_menu),
        pystray.MenuItem('재시작', restart_app),
        pystray.MenuItem('종료', quit_app),
    )
    icon = pystray.Icon('batang_nyan', icon_img, '바탕화면 고양이', menu)
    icon.run()
