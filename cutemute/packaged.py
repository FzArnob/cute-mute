"""Am I running from an MSIX package, and what changes if I am.

The Store build is this same code in a different container. Three things that
are right for a loose exe are wrong inside a package -- and all three are things
the package already does for itself:

    Start menu entry        the manifest declares it
    Installed apps entry    Windows generates it, and MSIX uninstalls cleanly
    run-at-login            the Run key is virtualised inside a package, so
                            writing it silently does nothing. `windows.startupTask`
                            in the manifest is the supported route, and it puts
                            the switch in Settings > Apps > Startup, where
                            Windows -- not this app -- owns it

So ask once, and skip all three when the answer is yes. Nothing here changes
what CuteMute does; it only stops it writing to places a package cannot reach,
which would otherwise fail silently and look like a bug in the mute key.
"""
import ctypes
from ctypes import byref, create_unicode_buffer, wintypes
from functools import lru_cache

# GetCurrentPackageFamilyName's way of saying "you are not in a package". Not an
# error: it is the answer to the question.
APPMODEL_ERROR_NO_PACKAGE = 15700

STARTUP_SETTINGS = "ms-settings:startupapps"

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


@lru_cache(maxsize=1)
def family_name():
    """The package family name, or None when running as a plain exe."""
    try:
        query = kernel32.GetCurrentPackageFamilyName
    except AttributeError:
        return None                 # older than Windows 8: no packages at all
    query.argtypes = [ctypes.POINTER(wintypes.UINT), wintypes.LPWSTR]
    query.restype = wintypes.LONG

    length = wintypes.UINT(0)
    # First call sizes the buffer. Unpackaged, it answers NO_PACKAGE instead.
    if query(byref(length), None) == APPMODEL_ERROR_NO_PACKAGE:
        return None
    if not length.value:
        return None
    buffer = create_unicode_buffer(length.value)
    if query(byref(length), buffer) != 0:
        return None
    return buffer.value or None


def is_packaged():
    """True inside an MSIX package -- a Store install, or a sideloaded one."""
    return family_name() is not None


def open_startup_settings():
    """Show Settings > Apps > Startup, where a packaged app's switch lives.

    Returns True if the shell took the request. Never raises: failing to open
    a settings page is not worth an exception in a tray app.
    """
    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "open", STARTUP_SETTINGS, None, None, 1)  # SW_SHOWNORMAL
        return int(result) > 32          # ShellExecute's idea of success
    except Exception:
        return False
