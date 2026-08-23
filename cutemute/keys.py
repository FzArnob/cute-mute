"""Virtual-key <-> human-readable name mapping for hotkey display and config."""
import ctypes

from .w32 import user32

# Order matters: this is also the order modifiers are rendered in.
MOD_ORDER = ("ctrl", "alt", "shift", "win")

# Left/right virtual-key pairs for each modifier.
MOD_VKS = {
    "ctrl": (0xA2, 0xA3),
    "alt": (0xA4, 0xA5),
    "shift": (0xA0, 0xA1),
    "win": (0x5B, 0x5C),
}

# Every vk that is itself only a modifier; these can never be a trigger key.
MODIFIER_VKS = {vk for pair in MOD_VKS.values() for vk in pair} | {0x10, 0x11, 0x12}

VK_ESCAPE = 0x1B
VK_TAB = 0x09

# Names that Windows either reports badly or not at all.
SPECIAL_NAMES = {
    0x01: "Mouse Left", 0x02: "Mouse Right", 0x04: "Mouse Middle",
    0x05: "Mouse 4", 0x06: "Mouse 5",
    0x08: "Backspace", 0x09: "Tab", 0x0C: "Clear", 0x0D: "Enter",
    0x13: "Pause", 0x14: "Caps Lock", 0x1B: "Esc", 0x20: "Space",
    0x21: "Page Up", 0x22: "Page Down", 0x23: "End", 0x24: "Home",
    0x25: "Left", 0x26: "Up", 0x27: "Right", 0x28: "Down",
    0x29: "Select", 0x2C: "Print Screen", 0x2D: "Insert", 0x2E: "Delete",
    0x5D: "Menu", 0x5F: "Sleep",
    0x60: "Num 0", 0x61: "Num 1", 0x62: "Num 2", 0x63: "Num 3", 0x64: "Num 4",
    0x65: "Num 5", 0x66: "Num 6", 0x67: "Num 7", 0x68: "Num 8", 0x69: "Num 9",
    0x6A: "Num *", 0x6B: "Num +", 0x6C: "Num Enter", 0x6D: "Num -",
    0x6E: "Num .", 0x6F: "Num /",
    0x90: "Num Lock", 0x91: "Scroll Lock",
    0xA6: "Browser Back", 0xA7: "Browser Forward", 0xA8: "Browser Refresh",
    0xAD: "Volume Mute", 0xAE: "Volume Down", 0xAF: "Volume Up",
    0xB0: "Next Track", 0xB1: "Prev Track", 0xB2: "Stop", 0xB3: "Play/Pause",
    0xFF: "(unassigned)",
}
for _i in range(1, 25):
    SPECIAL_NAMES[0x6F + _i] = "F%d" % _i        # 0x70..0x87 -> F1..F24
for _c in range(0x30, 0x3A):
    SPECIAL_NAMES[_c] = chr(_c)                  # 0..9
for _c in range(0x41, 0x5B):
    SPECIAL_NAMES[_c] = chr(_c)                  # A..Z

MAPVK_VK_TO_VSC_EX = 4
EXTENDED_VKS = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,
                0x2D, 0x2E, 0x6F, 0x90, 0xA3, 0xA5, 0x5B, 0x5C, 0x5D}


def key_name(vk):
    """Best-effort display name for a virtual-key code."""
    if vk in SPECIAL_NAMES:
        return SPECIAL_NAMES[vk]
    scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC_EX)
    if scan:
        lparam = (scan & 0xFF) << 16
        if vk in EXTENDED_VKS or scan & 0xE000:
            lparam |= 1 << 24
        buf = ctypes.create_unicode_buffer(64)
        if user32.GetKeyNameTextW(lparam, buf, len(buf)) > 0:
            return buf.value.title() if buf.value.isupper() else buf.value
    return "VK 0x%02X" % vk


def chord_text(vk, mods):
    """Render a hotkey as e.g. 'Tab' or 'Ctrl+Shift+M'."""
    parts = [m.capitalize() if m != "win" else "Win"
             for m in MOD_ORDER if m in set(mods or ())]
    parts.append(key_name(vk))
    return "+".join(parts)


def held_modifiers(exclude_vk=None):
    """Modifiers physically down right now, ignoring the trigger key itself."""
    held = set()
    for name, vks in MOD_VKS.items():
        for vk in vks:
            if vk == exclude_vk:
                continue
            if user32.GetAsyncKeyState(vk) & 0x8000:
                held.add(name)
                break
    return held
