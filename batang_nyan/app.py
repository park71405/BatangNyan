"""Tk 오버레이 앱: 렌더 루프, 말풍선, 클릭·드래그, 커서 폴링, 크기·모니터 설정, 화면 절전 방지."""

import datetime
import json
import logging
import threading
import tkinter as tk
import traceback

from . import sprite, tray
from .cat import Cat
from .constants import (
    BUBBLE_CHECK_MS,
    BUBBLE_EXTRA_H,
    BUBBLE_FONT,
    BUBBLE_PAD_X,
    BUBBLE_PAD_Y,
    BUBBLE_SCHEDULE,
    BUBBLE_TAIL_H,
    CONFIG_DIR,
    CONFIG_PATH,
    KEY_HEX,
    SCALE_FACTORS,
    TICK_MS,
)
from .win32util import allow_sleep, get_monitors, get_virtual_screen, prevent_sleep, refresh_window

# 에러 로그: %APPDATA%\BatangNyan\error.log
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(CONFIG_DIR / 'error.log'),
    level=logging.ERROR,
    format='%(asctime)s\n%(message)s\n',
    encoding='utf-8',
)


class BatangNyanApp:
    """투명 최상위 창으로 고양이를 그리고 입력을 받는다."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.wm_attributes('-topmost', True)
        # Windows transparentcolor: KEY_HEX 픽셀은 클릭·표시 모두 통과
        self.root.wm_attributes('-transparentcolor', KEY_HEX)
        self.root.configure(bg=KEY_HEX)

        cfg = self._load_config()
        self._current_size = cfg.get('size', 'medium') if cfg.get('size') in SCALE_FACTORS else 'medium'

        pil_sprites = sprite.load_all(SCALE_FACTORS[self._current_size])
        virt_x, virt_y, virt_w, virt_h = get_virtual_screen()
        self._all_monitors = get_monitors()
        self._virt_rect = (virt_x, virt_y, virt_w, virt_h)

        saved_idx = cfg.get('monitor')
        if isinstance(saved_idx, int) and 0 <= saved_idx < len(self._all_monitors):
            self._current_monitor_idx = saved_idx
            mx, my, mw, mh = self._all_monitors[saved_idx]
            self.cat = Cat(pil_sprites, mw, mh, screen_x=mx, screen_y=my,
                           monitors=[self._all_monitors[saved_idx]])
        else:
            self._current_monitor_idx = None
            self.cat = Cat(pil_sprites, virt_w, virt_h, screen_x=virt_x, screen_y=virt_y,
                           monitors=self._all_monitors)

        init = self.cat.current_frame()
        self.canvas = tk.Canvas(
            self.root,
            width=init.width(),
            height=init.height(),
            bg=KEY_HEX,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()
        # delete('all') 대신 itemconfig로 바꿔 깜빡임을 줄인다
        self.sprite_id = self.canvas.create_image(0, 0, image=init, anchor='nw')

        self.root.update_idletasks()
        self.hwnd = self.root.winfo_id()

        self._last_notified_hour = -1
        self._last_draw = {}
        self._reset_draw_cache()

        prevent_sleep()
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

        self._bind_mouse()
        self._tick()
        self._check_time()

        threading.Thread(
            target=tray.setup_tray,
            args=(self.root, self.set_size, self._current_size,
                  self.set_monitor, self._all_monitors, self._current_monitor_idx),
            daemon=True,
        ).start()

    def _bind_mouse(self):
        """캔버스에 클릭/드래그/릴리즈를 연결한다."""
        self.canvas.bind('<ButtonPress-1>', self._on_press)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)

    def _on_press(self, event):
        """집기 시작."""
        self.cat.start_held(
            event.x, event.y, self.root.winfo_x(), self.root.winfo_y()
        )
        self.paint(force=True)

    def _on_drag(self, event):
        """집은 채로 커서 따라가기."""
        if self.cat.state != 'held':
            return
        self.cat.drag_to(event.x_root, event.y_root)
        self.paint(force=True)

    def _on_release(self, event):
        """놓기 → release 애니 → walk."""
        if self.cat.state != 'held':
            return
        self.cat.drag_to(event.x_root, event.y_root)
        self.cat.release_held()
        self.paint(force=True)

    def _draw_bubble(self, text, fw):
        """고양이 위 말풍선(태그 bubble)을 그린다.

        Tk polygon outline은 삼각형 아랫변(고양이 쪽)까지 그어져 말풍선 본체와
        겹쳐 보인다. 그래서 변 두 줄 + 아랫변을 흰색으로 덮어 ‘꼬리’만 남긴다.
        """
        self.canvas.delete('bubble')
        cx = fw // 2
        tmp = self.canvas.create_text(0, 0, text=text, font=BUBBLE_FONT)
        tx1, ty1, tx2, ty2 = self.canvas.bbox(tmp)
        self.canvas.delete(tmp)
        tw, th = tx2 - tx1, ty2 - ty1

        bx1 = cx - tw // 2 - BUBBLE_PAD_X
        bx2 = cx + tw // 2 + BUBBLE_PAD_X
        by1 = 4
        by2 = by1 + th + BUBBLE_PAD_Y * 2

        self.canvas.create_rectangle(
            bx1, by1, bx2, by2,
            fill='white', outline='#555555', width=1, tags='bubble',
        )
        self.canvas.create_polygon(
            cx - 5, by2, cx + 5, by2, cx, by2 + BUBBLE_TAIL_H,
            fill='white', outline='#555555', tags='bubble',
        )
        self.canvas.create_line(cx - 5, by2, cx, by2 + BUBBLE_TAIL_H, fill='#555555', tags='bubble')
        self.canvas.create_line(cx + 5, by2, cx, by2 + BUBBLE_TAIL_H, fill='#555555', tags='bubble')
        self.canvas.create_line(cx - 4, by2, cx + 4, by2, fill='white', tags='bubble')
        self.canvas.create_text(
            cx, by1 + BUBBLE_PAD_Y + th // 2,
            text=text, font=BUBBLE_FONT, fill='#222222', tags='bubble',
        )

    def _reset_draw_cache(self):
        self._last_draw = {'frame': None, 'geom': None, 'bubble': None, 'extra': -1}

    def paint(self, force=False):
        """고양이(·말풍선)를 그리고 창 geometry를 맞춘다. 변화 없으면 생략.

        force=True: 근접 점프 직후·클릭 등 프레임 동일해도 Win32 갱신이 필요할 때.
        매 성공 paint 끝의 refresh_window 는 transparentcolor 창의 잔상/깜빡임 완화용.
        """
        cat = self.cat
        frame = cat.current_frame()
        fw, fh = frame.width(), frame.height()
        x, y = cat.window_pos()

        has_bubble = bool(cat.bubble_text) and cat.state != 'held'
        extra = BUBBLE_EXTRA_H if has_bubble else 0
        total_h = fh + extra
        geom = (fw, total_h, x, y - extra)
        bubble_key = cat.bubble_text if has_bubble else None
        last = self._last_draw

        frame_changed = frame is not last['frame']
        geom_changed = geom != last['geom']
        bubble_changed = bubble_key != last['bubble'] or extra != last['extra']

        if not force and not (frame_changed or geom_changed or bubble_changed):
            return

        if geom_changed or extra != last['extra'] or force:
            self.canvas.configure(width=fw, height=total_h)
            self.root.geometry(f'{fw}x{total_h}+{x}+{y - extra}')

        if bubble_changed:
            if has_bubble:
                self._draw_bubble(cat.bubble_text, fw)
            else:
                self.canvas.delete('bubble')

        if frame_changed or bubble_changed or force:
            self.canvas.coords(self.sprite_id, 0, extra)
            self.canvas.itemconfig(self.sprite_id, image=frame)
            if has_bubble:
                self.canvas.tag_raise('bubble')

        last['frame'] = frame
        last['geom'] = geom
        last['bubble'] = bubble_key
        last['extra'] = extra
        refresh_window(self.hwnd)

    def _tick(self):
        """주기적으로 커서 근접 검사 → cat.update → paint."""
        try:
            mx = self.root.winfo_pointerx()
            my = self.root.winfo_pointery()
            scared = self.cat.try_mouse_scare(mx, my)
            gaze_changed = self.cat.update_gaze(mx, my)
            self.cat.update()
            self.paint(force=scared or gaze_changed)
        except tk.TclError:
            return  # 종료 중 창이 사라진 경우 — 루프 중단
        except Exception:
            logging.error(traceback.format_exc())
        self.root.after(TICK_MS, self._tick)

    def _check_time(self):
        """정각 스케줄 말풍선 (중복 방지)."""
        h = datetime.datetime.now().hour
        if h in BUBBLE_SCHEDULE and h != self._last_notified_hour:
            self.cat.show_bubble(BUBBLE_SCHEDULE[h])
            self._last_notified_hour = h
        self.root.after(BUBBLE_CHECK_MS, self._check_time)

    def set_size(self, size_name):
        """설정을 즉시 저장하고 스프라이트를 백그라운드에서 로드한 뒤 적용한다."""
        if size_name == self._current_size:
            return
        self._current_size = size_name
        self._save_config()

        def _load():
            new_sprites = sprite.load_all(SCALE_FACTORS[size_name])

            def _apply():
                if self._current_size != size_name:
                    return  # 로드 중 다른 크기로 변경된 경우 무시
                self.cat.reload_sprites(new_sprites)
                self._reset_draw_cache()
                self.paint(force=True)

            self.root.after(0, _apply)

        threading.Thread(target=_load, daemon=True).start()

    def set_monitor(self, idx):
        """모니터 선택. idx=None이면 전체 가상 데스크톱 (Tk 메인 스레드에서 호출)."""
        if idx == self._current_monitor_idx:
            return
        self._current_monitor_idx = idx
        if idx is None:
            vx, vy, vw, vh = self._virt_rect
            self.cat.set_active_region(vx, vy, vw, vh, self._all_monitors)
        else:
            mx, my, mw, mh = self._all_monitors[idx]
            self.cat.set_active_region(mx, my, mw, mh, [self._all_monitors[idx]])
        self._reset_draw_cache()
        self.paint(force=True)
        self._save_config()

    @staticmethod
    def _load_config():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
        except Exception:
            return {}

    def _save_config(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps({'size': self._current_size, 'monitor': self._current_monitor_idx},
                       ensure_ascii=False),
            encoding='utf-8',
        )

    def _on_close(self):
        allow_sleep()
        self.root.destroy()

    def run(self):
        """Tk 메인 루프."""
        self.root.mainloop()
        allow_sleep()  # mainloop 종료 경로(트레이 quit 등) 공통 처리
