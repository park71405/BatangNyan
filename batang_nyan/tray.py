"""시스템 트레이: 보이기/숨기기, 종료."""

import pystray
from PIL import Image

from .constants import ICON_PATH

_visible = True


def setup_tray(root):
    """트레이 아이콘을 띄우고 블로킹 루프를 돈다 (별도 데몬 스레드에서 호출)."""
    global _visible

    icon_img = Image.open(ICON_PATH).resize((32, 32), Image.LANCZOS)

    def toggle(icon, item):
        global _visible
        _visible = not _visible
        if _visible:
            root.after(0, root.deiconify)
        else:
            root.after(0, root.withdraw)

    def quit_app(icon, item):
        icon.stop()
        root.after(0, root.destroy)

    menu = pystray.Menu(
        pystray.MenuItem('보이기/숨기기', toggle),
        pystray.MenuItem('종료', quit_app),
    )
    icon = pystray.Icon('batang_nyan', icon_img, 'BatangNyan', menu)
    icon.run()
