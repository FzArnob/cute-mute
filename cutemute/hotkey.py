"""Global hotkey via a low-level keyboard hook.

Why a hook rather than RegisterHotKey: RegisterHotKey always eats the key, so a
bare Tab would stop working everywhere. A WH_KEYBOARD_LL hook lets us watch for
the chord and still pass it through, with swallowing as an opt-in.

The hook lives on its own thread whose only job is pumping messages, and the
callback does nothing but compare a few integers and drop a request into a
queue. That matters: if a low-level hook takes longer than
LowLevelHooksTimeout (300 ms by default) Windows silently unhooks it.
"""
import ctypes
import threading

from . import keys
from .w32 import (HOOKPROC, KBDLLHOOKSTRUCT, WH_KEYBOARD_LL, WM_KEYDOWN,
                  WM_KEYUP, WM_QUIT, WM_SYSKEYDOWN, WM_SYSKEYUP, kernel32,
                  message_loop, user32)

_DOWN = (WM_KEYDOWN, WM_SYSKEYDOWN)
_UP = (WM_KEYUP, WM_SYSKEYUP)


class HotkeyListener(threading.Thread):
    """Watches for one chord; can also capture the next chord for the UI."""

    def __init__(self, on_trigger, vk=keys.VK_TAB, mods=(), suppress=False):
        super().__init__(name="CuteMute-hotkey", daemon=True)
        self._on_trigger = on_trigger
        self._lock = threading.Lock()
        self._vk = vk
        self._mods = frozenset(mods)
        self._suppress = bool(suppress)
        self._capture_cb = None
        self._latched = False       # armed-state, so auto-repeat fires once
        self._swallow_up = set()
        self._thread_id = None
        self._hook = None
        self._proc = HOOKPROC(self._hook_proc)   # must outlive the hook
        self.ready = threading.Event()
        self.failure = None

    # -- public API (thread-safe) -----------------------------------------
    def set_hotkey(self, vk, mods, suppress):
        with self._lock:
            self._vk = int(vk)
            self._mods = frozenset(mods or ())
            self._suppress = bool(suppress)
            self._latched = False

    def capture_next(self, callback):
        """Report the next real chord to `callback` instead of toggling."""
        with self._lock:
            self._capture_cb = callback

    def cancel_capture(self):
        with self._lock:
            self._capture_cb = None

    def stop(self):
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)

    # -- worker ------------------------------------------------------------
    def run(self):
        self._thread_id = kernel32.GetCurrentThreadId()
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, None, 0)
        if not self._hook:
            self.failure = "SetWindowsHookEx failed (error %d)" % (
                ctypes.get_last_error(),)
            self.ready.set()
            return
        self.ready.set()
        message_loop()
        user32.UnhookWindowsHookEx(self._hook)
        self._hook = None

    def _hook_proc(self, code, wparam, lparam):
        try:
            if code == 0 and self._interested(wparam, lparam):
                return 1
        except Exception:
            pass    # never let a Python error break the whole keyboard
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def _interested(self, wparam, lparam):
        """Return True to swallow the keystroke."""
        info = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        vk = info.vkCode
        down = wparam in _DOWN
        if not down and wparam not in _UP:
            return False

        with self._lock:
            capture_cb = self._capture_cb
            want_vk, want_mods, suppress = self._vk, self._mods, self._suppress

            if not down:
                # Clear the latch even when swallowing the key-up, otherwise a
                # suppressed hotkey would stay latched and only ever fire once.
                swallow = vk in self._swallow_up
                self._swallow_up.discard(vk)
                if vk == want_vk:
                    self._latched = False
                return swallow

            if capture_cb is not None:
                if vk in keys.MODIFIER_VKS:
                    return False              # wait for a real trigger key
                self._capture_cb = None
                self._swallow_up.add(vk)
                mods = () if vk == keys.VK_ESCAPE else tuple(
                    sorted(keys.held_modifiers(exclude_vk=vk)))
                cancelled = vk == keys.VK_ESCAPE
                # Swallow the capture keystroke so it cannot leak into the UI.
                threading.Thread(target=capture_cb, args=(vk, mods, cancelled),
                                 daemon=True).start()
                return True

            if vk != want_vk or self._latched:
                return suppress and vk == want_vk
            if keys.held_modifiers(exclude_vk=vk) != set(want_mods):
                return False
            self._latched = True
            if suppress:
                self._swallow_up.add(vk)

        self._on_trigger()      # queue push only; never blocks the hook
        return suppress
