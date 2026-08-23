"""The muted badge: a layered, click-through, always-on-top window.

Per-pixel alpha via UpdateLayeredWindow, so the rounded badge is genuinely
anti-aliased over whatever is underneath instead of showing a colour-keyed
fringe. WS_EX_TRANSPARENT keeps clicks going through to the window below,
WS_EX_NOACTIVATE stops it stealing focus, WS_EX_TOOLWINDOW keeps it out of
Alt+Tab, and there is no repaint at all while it just sits there.
"""
import ctypes
import threading
from ctypes import byref, wintypes

from . import iconart
from .w32 import (AC_SRC_ALPHA, AC_SRC_OVER, BI_RGB, BITMAPINFO, BLENDFUNCTION,
                  DIB_RGB_COLORS, HWND_TOPMOST, SIZE, SWP_NOACTIVATE,
                  SWP_NOMOVE, SWP_NOSIZE, SW_HIDE, SW_SHOWNOACTIVATE,
                  ULW_ALPHA, WM_APP, WM_DESTROY, WM_DISPLAYCHANGE,
                  WM_SETTINGCHANGE, WM_TIMER, WNDCLASSEXW, WNDPROC, WS_EX_LAYERED,
                  WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TOPMOST,
                  WS_EX_TRANSPARENT, WS_POPUP, gdi32, kernel32,
                  primary_work_area, user32)

WM_OVERLAY_VISIBLE = WM_APP + 1
WM_OVERLAY_REFRESH = WM_APP + 2

TOPMOST_TIMER = 1
TOPMOST_INTERVAL_MS = 3000      # cheap insurance against losing the top slot

CLASS_NAME = "CuteMuteOverlay"


class Overlay:
    """Created and driven on the Win32 UI thread; poked from anywhere."""

    def __init__(self, cfg):
        self._lock = threading.Lock()
        self._cfg = dict(cfg["overlay"])
        self.hwnd = None
        self._visible = False
        self._want_visible = False
        self._proc = WNDPROC(self._wnd_proc)
        self._class_registered = False

    # -- called from any thread --------------------------------------------
    @property
    def wants_visible(self):
        with self._lock:
            return self._want_visible

    def set_visible(self, visible):
        with self._lock:
            self._want_visible = bool(visible)
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_OVERLAY_VISIBLE,
                                1 if visible else 0, 0)

    def apply(self, cfg):
        with self._lock:
            self._cfg = dict(cfg["overlay"])
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_OVERLAY_REFRESH, 0, 0)

    # -- UI thread ---------------------------------------------------------
    def create(self):
        hinstance = kernel32.GetModuleHandleW(None)
        cls = WNDCLASSEXW()
        cls.cbSize = ctypes.sizeof(WNDCLASSEXW)
        cls.lpfnWndProc = self._proc
        cls.hInstance = hinstance
        cls.lpszClassName = CLASS_NAME
        if not user32.RegisterClassExW(byref(cls)):
            err = ctypes.get_last_error()
            if err != 1410:                      # ERROR_CLASS_ALREADY_EXISTS
                raise ctypes.WinError(err)
        self._class_registered = True

        self.hwnd = user32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST
            | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            CLASS_NAME, "CuteMute badge", WS_POPUP,
            0, 0, 1, 1, None, None, hinstance, None)
        if not self.hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        self._repaint()
        with self._lock:
            want = self._want_visible
        self._show(want)

    def destroy(self):
        if self.hwnd:
            user32.KillTimer(self.hwnd, ctypes.c_void_p(TOPMOST_TIMER))
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
        if self._class_registered:
            user32.UnregisterClassW(CLASS_NAME, kernel32.GetModuleHandleW(None))
            self._class_registered = False

    # -- internals ---------------------------------------------------------
    def _geometry(self):
        with self._lock:
            cfg = dict(self._cfg)
        size = max(10, int(cfg.get("size", 20)))
        margin = max(0, int(cfg.get("margin", 8)))
        corner = cfg.get("corner", "bottom-right")
        left, top, right, bottom = primary_work_area()
        x = right - margin - size if corner.endswith("right") else left + margin
        y = bottom - margin - size if corner.startswith("bottom") else top + margin
        return x, y, size, cfg

    def _repaint(self):
        """Push a fresh ARGB bitmap and position into the layered window."""
        if not self.hwnd:
            return
        x, y, size, cfg = self._geometry()
        pixels = iconart.bgra_premultiplied(size, True)

        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(info.bmiHeader)
        info.bmiHeader.biWidth = size
        info.bmiHeader.biHeight = -size          # negative: top-down rows
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = BI_RGB

        screen_dc = user32.GetDC(None)
        mem_dc = gdi32.CreateCompatibleDC(screen_dc)
        bits = ctypes.c_void_p()
        bitmap = gdi32.CreateDIBSection(screen_dc, byref(info), DIB_RGB_COLORS,
                                        byref(bits), None, 0)
        old = None
        try:
            if not bitmap or not bits:
                return
            ctypes.memmove(bits, pixels, len(pixels))
            old = gdi32.SelectObject(mem_dc, bitmap)

            blend = BLENDFUNCTION(AC_SRC_OVER, 0,
                                  int(max(20, min(100, cfg.get("opacity", 100)))
                                      * 255 // 100),
                                  AC_SRC_ALPHA)
            user32.UpdateLayeredWindow(
                self.hwnd, screen_dc, byref(wintypes.POINT(x, y)),
                byref(SIZE(size, size)), mem_dc, byref(wintypes.POINT(0, 0)),
                0, byref(blend), ULW_ALPHA)
        finally:
            if old:
                gdi32.SelectObject(mem_dc, old)
            if bitmap:
                gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(None, screen_dc)

    def _raise(self):
        user32.SetWindowPos(self.hwnd, wintypes.HWND(HWND_TOPMOST), 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def _show(self, visible, force=False):
        with self._lock:
            enabled = bool(self._cfg.get("enabled", True))
        visible = bool(visible) and enabled
        if visible == self._visible and not force:
            if visible:
                self._raise()
            return
        self._visible = visible
        if visible:
            user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
            self._raise()
            user32.SetTimer(self.hwnd, ctypes.c_void_p(TOPMOST_TIMER),
                            TOPMOST_INTERVAL_MS, None)
        else:
            user32.KillTimer(self.hwnd, ctypes.c_void_p(TOPMOST_TIMER))
            user32.ShowWindow(self.hwnd, SW_HIDE)

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_OVERLAY_VISIBLE:
                self._show(bool(wparam))
                return 0
            if msg == WM_OVERLAY_REFRESH:
                self._repaint()
                # force=True so a change to the "enabled" switch alone still
                # takes effect, even though the wanted visibility is unchanged.
                self._show(self.wants_visible, force=True)
                return 0
            if msg in (WM_DISPLAYCHANGE, WM_SETTINGCHANGE):
                self._repaint()          # taskbar moved or resolution changed
                return 0
            if msg == WM_TIMER and wparam == TOPMOST_TIMER:
                if self._visible:
                    self._raise()
                return 0
            if msg == WM_DESTROY:
                return 0
        except Exception:
            pass
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
