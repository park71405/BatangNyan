"""스프라이트 시트 로드·스케일·키컬러 합성.

walk: 시트에 가로로 베이크된 이동을 프레임 중앙 정렬로 제거한다.
jump: 발 바닥 + 몸통 무게중심 X를 고정한 뒤, 창 Y 포물선만 쓴다
      (시트에 그려진 가로·세로 이동이 창 이동과 겹치면 ‘갔다가 돌아옴’처럼 보인다).
hiss: 프레임별 독립 스케일을 피하고 전체 프레임의 최대 콘텐츠 높이 기준 단일 배율을 적용한다.
"""

import math
from PIL import Image

from .constants import (
    HELD_BODY_SCALE,
    IMG_DIR,
    KEY_COLOR,
    PADDING,
    SCALE,
    WALK_SCALE,
    WALK_STATES,
)

__all__ = ['load_all']


def _is_guide_pixel(r, g, b, a):
    """빨간 정렬 가이드 픽셀 여부 (bbox에 넣지 않음)."""
    return a > 0 and r > 200 and g < 80 and b < 80


def _content_bbox(frame):
    """가이드를 제외한 불투명 픽셀의 bounding box. 없으면 None."""
    w, h = frame.size
    px = frame.load()
    x0, y0, x1, y1 = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 16 or _is_guide_pixel(r, g, b, a):
                continue
            if x < x0:
                x0 = x
            if y < y0:
                y0 = y
            if x > x1:
                x1 = x
            if y > y1:
                y1 = y
    if x1 < 0:
        return None
    return (x0, y0, x1 + 1, y1 + 1)


def _strip_guides(frame):
    """빨간 가이드를 투명으로 지운 복사본."""
    out = frame.copy()
    px = out.load()
    w, h = frame.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if _is_guide_pixel(r, g, b, a):
                px[x, y] = (0, 0, 0, 0)
    return out


def _register_frames(cells):
    """셀마다 내용만 잘라 공유 캔버스에 올린다.

    가로는 중앙 정렬(walk 베이크 이동 제거), 세로는 시트 상대 위치 유지.
    """
    boxes = []
    cleaned = []
    for cell in cells:
        frame = _strip_guides(cell)
        cleaned.append(frame)
        fw, fh = frame.size
        bb = _content_bbox(frame)
        if bb is None:
            boxes.append((0, 0, fw, fh))
        else:
            boxes.append((
                max(0, bb[0] - PADDING),
                max(0, bb[1] - PADDING),
                min(fw, bb[2] + PADDING),
                min(fh, bb[3] + PADDING),
            ))
    uy0 = min(b[1] for b in boxes)
    uy1 = max(b[3] for b in boxes)
    out_w = max(1, max(b[2] - b[0] for b in boxes))
    out_h = max(1, uy1 - uy0)

    frames = []
    for frame, (bx0, by0, bx1, by1) in zip(cleaned, boxes):
        tight = frame.crop((bx0, by0, bx1, by1))
        canvas = Image.new('RGBA', (out_w, out_h), (0, 0, 0, 0))
        ox = (out_w - tight.width) // 2
        oy = by0 - uy0
        canvas.alpha_composite(tight, dest=(ox, oy))
        frames.append(canvas)
    return frames


def load_sheet(filename, total_frames, start=0, end=None):
    """가로 등분 시트에서 [start, end) 프레임을 로드한다."""
    if end is None:
        end = total_frames
    img = Image.open(IMG_DIR / filename).convert('RGBA')
    w, h = img.size
    fw = w // total_frames
    cells = [img.crop((i * fw, 0, (i + 1) * fw, h)) for i in range(start, end)]
    return _register_frames(cells)


