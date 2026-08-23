"""The tray menu, painted to match the settings panel instead of the system.

Windows is good at the parts of a popup menu that are easy to get wrong:
keyboard navigation, dismissing on a click somewhere else, staying on the right
monitor, the frame and its shadow. So the menu stays a real menu and only the
items are owner-drawn - same palette, same Segoe UI, same rounded highlight as
a row in the settings window.

The background brush is not optional: Windows 11 still paints a classic Win32
menu in the light theme even when everything else on the desktop is dark, and
light grey text on it would be unreadable. That brush is also why the popup
keeps square corners - the rounded frame Windows draws lives in the same pixels
the brush covers, and neither DWM nor a window region will round a menu back
up.

Drawing happens on the Win32 UI thread, inside WM_DRAWITEM, so it is plain GDI
here rather than the sprite kit the panel uses. The two agree because they read
their colours from theme.py.
"""
import collections
import ctypes
from ctypes import byref, wintypes

from . import theme
from .w32 import (CLEARTYPE_QUALITY, DEFAULT_CHARSET, DRAWITEMSTRUCT, DT_LEFT,
                  DT_NOPREFIX, DT_RIGHT, DT_SINGLELINE, DT_VCENTER, FW_NORMAL,
                  FW_SEMIBOLD, MEASUREITEMSTRUCT, MENUINFO, MF_BYCOMMAND,
                  MF_OWNERDRAW, MIM_BACKGROUND, ODS_DEFAULT, ODS_SELECTED,
                  PS_SOLID, SIZE, TPM_RETURNCMD, TPM_RIGHTBUTTON, TRANSPARENT,
                  WM_NULL, gdi32, system_dpi, user32)

# One item of the menu. `accel` is right-aligned and dimmed, `checked` draws a
# tick in the left gutter.
Item = collections.namedtuple("Item", "ident label accel checked")
Item.__new__.__defaults__ = ("", False)

HEIGHT = 34                 # logical px per row
GUTTER = 30                 # left column, wide enough for the tick
PADDING = 14                # right of the label, left of the accelerator
ACCEL_GAP = 30              # blank kept between a label and its accelerator
RADIUS = 6


def _colourref(colour):
    """'#rrggbb' -> the 0x00bbggrr integer GDI wants."""
    return (int(colour[5:7], 16) << 16 | int(colour[3:5], 16) << 8
            | int(colour[1:3], 16))


