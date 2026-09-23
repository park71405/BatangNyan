"""고양이 상태 머신: 걷기·대기·앉기·그루밍·점프(좌/우)·집기·에너지.

창/입력은 app.py가 담당한다.

타이밍 용어
  tick        : update() 한 번 (약 TICK_MS)
  frame_hold  : 현재 프레임을 유지할 tick 수
  state_timer : 현재 상태 남은 수명(tick). jump_* 는 시퀀스 완주가 종료 조건
  accel       : 걷기 시작 시 0→1 ease-in 배율 (물리 가속도 아님)
"""

import math
import random

from PIL import ImageOps
from PIL import ImageTk

from .constants import (
    DURATION,
    ENERGY_INSTANT,
    ENERGY_PER_TICK,
    FRAME_HOLDS,
    FRAME_PERIOD,
    GAZE_STATES,
    GROUND_MARGIN,
    HELD_FRAME_PERIOD,
    HELD_HOLD_FRAME,
    HELD_PICKUP,
    HELD_RELEASE,
    JUMP_FRAME_MAP,
    JUMP_STATES,
    JUMP_Y_OFFSETS,
    MOUSE_JUMP_LEAVE_EXTRA,
    MOUSE_JUMP_RADIUS,
    REACTION_STATES,
    TRANSITIONS,
    WALK_SPEED_MAX,
    WALK_SPEED_MIN,
    WALK_STATES,
    WALL_MARGIN,
    WALL_SLOW_ZONE,
)