def _gap_cuts(img, expected_frames):
    """빈 열(gap) 중점으로 프레임 경계를 잡는다. 개수가 안 맞으면 None.

    cat-click처럼 간격이 들쭉날쭉한 시트에서 등분 자르기 잘림을 막는다.
    """
    w, h = img.size
    px = img.load()

    def has_content(x):
        for y in range(h):
            r, g, b, a = px[x, y]
            if a >= 16 and not _is_guide_pixel(r, g, b, a):
                return True
        return False

    spans = []
    in_c = False
    start = 0
    for x in range(w):
        c = has_content(x)
        if c and not in_c:
            in_c = True
            start = x
        elif not c and in_c:
            in_c = False
            spans.append((start, x))
    if in_c:
        spans.append((start, w))

    if len(spans) != expected_frames:
        return None

    cuts = [0]
    for i in range(len(spans) - 1):
        cuts.append((spans[i][1] + spans[i + 1][0]) // 2)
    cuts.append(w)
    return cuts


def load_sheet_gaps(filename, total_frames):
    """불균일 간격 시트를 gap 기준으로 로드한다. 실패 시 등분으로 폴백."""
    img = Image.open(IMG_DIR / filename).convert('RGBA')
    h = img.size[1]
    cuts = _gap_cuts(img, total_frames)
    if cuts is None:
        return load_sheet(filename, total_frames)
    cells = [img.crop((cuts[i], 0, cuts[i + 1], h)) for i in range(total_frames)]
    return _register_frames(cells)


def _scale_rgba(frames, scale=SCALE):
    """일괄 배율 리사이즈."""
    result = []
    for img in frames:
        nw = max(1, round(img.width * scale))
        nh = max(1, round(img.height * scale))
        result.append(img.resize((nw, nh), Image.LANCZOS))
    return result


def _scale_to_content_height(frames, target_h):
    """불투명 내용 높이를 target_h에 맞춘다 (held 등 원본 스케일이 다른 시트)."""
    result = []
    for img in frames:
        bb = _content_bbox(img)
        if bb is None:
            result.append(img)
            continue
        content = img.crop(bb)
        if content.height <= 0:
            result.append(img)
            continue
        scale = target_h / content.height
        nw = max(1, round(content.width * scale))
        nh = max(1, round(content.height * scale))
        result.append(content.resize((nw, nh), Image.LANCZOS))
    return result


def _content_anchor_x(frame):
    """불투명 픽셀의 가로 무게중심 (몸통 앵커)."""
    bb = _content_bbox(frame)
    if bb is None:
        return frame.width / 2
    px = frame.load()
    total = 0
    n = 0
    for y in range(bb[1], bb[3]):
        for x in range(bb[0], bb[2]):
            r, g, b, a = px[x, y]
            if a >= 16 and not _is_guide_pixel(r, g, b, a):
                total += x
                n += 1
    return (total / n) if n else frame.width / 2


def _pin_jump_frames(frames):
    """점프 프레임을 바닥 정렬하고 몸통 무게중심 X를 공유 중심선에 고정한다.

    이후 창은 jump_y_offset 만으로 포물선을 그린다 (가로 dx 없음).
    """
    metas = []
    for img in frames:
        bb = _content_bbox(img)
        if bb is None:
            metas.append((img, img.width / 2))
            continue
        content = img.crop(bb)
        ax = _content_anchor_x(img) - bb[0]  # content 로컬 좌표
        metas.append((content, ax))

    out_h = max(1, max(c.height for c, _ in metas))
    half = max(1, int(math.ceil(max(max(ax, c.width - ax) for c, ax in metas))))
    out_w = half * 2

    result = []
    for content, ax in metas:
        canvas = Image.new('RGBA', (out_w, out_h), (0, 0, 0, 0))
        x = int(round(out_w / 2 - ax))
        y = out_h - content.height
        canvas.alpha_composite(content, dest=(x, y))
        result.append(canvas)
    return result


def _to_display(frames):
    """RGBA → 키컬러 RGB.

    알파 < 200 은 완전 투명으로 잘라 반투명 가장자리가 키컬러로 남는 fringe 를 막는다.
    """
    result = []
    for frame in frames:
        r, g, b, a = frame.split()
        a = a.point(lambda p: 0 if p < 200 else 255)
        frame = Image.merge('RGBA', (r, g, b, a))
        bg = Image.new('RGBA', frame.size, (*KEY_COLOR, 255))
        bg.alpha_composite(frame)
        result.append(bg.convert('RGB'))
    return result


def _unify_size(states):
    """모든 상태 프레임을 동일 크기로 맞춘다 (바닥·가로 중앙 패딩).

    창 geometry가 상태마다 바뀌면 깜빡이므로, 로드 시점에 한 번 통일한다.
    """
    max_w = max(f.width for frames in states.values() for f in frames)
    max_h = max(f.height for frames in states.values() for f in frames)
    result = {}
    for name, frames in states.items():
        unified = []
        for f in frames:
            canvas = Image.new('RGB', (max_w, max_h), KEY_COLOR)
            x = (max_w - f.width) // 2
            y = max_h - f.height
            canvas.paste(f, (x, y))
            unified.append(canvas)
        result[name] = unified
    return result


def load_all(scale_factor=1.0):
    """게임에 쓰는 모든 상태 스프라이트를 로드·스케일·통일 크기로 반환한다."""
    raw = {
        'walk_r': load_sheet('cat-walk-right.png', 8),
        'walk_l': load_sheet('cat-walk-left.png', 8),
        'idle': load_sheet('cat-idle-stop.png', 8, 0, 2),
        'sit': load_sheet('cat-idle-stop.png', 8, 6, 7),  # 7번 칸은 비어 있음
        'groom': load_sheet('cat-groom.png', 8),
        'jump_r': _pin_jump_frames(load_sheet('cat-jump-cycle-right.png', 6)),
        'jump_l': _pin_jump_frames(load_sheet('cat-jump-cycle-left.png', 6)),
    }
    if (IMG_DIR / 'cat-hissing.png').exists():
        raw['hiss'] = load_sheet('cat-hissing.png', 8)

    walk_bb = _content_bbox(raw['walk_r'][0])
    walk_content_h = (walk_bb[3] - walk_bb[1]) if walk_bb else raw['walk_r'][0].height
    held_body_h = max(1, round(walk_content_h * HELD_BODY_SCALE * scale_factor))

    scaled = {}
    for k, v in raw.items():
        if k == 'hiss':
            continue  # 아래에서 groom 기준 높이로 별도 처리
        scale = (WALK_SCALE if k in WALK_STATES else SCALE) * scale_factor
        scaled[k] = _scale_rgba(v, scale)

    if 'hiss' in raw:
        ref = scaled.get('groom') or scaled.get('idle')
        ref_bb = _content_bbox(ref[0]) if ref else None
        ref_h = (ref_bb[3] - ref_bb[1]) if ref_bb else None
        if ref_h:
            # 프레임별 독립 스케일을 피하기 위해 전체 프레임의 최대 콘텐츠 높이로
            # 단일 배율을 결정하고 _scale_rgba 로 균일 적용한다.
            bbs = [_content_bbox(f) for f in raw['hiss']]
            content_heights = [(bb[3] - bb[1]) for bb in bbs if bb is not None]
            if content_heights:
                hiss_scale = ref_h / max(content_heights) * 1.1
                scaled['hiss'] = _scale_rgba(raw['hiss'], hiss_scale)
            else:
                scaled['hiss'] = _scale_rgba(raw['hiss'], SCALE * scale_factor)
        else:
            scaled['hiss'] = _scale_rgba(raw['hiss'], SCALE * scale_factor)

    if (IMG_DIR / 'cat-click.png').exists():
        click_raw = load_sheet_gaps('cat-click.png', 7)
        scaled['held'] = _scale_to_content_height(click_raw, held_body_h)

    display = {k: _to_display(v) for k, v in scaled.items()}
    return _unify_size(display)
