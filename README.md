# BatangNyan (바탕화면 고양이)

Windows 바탕화면 위를 돌아다니는 투명 오버레이 고양이.

## 데모

![BatangNyan 데모](BatangNyan_test.gif)

---

## 실행

### 방법 1: exe 실행 (Python 설치 불필요)

1. `dist` 폴더의 `BatangNyan.exe`를 내려받는다.
2. 원하는 위치에 두고 더블클릭으로 실행한다.
3. Windows SmartScreen 경고가 뜨면 **추가 정보** → **실행**을 누른다.

종료: 트레이 → **종료**.

### 방법 2: 소스에서 실행

```bash
pip install pillow pystray
python main.py
```

프로젝트 루트에서 실행. 종료: 트레이 → **종료**.

### exe 직접 빌드

```bash
pip install pyinstaller
pyinstaller BatangNyan.spec
```

빌드 결과물: `dist/BatangNyan.exe`

---

## 기능

| 기능 | 설명 |
|------|------|
| 자율 행동 | walk → idle → sit → groom 순환, 에너지에 따라 행동 빈도 변화 |
| 커서 반응 | 커서가 120px 이내 접근 시 점프 또는 하악질 랜덤 발동 |
| 시선 추적 | idle·sit 중 커서 방향으로 고개 전환 (15px 히스테리시스) |
| 클릭·드래그 | 고양이를 집어 화면 어디든 이동 가능 |
| 크기 조절 | 트레이 메뉴에서 소·중·대 즉시 변경, 재시작 후에도 유지 |
| 멀티모니터 | 전체 가상 데스크톱 또는 특정 모니터로 이동 범위 제한 |
| 화면 절전 방지 | 실행 중 Windows 화면 끄기·절전 차단 |
| 설정 유지 | 크기·모니터 선택을 `%APPDATA%\BatangNyan\config.json`에 저장 |
| 오류 로그 | 런타임 예외를 `%APPDATA%\BatangNyan\error.log`에 기록 |

---

## 디렉터리 구조

```
BatangNyan/
├── main.py                      ← 진입점
├── README.md
├── BatangNyan.spec              ← PyInstaller 빌드 설정
├── cat1.png                     ← 트레이 아이콘
├── cat1.ico                     ← exe 아이콘
├── BatangNyan_test.gif          ← 데모 영상
├── img/                         ← 스프라이트 시트
│   ├── cat-walk-right.png       (8프레임) → walk_r
│   ├── cat-walk-left.png        (8프레임) → walk_l
│   ├── cat-idle-stop.png        (idle: 0–1번, sit: 6번)
│   ├── cat-groom.png            (8프레임) → groom
│   ├── cat-jump-cycle-right.png (6프레임) → jump_r
│   ├── cat-jump-cycle-left.png  (6프레임) → jump_l
│   ├── cat-click.png            (7프레임, 간격 불균일) → held
│   └── cat-hissing.png          (8프레임) → hiss
└── batang_nyan/                 ← 패키지
    ├── __init__.py
    ├── app.py       ← Tk 오버레이, 렌더 루프, 말풍선, 마우스, 설정
    ├── cat.py       ← 상태 머신, 이동, 에너지, 커서 반응, 시선 추적
    ├── sprite.py    ← 시트 로드, 스케일, 키컬러 합성, 점프 정렬
    ├── constants.py ← 전역 상수 (경로·스케일·전환·말풍선)
    ├── win32util.py ← 투명 창 갱신, 모니터 열거, 절전 방지
    └── tray.py      ← 시스템 트레이 메뉴
```

---

## 모듈 책임

| 모듈 | 역할 |
|------|------|
| `main` | `BatangNyanApp().run()` |
| `app` | 창·캔버스·페인트·말풍선·클릭/드래그·틱·커서 폴링·크기·모니터 설정 |
| `cat` | 상태 전환, 걷기/점프/에너지, 커서 반응, 시선 추적(`update_gaze`), 집기(held) |
| `cat` (held) | pickup(0–3) → hold(4) → release(5–6) → walk |
| `sprite` | 시트 로드, walk/jump 정렬, 크기 통일, hiss 스케일 조정 |
| `constants` | 스케일·속도·점프·전환·말풍선·크기 프리셋·설정 경로 |
| `win32util` | 깜빡임 완화 창 갱신, 모니터 열거, 화면 절전 방지 |
| `tray` | 트레이 메뉴 (크기·모니터·재시작·종료) |

---

## 상태 머신

```
walk_r ──► idle ──► sit ──► groom ──► sit
  │          │       │                 │
  │          │       └── walk_r/l      └── idle
  │          └── walk_r/l
  │          └── groom
  └── (커서 근접) ──► jump_r / hiss ──► walk_r
walk_l ──► … 동일, jump_l ──► walk_l
```

