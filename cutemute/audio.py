"""Microphone mute via Core Audio (IAudioEndpointVolume), driven by raw ctypes.

We call the COM vtables directly rather than pulling in pycaw/comtypes: it is
about eighty lines, has no packaging quirks when frozen, and keeps the toggle
path down to a couple of virtual calls.

All of this runs on one dedicated thread that owns its own COM apartment; the
keyboard hook only ever drops a request into a queue, so a slow audio driver can
never stall keyboard input.
"""
import ctypes
import queue
import threading
from ctypes import POINTER, byref, c_uint, c_void_p, c_wchar_p
from ctypes import wintypes

from .w32 import GUID, ole32

CLSID_MMDeviceEnumerator = "{BCDE0395-E52F-467C-8E3D-C4579291692E}"
IID_IMMDeviceEnumerator = "{A95664D2-9614-4F35-A746-DE8DB63617E6}"
IID_IAudioEndpointVolume = "{5CDF2C82-841E-4546-9722-0CF74078229A}"

CLSCTX_ALL = 0x17
COINIT_MULTITHREADED = 0x0

E_CAPTURE = 1
ROLE_CONSOLE = 0
ROLE_COMMUNICATIONS = 2
DEVICE_STATE_ACTIVE = 0x1

# vtable slots (IUnknown occupies 0..2 in every interface)
RELEASE = 2
ENUM_ENUMAUDIOENDPOINTS = 3
ENUM_GETDEFAULTENDPOINT = 4
COLL_GETCOUNT = 3
COLL_ITEM = 4
DEV_ACTIVATE = 3
DEV_GETID = 5
VOL_SETMUTE = 14
VOL_GETMUTE = 15


def _call(ptr, slot, *argtypes):
    """Bind vtable[slot] of a COM interface pointer as a callable."""
    vtable = ctypes.cast(ptr, POINTER(POINTER(c_void_p))).contents
    proto = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, *argtypes)
    return proto(vtable[slot])


def _release(ptr):
    if ptr and ptr.value:
        ctypes.WINFUNCTYPE(ctypes.c_ulong, c_void_p)(
            ctypes.cast(ptr, POINTER(POINTER(c_void_p))).contents[RELEASE])(ptr)
        ptr.value = None


class MicMute:
    """Mute/unmute capture endpoints. Use from a single COM-initialised thread."""

    def __init__(self, mute_all_inputs=False):
        self.mute_all_inputs = bool(mute_all_inputs)
        self._enumerator = None
        self._volumes = {}      # device id -> IAudioEndpointVolume*

    # -- lifecycle ---------------------------------------------------------
    def open(self):
        ptr = c_void_p()
        ole32.CoCreateInstance(byref(GUID(CLSID_MMDeviceEnumerator)), None,
                               CLSCTX_ALL, byref(GUID(IID_IMMDeviceEnumerator)),
                               byref(ptr))
        self._enumerator = ptr

    def close(self):
        self._forget()
        if self._enumerator:
            _release(self._enumerator)
            self._enumerator = None

    def _forget(self):
        for ptr in self._volumes.values():
            _release(ptr)
        self._volumes.clear()

    # -- device plumbing ---------------------------------------------------
    def _device_id(self, device):
        text = c_wchar_p()
        _call(device, DEV_GETID, POINTER(c_wchar_p))(device, byref(text))
        try:
            return text.value
        finally:
            ole32.CoTaskMemFree(ctypes.cast(text, c_void_p))

    def _endpoint_volume(self, device):
        ptr = c_void_p()
        _call(device, DEV_ACTIVATE, POINTER(GUID), wintypes.DWORD, c_void_p,
              POINTER(c_void_p))(device, byref(GUID(IID_IAudioEndpointVolume)),
                                 CLSCTX_ALL, None, byref(ptr))
        return ptr

    def _target_devices(self):
        """IMMDevice pointers we should act on. Caller releases them."""
        devices = []
        if self.mute_all_inputs:
            collection = c_void_p()
            _call(self._enumerator, ENUM_ENUMAUDIOENDPOINTS,
                  c_uint, wintypes.DWORD, POINTER(c_void_p))(
                      self._enumerator, E_CAPTURE, DEVICE_STATE_ACTIVE,
                      byref(collection))
            try:
                count = c_uint()
                _call(collection, COLL_GETCOUNT, POINTER(c_uint))(
                    collection, byref(count))
                for index in range(count.value):
                    device = c_void_p()
                    _call(collection, COLL_ITEM, c_uint, POINTER(c_void_p))(
                        collection, index, byref(device))
                    devices.append(device)
            finally:
                _release(collection)
        else:
            # Console and communications defaults are usually the same device,
            # but when a headset is set as the "chat" device they are not, and
            # users expect one keypress to silence both.
            for role in (ROLE_CONSOLE, ROLE_COMMUNICATIONS):
                device = c_void_p()
                try:
                    _call(self._enumerator, ENUM_GETDEFAULTENDPOINT,
                          c_uint, c_uint, POINTER(c_void_p))(
                              self._enumerator, E_CAPTURE, role, byref(device))
                except OSError:
                    continue
                devices.append(device)
        return devices

    def resolve(self):
        """(Re)bind endpoint volumes. Picks up plugged/unplugged microphones."""
        if not self._enumerator:
            self.open()
        found = {}
        for device in self._target_devices():
            try:
                dev_id = self._device_id(device)
                if dev_id in found:
                    continue
                found[dev_id] = (self._volumes.pop(dev_id, None)
                                 or self._endpoint_volume(device))
            except OSError:
                pass
            finally:
                _release(device)
        self._forget()
        self._volumes = found
        return bool(self._volumes)

    def _ensure(self):
        if not self._volumes:
            self.resolve()
        return bool(self._volumes)

    # -- state -------------------------------------------------------------
    def get_mute(self):
        """True only when every target endpoint is muted. None if unavailable."""
        for attempt in (0, 1):
            if not self._ensure():
                return None
            try:
                states = []
                for ptr in self._volumes.values():
                    flag = wintypes.BOOL()
                    _call(ptr, VOL_GETMUTE, POINTER(wintypes.BOOL))(
                        ptr, byref(flag))
                    states.append(bool(flag.value))
                return all(states) if states else None
            except OSError:
                self._forget()          # stale endpoint: rebind once and retry
                if attempt:
                    return None
        return None

    def set_mute(self, muted):
        flag = 1 if muted else 0
        for attempt in (0, 1):
            if not self._ensure():
                return None
            try:
                for ptr in self._volumes.values():
                    _call(ptr, VOL_SETMUTE, wintypes.BOOL, c_void_p)(
                        ptr, flag, None)
                return bool(muted)
            except OSError:
                self._forget()
                if attempt:
                    return None
        return None


