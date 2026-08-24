"""CuteMute: wiring, lifecycle and the main thread.

Four threads, all of them blocked on something the kernel wakes them for, so an
idle CuteMute costs no measurable CPU:

  main         waits on a queue; builds a Tk window when asked to, and is
               asked to as soon as CuteMute starts unless --tray says not to
  CuteMute-winui   one Win32 message pump for the badge and the tray icon
  CuteMute-hotkey  the low-level keyboard hook, kept deliberately empty
  CuteMute-audio   owns the COM apartment and does all mute work

The realtime path is short on purpose: hook callback -> queue.put -> audio
thread sets mute. Nothing in it waits on the GUI, and the badge is updated
afterwards, so a slow driver or a busy desktop can never delay the keystroke.
"""
import argparse
import ctypes
import queue
import sys
import threading
from pathlib import Path

from . import (APP_NAME, PUBLISHER, __version__, config, install, keys,
               packaged, startup)
from .audio import AudioService, COINIT_MULTITHREADED, MicMute
from .hotkey import HotkeyListener
from .settings_ui import SettingsWindow
from .tray import CLASS_NAME as TRAY_CLASS
from .w32 import (ERROR_ALREADY_EXISTS, IDYES, MB_ICONINFORMATION,
                  MB_ICONQUESTION, MB_OK, MB_SETFOREGROUND, MB_YESNO,
                  kernel32, ole32, set_dpi_awareness, user32)
from .winui import WinUI

MUTEX_NAME = "Local\\CuteMute-single-instance"


class SingleInstance:
    """A named mutex: cheap, released by the kernel even if we are killed."""

    def __init__(self):
        self.handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        self.already_running = (ctypes.get_last_error() == ERROR_ALREADY_EXISTS)

    def release(self):
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None


def _poke_existing_instance():
    """Ask the running copy to show its window, then step aside."""
    hwnd = user32.FindWindowW(TRAY_CLASS, None)
    if hwnd:
        msg = user32.RegisterWindowMessageW("CuteMute.ShowSettings")
        user32.PostMessageW(hwnd, msg, 0, 0)
        return True
    return False


def _uninstall():
    """--uninstall: take back everything install.register() did, then exit.

    This is what Settings > Apps runs, and a windowed exe has nowhere to print,
    so the question and the answer are both message boxes.
    """
    question = (
        "Remove %s's Start menu entry, its Win+R name, its Installed apps "
        "entry, its run-at-login entry and its saved settings?\n\n"
        "The program file itself stays where it is - delete\n%s\nyourself if "
        "you no longer want it." % (APP_NAME, sys.executable))
    if user32.MessageBoxW(None, question, "Uninstall %s" % APP_NAME,
                          MB_YESNO | MB_ICONQUESTION
                          | MB_SETFOREGROUND) != IDYES:
        return 0

    removed = install.unregister()
    if removed:
        told = "Removed:\n\n" + "\n".join("    \u2022 %s" % item
                                           for item in removed)
    else:
        told = "There was nothing left to remove."
    if user32.FindWindowW(TRAY_CLASS, None):
        told += ("\n\n%s is still running: right-click its tray icon and "
                 "choose Exit %s." % (APP_NAME, APP_NAME))
    user32.MessageBoxW(None, told, "Uninstall %s" % APP_NAME,
                       MB_OK | MB_ICONINFORMATION | MB_SETFOREGROUND)
    return 0


def _one_shot_toggle():
    """--toggle: flip the mute state and exit, for external key bindings."""
    ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
    mic = MicMute(config.load()["audio"]["mute_all_inputs"])
    try:
        mic.open()
        state = mic.get_mute()
        if state is None:
            print("CuteMute: no microphone available", file=sys.stderr)
            return 1
        mic.set_mute(not state)
        print("microphone %s" % ("muted" if not state else "live"))
        return 0
    finally:
        mic.close()
        ole32.CoUninitialize()


