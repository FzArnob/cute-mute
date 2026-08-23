"""Thin ctypes bindings for the slice of Win32 that CuteMute needs.

Everything here is stdlib-only on purpose: no pywin32, no comtypes, no Pillow.
That keeps the frozen exe small and the idle footprint tiny.
"""
import ctypes
import sys
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
ole32 = ctypes.WinDLL("ole32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
HANDLE = wintypes.HANDLE
HICON = HANDLE
HBITMAP = HANDLE
HMENU = HANDLE
HMONITOR = HANDLE
HHOOK = HANDLE

WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM)
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int,
                              wintypes.WPARAM, wintypes.LPARAM)

# ---------------------------------------------------------------- structures


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8)]

    def __init__(self, text=None):
        super().__init__()
        if text:
            ole32.CLSIDFromString(ctypes.c_wchar_p(text), ctypes.byref(self))


class SIZE(ctypes.Structure):
    _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT),
                ("style", wintypes.UINT),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", HICON),
                ("hCursor", HANDLE),
                ("hbrBackground", HANDLE),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
                ("hIconSm", HICON)]


class MENUINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("fMask", wintypes.DWORD),
                ("dwStyle", wintypes.DWORD), ("cyMax", wintypes.UINT),
                ("hbrBack", HANDLE), ("dwContextHelpID", wintypes.DWORD),
                ("dwMenuData", ctypes.c_void_p)]


class MEASUREITEMSTRUCT(ctypes.Structure):
    _fields_ = [("CtlType", wintypes.UINT), ("CtlID", wintypes.UINT),
                ("itemID", wintypes.UINT), ("itemWidth", wintypes.UINT),
                ("itemHeight", wintypes.UINT), ("itemData", ctypes.c_void_p)]


class DRAWITEMSTRUCT(ctypes.Structure):
    _fields_ = [("CtlType", wintypes.UINT), ("CtlID", wintypes.UINT),
                ("itemID", wintypes.UINT), ("itemAction", wintypes.UINT),
                ("itemState", wintypes.UINT), ("hwndItem", wintypes.HWND),
                ("hDC", wintypes.HDC), ("rcItem", wintypes.RECT),
                ("itemData", ctypes.c_void_p)]


class MARGINS(ctypes.Structure):
    _fields_ = [("cxLeftWidth", ctypes.c_int), ("cxRightWidth", ctypes.c_int),
                ("cyTopHeight", ctypes.c_int), ("cyBottomHeight", ctypes.c_int)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte),
                ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte),
                ("AlphaFormat", ctypes.c_ubyte)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD),
                ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER),
                ("bmiColors", wintypes.DWORD * 3)]


class ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wintypes.BOOL),
                ("xHotspot", wintypes.DWORD),
                ("yHotspot", wintypes.DWORD),
                ("hbmMask", HBITMAP),
                ("hbmColor", HBITMAP)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD)]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD),
                ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_void_p)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD),
                ("hWnd", wintypes.HWND),
                ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT),
                ("uCallbackMessage", wintypes.UINT),
                ("hIcon", HICON),
                ("szTip", wintypes.WCHAR * 128),
                ("dwState", wintypes.DWORD),
                ("dwStateMask", wintypes.DWORD),
                ("szInfo", wintypes.WCHAR * 256),
                ("uVersion", wintypes.UINT),
                ("szInfoTitle", wintypes.WCHAR * 64),
                ("dwInfoFlags", wintypes.DWORD),
                ("guidItem", GUID),
                ("hBalloonIcon", HICON)]

# ---------------------------------------------------------------- constants

WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

SW_HIDE = 0
SW_SHOWNOACTIVATE = 4

HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_QUIT = 0x0012
WM_SETTINGCHANGE = 0x001A
WM_DISPLAYCHANGE = 0x007E
WM_NULL = 0x0000
WM_COMMAND = 0x0111
WM_TIMER = 0x0113
WM_APP = 0x8000

WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_CONTEXTMENU = 0x007B

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

WH_KEYBOARD_LL = 13
LLKHF_INJECTED = 0x10

BI_RGB = 0
DIB_RGB_COLORS = 0
ULW_ALPHA = 0x02
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01

NIM_ADD = 0
NIM_MODIFY = 1
NIM_DELETE = 2
NIF_MESSAGE = 0x01
NIF_ICON = 0x02
NIF_TIP = 0x04

MF_OWNERDRAW = 0x0100
MF_BYCOMMAND = 0x0000
MIM_BACKGROUND = 0x00000002
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100

WM_DRAWITEM = 0x002B
WM_MEASUREITEM = 0x002C
ODS_SELECTED = 0x0001
ODS_DEFAULT = 0x0020

DT_LEFT = 0x0000
DT_RIGHT = 0x0002
DT_VCENTER = 0x0004
DT_SINGLELINE = 0x0020
DT_NOPREFIX = 0x0800
TRANSPARENT = 1
FW_NORMAL = 400
FW_SEMIBOLD = 600
DEFAULT_CHARSET = 1
CLEARTYPE_QUALITY = 5
PS_SOLID = 0

MONITOR_DEFAULTTOPRIMARY = 1

WM_SETICON = 0x0080
ICON_SMALL = 0
ICON_BIG = 1
GA_ROOT = 2

GWL_EXSTYLE = -20
WS_EX_APPWINDOW = 0x00040000
SW_MINIMIZE = 6
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2

SM_CXSMICON = 49
SM_CYSMICON = 50

ERROR_ALREADY_EXISTS = 183

COM_RELEASE = 2             # IUnknown::Release, slot 2 of every vtable
CLSCTX_INPROC_SERVER = 0x1
COINIT_APARTMENTTHREADED = 0x2

MB_YESNO = 0x0004
MB_OK = 0x0000
MB_ICONQUESTION = 0x0020
MB_ICONINFORMATION = 0x0040
MB_SETFOREGROUND = 0x00010000
IDYES = 6

# ---------------------------------------------------------------- prototypes

user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT,
                                  wintypes.WPARAM, wintypes.LPARAM]
user32.RegisterClassExW.restype = wintypes.WORD
user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                   wintypes.DWORD, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                   HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.GetMessageW.restype = ctypes.c_int
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                               wintypes.UINT, wintypes.UINT]
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT,
                                      wintypes.WPARAM, wintypes.LPARAM]
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.SetTimer.restype = ctypes.c_void_p
user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_void_p,
                            wintypes.UINT, ctypes.c_void_p]
user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.RegisterWindowMessageW.restype = wintypes.UINT
user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.GetDC.argtypes = [wintypes.HWND]
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.UpdateLayeredWindow.argtypes = [wintypes.HWND, wintypes.HDC,
                                       ctypes.POINTER(wintypes.POINT),
                                       ctypes.POINTER(SIZE), wintypes.HDC,
                                       ctypes.POINTER(wintypes.POINT), wintypes.DWORD,
                                       ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD]
user32.CreateIconIndirect.restype = HICON
user32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
user32.DestroyIcon.argtypes = [HICON]
user32.MonitorFromPoint.restype = HMONITOR
user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
user32.GetMonitorInfoW.argtypes = [HMONITOR, ctypes.POINTER(MONITORINFO)]
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.SetWindowsHookExW.restype = HHOOK
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC,
                                     wintypes.HINSTANCE, wintypes.DWORD]
user32.UnhookWindowsHookEx.argtypes = [HHOOK]
user32.CallNextHookEx.restype = LRESULT
user32.CallNextHookEx.argtypes = [HHOOK, ctypes.c_int,
                                  wintypes.WPARAM, wintypes.LPARAM]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetKeyNameTextW.restype = ctypes.c_int