class AudioService(threading.Thread):
    """Serialises mute work onto one thread and reports state changes.

    Blocks on a queue, so idle cost is zero. The timeout doubles as a slow poll
    that notices mutes made elsewhere (Windows settings, a headset button) and
    devices coming and going.
    """

    POLL_SECONDS = 1.0

    def __init__(self, cfg, on_state, on_error=None):
        super().__init__(name="CuteMute-audio", daemon=True)
        self._queue = queue.Queue()
        self._cfg = cfg
        self._on_state = on_state
        self._on_error = on_error
        self._stop = threading.Event()
        self._reported = None

    # -- public API (thread-safe) -----------------------------------------
    def request_toggle(self):
        self._queue.put(("toggle", None))

    def request_set(self, muted):
        self._queue.put(("set", bool(muted)))

    def request_resync(self):
        self._queue.put(("resync", None))

    def set_options(self, mute_all_inputs):
        self._queue.put(("options", bool(mute_all_inputs)))

    def stop(self):
        self._stop.set()
        self._queue.put(("stop", None))

    # -- worker ------------------------------------------------------------
    def run(self):
        ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
        mic = MicMute(self._cfg["audio"]["mute_all_inputs"])
        try:
            mic.open()
        except OSError as exc:
            if self._on_error:
                self._on_error("No audio endpoint available: %s" % exc)
        self._publish(mic.get_mute())

        while not self._stop.is_set():
            try:
                action, payload = self._queue.get(timeout=self.POLL_SECONDS)
            except queue.Empty:
                action, payload = "resync", None

            if action == "stop":
                break
            try:
                if action == "toggle":
                    current = mic.get_mute()
                    self._publish(mic.set_mute(not bool(current)))
                elif action == "set":
                    self._publish(mic.set_mute(payload))
                elif action == "options":
                    mic.mute_all_inputs = payload
                    mic.resolve()
                    self._publish(mic.get_mute())
                else:
                    mic.resolve()
                    self._publish(mic.get_mute())
            except OSError as exc:
                if self._on_error:
                    self._on_error(str(exc))

        mic.close()
        ole32.CoUninitialize()

    def _publish(self, muted):
        if muted is None or muted == self._reported:
            return
        self._reported = muted
        self._on_state(muted)