class App:
    def __init__(self, selftest=False):
        self.cfg = config.load()
        self.selftest = selftest
        self._mainq = queue.Queue()
        self._settings_hwnd = None
        self._settings_open = threading.Event()
        self._closing = threading.Event()
        self._muted = False
        self._first_state = True

        self.audio = AudioService(self.cfg, on_state=self._on_state,
                                  on_error=self._on_audio_error)
        self.winui = WinUI(self.cfg, on_command=self._on_command,
                           hotkey_text=self._hotkey_text)
        self.hotkey = HotkeyListener(
            on_trigger=self.audio.request_toggle,
            vk=self.cfg["hotkey"]["vk"],
            mods=self.cfg["hotkey"]["mods"],
            suppress=self.cfg["hotkey"]["suppress"])

    # -- helpers -----------------------------------------------------------
    def _hotkey_text(self):
        return keys.chord_text(self.cfg["hotkey"]["vk"], self.cfg["hotkey"]["mods"])

    def _on_audio_error(self, message):
        print("CuteMute (audio): %s" % message, file=sys.stderr)

    def _on_state(self, muted):
        """Called on the audio thread once the endpoint really changed."""
        self._muted = bool(muted)
        self.winui.set_muted(self._muted)
        if self._first_state:
            self._first_state = False
        elif self.cfg["feedback"]["sound"]:
            threading.Thread(target=_beep, args=(self._muted,),
                             daemon=True).start()

    def _on_command(self, command):
        """Tray menu, from the Win32 UI thread."""
        if command == "toggle":
            self.audio.request_toggle()
        elif command == "settings":
            self.request_settings()
        elif command == "startup":
            if startup.managed_by_windows():
                packaged.open_startup_settings()
                return
            wanted = not self.cfg["start_with_windows"]
            if startup.set_enabled(wanted):
                self.cfg["start_with_windows"] = wanted
                config.save(self.cfg)
        elif command == "exit":
            self.quit()

    def request_settings(self):
        if self._settings_open.is_set():
            if self._settings_hwnd:
                user32.SetForegroundWindow(self._settings_hwnd)
            return
        self._mainq.put(("settings",))

    def quit(self):
        self._closing.set()
        self._mainq.put(None)

    # -- settings ----------------------------------------------------------
    def _remember_settings_hwnd(self, hwnd):
        self._settings_hwnd = hwnd
        if hwnd:
            self._settings_open.set()
        else:
            self._settings_open.clear()

    def _open_settings(self):
        window = SettingsWindow(self.cfg, self.hotkey, self._apply,
                                on_hwnd=self._remember_settings_hwnd)
        window.should_close = self._closing.is_set
        try:
            window.run()
        except Exception as exc:
            print("CuteMute (settings): %s" % exc, file=sys.stderr)
        finally:
            self._remember_settings_hwnd(None)

    def _apply(self, updates):
        """Take a settings dict, persist it, and push it into everything live.

        Called on every change now that the settings window saves as you touch
        it, so it does no work it does not have to: the registry is only written
        when the run-at-login flag actually moved.
        """
        was_startup = bool(self.cfg.get("start_with_windows"))
        saved = config.save(updates)
        # Mutate in place: the tray holds a reference to this same dict.
        self.cfg.clear()
        self.cfg.update(saved)
        self.hotkey.set_hotkey(saved["hotkey"]["vk"], saved["hotkey"]["mods"],
                               saved["hotkey"]["suppress"])
        self.audio.set_options(saved["audio"]["mute_all_inputs"])
        self.winui.apply(self.cfg)
        if saved["start_with_windows"] != was_startup:
            startup.set_enabled(saved["start_with_windows"])

    # -- run ---------------------------------------------------------------
    def run(self):
        set_dpi_awareness()
        if not self.selftest:
            # Cheap and idempotent: it writes something only on the first
            # run, or after the exe has moved or been replaced.
            install.register()

        self.audio.start()
        self.winui.start()
        self.winui.ready.wait(5.0)
        if self.winui.failure:
            print("CuteMute: could not create the tray/badge windows: %s"
                  % self.winui.failure, file=sys.stderr)
            return 1

        self.hotkey.start()
        self.hotkey.ready.wait(5.0)
        if self.hotkey.failure:
            print("CuteMute: %s\nThe tray menu still works."
                  % self.hotkey.failure, file=sys.stderr)

        if self.selftest:
            threading.Thread(target=self._selftest, daemon=True).start()

        try:
            while True:
                item = self._mainq.get()
                if item is None:
                    break
                if item[0] == "settings":
                    self._open_settings()
        except KeyboardInterrupt:
            pass
        finally:
            self._closing.set()
            self.hotkey.stop()
            self.winui.stop()
            self.audio.stop()
            self.winui.join(2.0)
        return 0

    def _selftest(self):
        import time
        print("%s %s self-test" % (APP_NAME, __version__))
        print("  hotkey        : %s (suppress=%s)"
              % (self._hotkey_text(), self.cfg["hotkey"]["suppress"]))
        print("  hook          : %s"
              % ("failed: %s" % self.hotkey.failure if self.hotkey.failure
                 else "installed"))
        print("  tray + badge  : created")
        print("  badge         : %dpx %s, margin %d, opacity %d%%"
              % (self.cfg["overlay"]["size"], self.cfg["overlay"]["corner"],
                 self.cfg["overlay"]["margin"], self.cfg["overlay"]["opacity"]))
        print("  config        : %s" % config.config_path())
        print("  publisher     : %s" % PUBLISHER)
        print("  start menu    : %s"
              % ("registered" if install.is_registered()
                 else "not registered"))
        print("  mic muted     : %s" % self._muted)
        print("showing the badge for 3s without touching the mic...")
        self.winui.set_muted(True)
        time.sleep(3.0)
        self.winui.set_muted(self._muted)
        time.sleep(0.3)
        print("self-test done")
        self.quit()


