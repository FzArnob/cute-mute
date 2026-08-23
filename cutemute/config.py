"""Settings persistence: %APPDATA%\\CuteMute\\config.json."""
import copy
import json
import os
import sys

from . import APP_NAME

DEFAULTS = {
    "hotkey": {
        "vk": 0x09,          # Tab
        "mods": [],
        "suppress": False,   # let the key through to the focused app by default
    },
    "overlay": {
        "enabled": True,
        "size": 20,
        "margin": 8,
        "corner": "bottom-right",
        "opacity": 100,
    },
    "audio": {
        "mute_all_inputs": False,
    },
    "feedback": {
        "sound": False,
    },
    "start_with_windows": False,
}

CORNERS = ("bottom-right", "bottom-left", "top-right", "top-left")


def config_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_NAME)


def config_path():
    return os.path.join(config_dir(), "config.json")


def _merge(defaults, loaded):
    out = copy.deepcopy(defaults)
    if not isinstance(loaded, dict):
        return out
    for key, value in loaded.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key].update({k: v for k, v in value.items() if k in out[key]})
        elif key in out:
            out[key] = value
    return out


def _sanitise(cfg):
    hk = cfg["hotkey"]
    try:
        hk["vk"] = max(1, min(0xFE, int(hk["vk"])))
    except (TypeError, ValueError):
        hk["vk"] = DEFAULTS["hotkey"]["vk"]
    valid = ("ctrl", "alt", "shift", "win")
    hk["mods"] = sorted({m for m in hk.get("mods") or () if m in valid})
    hk["suppress"] = bool(hk.get("suppress"))

    ov = cfg["overlay"]
    ov["enabled"] = bool(ov.get("enabled", True))
    ov["size"] = max(10, min(128, int(ov.get("size") or 20)))
    ov["margin"] = max(0, min(400, int(ov.get("margin") or 0)))
    ov["opacity"] = max(20, min(100, int(ov.get("opacity") or 100)))
    if ov.get("corner") not in CORNERS:
        ov["corner"] = "bottom-right"

    cfg["audio"]["mute_all_inputs"] = bool(cfg["audio"].get("mute_all_inputs"))
    cfg["feedback"]["sound"] = bool(cfg["feedback"].get("sound"))
    cfg["start_with_windows"] = bool(cfg.get("start_with_windows"))
    return cfg


def load():
    try:
        with open(config_path(), "r", encoding="utf-8") as fh:
            loaded = json.load(fh)
    except (OSError, ValueError):
        loaded = {}
    return _sanitise(_merge(DEFAULTS, loaded))


def save(cfg):
    """Write atomically so a crash mid-write cannot leave a truncated file."""
    cfg = _sanitise(_merge(DEFAULTS, cfg))
    try:
        os.makedirs(config_dir(), exist_ok=True)
        tmp = config_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2)
        os.replace(tmp, config_path())
    except OSError as exc:
        print("CuteMute: could not save settings: %s" % exc, file=sys.stderr)
    return cfg