user32.GetKeyNameTextW.argtypes = [wintypes.LONG, wintypes.LPWSTR, ctypes.c_int]
user32.MapVirtualKeyW.restype = wintypes.UINT
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
user32.CreatePopupMenu.restype = HMENU
user32.AppendMenuW.argtypes = [HMENU, wintypes.UINT, ctypes.c_void_p, wintypes.LPCWSTR]
user32.DestroyMenu.argtypes = [HMENU]
user32.TrackPopupMenu.restype = ctypes.c_int
user32.TrackPopupMenu.argtypes = [HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, wintypes.HWND, ctypes.c_void_p]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.MessageBoxW.restype = ctypes.c_int
user32.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR,
                               wintypes.LPCWSTR, wintypes.UINT]
user32.SendMessageW.restype = LRESULT
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                wintypes.WPARAM, wintypes.LPARAM]
user32.GetAncestor.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]

user32.GetWindowLongW.restype = wintypes.LONG
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowLongW.restype = wintypes.LONG
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
user32.SetMenuDefaultItem.argtypes = [HMENU, wintypes.UINT, wintypes.UINT]
user32.SetMenuDefaultItem.restype = wintypes.BOOL
user32.SetMenuInfo.argtypes = [HMENU, ctypes.POINTER(MENUINFO)]
user32.FillRect.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT), HANDLE]
user32.DrawTextW.restype = ctypes.c_int
user32.DrawTextW.argtypes = [wintypes.HDC, wintypes.LPCWSTR, ctypes.c_int,
                             ctypes.POINTER(wintypes.RECT), wintypes.UINT]

gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.CreateDIBSection.restype = HBITMAP
gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.POINTER(BITMAPINFO),
                                   wintypes.UINT, ctypes.POINTER(ctypes.c_void_p),
                                   HANDLE, wintypes.DWORD]
gdi32.CreateBitmap.restype = HBITMAP
gdi32.CreateBitmap.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.UINT,
                               wintypes.UINT, ctypes.c_void_p]
gdi32.SelectObject.restype = HANDLE
gdi32.SelectObject.argtypes = [wintypes.HDC, HANDLE]
gdi32.DeleteObject.argtypes = [HANDLE]

gdi32.CreateSolidBrush.restype = HANDLE
gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]
gdi32.CreateRoundRectRgn.restype = HANDLE
gdi32.CreateRoundRectRgn.argtypes = [ctypes.c_int] * 6
gdi32.FillRgn.argtypes = [wintypes.HDC, HANDLE, HANDLE]
gdi32.SetBkMode.argtypes = [wintypes.HDC, ctypes.c_int]
gdi32.SetTextColor.restype = wintypes.COLORREF
gdi32.SetTextColor.argtypes = [wintypes.HDC, wintypes.COLORREF]
gdi32.CreateFontW.restype = HANDLE
gdi32.CreateFontW.argtypes = [ctypes.c_int] * 8 + [wintypes.DWORD] * 5 + [
    wintypes.LPCWSTR]
gdi32.CreatePen.restype = HANDLE
gdi32.CreatePen.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.COLORREF]
gdi32.Polyline.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.POINT),
                           ctypes.c_int]
gdi32.GetTextExtentPoint32W.argtypes = [wintypes.HDC, wintypes.LPCWSTR,
                                        ctypes.c_int, ctypes.POINTER(SIZE)]

shell32.Shell_NotifyIconW.restype = wintypes.BOOL
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]

ole32.CLSIDFromString.restype = ctypes.HRESULT
ole32.CLSIDFromString.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(GUID)]
# CoInitializeEx legitimately returns S_FALSE, so do not let HRESULT raise on it.
ole32.CoInitializeEx.restype = ctypes.c_long
ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
ole32.CoUninitialize.argtypes = []
ole32.CoCreateInstance.restype = ctypes.HRESULT
ole32.CoCreateInstance.argtypes = [ctypes.POINTER(GUID), ctypes.c_void_p,
                                   wintypes.DWORD, ctypes.POINTER(GUID),
                                   ctypes.POINTER(ctypes.c_void_p)]
ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]

kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.CreateMutexW.restype = HANDLE
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CloseHandle.argtypes = [HANDLE]


def com_call(ptr, slot, *argtypes):
    """Bind vtable[slot] of a COM interface pointer as a callable.

    The callable takes the interface pointer as its first argument, so a call
    reads like the C++ one: com_call(link, SETPATH, c_wchar_p)(link, path).
    """
    vtable = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))
    proto = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, *argtypes)
    return proto(vtable.contents[slot])


def com_release(ptr):
    if ptr and ptr.value:
        vtable = ctypes.cast(ptr,
                             ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))
        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(
            vtable.contents[COM_RELEASE])(ptr)
        ptr.value = None


def set_dpi_awareness():
    """Per-monitor-v2, so a 20 px badge really is 20 physical pixels and never blurs."""
    try:
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except AttributeError:
        pass
    try:
        ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


def make_frameless(hwnd):
    """Give a borderless window back what a frame would have granted it.

    The settings window draws its own title bar, because Windows insists on
    showing a (greyed out) maximise button beside the minimise one and there is
    no style that says "minimise and close only". So the frame goes, and with
    it the taskbar button, Alt+Tab entry and rounded corners - all three are
    asked for again here.
    """
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_APPWINDOW)
    round_corners(hwnd)
    try:
        dwmapi = ctypes.WinDLL("dwmapi")
    except OSError:
        return
    # One pixel of frame is enough for DWM to draw the border and shadow that
    # tell the panel apart from whatever is behind it.
    dwmapi.DwmExtendFrameIntoClientArea(wintypes.HWND(hwnd),
                                        ctypes.byref(MARGINS(0, 0, 1, 0)))


def round_corners(hwnd):
    """Windows 11 rounded corners, for a window that is not getting them."""
    try:
        dwmapi = ctypes.WinDLL("dwmapi")
    except OSError:
        return
    preference = ctypes.c_int(DWMWCP_ROUND)
    dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd),
                                 wintypes.DWORD(DWMWA_WINDOW_CORNER_PREFERENCE),
                                 ctypes.byref(preference),
                                 ctypes.sizeof(preference))


def allow_dark_menus():
    """Put this process in uxtheme's dark mode, so menus come up dark.

    SetPreferredAppMode has no header and no name in uxtheme's export table -
    it is ordinal 135 - but it is what every dark Win32 app calls and has been
    there since Windows 10 1809, which is why the build is checked first. The
    worst case if Microsoft ever moves it is a light frame around our dark
    menu items, so failure is quietly acceptable here.
    """
    try:
        if sys.getwindowsversion().build < 17763:
            return
        uxtheme = ctypes.WinDLL("uxtheme")
        set_preferred_app_mode = uxtheme[135]
        set_preferred_app_mode.argtypes = [ctypes.c_int]
        set_preferred_app_mode.restype = ctypes.c_int
        set_preferred_app_mode(2)               # ForceDark
        uxtheme[136]()                          # FlushMenuThemes
    except Exception:
        pass


def minimise(hwnd):
    """Tk refuses to iconify an override-redirect window; Windows does not."""
    user32.ShowWindow(hwnd, SW_MINIMIZE)


def system_dpi():
    try:
        return int(user32.GetDpiForSystem())
    except AttributeError:
        return 96


def primary_work_area():
    """Work area of the primary monitor (taskbar excluded), in physical pixels."""
    mon = user32.MonitorFromPoint(wintypes.POINT(0, 0), MONITOR_DEFAULTTOPRIMARY)
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if mon and user32.GetMonitorInfoW(mon, ctypes.byref(info)):
        r = info.rcWork
        return r.left, r.top, r.right, r.bottom
    return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def message_loop():
    """Standard blocking pump. Returns when WM_QUIT arrives. Costs zero CPU idle."""
    msg = wintypes.MSG()
    while True:
        got = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if got in (0, -1):
            return
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
