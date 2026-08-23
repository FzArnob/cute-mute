"""Run-at-login via the per-user Run key (no admin rights, no scheduled task)."""
import os
import sys
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "CuteMute"


def launch_parts(tray=True):
    """(program, arguments) that start CuteMute without a console window.

    The Run key and the Start menu shortcut want the same two strings, and they
    differ in one thing only: logging in is not a request to see the settings,
    so that one gets --tray and the shortcut you clicked does not.
    """
    flag = " --tray" if tray else ""
    if getattr(sys, "frozen", False):
        return sys.executable, flag.lstrip()
    interpreter = sys.executable
    windowed = os.path.join(os.path.dirname(interpreter), "pythonw.exe")
    if os.path.exists(windowed):
        interpreter = windowed
    entry = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "CuteMute.pyw")
    return interpreter, '"%s"%s' % (entry, flag)


def launch_command():
    """One command line for the per-user Run key."""
    program, arguments = launch_parts()
    return '"%s" %s' % (program, arguments) if arguments else '"%s"' % program


def is_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return bool(value)
    except OSError:
        return False


def set_enabled(enabled):
    """Returns True on success. Never raises: this is a nice-to-have."""
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                                winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ,
                                  launch_command())
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False
