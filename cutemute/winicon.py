"""Turn the procedural badge into a real HICON for the tray and window frames."""
import ctypes
from ctypes import byref

from . import iconart
from .w32 import (BI_RGB, BITMAPINFO, DIB_RGB_COLORS, ICONINFO, gdi32, user32)


def make_hicon(size, muted):
    """32bpp alpha icon. Returns None on failure; caller owns the handle."""
    pixels = iconart.bgra_straight(size, muted)

    info = BITMAPINFO()
    info.bmiHeader.biSize = ctypes.sizeof(info.bmiHeader)
    info.bmiHeader.biWidth = size
    info.bmiHeader.biHeight = -size            # top-down
    info.bmiHeader.biPlanes = 1
    info.bmiHeader.biBitCount = 32
    info.bmiHeader.biCompression = BI_RGB

    screen_dc = user32.GetDC(None)
    colour = mask = None
    try:
        bits = ctypes.c_void_p()
        colour = gdi32.CreateDIBSection(screen_dc, byref(info), DIB_RGB_COLORS,
                                        byref(bits), None, 0)
        if not colour or not bits:
            return None
        ctypes.memmove(bits, pixels, len(pixels))

        # An all-zero AND mask means "use the colour bitmap"; the alpha channel
        # does the real work on every Windows that matters.
        stride = ((size + 15) // 16) * 2
        blank = (ctypes.c_ubyte * (stride * size))()
        mask = gdi32.CreateBitmap(size, size, 1, 1, blank)
        if not mask:
            return None

        icon_info = ICONINFO()
        icon_info.fIcon = True
        icon_info.hbmMask = mask
        icon_info.hbmColor = colour
        return user32.CreateIconIndirect(byref(icon_info)) or None
    finally:
        if colour:
            gdi32.DeleteObject(colour)
        if mask:
            gdi32.DeleteObject(mask)
        user32.ReleaseDC(None, screen_dc)


def destroy_hicon(handle):
    if handle:
        user32.DestroyIcon(handle)
