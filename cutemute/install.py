"""Making CuteMute something Windows has heard of.

A single exe copied onto a machine is, as far as the shell is concerned, an
anonymous blob: Start cannot find it, Search cannot find it, Win+R does not know
the name, and Settings has never heard of it. None of that needs an installer -
the places the shell actually looks are one shortcut and two registry keys, all
per-user, all writable without admin rights - so CuteMute puts itself there the
first time it runs, and takes it all back with --uninstall.

What this cannot do is stop SmartScreen calling the file unknown. That is a
question about who signed the exe, not about where it is registered, and the
only answer is an Authenticode certificate.

Registration is cheap (a few milliseconds) and idempotent: it rewrites the
entries only when the exe has moved or the version has changed, so a normal
start does two stat calls and nothing else.
"""
import ctypes
import os
import sys
import time
import winreg
from ctypes import POINTER, byref, c_int, c_void_p, c_wchar_p, wintypes

from . import (APP_NAME, DESCRIPTION, PUBLISHER, TAGLINE, __version__, config,
               packaged, startup)
from .w32 import (CLSCTX_INPROC_SERVER, COINIT_APARTMENTTHREADED, GUID,
                  com_call, com_release, ole32)

CLSID_ShellLink = "{00021401-0000-0000-C000-000000000046}"
IID_IShellLinkW = "{000214F9-0000-0000-C000-000000000046}"
IID_IPersistFile = "{0000010B-0000-0000-C000-000000000046}"

# IShellLinkW vtable slots; IUnknown occupies 0..2 in every interface.
QUERY_INTERFACE = 0
LINK_SETDESCRIPTION = 7
LINK_SETWORKINGDIRECTORY = 9
LINK_SETARGUMENTS = 11
LINK_SETICONLOCATION = 17
LINK_SETPATH = 20
PERSIST_SAVE = 6

APP_PATHS_KEY = (r"Software\Microsoft\Windows\CurrentVersion\App Paths"
                 r"\%s.exe" % APP_NAME)
UNINSTALL_KEY = (r"Software\Microsoft\Windows\CurrentVersion\Uninstall\%s"
                 % APP_NAME)


def start_menu_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Microsoft", "Windows", "Start Menu", "Programs")


def shortcut_path():
    """Where Start and Search look. A .lnk here needs no admin rights."""
    return os.path.join(start_menu_dir(), "%s.lnk" % APP_NAME)


def icon_path(program):
    """The exe carries its own icon; from a source tree, use the built .ico."""
    if getattr(sys, "frozen", False):
        return program
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ico = os.path.join(here, "%s.ico" % APP_NAME)
    return ico if os.path.exists(ico) else program


# -- the shortcut ----------------------------------------------------------
def _write_shortcut(path, program, arguments, icon):
    """Write a .lnk. IShellLink is the only supported way to make one."""
    ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    link = c_void_p()
    try:
        ole32.CoCreateInstance(byref(GUID(CLSID_ShellLink)), None,
                               CLSCTX_INPROC_SERVER,
                               byref(GUID(IID_IShellLinkW)), byref(link))
        com_call(link, LINK_SETPATH, c_wchar_p)(link, program)
        if arguments:
            com_call(link, LINK_SETARGUMENTS, c_wchar_p)(link, arguments)
        com_call(link, LINK_SETDESCRIPTION, c_wchar_p)(link, TAGLINE)
        com_call(link, LINK_SETWORKINGDIRECTORY, c_wchar_p)(
            link, os.path.dirname(program))
        com_call(link, LINK_SETICONLOCATION, c_wchar_p, c_int)(link, icon, 0)

        persist = c_void_p()
        com_call(link, QUERY_INTERFACE, POINTER(GUID), POINTER(c_void_p))(
            link, byref(GUID(IID_IPersistFile)), byref(persist))
        try:
            com_call(persist, PERSIST_SAVE, c_wchar_p, wintypes.BOOL)(
                persist, path, True)
        finally:
            com_release(persist)
    finally:
        com_release(link)
        ole32.CoUninitialize()


