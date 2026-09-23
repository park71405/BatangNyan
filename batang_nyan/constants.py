"""앱 전역에서 쓰는 튜닝 상수.

경로·스케일·이동·점프·상태 전환·클릭(held)·말풍선 설정을 한곳에 둔다.
값만 바꿔도 체감이 바뀌므로, 비고 없는 숫자는 ‘의도된 튜닝값’으로 본다.
"""

import os
import sys
from pathlib import Path

# 프로젝트 루트(BatangNyan/). 패키지(batang_nyan/)의 상위.
# PyInstaller onefile 실행 시 리소스는 임시 추출 폴더(_MEIPASS)에 있다.
if getattr(sys, 'frozen', False):
    ROOT = Path(sys._MEIPASS).resolve()  # 8.3 단축 경로 → 실제 경로 정규화
else:
    ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / 'img'
ICON_PATH = ROOT / 'cat1.png'

# --- 스프라이트 표시 ---
PADDING = 12
SCALE = 0.40            # idle / sit / groom / jump_*
WALK_SCALE = 0.46       # 걷기만 (다른 포즈보다 약간 큼)
HELD_BODY_SCALE = 0.60  # 클릭 held 몸통 높이 (walk 원본 몸통 대비, WALK_SCALE과 독립)
# 투명 키: 순수 #ffffff 는 고양이 흰 몸통과 겹쳐 구멍이 난다 → 한 단계만 어두운 키 사용
KEY_COLOR = (255, 255, 254)
KEY_HEX = '#fffffe'

# --- 월드 / 이동 (1 tick = TICK_MS) ---
TICK_MS = 100
WALK_SPEED_MIN = 1.6
WALK_SPEED_MAX = 2.8
WALL_SLOW_ZONE = 120    # 이 거리부터 걷기 감속
GROUND_MARGIN = 50
WALL_MARGIN = 80

# --- 커서 근접 점프 (진입 1회, 이탈 후 재진입 시 재발동) ---
MOUSE_JUMP_RADIUS = 120
MOUSE_JUMP_LEAVE_EXTRA = 20  # 이탈 판정 = RADIUS + 이 값 (히스테리시스)

# 방향 상태 묶음 (전환·애니 분기에서 공통 사용)
WALK_STATES = frozenset({'walk_r', 'walk_l'})
JUMP_STATES = frozenset({'jump_r', 'jump_l'})
# 커서 근접 반응 상태 (중복 발동 방지용)
REACTION_STATES = JUMP_STATES | frozenset({'hiss'})
# 시선 추적 대상 상태 (idle/sit 에서 마우스 방향으로 반전)
GAZE_STATES = frozenset({'idle', 'sit'})

# 상태별 기본 프레임 유지 tick 수
FRAME_PERIOD = {
    'walk_r': 2,
    'walk_l': 2,
    'groom': 2,
    'jump_r': 1,
    'jump_l': 1,
    'idle': 5,
    'sit': 6,
    'hiss': 3,   # 8프레임 × 3tick = 24tick에 1회 재생
}

# 프레임 인덱스별 홀드 (기계적인 루프 완화)
FRAME_HOLDS = {
    'groom': [2, 2, 4, 5, 5, 4, 2, 2],
    'idle': [18, 3],  # 대부분 눈 뜸, 짧게 깜빡
}

# --- 제자리 점프 ---
# 가로는 창을 움직이지 않는다. 시트에 베이크된 이동은 sprite._pin_jump_frames 로 제거한 뒤
# 창 Y만 JUMP_Y_OFFSETS 포물선으로 올린다. jump_r / jump_l 프레임 맵은 동일.
JUMP_PEAK = 38
JUMP_STEPS = 10
# y = -4 * peak * t * (1-t)  → 시작·착지 0, 중간에 되돌아오지 않음
JUMP_Y_OFFSETS = [
    round(-4 * JUMP_PEAK * (i / (JUMP_STEPS - 1)) * (1 - i / (JUMP_STEPS - 1)))
    for i in range(JUMP_STEPS)
]
# 상승 → 정점 → 하강 포즈 (시트 6프레임)
JUMP_FRAME_MAP = [0, 1, 2, 2, 3, 3, 4, 4, 5, 5]

# 상태 지속 시간 (tick). jump_* 는 시퀀스 완주로 종료 → None
DURATION = {
    'walk_r': (30, 80),
    'walk_l': (30, 80),
    'idle':   (20, 55),
    'sit':    (45, 110),
    'groom':  (24, 56),
    'jump_r': None,
    'jump_l': None,
    'hiss': (24, 24),  # 8프레임 × 3tick, 1회 재생 후 전환
}

# 상태 전환 후보 (이름, 가중치). 로드된 스프라이트만 실제 사용.
# jump_* 는 마우스 근접 반응 전용 — walk 전환에서 제거.
TRANSITIONS = {
    'walk_r': [('idle', 9), ('sit', 2)],                            # 걷다 멈추거나 바로 앉음
    'walk_l': [('idle', 9), ('sit', 2)],
    'idle':   [('walk_r', 3), ('walk_l', 3), ('sit', 5), ('groom', 2)],  # 서있다 앉거나 가끔 그루밍
    'sit':    [('idle', 2), ('groom', 5), ('walk_r', 1.5), ('walk_l', 1.5)],
    'groom':  [('sit', 6), ('idle', 1)],
    'jump_r': [('walk_r', 1)],
    'jump_l': [('walk_l', 1)],
    'hiss':   [('idle', 1), ('walk_r', 2.5), ('walk_l', 2.5)],     # 하악 후 도망 선호
}

# tick당 에너지 변화. 점프는 tick 소모 없이 ENERGY_INSTANT 만 적용.
ENERGY_PER_TICK = {
    'walk_r': -0.7, 'walk_l': -0.7,
    'idle': -0.15,
    'sit': 0.35,
    'groom': 0.2,
}
ENERGY_INSTANT = {
    'jump_r': -10,
    'jump_l': -10,
    'hiss': -5,
}

# --- 클릭 held: cat-click 시트 인덱스 ---
# 0–3 pickup → 4 hold(드래그) → 5–6 release → walk
HELD_PICKUP = [0, 1, 2, 3]
HELD_HOLD_FRAME = 4
HELD_RELEASE = [5, 6]
HELD_FRAME_PERIOD = 2

# --- 크기 프리셋 ---
SCALE_FACTORS = {'small': 0.7, 'medium': 1.0, 'large': 1.4}
SIZE_LABELS = {'small': '소', 'medium': '중', 'large': '대'}
CONFIG_DIR = Path(os.environ.get('APPDATA', Path.home())) / 'BatangNyan'
CONFIG_PATH = CONFIG_DIR / 'config.json'

# --- UI ---
BUBBLE_EXTRA_H = 44
BUBBLE_PAD_X   = 10
BUBBLE_PAD_Y   = 6
BUBBLE_TAIL_H  = 10
BUBBLE_FONT    = ('맑은 고딕', 11, 'bold')
BUBBLE_SCHEDULE = {
    9: '냥',
    12: '냐냥',
    18: '냐냐냥',
}
BUBBLE_CHECK_MS = 30_000
