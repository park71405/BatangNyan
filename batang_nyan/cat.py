"""고양이 상태 머신: 걷기·대기·앉기·그루밍·점프(좌/우)·에너지 (+ sleep/stretch).

HeldMixin으로 클릭 집기를 섞는다. 창/입력은 app.py가 담당한다.
"""

import math
import random

from PIL import ImageTk

from .constants import (
    DURATION,
    ENERGY_INSTANT,
    ENERGY_PER_TICK,
    FRAME_HOLDS,
    FRAME_PERIOD,
    GROUND_MARGIN,
    JUMP_FRAME_MAP,
    JUMP_Y_OFFSETS,
    MOUSE_JUMP_LEAVE_EXTRA,
    MOUSE_JUMP_RADIUS,
    TRANSITIONS,
    WALK_SPEED_MAX,
    WALK_SPEED_MIN,
    WALL_MARGIN,
    WALL_SLOW_ZONE,
)
from .held import HeldMixin


class Cat(HeldMixin):
    """자동 행동·애니메이션·근접 점프를 가진 고양이 캐릭터."""

    def __init__(self, pil_sprites, screen_w, screen_h):
        """스프라이트 dict와 화면 크기로 초기화한다."""
        self.pil_sprites = pil_sprites
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.ground_y = screen_h - GROUND_MARGIN

        self.sprites = {
            k: [ImageTk.PhotoImage(f) for f in frames]
            for k, frames in pil_sprites.items()
        }
        # 로드되지 않은 상태(sleep 등)는 전환 표에서 제외
        self._transitions = {
            src: [(s, w) for s, w in opts if s in self.sprites]
            for src, opts in TRANSITIONS.items()
            if src in self.sprites
        }
        for src, opts in list(self._transitions.items()):
            if not opts:
                self._transitions[src] = [
                    (s, w) for s, w in [('idle', 1), ('walk_r', 1), ('walk_l', 1)]
                    if s in self.sprites
                ]

        self.state = 'walk_r'
        self.prev_state = None
        self.facing = 1  # 1=오른쪽, -1=왼쪽
        self.frame_idx = 0
        self.tick = 0
        self.frame_hold = self._hold_for('walk_r', 0)
        self.state_timer = random.randint(*DURATION['walk_r'])
        self.jump_step = 0
        self.jump_y_offset = 0
        self.breath_offset = 0
        self.breath_phase = 0.0
        self.walk_speed = random.uniform(WALK_SPEED_MIN, WALK_SPEED_MAX)
        self.accel = 0.0
        self.energy = random.randint(50, 80)
        self.bubble_text = None
        self.bubble_ticks = 0
        self._mouse_near = False  # 근접 영역 안에 있는지 (진입 에지 감지용)
        self._init_held()

        w, h = self._size()
        self.x = float(random.randint(WALL_MARGIN, max(WALL_MARGIN, screen_w - w - WALL_MARGIN)))
        self.y = float(self.ground_y - h)

    def _size(self, state=None):
        """해당 상태 스프라이트의 (너비, 높이)."""
        s = state or self.state
        return self.pil_sprites[s][0].size

    def _hold_for(self, state, frame_idx):
        """프레임을 몇 tick 유지할지."""
        holds = FRAME_HOLDS.get(state)
        if holds:
            return holds[frame_idx % len(holds)]
        return FRAME_PERIOD.get(state, 2)

    def current_frame(self):
        """지금 그릴 PhotoImage."""
        frames = self.sprites[self.state]
        return frames[self.frame_idx % len(frames)]

    def window_pos(self):
        """화면상 창 왼쪽·위 좌표. held는 자유 Y, 그 외는 바닥 + 점프/호흡 오프셋."""
        _, h = self._size()
        if self.state == 'held':
            return int(round(self.x)), int(round(self.y))
        y_off = self.jump_y_offset + self.breath_offset
        return int(round(self.x)), self.ground_y - h + y_off

    def show_bubble(self, text, duration_ticks=30):
        """머리 위 말풍선 텍스트를 표시한다."""
        self.bubble_text = text
        self.bubble_ticks = duration_ticks

    def try_mouse_scare(self, mx, my):
        """커서가 근접 영역에 들어오면 제자리 점프 1회. 시작했으면 True.

        held/jump 중에는 무시. 영역을 나간 뒤 다시 들어와야 재발동.
        커서 반대 방향으로 점프한 뒤 그 방향으로 걷는다.
        """
        if self.state in ('held', 'jump_r', 'jump_l'):
            return False

        w, h = self._size()
        wx, wy = self.window_pos()
        cx = wx + w / 2
        cy = wy + h / 2
        dist = math.hypot(mx - cx, my - cy)

        enter_r = MOUSE_JUMP_RADIUS
        leave_r = MOUSE_JUMP_RADIUS + MOUSE_JUMP_LEAVE_EXTRA

        if self._mouse_near:
            if dist > leave_r:
                self._mouse_near = False
            return False

        if dist > enter_r:
            return False

        # 진입 에지: 커서 반대 방향(도망)으로 점프
        self._mouse_near = True
        self.facing = 1 if mx < cx else -1
        self._set_state('jump_r' if self.facing > 0 else 'jump_l')
        return True

    def _pick_next(self):
        """에너지·facing·벽 위치를 반영해 다음 상태를 고른다."""
        opts = list(self._transitions[self.state])
        adjusted = []
        for s, w in opts:
            if self.energy > 70:
                if s in ('walk_r', 'walk_l', 'jump_r', 'jump_l'):
                    w *= 2.0
                elif s in ('sleep', 'sit'):
                    w *= 0.5
            elif self.energy < 30:
                if s in ('walk_r', 'walk_l', 'jump_r', 'jump_l'):
                    w *= 0.15
                elif s in ('sit', 'groom', 'sleep'):
                    w *= 2.5
            if s == 'walk_r' and self.facing > 0:
                w *= 1.6
            elif s == 'walk_l' and self.facing < 0:
                w *= 1.6
            # 직전 walk와 바로 U턴하는 전환은 억제
            if self.prev_state == 'walk_r' and s == 'walk_l':
                w *= 0.35
            elif self.prev_state == 'walk_l' and s == 'walk_r':
                w *= 0.35
            if self.prev_state == 'groom' and s == 'groom':
                w *= 0.15
            adjusted.append((s, w))

        states, weights = zip(*adjusted)
        chosen = random.choices(states, weights=list(weights))[0]

        w_sz, _ = self._size()
        if chosen == 'walk_r' and self.x + w_sz > self.screen_w - WALL_MARGIN:
            chosen = 'walk_l'
        elif chosen == 'walk_l' and self.x < WALL_MARGIN:
            chosen = 'walk_r'
        return chosen

    def _set_state(self, state):
        """상태를 바꾸고 애니·타이머·바닥 Y를 리셋한다."""
        self.prev_state = self.state
        self.state = state
        self.frame_idx = 0
        self.tick = 0
        self.frame_hold = self._hold_for(state, 0)
        self.jump_step = 0
        self.jump_y_offset = 0
        self.breath_offset = 0
        self.breath_phase = 0.0
        self.accel = 0.0
        self._clear_held()
        self.energy = max(0, min(100, self.energy + ENERGY_INSTANT.get(state, 0)))
        d = DURATION[state]
        self.state_timer = random.randint(*d) if d else 0

        if state in ('walk_r', 'jump_r'):
            self.facing = 1
            if state == 'walk_r':
                self.walk_speed = random.uniform(WALK_SPEED_MIN, WALK_SPEED_MAX)
        elif state in ('walk_l', 'jump_l'):
            self.facing = -1
            if state == 'walk_l':
                self.walk_speed = random.uniform(WALK_SPEED_MIN, WALK_SPEED_MAX)

        w, h = self._size()
        self.y = float(self.ground_y - h)
        self.x = max(0.0, min(self.x, float(self.screen_w - w)))

    def _edge_speed_scale(self):
        """화면 가장자리 근처에서 걷기 속도를 부드럽게 줄인다."""
        w_sz, _ = self._size()
        left_dist = self.x
        right_dist = self.screen_w - (self.x + w_sz)
        dist = left_dist if self.state == 'walk_l' else right_dist
        if dist >= WALL_SLOW_ZONE:
            return 1.0
        t = max(0.0, min(1.0, dist / WALL_SLOW_ZONE))
        return 0.25 + 0.75 * (t * t * (3 - 2 * t))

    def _move_horizontal(self, dx):
        """수평 이동. 화면 끝에 닿으면 idle로 바꾸고 False."""
        w_sz, _ = self._size()
        nx = self.x + dx
        if dx > 0 and nx + w_sz > self.screen_w:
            self.x = float(self.screen_w - w_sz)
            self._set_state('idle')
            return False
        if dx < 0 and nx < 0:
            self.x = 0.0
            self._set_state('idle')
            return False
        self.x = nx
        return True

    def update(self):
        """한 틱 진행: 이동·에너지·상태 타이머·프레임."""
        if self.bubble_ticks > 0:
            self.bubble_ticks -= 1
            if self.bubble_ticks == 0:
                self.bubble_text = None

        if self.state == 'held':
            self._update_held_anim()
            return

        if self.state in ('walk_r', 'walk_l'):
            self.accel = min(1.0, self.accel + 0.14)
            speed = self.walk_speed * self.accel * self._edge_speed_scale()
            dx = speed if self.state == 'walk_r' else -speed
            if not self._move_horizontal(dx):
                return

        if self.state == 'sleep':
            self.breath_phase += 0.18
            self.breath_offset = int(round(math.sin(self.breath_phase) * 1.2))

        self.energy = max(0, min(100, self.energy + ENERGY_PER_TICK.get(self.state, 0)))

        if self.state not in ('jump_r', 'jump_l'):
            self.state_timer -= 1
            if self.state_timer <= 0:
                self._set_state(self._pick_next())
                return

        self.tick += 1
        if self.tick >= self.frame_hold:
            self.tick = 0
            if self.state in ('jump_r', 'jump_l'):
                nxt = self.jump_step + 1
                if nxt >= len(JUMP_Y_OFFSETS):
                    self._set_state(self._pick_next())
                else:
                    self.jump_step = nxt
                    self.frame_idx = JUMP_FRAME_MAP[nxt]
                    self.jump_y_offset = JUMP_Y_OFFSETS[nxt]
                    self.frame_hold = FRAME_PERIOD[self.state]
            else:
                n = len(self.sprites[self.state])
                self.frame_idx = (self.frame_idx + 1) % n
                self.frame_hold = self._hold_for(self.state, self.frame_idx)