class Cat:
    """자동 행동·애니메이션·근접 점프를 가진 고양이 캐릭터."""

    def __init__(self, pil_sprites, screen_w, screen_h, screen_x=0, screen_y=0, monitors=None):
        """스프라이트 dict와 가상 데스크톱 범위로 초기화한다."""
        self.pil_sprites = pil_sprites
        self.screen_x = screen_x  # 가상 데스크톱 좌측 끝 (보조 모니터가 왼쪽이면 음수)
        self.screen_y = screen_y  # 가상 데스크톱 상단 끝
        self.screen_w = screen_w
        self.screen_h = screen_h
        # 각 모니터의 (left, top, width, height). 없으면 가상 데스크톱 전체를 단일 모니터로 간주
        self._monitors = monitors or [(screen_x, screen_y, screen_w, screen_h)]

        self.sprites = {
            k: [ImageTk.PhotoImage(f) for f in frames]
            for k, frames in pil_sprites.items()
        }
        # 스프라이트가 없는 선택적 상태는 전환 표에서 제외
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
        self.facing = 1       # 1=오른쪽, -1=왼쪽
        self.gaze_facing = -1  # idle/sit 시선 방향 (-1=왼쪽=원본, 1=오른쪽=반전본)
        self.frame_idx = 0
        self.tick = 0
        self.frame_hold = self._hold_for('walk_r', 0)
        self.state_timer = random.randint(*DURATION['walk_r'])
        self.jump_step = 0
        self.jump_y_offset = 0
        self.walk_speed = random.uniform(WALK_SPEED_MIN, WALK_SPEED_MAX)
        self.accel = 0.0  # walk ease-in 0→1
        self.energy = random.randint(50, 80)
        self.bubble_text = None
        self.bubble_ticks = 0
        self._mouse_near = False  # 근접 영역 안인지 (진입 에지 감지용)
        self._init_held()
        self._add_mirrored_sprites(pil_sprites)

        w, _ = self._size()
        x_min = screen_x + WALL_MARGIN
        x_max = max(x_min, screen_x + screen_w - w - WALL_MARGIN)
        self.x = float(random.randint(x_min, x_max))
        self._snap_to_ground()

    # --- 유틸 ---

    def _add_mirrored_sprites(self, pil_sprites):
        """GAZE_STATES 스프라이트를 좌우 반전해 '{state}_r' 키로 추가한다.

        원본 스프라이트가 왼쪽을 향하므로, 반전본이 오른쪽 방향(_r)이 된다.
        """
        for state in GAZE_STATES:
            if state in pil_sprites:
                mirrored = [ImageOps.mirror(f) for f in pil_sprites[state]]
                self.sprites[f'{state}_r'] = [ImageTk.PhotoImage(f) for f in mirrored]

    def _floor_y_at(self, x):
        """x 위치가 속한 모니터의 바닥 y를 반환한다.

        어느 모니터에도 속하지 않으면 수평 중심이 가장 가까운 모니터의 바닥을 사용한다.
        """
        w, _ = self._size()
        cx = x + w / 2
        for mx, my, mw, mh in self._monitors:
            if mx <= cx < mx + mw:
                return my + mh - GROUND_MARGIN
        closest = min(self._monitors, key=lambda m: abs(m[0] + m[2] / 2 - cx))
        return closest[1] + closest[3] - GROUND_MARGIN

    def _snap_to_ground(self):
        """현재 x 기준으로 ground_y와 y를 바닥에 맞춘다."""
        self.ground_y = self._floor_y_at(self.x)
        _, h = self._size()
        self.y = float(self.ground_y - h)

    def _update_floor(self):
        """걷는 중 모니터 경계를 넘었을 때 ground_y·y를 갱신한다."""
        new_ground = self._floor_y_at(self.x)
        if new_ground == self.ground_y:
            return
        self.ground_y = new_ground
        _, h = self._size()
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

    @staticmethod
    def _clamp_energy(value):
        return max(0, min(100, value))

    def _clamp_x(self, x=None):
        """창이 가상 데스크톱 밖으로 나가지 않도록 X를 클램프한다."""
        w, _ = self._size()
        if x is None:
            x = self.x
        return max(float(self.screen_x), min(float(x), float(self.screen_x + self.screen_w - w)))

    def _walk_for_facing(self):
        """현재 facing에 맞는 walk 상태 이름."""
        return 'walk_r' if self.facing >= 0 else 'walk_l'

    def _jump_for_facing(self):
        """현재 facing에 맞는 jump 상태 이름."""
        return 'jump_r' if self.facing > 0 else 'jump_l'

    # --- 표시 ---

    def current_frame(self):
        """지금 그릴 PhotoImage. idle/sit은 gaze_facing 방향 스프라이트를 사용한다.

        원본이 왼쪽 방향이므로: gaze_facing>0(오른쪽) → 반전본(_r) 사용.
        """
        state = self.state
        if state in GAZE_STATES and self.gaze_facing > 0:
            mirror_key = f'{state}_r'
            if mirror_key in self.sprites:
                state = mirror_key
        frames = self.sprites[state]
        return frames[self.frame_idx % len(frames)]

    def window_pos(self):
        """화면상 창 왼쪽·위 좌표. held는 자유 Y, 그 외는 바닥 + 점프 오프셋."""
        _, h = self._size()
        if self.state == 'held':
            return int(round(self.x)), int(round(self.y))
        return int(round(self.x)), self.ground_y - h + self.jump_y_offset

    def set_active_region(self, screen_x, screen_y, screen_w, screen_h, monitors):
        """이동 가능 영역을 변경하고, 현재 위치가 범위 밖이면 해당 영역으로 즉시 이동한다."""
        self.screen_x = screen_x
        self.screen_y = screen_y
        self.screen_w = screen_w
        self.screen_h = screen_h
        self._monitors = monitors

        w, _ = self._size()
        x_min = screen_x + WALL_MARGIN
        x_max = max(x_min, screen_x + screen_w - w - WALL_MARGIN)
        if self.x < screen_x or self.x + w > screen_x + screen_w:
            self.x = float(random.randint(x_min, x_max))
        else:
            self.x = self._clamp_x()

        if self.state == 'held':
            self.ground_y = self._floor_y_at(self.x)
        else:
            self._snap_to_ground()

    def reload_sprites(self, pil_sprites):
        """스프라이트를 새 크기로 교체하고 위치를 재클램프한다."""
        self.pil_sprites = pil_sprites
        self.sprites = {
            k: [ImageTk.PhotoImage(f) for f in frames]
            for k, frames in pil_sprites.items()
        }
        self._add_mirrored_sprites(pil_sprites)
        self.x = self._clamp_x()
        self._snap_to_ground()

    def show_bubble(self, text, duration_ticks=30):
        """머리 위 말풍선 텍스트를 표시한다."""
        self.bubble_text = text
        self.bubble_ticks = duration_ticks

    # --- 집기 (held) ---
    # cat-click.png 프레임: 0–3 pickup → 4 hold(드래그) → 5–6 release → walk

    def _init_held(self):
        self.held_phase = None  # 'pickup' | 'hold' | 'release'
        self.held_seq_i = 0
        self.grab_dx = 0
        self.grab_dy = 0

    def _clear_held(self):
        self.held_phase = None
        self.held_seq_i = 0

    def start_held(self, grab_dx, grab_dy, win_x, win_y):
        """마우스 누름: 집기 애니 시작."""
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
        self.grab_dx = grab_dx
        self.grab_dy = grab_dy
        self.x = float(win_x)
        self.y = float(win_y)

    def drag_to(self, screen_x, screen_y):
        """누르는 중 화면 좌표로 창 위치를 따라가게 한다 (release 중에는 무시)."""
        if self.state != 'held' or self.held_phase == 'release':
            return
        w, h = self._size()
        self.x = self._clamp_x(screen_x - self.grab_dx)
        self.y = max(float(self.screen_y), min(float(screen_y - self.grab_dy), float(self.screen_y + self.screen_h - h)))

    def release_held(self):
        """마우스 뗌: Y를 바닥에 붙이고 release 프레임(5→6)을 재생한다."""
        if self.state != 'held' or self.held_phase == 'release':
            return
        self.x = self._clamp_x()
        self._snap_to_ground()
        self.held_phase = 'release'
        self.held_seq_i = 0
        self.frame_idx = HELD_RELEASE[0]
        self.tick = 0
        self.frame_hold = HELD_FRAME_PERIOD

    def _update_held_anim(self):
        """held 상태의 프레임을 한 틱 진행한다."""
        if self.held_phase == 'hold':
            return

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
                self._set_state(self._walk_for_facing())
            else:
                self.frame_idx = HELD_RELEASE[self.held_seq_i]
                self.frame_hold = HELD_FRAME_PERIOD

    # --- 시선 추적 ---

    def update_gaze(self, mx, my):
        """idle/sit 중 마우스 X 위치에 따라 시선 방향을 갱신한다.

        15px 히스테리시스로 경계에서의 깜빡임을 방지한다.
        변경이 일어났으면 True를 반환한다 (paint force 트리거용).
        """
        if self.state not in GAZE_STATES:
            return False
        w, _ = self._size()
        wx, _ = self.window_pos()
        cat_cx = wx + w / 2
        prev = self.gaze_facing
        if mx < cat_cx - 15:
            self.gaze_facing = -1
        elif mx > cat_cx + 15:
            self.gaze_facing = 1
        return self.gaze_facing != prev

    # --- 근접 점프 ---

    def try_mouse_scare(self, mx, my):
        """커서가 근접 영역에 들어오면 점프 또는 하악질 중 하나를 랜덤 실행. 시작했으면 True.

        held / 반응 상태(jump_*, hiss) 중에는 무시.
        영역을 나간 뒤 다시 들어와야 재발동.
        """
        if self.state == 'held' or self.state in REACTION_STATES:
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

        # 진입 에지: hiss 에셋이 있으면 50% 확률로 하악질, 나머지는 점프
        self._mouse_near = True
        self.facing = 1 if mx < cx else -1
        if 'hiss' in self.sprites and random.random() < 0.5:
            self._set_state('hiss')
        else:
            self._set_state(self._jump_for_facing())
        return True

    # --- 상태 전환 ---

    def _pick_next(self):
        """에너지·facing·벽 위치를 반영해 다음 상태를 고른다."""
        opts = list(self._transitions.get(self.state, []))
        adjusted = []
        for s, w in opts:
            if self.energy > 70:
                if s in WALK_STATES or s in JUMP_STATES:
                    w *= 2.0
                elif s == 'sit':
                    w *= 0.5
            elif self.energy < 30:
                if s in WALK_STATES or s in JUMP_STATES:
                    w *= 0.15
                elif s in ('sit', 'groom'):
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

        if not adjusted:
            for s in ('idle', 'walk_r', 'walk_l'):
                if s in self.sprites:
                    return s
            return next(iter(self.sprites))

        states, weights = zip(*adjusted)
        chosen = random.choices(states, weights=list(weights))[0]

        w_sz, _ = self._size()
        if chosen == 'walk_r' and self.x + w_sz > self.screen_x + self.screen_w - WALL_MARGIN:
            chosen = 'walk_l'
        elif chosen == 'walk_l' and self.x < self.screen_x + WALL_MARGIN:
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
        self.accel = 0.0
        self._clear_held()
        self.energy = self._clamp_energy(self.energy + ENERGY_INSTANT.get(state, 0))
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

        # gaze는 상태 진입 시 이동 방향으로 초기화 (이후 update_gaze 가 마우스 기준으로 갱신)
        if state in GAZE_STATES:
            self.gaze_facing = self.facing

        self.x = self._clamp_x()
        self._snap_to_ground()

    # --- 이동 ---

    def _edge_speed_scale(self):
        """가상 데스크톱 가장자리 근처에서 걷기 속도를 부드럽게 줄인다."""
        w_sz, _ = self._size()
        left_dist = self.x - self.screen_x
        right_dist = (self.screen_x + self.screen_w) - (self.x + w_sz)
        dist = left_dist if self.state == 'walk_l' else right_dist
        if dist >= WALL_SLOW_ZONE:
            return 1.0
        t = max(0.0, min(1.0, dist / WALL_SLOW_ZONE))
        return 0.25 + 0.75 * (t * t * (3 - 2 * t))

    def _move_horizontal(self, dx):
        """수평 이동. 가상 데스크톱 끝에 닿으면 idle로 바꾸고 False."""
        w_sz, _ = self._size()
        nx = self.x + dx
        right_edge = self.screen_x + self.screen_w
        if dx > 0 and nx + w_sz > right_edge:
            self.x = float(right_edge - w_sz)
            self._set_state('idle')
            return False
        if dx < 0 and nx < self.screen_x:
            self.x = float(self.screen_x)
            self._set_state('idle')
            return False
        self.x = nx
        return True

    def _advance_jump_frame(self):
        """점프 시퀀스 한 스텝. 끝나면 True(상태 전환됨)."""
        nxt = self.jump_step + 1
        if nxt >= len(JUMP_Y_OFFSETS):
            self._set_state(self._pick_next())
            return True
        self.jump_step = nxt
        self.frame_idx = JUMP_FRAME_MAP[nxt]
        self.jump_y_offset = JUMP_Y_OFFSETS[nxt]
        self.frame_hold = FRAME_PERIOD[self.state]
        return False

    def update(self):
        """한 틱 진행: 이동·에너지·상태 타이머·프레임."""
        if self.bubble_ticks > 0:
            self.bubble_ticks -= 1
            if self.bubble_ticks == 0:
                self.bubble_text = None

        if self.state == 'held':
            self._update_held_anim()
            return

        if self.state in WALK_STATES:
            self.accel = min(1.0, self.accel + 0.14)
            speed = self.walk_speed * self.accel * self._edge_speed_scale()
            dx = speed if self.state == 'walk_r' else -speed
            if not self._move_horizontal(dx):
                return
            self._update_floor()

        self.energy = self._clamp_energy(
            self.energy + ENERGY_PER_TICK.get(self.state, 0)
        )

        # jump_* 는 state_timer 대신 시퀀스 완주가 종료 조건
        if self.state not in JUMP_STATES:
            self.state_timer -= 1
            if self.state_timer <= 0:
                self._set_state(self._pick_next())
                return

        self.tick += 1
        if self.tick >= self.frame_hold:
            self.tick = 0
            if self.state in JUMP_STATES:
                self._advance_jump_frame()
            else:
                n = len(self.sprites[self.state])
                self.frame_idx = (self.frame_idx + 1) % n
                self.frame_hold = self._hold_for(self.state, self.frame_idx)
