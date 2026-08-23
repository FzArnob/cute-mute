"""The Win32 UI thread: one message pump shared by the overlay and the tray."""
import threading

from .overlay import Overlay
from .tray import Tray
from .w32 import WM_QUIT, kernel32, message_loop, user32


class WinUI(threading.Thread):
    def __init__(self, cfg, on_command, hotkey_text=lambda: ""):
        super().__init__(name="CuteMute-winui", daemon=True)
        self.overlay = Overlay(cfg)
        self.tray = Tray(cfg, on_command, hotkey_text)
        self.ready = threading.Event()
        self.failure = None
        self._thread_id = None

    # -- called from any thread --------------------------------------------
    def set_muted(self, muted):
        self.overlay.set_visible(muted)
        self.tray.set_muted(muted)

    def apply(self, cfg):
        self.overlay.apply(cfg)
        # Re-push the state so the tray tooltip picks up a changed hotkey too.
        self.tray.set_muted(self.overlay.wants_visible)

    def stop(self):
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)

    # -- worker ------------------------------------------------------------
    def run(self):
        self._thread_id = kernel32.GetCurrentThreadId()
        try:
            self.overlay.create()
            self.tray.create()
        except Exception as exc:
            self.failure = str(exc)
            self.ready.set()
            return
        self.ready.set()
        try:
            message_loop()
        finally:
            self.tray.destroy()
            self.overlay.destroy()