def _beep(muted):
    try:
        import winsound
        winsound.Beep(620 if muted else 980, 70)
    except Exception:
        pass


STARTUP_COPY = "cutemutetray"


def _launched_as_startup_copy():
    """True when this process is the package's CuteMuteTray.exe.

    See the windows.startupTask extension in packaging/msix/AppxManifest.xml.
    A no-op for the loose exe, which is never named that.
    """
    try:
        return Path(sys.executable).stem.lower() == STARTUP_COPY
    except Exception:
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="CuteMute",
        description="Mute your microphone with one keypress, with an "
                    "always-on-top badge while muted.")
    parser.add_argument("--tray", action="store_true",
                        help="start straight into the tray, without the window "
                             "(this is what the run-at-login entry uses)")
    parser.add_argument("--toggle", action="store_true",
                        help="toggle mute once and exit (no tray icon)")
    parser.add_argument("--uninstall", action="store_true",
                        help="remove the Start menu, Win+R, Installed "
                             "apps and run-at-login entries, and the "
                             "saved settings")
    parser.add_argument("--selftest", action="store_true",
                        help="start up, report diagnostics, show the badge, exit")
    parser.add_argument("--version", action="version",
                        version="%s %s" % (APP_NAME, __version__))
    args = parser.parse_args(argv)

    # The MSIX startup task cannot pass arguments, so the packaged build ships a
    # second copy of this same binary under another name and lets the filename
    # carry the intent. Logging in is not a request to see the settings window.
    if not args.tray and _launched_as_startup_copy():
        args.tray = True

    if args.uninstall:
        return _uninstall()

    if args.toggle:
        return _one_shot_toggle()

    instance = SingleInstance()
    if instance.already_running:
        instance.release()
        if not _poke_existing_instance():
            print("CuteMute is already running.", file=sys.stderr)
        return 0

    try:
        app = App(selftest=args.selftest)
        # Running CuteMute means showing it; closing the window leaves it in
        # the tray. Only --tray (and a self-test) start out of sight.
        if not args.tray and not args.selftest:
            app.request_settings()
        return app.run()
    finally:
        instance.release()