# -- the registry ----------------------------------------------------------
def _write_values(key_path, values):
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0,
                            winreg.KEY_SET_VALUE) as key:
        for name, value in values:
            kind = winreg.REG_DWORD if isinstance(value, int) else winreg.REG_SZ
            winreg.SetValueEx(key, name, 0, kind, value)


def _read_value(key_path, name):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def _delete_key(key_path):
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
        return True
    except OSError:
        return False


def _app_paths(program):
    """Teaches Win+R and the shell the bare name 'CuteMute'."""
    _write_values(APP_PATHS_KEY, [("", program),
                                  ("Path", os.path.dirname(program))])


def _installed_apps(program):
    """The Settings > Apps entry: a name, a publisher and a way back out.

    Portable software is normally invisible here, which is exactly what makes
    it look untrustworthy. The uninstall entry points back at the exe, and
    removes what CuteMute wrote rather than the exe itself, since a running
    program cannot delete its own file.
    """
    try:
        size = os.path.getsize(program) // 1024
    except OSError:
        size = 0
    _write_values(UNINSTALL_KEY, [
        ("DisplayName", APP_NAME),
        ("DisplayVersion", __version__),
        ("Publisher", PUBLISHER),
        ("DisplayIcon", program),
        ("InstallLocation", os.path.dirname(program)),
        ("UninstallString", '"%s" --uninstall' % program),
        ("Comments", DESCRIPTION),
        ("InstallDate", time.strftime("%Y%m%d")),
        ("EstimatedSize", size),
        ("NoModify", 1),
        ("NoRepair", 1),
    ])


# -- public API ------------------------------------------------------------
def is_registered():
    return os.path.exists(shortcut_path())


def _up_to_date(program):
    if not os.path.exists(shortcut_path()):
        return False
    if not getattr(sys, "frozen", False):
        return True         # a source tree gets the shortcut and nothing else
    return (_read_value(UNINSTALL_KEY, "DisplayIcon") == program
            and _read_value(UNINSTALL_KEY, "DisplayVersion") == __version__)


def register():
    """Put CuteMute where the shell looks. Returns True if anything changed.

    Never raises: being missing from Start is a blemish, not a reason to refuse
    to mute a microphone.
    """
    if packaged.is_packaged():
        # The manifest already declares every one of these, and a package
        # cannot write outside itself anyway. Uninstall is the Store's job.
        return False
    try:
        program, arguments = startup.launch_parts(tray=False)
        if _up_to_date(program):
            return False
        os.makedirs(start_menu_dir(), exist_ok=True)
        _write_shortcut(shortcut_path(), program, arguments,
                        icon_path(program))
        if getattr(sys, "frozen", False):
            # Only the exe is a thing you can install; a checkout is not.
            _app_paths(program)
            _installed_apps(program)
        return True
    except Exception as exc:
        print("CuteMute: could not register with the shell: %s" % exc,
              file=sys.stderr)
        return False


def unregister():
    """Undo register(), the run-at-login entry and the saved settings.

    Returns the list of things actually removed, so the caller can say so.
    """
    removed = []
    try:
        if os.path.exists(shortcut_path()):
            os.remove(shortcut_path())
            removed.append("Start menu entry")
    except OSError:
        pass
    if _delete_key(APP_PATHS_KEY):
        removed.append("Win+R name")
    if _delete_key(UNINSTALL_KEY):
        removed.append("Installed apps entry")
    if startup.is_enabled() and startup.set_enabled(False):
        removed.append("run-at-login entry")
    try:
        if os.path.exists(config.config_path()):
            os.remove(config.config_path())
            removed.append("saved settings")
        os.rmdir(config.config_dir())
    except OSError:
        pass
    return removed
