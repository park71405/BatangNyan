"""앱 전역에서 쓰는 튜닝 상수.

경로·스케일·이동·점프·상태 전환·클릭(held)·말풍선 설정을 한곳에 둔다.
"""

import sys
from pathlib import Path

# 프로젝트 루트(BatangNyan/). 패키지(batang_nyan/)의 상위.
# PyInstaller 실행 시에는 번들 추출 경로(_MEIPASS)를 사용한다.
if getattr(sys, 'frozen', False):
    ROOT = Path(sys._MEIPASS)
else:
    ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / 'img'
ICON_PATH = ROOT / 'cat1.png'

# --- 스프라이트 표시 ---
PADDING = 12
SCALE = 0.40            # idle / sit / groom / jump
WALK_SCALE = 0.46       # 걷기만 (다른 포즈보다 약간 큼)
HELD_BODY_SCALE = 0.60  # 클릭 held 몸통 높이 (walk 원본 몸통 대비, WALK_SCALE과 독립)
# 투명 키: 순백에 가깝지만 고양이 몸통 흰색과 구분
KEY_COLOR = (255, 255, 254)
KEY_HEX = '#fffffe'

# --- 월드 / 이동 (1 tick = 100ms) ---
TICK_MS = 100
WALK_SPEED_MIN = 1.6
WALK_SPEED_MAX = 2.8
WALL_SLOW_ZONE = 120    # 이 거리부터 걷기 감속
GROUND_MARGIN = 50
WALL_MARGIN = 80

# --- 커서 근접 점프 (진입 시 1회, 이탈 후 재진입 시 재발동) ---
MOUSE_JUMP_RADIUS = 120
MOUSE_JUMP_LEAVE_EXTRA = 20  # 이탈 판정 = RADIUS + 이 값 (히스테리시스)

# 상태별 기본 프레임 유지 tick 수
FRAME_PERIOD = {
    'walk_r': 2,
    'walk_l': 2,
    'groom': 2,
    'jump_r': 1,
    'jump_l': 1,
    'idle': 5,
    'sit': 6,
    'sleep': 8,
    'stretch': 4,
}

# 프레임 인덱스별 홀드 (기계적인 루프 완화)
FRAME_HOLDS = {
    'groom': [2, 2, 4, 5, 5, 4, 2, 2],
    'idle': [18, 3],  # 대부분 눈 뜸, 짧게 깜빡
}

# --- 제자리 점프 포물선 ---
JUMP_PEAK = 38
JUMP_STEPS = 10
# y = -4 * peak * t * (1-t)  → 시작·착지 0, 중간에 되돌아오지 않음
JUMP_Y_OFFSETS = [
    round(-4 * JUMP_PEAK * (i / (JUMP_STEPS - 1)) * (1 - i / (JUMP_STEPS - 1)))
    for i in range(JUMP_STEPS)
]
# 상승 → 정점 → 하강 포즈 (시트 6프레임)
JUMP_FRAME_MAP = [0, 1, 2, 2, 3, 3, 4, 4, 5, 5]

# 상태 지속 시간 (tick). jump는 시퀀스 완주로 종료 → None
DURATION = {
    'walk_r': (30, 80),
    'walk_l': (30, 80),
    'idle': (15, 40),
    'sit': (35, 90),
    'groom': (24, 48),
    'sleep': (60, 160),
    'stretch': (12, 22),
    'jump_r': None,
    'jump_l': None,
}

# 상태 전환 후보 (이름, 가중치). 로드된 스프라이트만 실제 사용.
TRANSITIONS = {
    'walk_r': [('idle', 10), ('jump_r', 0.35)],
    'walk_l': [('idle', 10), ('jump_l', 0.35)],
    'idle': [('walk_r', 4), ('walk_l', 4), ('sit', 3)],
    'sit': [('idle', 3), ('groom', 4), ('sleep', 1.5)],
    'groom': [('sit', 3), ('idle', 1)],
    'sleep': [('stretch', 1)],
    'stretch': [('idle', 3), ('walk_r', 2), ('walk_l', 2)],
    'jump_r': [('walk_r', 1)],
    'jump_l': [('walk_l', 1)],
}

# tick당 에너지 변화 / 상태 진입 시 일회 변화
ENERGY_PER_TICK = {
    'walk_r': -0.7, 'walk_l': -0.7,
    'idle': -0.15,
    'sit': 0.35,
    'groom': 0.2,
    'sleep': 0.8,
    'stretch': 0.1,
    'jump_r': 0.0,
    'jump_l': 0.0,
}
ENERGY_INSTANT = {
    'jump_r': -10,
    'jump_l': -10,
}

# --- 클릭 held: pickup → 4번 프레임 유지 → 놓으면 5·6 → walk ---
HELD_PICKUP = [0, 1, 2, 3]
HELD_HOLD_FRAME = 4
HELD_RELEASE = [5, 6]
HELD_FRAME_PERIOD = 2

# --- UI ---
BUBBLE_EXTRA_H = 44   # 말풍선용 캔버스 추가 높이
BUBBLE_SCHEDULE = {
    9: '냥',
    12: '냐냥',
    18: '냐냐냥',
}
BUBBLE_CHECK_MS = 30_000