| 상태 | 지속(tick) | 비고 |
|------|------------|------|
| `walk_r`/`walk_l` | 30–80 | 속도 1.6–2.8, 가속·벽 감속 |
| `idle` | 20–55 | 홀드 \[18, 3\] (눈 깜빡임) |
| `sit` | 45–110 | 정적 1프레임 |
| `groom` | 24–56 | 프레임별 홀드 |
| `jump_r`/`jump_l` | 시퀀스 완주 | 제자리, Y 포물선 10스텝 |
| `hiss` | 24 (고정) | 마우스 접근 시 50% 확률 발동 |
| `held` | 입력 종속 | 클릭·드래그 |

1 tick = 100 ms (`TICK_MS`).

### 전환 가중치

| 현재 | 다음 후보 (이름·가중치) |
|------|------------------------|
| walk_r | idle(9), sit(2) |
| walk_l | idle(9), sit(2) |
| idle | walk_r(3), walk_l(3), sit(5), groom(2) |
| sit | idle(2), groom(5), walk_r(1.5), walk_l(1.5) |
| groom | sit(6), idle(1) |
| jump_r | walk_r(1) |
| jump_l | walk_l(1) |
| hiss | idle(1), walk_r(2.5), walk_l(2.5) |

에너지 > 70이면 walk 가중치 ×2, sit 가중치 ×0.5.  
에너지 < 30이면 walk 가중치 ×0.15, sit/groom 가중치 ×2.5.

---

## 커서 반응

- 커서가 고양이 중심으로부터 **120px** 이내 진입 시 1회 발동
- 50% 확률로 **점프** 또는 **하악질**
- 방향: 커서 반대 방향 (점프 착지 후 그 방향 walk, 하악질 후 도망)
- `held`·`jump_*`·`hiss` 중에는 재발동 없음
- 이탈 판정: 중심 거리 > 140px (20px 히스테리시스)

---

## 시선 추적

`idle`·`sit` 상태에서 커서 X 위치에 따라 방향 전환.

- 원본 스프라이트: 왼쪽 방향
- 미러 스프라이트(`{state}_r`): 오른쪽 방향 (`ImageOps.mirror`)
- 히스테리시스: 고양이 중심 ±15px 이내에서는 전환 없음
- 상태 진입 시 직전 이동 방향으로 초기화

---

## Jump

- **제자리**: 가로 dx 없음. 시트에 베이크된 이동은 `_pin_jump_frames`로 제거
- **Y**: `y = -4 × JUMP_PEAK × t × (1-t)`, `JUMP_PEAK=38`, 10스텝
- **포즈**: `JUMP_FRAME_MAP = [0,1,2,2,3,3,4,4,5,5]`

---

## Held (클릭·드래그)

1. **누름**: 프레임 0→1→2→3 재생 후 **프레임 4** 유지, 드래그 가능
2. **뗌**: Y를 해당 모니터 바닥에 고정 → **5→6** 재생 → walk

---

## 스프라이트 처리 요점

- **walk**: 시트에 가로 이동 베이크됨 → 프레임마다 가로 중앙 정렬
- **jump**: 발 바닥 + 몸통 무게중심 X 고정 → 창 Y 포물선만 사용
- **hiss**: groom 콘텐츠 높이 기준으로 배율 결정 (전 프레임 균일 적용)
- **held**: 프레임 간격 불균일 → `load_sheet_gaps`로 로드
- 모든 상태 프레임은 `_unify_size`로 동일 캔버스 크기

---

## 말풍선

| 시각 | 텍스트 |
|------|--------|
| 9시 | 냥 |
| 12시 | 냐냥 |
| 18시 | 냐냐냥 |

`held` 중에는 숨김.

---

## 주요 상수 (`constants.py`)

| 상수 | 값 | 용도 |
|------|----|------|
| `SCALE` | 0.40 | idle·sit·groom·jump 기본 배율 |
| `WALK_SCALE` | 0.46 | 걷기 배율 |
| `HELD_BODY_SCALE` | 0.60 | held 몸통 높이 (walk 원본 대비) |
| `SCALE_FACTORS` | 0.7/1.0/1.4 | 소·중·대 크기 프리셋 |
| `TICK_MS` | 100 | 틱 주기 (ms) |
| `MOUSE_JUMP_RADIUS` | 120 | 커서 반응 반경 (px) |
| `JUMP_PEAK` | 38 | 점프 최고 높이 (px) |
| `KEY_COLOR` / `KEY_HEX` | (255,255,254) / `#fffffe` | 투명 처리 키컬러 |
