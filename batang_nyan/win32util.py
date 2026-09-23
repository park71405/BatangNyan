"""투명 창 다시 그리기 및 가상 데스크톱 정보 조회용 Win32 헬퍼."""

import ctypes
import ctypes.wintypes as wt

_user32 = ctypes.windll.user32
_user32.InvalidateRect.argtypes = [wt.HWND, ctypes.c_void_p, wt.BOOL]
_user32.InvalidateRect.restype = wt.BOOL
_user32.UpdateWindow.argtypes = [wt.HWND]
_user32.UpdateWindow.restype = wt.BOOL
_user32.GetSystemMetrics.argtypes = [ctypes.c_int]
_user32.GetSystemMetrics.restype = ctypes.c_int

_MONITORENUMPROC = ctypes.WINFUNCTYPE(
    wt.BOOL,
    wt.HMONITOR,
    wt.HDC,
    ctypes.POINTER(wt.RECT),
    wt.LPARAM,
)
_user32.EnumDisplayMonitors.argtypes = [wt.HDC, ctypes.POINTER(wt.RECT), _MONITORENUMPROC, wt.LPARAM]
_user32.EnumDisplayMonitors.restype = wt.BOOL

_kernel32 = ctypes.windll.kernel32
_kernel32.SetThreadExecutionState.argtypes = [ctypes.c_uint]
_kernel32.SetThreadExecutionState.restype  = ctypes.c_uint

_ES_CONTINUOUS       = 0x80000000
_ES_DISPLAY_REQUIRED = 0x00000002

_SM_XVIRTUALSCREEN = 76
_SM_YVIRTUALSCREEN = 77
_SM_CXVIRTUALSCREEN = 78
_SM_CYVIRTUALSCREEN = 79


def get_monitors():
    """연결된 모든 모니터의 (left, top, width, height) 목록을 반환한다."""
    monitors = []

    def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
        r = lprcMonitor.contents
        monitors.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True

    _user32.EnumDisplayMonitors(None, None, _MONITORENUMPROC(callback), 0)
    return monitors


def get_virtual_screen():
    """전체 모니터를 포함하는 가상 데스크톱 범위를 (left, top, width, height)로 반환한다.

    단일 모니터 환경에서는 (0, 0, screen_w, screen_h)와 동일.
    보조 모니터가 왼쪽에 있으면 left 가 음수가 될 수 있다.
    """
    get = _user32.GetSystemMetrics
    return (
        get(_SM_XVIRTUALSCREEN),
        get(_SM_YVIRTUALSCREEN),
        get(_SM_CXVIRTUALSCREEN),
        get(_SM_CYVIRTUALSCREEN),
    )


def prevent_sleep():
    """앱 실행 중 화면 끄기·절전을 막는다."""
    _kernel32.SetThreadExecutionState(_ES_CONTINUOUS | _ES_DISPLAY_REQUIRED)


def allow_sleep():
    """절전 방지를 해제한다 (앱 종료 시 호출)."""
    _kernel32.SetThreadExecutionState(_ES_CONTINUOUS)


def refresh_window(hwnd):
    """키 컬러로 지우지 않고 다시 그린다.

    erase=False: 배경을 키컬러로 먼저 지우지 않아 transparentcolor 창의 깜빡임을 줄인다.
    """
    _user32.InvalidateRect(hwnd, None, False)
    _user32.UpdateWindow(hwnd)
