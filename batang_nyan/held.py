"""클릭으로 고양이를 집고 드래그하는 held 상호작용 (Cat에 mixin)."""

from .constants import (
    HELD_FRAME_PERIOD,
    HELD_HOLD_FRAME,
    HELD_PICKUP,
    HELD_RELEASE,
)


class HeldMixin:
    """pickup → 프레임 4 유지 → 놓으면 5→6 재생 → walk."""

    def _init_held(self):
        """held 관련 필드를 초기화한다."""
        self.held_phase = None  # 'pickup' | 'hold' | 'release'
        self.held_seq_i = 0
        self.grab_dx = 0
        self.grab_dy = 0

    def _clear_held(self):
        """held 페이즈를 해제한다 (다른 상태로 전환될 때)."""
        self.held_phase = None
        self.held_seq_i = 0

    def start_held(self, grab_dx, grab_dy, win_x, win_y):
        """마우스 누름: 집기 애니 시작. grab_*는 창 안 커서 오프셋."""
        if 'held' not in self.sprites:
            return
        self.prev_state = self.state
        self.state = 'held'
        self.held_phase = 'pickup'
        self.held_seq_i = 0
        self.frame_idx = HELD_PICKUP[0]
        self.tick = 0
        self.frame_hold = HELD_FRAME_PERIOD
        self.jump_y_offset = 0
        self.breath_offset = 0
        self.grab_dx = grab_dx
        self.grab_dy = grab_dy
        self.x = float(win_x)
        self.y = float(win_y)

    def drag_to(self, screen_x, screen_y):
        """누르는 중 화면 좌표로 창 위치를 따라가게 한다 (release 중에는 무시)."""
        if self.state != 'held' or self.held_phase == 'release':
            return
        w, h = self._size()
        self.x = max(0.0, min(float(screen_x - self.grab_dx), float(self.screen_w - w)))
        self.y = max(0.0, min(float(screen_y - self.grab_dy), float(self.screen_h - h)))

    def release_held(self):
        """마우스 뗌: Y를 바닥에 붙이고 release 프레임(5→6)을 재생한다."""
        if self.state != 'held' or self.held_phase == 'release':
            return
        w, h = self._size()
        self.y = float(self.ground_y - h)
        self.x = max(0.0, min(self.x, float(self.screen_w - w)))
        self.held_phase = 'release'
        self.held_seq_i = 0
        self.frame_idx = HELD_RELEASE[0]
        self.tick = 0
        self.frame_hold = HELD_FRAME_PERIOD

    def _update_held_anim(self):
        """held 상태의 프레임을 한 틱 진행한다."""
        if self.held_phase == 'hold':
            return  # 누르는 동안 4번 프레임 고정

        self.tick += 1
        if self.tick < self.frame_hold:
            return
        self.tick = 0

        if self.held_phase == 'pickup':
            self.held_seq_i += 1
            if self.held_seq_i >= len(HELD_PICKUP):
                self.held_phase = 'hold'
                self.frame_idx = HELD_HOLD_FRAME
            else:
                self.frame_idx = HELD_PICKUP[self.held_seq_i]
            self.frame_hold = HELD_FRAME_PERIOD
            return

        if self.held_phase == 'release':
            self.held_seq_i += 1
            if self.held_seq_i >= len(HELD_RELEASE):
                walk = 'walk_r' if self.facing >= 0 else 'walk_l'
                self._set_state(walk)
            else:
                self.frame_idx = HELD_RELEASE[self.held_seq_i]
                self.frame_hold = HELD_FRAME_PERIOD