class DarkMenu:
    """One reusable popup. Build it, show it, get the chosen id back."""

    def __init__(self):
        self._items = {}
        self._fonts = {}
        self._brushes = {}
        self._scale = system_dpi() / 96.0

    def s(self, value):
        return int(round(value * self._scale))

    # -- resources, made once and kept for the life of the tray ------------
    def _brush(self, colour):
        brush = self._brushes.get(colour)
        if brush is None:
            brush = gdi32.CreateSolidBrush(_colourref(colour))
            self._brushes[colour] = brush
        return brush

    def _font(self, bold=False):
        font = self._fonts.get(bool(bold))
        if font is None:
            font = gdi32.CreateFontW(
                -self.s(12), 0, 0, 0, FW_SEMIBOLD if bold else FW_NORMAL,
                0, 0, 0, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0,
                "Segoe UI")
            self._fonts[bool(bold)] = font
        return font

    def destroy(self):
        for handle in list(self._brushes.values()) + list(self._fonts.values()):
            if handle:
                gdi32.DeleteObject(handle)
        self._brushes.clear()
        self._fonts.clear()

    # -- showing -----------------------------------------------------------
    def show(self, hwnd, items, default=None):
        """Pop up at the cursor; returns the chosen ident, or 0 if dismissed."""
        menu = user32.CreatePopupMenu()
        if not menu:
            return 0
        self._items = {item.ident: item for item in items}
        try:
            for item in items:
                user32.AppendMenuW(menu, MF_OWNERDRAW, item.ident, None)

            # Without this the frame and the gap around the items stay in the
            # system's colours, which on a light theme is a white halo.
            info = MENUINFO()
            info.cbSize = ctypes.sizeof(MENUINFO)
            info.fMask = MIM_BACKGROUND
            info.hbrBack = self._brush(theme.TILE)
            user32.SetMenuInfo(menu, byref(info))
            if default is not None:
                user32.SetMenuDefaultItem(menu, default, MF_BYCOMMAND)

            point = wintypes.POINT()
            user32.GetCursorPos(byref(point))
            # Required so the menu dismisses properly when focus moves away.
            user32.SetForegroundWindow(hwnd)
            choice = user32.TrackPopupMenu(
                menu, TPM_RIGHTBUTTON | TPM_RETURNCMD, point.x, point.y, 0,
                hwnd, None)
            user32.PostMessageW(hwnd, WM_NULL, 0, 0)
            return choice
        finally:
            user32.DestroyMenu(menu)

    # -- owner draw, called from the tray window's message loop ------------
    def measure(self, lparam):
        info = ctypes.cast(lparam,
                           ctypes.POINTER(MEASUREITEMSTRUCT)).contents
        item = self._items.get(info.itemID)
        if item is None:
            return False
        width = self.s(GUTTER) + self._width(item.label) + self.s(PADDING)
        if item.accel:
            width += self.s(ACCEL_GAP) + self._width(item.accel)
        info.itemWidth = width
        info.itemHeight = self.s(HEIGHT)
        return True

    def draw(self, lparam):
        info = ctypes.cast(lparam, ctypes.POINTER(DRAWITEMSTRUCT)).contents
        item = self._items.get(info.itemID)
        if item is None:
            return False
        hdc, rect = info.hDC, info.rcItem
        user32.FillRect(hdc, byref(rect), self._brush(theme.TILE))
        if info.itemState & ODS_SELECTED:
            self._highlight(hdc, rect)

        gdi32.SetBkMode(hdc, TRANSPARENT)
        old_font = gdi32.SelectObject(
            hdc, self._font(bool(info.itemState & ODS_DEFAULT)))
        box = wintypes.RECT(rect.left + self.s(GUTTER), rect.top,
                            rect.right - self.s(PADDING), rect.bottom)
        gdi32.SetTextColor(hdc, _colourref(theme.TEXT))
        user32.DrawTextW(hdc, item.label, -1, byref(box),
                         DT_SINGLELINE | DT_VCENTER | DT_LEFT | DT_NOPREFIX)
        if item.accel:
            gdi32.SetTextColor(hdc, _colourref(theme.DIM))
            user32.DrawTextW(hdc, item.accel, -1, byref(box),
                             DT_SINGLELINE | DT_VCENTER | DT_RIGHT
                             | DT_NOPREFIX)
        gdi32.SelectObject(hdc, old_font)
        if item.checked:
            self._tick(hdc, rect)
        return True

    def _highlight(self, hdc, rect):
        """The same rounded lozenge a hovered row gets in the panel."""
        inset, radius = self.s(4), self.s(RADIUS) * 2
        region = gdi32.CreateRoundRectRgn(rect.left + inset,
                                          rect.top + self.s(1),
                                          rect.right - inset,
                                          rect.bottom - self.s(1),
                                          radius, radius)
        if region:
            gdi32.FillRgn(hdc, region, self._brush(theme.MENU_HOVER))
            gdi32.DeleteObject(region)

    def _tick(self, hdc, rect):
        pen = gdi32.CreatePen(PS_SOLID, max(2, self.s(2)),
                              _colourref(theme.ACCENT))
        old = gdi32.SelectObject(hdc, pen)
        box = self.s(12)
        x = rect.left + (self.s(GUTTER) - box) // 2 + self.s(2)
        y = rect.top + ((rect.bottom - rect.top) - box) // 2
        points = (wintypes.POINT * 3)(
            wintypes.POINT(x, y + int(box * 0.55)),
            wintypes.POINT(x + int(box * 0.35), y + int(box * 0.85)),
            wintypes.POINT(x + int(box * 0.95), y + int(box * 0.18)))
        gdi32.Polyline(hdc, points, 3)
        gdi32.SelectObject(hdc, old)
        gdi32.DeleteObject(pen)

    def _width(self, text):
        dc = user32.GetDC(None)
        old = gdi32.SelectObject(dc, self._font())
        size = SIZE()
        gdi32.GetTextExtentPoint32W(dc, text, len(text), byref(size))
        gdi32.SelectObject(dc, old)
        user32.ReleaseDC(None, dc)
        return size.cx
