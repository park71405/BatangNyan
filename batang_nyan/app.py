"""Tk 오버레이 앱: 렌더 루프, 말풍선, 클릭·드래그, 커서 근접 폴링."""

import datetime
import threading
import tkinter as tk

from . import sprite, tray
from .cat import Cat
from .constants import (
    BUBBLE_CHECK_MS,
    BUBBLE_EXTRA_H,
    BUBBLE_SCHEDULE,
    TICK_MS,
)
from .win32util import refresh_window


class BatangNyanApp:
    """투명 최상위 창으로 고양이를 그리고 입력을 받는다."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.wm_attributes('-topmost', True)
        self.root.wm_attributes('-transparentcolor', sprite.KEY_HEX)
        self.root.configure(bg=sprite.KEY_HEX)

        pil_sprites = sprite.load_all()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.cat = Cat(pil_sprites, screen_w, screen_h)

        init = self.cat.current_frame()
        self.canvas = tk.Canvas(
            self.root,
            width=init.width(),
            height=init.height(),
            bg=sprite.KEY_HEX,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()
        # delete('all') 대신 itemconfig로 바꿔 깜빡임을 줄인다
        self.sprite_id = self.canvas.create_image(0, 0, image=init, anchor='nw')

        self.root.update_idletasks()
        self.hwnd = self.root.winfo_id()

        self._last_notified_hour = -1
        # 이전 그리기 결과 캐시 — 변화 없을 때 전체 갱신 생략
        self._last_draw = {
            'frame': None,
            'geom': None,
            'bubble': None,
            'extra': -1,
        }

        self._bind_mouse()
        self._tick()
        self._check_time()

        threading.Thread(
            target=tray.setup_tray, args=(self.root,), daemon=True
        ).start()

    def _bind_mouse(self):
        """창·캔버스에 클릭/드래그/릴리즈를 연결한다."""
        for widget in (self.root, self.canvas):
            widget.bind('<ButtonPress-1>', self._on_press)
            widget.bind('<B1-Motion>', self._on_drag)
            widget.bind('<ButtonRelease-1>', self._on_release)

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
        """고양이 위 말풍선(태그 bubble)을 그린다."""
        self.canvas.delete('bubble')
        cx = fw // 2
        pad_x, pad_y = 10, 6
        font = ('맑은 고딕', 11, 'bold')
        tmp = self.canvas.create_text(0, 0, text=text, font=font)
        tx1, ty1, tx2, ty2 = self.canvas.bbox(tmp)
        self.canvas.delete(tmp)
        tw, th = tx2 - tx1, ty2 - ty1

        bx1 = cx - tw // 2 - pad_x
        bx2 = cx + tw // 2 + pad_x
        by1 = 4
        by2 = by1 + th + pad_y * 2

        self.canvas.create_rectangle(
            bx1, by1, bx2, by2,
            fill='white', outline='#555555', width=1, tags='bubble',
        )
        self.canvas.create_polygon(
            cx - 5, by2, cx + 5, by2, cx, by2 + 10,
            fill='white', outline='#555555', tags='bubble',
        )
        self.canvas.create_line(cx - 5, by2, cx, by2 + 10, fill='#555555', tags='bubble')
        self.canvas.create_line(cx + 5, by2, cx, by2 + 10, fill='#555555', tags='bubble')
        self.canvas.create_line(cx - 4, by2, cx + 4, by2, fill='white', tags='bubble')
        self.canvas.create_text(
            cx, by1 + pad_y + th // 2,
            text=text, font=font, fill='#222222', tags='bubble',
        )

    def paint(self, force=False):
        """고양이(·말풍선)를 그리고 창 geometry를 맞춘다. 변화 없으면 생략."""
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
            self.cat.update()
            self.paint(force=scared)
            self.root.after(TICK_MS, self._tick)
        except tk.TclError:
            pass  # 종료 중 창이 사라진 경우

    def _check_time(self):
        """정각 스케줄 말풍선 (중복 방지)."""
        h = datetime.datetime.now().hour
        if h in BUBBLE_SCHEDULE and h != self._last_notified_hour:
            self.cat.show_bubble(BUBBLE_SCHEDULE[h])
            self._last_notified_hour = h
        self.root.after(BUBBLE_CHECK_MS, self._check_time)

    def run(self):
        """Tk 메인 루프."""
        self.root.mainloop()
