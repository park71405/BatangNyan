"""투명 창 다시 그리기용 최소 Win32 헬퍼."""

import ctypes
import ctypes.wintypes as wt

_user32 = ctypes.windll.user32
_user32.InvalidateRect.argtypes = [wt.HWND, ctypes.c_void_p, wt.BOOL]
_user32.InvalidateRect.restype = wt.BOOL
_user32.UpdateWindow.argtypes = [wt.HWND]
_user32.UpdateWindow.restype = wt.BOOL


def refresh_window(hwnd):
    """키 컬러로 지우지 않고 다시 그린다 (erase=False → 깜빡임 완화)."""
    _user32.InvalidateRect(hwnd, None, False)
    _user32.UpdateWindow(hwnd)
