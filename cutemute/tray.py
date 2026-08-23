"""Tray icon: the only always-visible sign the app is alive, plus its menu.

Lives on the same Win32 UI thread as the overlay, sharing one message pump.
Deliberately not on the hook thread: TrackPopupMenu blocks while the menu is
open, and a blocked low-level keyboard hook gets torn down by Windows.
"""
import ctypes
import threading
from ctypes import byref, wintypes

from .w32 import (MF_CHECKED, MF_SEPARATOR, MF_STRING, MF_UNCHECKED, NIF_ICON,
                  NIF_MESSAGE, NIF_TIP, NIM_ADD, NIM_DELETE, NIM_MODIFY,
                  NOTIFYICONDATAW, SM_CXSMICON, TPM_RETURNCMD, TPM_RIGHTBUTTON,
                  WM_APP, WM_COMMAND, WM_LBUTTONDBLCLK, WM_LBUTTONUP, WM_NULL,
                  WM_RBUTTONUP, WNDCLASSEXW, WNDPROC, kernel32, shell32, user32)
from .winicon import destroy_hicon, make_hicon

CLASS_NAME = "CuteMuteTray"
WINDOW_TITLE = "CuteMute"

WM_TRAY_CALLBACK = WM_APP + 20
WM_TRAY_STATE = WM_APP + 21

ID_TOGGLE = 1001
ID_SETTINGS = 1002
ID_STARTUP = 1003
ID_EXIT = 1004

ICON_UID = 1


class Tray:
    def __init__(self, cfg, on_command, hotkey_text=lambda: ""):
        self._cfg = cfg
        self._on_command = on_command
        self._hotkey_text = hotkey_text
        self._lock = threading.Lock()
        self.hwnd = None
        self._icons = {}
        self._muted = False
        self._added = False
        self._proc = WNDPROC(self._wnd_proc)
        self._class_registered = False
        self._taskbar_created_msg = user32.RegisterWindowMessageW("TaskbarCreated")
        self.show_settings_msg = user32.RegisterWindowMessageW(
            "CuteMute.ShowSettings")

    # -- called from any thread --------------------------------------------
    def set_muted(self, muted):
        with self._lock:
            self._muted = bool(muted)
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_TRAY_STATE, 1 if muted else 0, 0)

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
            if err != 1410:
                raise ctypes.WinError(err)
        self._class_registered = True

        # Message-only owner window: never shown, just a target for callbacks.
        self.hwnd = user32.CreateWindowExW(0, CLASS_NAME, WINDOW_TITLE, 0,
                                          0, 0, 0, 0, None, None, hinstance, None)
        if not self.hwnd:
            raise ctypes.WinError(ctypes.get_last_error())

        small = user32.GetSystemMetrics(SM_CXSMICON) or 16
        for state in (False, True):
            self._icons[state] = make_hicon(small, state)
        self._add()

    def destroy(self):
        if self._added and self.hwnd:
            data = self._notify_data(NIF_ICON)
            shell32.Shell_NotifyIconW(NIM_DELETE, byref(data))
            self._added = False
        for handle in self._icons.values():
            destroy_hicon(handle)
        self._icons.clear()
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
        if self._class_registered:
            user32.UnregisterClassW(CLASS_NAME, kernel32.GetModuleHandleW(None))
            self._class_registered = False

    # -- internals ---------------------------------------------------------
    def _tooltip(self):
        with self._lock:
            muted = self._muted
        chord = self._hotkey_text()
        state = "Microphone muted" if muted else "Microphone live"
        return "CuteMute - %s%s" % (state, ("\n%s to toggle" % chord) if chord else "")

    def _notify_data(self, flags):
        data = NOTIFYICONDATAW()
        data.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        data.hWnd = self.hwnd
        data.uID = ICON_UID
        data.uFlags = flags
        if flags & NIF_MESSAGE:
            data.uCallbackMessage = WM_TRAY_CALLBACK
        if flags & NIF_ICON:
            with self._lock:
                muted = self._muted
            data.hIcon = self._icons.get(muted) or 0
        if flags & NIF_TIP:
            data.szTip = self._tooltip()[:127]
        return data

    def _add(self):
        data = self._notify_data(NIF_ICON | NIF_MESSAGE | NIF_TIP)
        self._added = bool(shell32.Shell_NotifyIconW(NIM_ADD, byref(data)))

    def _refresh(self):
        if not self._added:
            self._add()
            return
        data = self._notify_data(NIF_ICON | NIF_TIP)
        if not shell32.Shell_NotifyIconW(NIM_MODIFY, byref(data)):
            self._added = False
            self._add()

    def _popup(self):
        with self._lock:
            muted = self._muted
        menu = user32.CreatePopupMenu()
        if not menu:
            return
        try:
            chord = self._hotkey_text()
            label = "Unmute microphone" if muted else "Mute microphone"
            if chord:
                label = "%s\t%s" % (label, chord)
            user32.AppendMenuW(menu, MF_STRING, ID_TOGGLE, label)
            user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(menu, MF_STRING, ID_SETTINGS, "Settings...")
            user32.AppendMenuW(
                menu, MF_STRING | (MF_CHECKED if self._cfg.get("start_with_windows")
                                   else MF_UNCHECKED),
                ID_STARTUP, "Start with Windows")
            user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(menu, MF_STRING, ID_EXIT, "Exit CuteMute")

            point = wintypes.POINT()
            user32.GetCursorPos(byref(point))
            # Required so the menu dismisses properly when focus moves away.
            user32.SetForegroundWindow(self.hwnd)
            choice = user32.TrackPopupMenu(
                menu, TPM_RIGHTBUTTON | TPM_RETURNCMD, point.x, point.y, 0,
                self.hwnd, None)
            user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        finally:
            user32.DestroyMenu(menu)

        if choice == ID_TOGGLE:
            self._on_command("toggle")
        elif choice == ID_SETTINGS:
            self._on_command("settings")
        elif choice == ID_STARTUP:
            self._on_command("startup")
        elif choice == ID_EXIT:
            self._on_command("exit")

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_TRAY_CALLBACK:
                event = lparam & 0xFFFF
                if event in (WM_RBUTTONUP,):
                    self._popup()
                elif event == WM_LBUTTONUP:
                    self._on_command("toggle")
                elif event == WM_LBUTTONDBLCLK:
                    self._on_command("settings")
                return 0
            if msg == WM_TRAY_STATE:
                self._refresh()
                return 0
            if msg == WM_COMMAND:
                return 0
            if msg == self._taskbar_created_msg:
                self._added = False      # explorer restarted; re-add the icon
                self._add()
                return 0
            if msg == self.show_settings_msg:
                self._on_command("settings")
                return 0
        except Exception:
            pass
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
