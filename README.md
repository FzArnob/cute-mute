# CuteMute

One keypress mutes your microphone. While it is muted, a small badge sits in the
corner of the screen on top of everything, so you can never be *accidentally*
muted or *accidentally* live.

- **Toggle key:** `Tab` by default, changeable in the window
- **Badge:** 20x20 px, bottom-right, always on top, click-through
- **Settings save themselves** as you touch them, and take effect at once
- **Runs in the tray** once you close the window, no console window, no
  measurable CPU when idle
- **No third-party dependencies** — stdlib Python plus direct Win32/COM calls

---

## Running it

```powershell
# from source, no console window
pythonw CuteMute.pyw

# or with a console, handy while trying things out
python -m cutemute
```

Starting CuteMute shows its window. Close the window and it keeps running in
the notification area: green mic = live, red slashed mic = muted.

| Action | How |
| --- | --- |
| Toggle mute | the hotkey, or left-click the tray icon |
| Open the window | right-click the tray icon → **Open**, or double-click it |
| Send it back to the tray | close the window |
| Quit | right-click the tray icon → Exit CuteMute |

The tray menu is four items — Open, Mute Microphone, Start with Windows,
Exit CuteMute — painted in the app's palette rather than the system's.

### Building CuteMute.exe

```powershell
python -m pip install pyinstaller
.\build.ps1              # -> dist\CuteMute.exe   (single file, no console)
.\build.ps1 -OneDir      # -> dist\CuteMute\      (starts faster)
```

`build.ps1` regenerates `CuteMute.ico` from the same code that draws the badge,
so the exe, the tray and the overlay never drift apart.

To start it with Windows, tick **Start CuteMute with Windows** in the window or
in the tray menu. It writes the per-user `Run` key — no admin rights, no
scheduled task — with `--tray`, so logging in does not pop the window open.

### Command line

| Flag | Effect |
| --- | --- |
| *(none)* | show the window; closing it leaves CuteMute in the tray |
| `--tray` | start straight into the tray — what run-at-login uses |
| `--toggle` | toggle mute once and exit — for binding from other tools |
| `--selftest` | start up, print diagnostics, flash the badge, exit |
| `--version` | print the version |

Launching a second copy does not start a second instance; it just brings the
running one's window up.

---

## A word about `Tab`

`Tab` is the default because you asked for it, but it is worth knowing what it
means. By default CuteMute **watches** for the key and lets it through, so `Tab`
still indents, still moves between fields — and also toggles your mic. That is
usually not what you want while typing.

Two ways to fix it, both in settings:

- **Block the key from other apps** — `Tab` now belongs to CuteMute alone and
  nothing else ever sees it. Simple, but you lose `Tab`.
- **Pick a different key** — click the key box and hit anything (`Esc`
  cancels, and so does clicking the box again): `F13`, `Pause`,
  `Scroll Lock`, a spare mouse-side key, or a combination like `Ctrl+Alt+M`.
  This is the recommended route.

Modifiers must match exactly, so a hotkey of plain `Tab` is *not* triggered by
`Alt+Tab` or `Ctrl+Tab`. Holding the key down toggles once, not once per repeat.

---

## Settings

There is no Save button. Every change is written a quarter of a second after
you stop fiddling and pushed straight into the running app — new hotkey, new
badge, new audio scope, all live — with a small *Saving / Saved* indicator in
the corner, so the write is visible rather than merely promised. Closing the
window flushes anything still pending.

Everything lives in `%APPDATA%\CuteMute\config.json`, written atomically, and
regenerated with defaults if it is missing or corrupt.

| Setting | Default | Notes |
| --- | --- | --- |
| Toggle key | `Tab` | captured through the global hook, so exotic keys work |
| Block the key from other apps | off | swallow the keystroke entirely |
| Show badge while muted | on | |
| Size | `20` px | real physical pixels at any display scaling |
| Margin | `8` px | distance from the corner of the work area |
| Corner | bottom-right | any of the four |
| Opacity | `100%` | |
| Mute every input device | off | on = every active capture endpoint |
| Play a short beep when toggling | off | low = muted, high = live |
| Start CuteMute with Windows | off | per-user `Run` key |

---

## How it works

Four threads, each blocked on something the kernel wakes it for. Nothing polls
in a spin loop, which is why idle CPU measures as flat zero.

```
main            waits on a queue; builds the window when asked, and is asked
                as soon as CuteMute starts unless --tray says otherwise
CuteMute-winui  one Win32 message pump shared by the badge and the tray icon
CuteMute-hotkey a WH_KEYBOARD_LL hook, kept deliberately tiny
CuteMute-audio  owns the COM apartment and does every mute/unmute
```

**The realtime path is short on purpose:**

```
hook callback  ->  queue.put_nowait  ->  audio thread  ->  IAudioEndpointVolume::SetMute
   (integer compares only)                                 (~3 ms, measured)
```

The hook callback never touches audio, GUI or COM. That is not just tidiness:
if a low-level keyboard hook takes longer than `LowLevelHooksTimeout` (300 ms by
default) Windows silently tears it down, and a stalled hook delays *every*
keystroke on the machine, in every app. So the callback compares a few integers,
pushes to a queue and returns. The badge is updated after the fact.

### Some specific choices

**Mute is a hook, not `RegisterHotKey`.** `RegisterHotKey` always consumes the
key, which would break `Tab` everywhere with no way to opt out. A hook can watch
and pass through, so swallowing becomes a setting.

**Both default capture devices are muted.** The console default and the
communications default are usually the same microphone, but when a headset is
set as the "chat" device they are not — and one keypress should silence both.

**The badge is a layered window with per-pixel alpha.** `UpdateLayeredWindow`
with a premultiplied ARGB bitmap gives a genuinely anti-aliased rounded badge
over whatever is underneath, instead of the hard colour-keyed fringe you get
from a transparent-colour window. It is `WS_EX_TRANSPARENT` (clicks pass
through), `WS_EX_NOACTIVATE` (never steals focus) and `WS_EX_TOOLWINDOW` (stays
out of Alt+Tab), and it re-asserts topmost every 3 s in case something else
grabs the top slot.

**The process is per-monitor-DPI-aware.** So 20 px is 20 real pixels and the
badge is never blurred by the compositor. The window scales every coordinate
it draws instead, and shrinks that scale if the panel would not fit the
screen.

**The icon is drawn in code.** `cutemute/iconart.py` rasterises the mic badge
from signed-distance tests with 4x4 supersampling — a few milliseconds, cached,
and it means one definition feeds the overlay, the tray icon and the `.ico`,
at any size, with no image files to ship.

**No pycaw, no comtypes, no Pillow.** `cutemute/audio.py` calls the Core Audio
COM vtables directly through `ctypes`; it is about eighty lines, has no
packaging quirks when frozen, and keeps the toggle path down to a couple of
virtual calls.

**The window is drawn, not themed.** ttk cannot give you rounded dark rows, a
switch or a dark combobox on Windows, so the panel is a single Tk canvas
painted from anti-aliased sprites (`paint.py`), with hit-testing done against
a list of rectangles rather than canvas tags — which is also what stops a
hovered row flickering as the pointer crosses the five items it is made of.
Sprite geometry is cached for the life of the process; the `PhotoImage`
objects die with the window.

**The title bar is ours too.** A window that says it cannot be maximised still
gets a greyed-out maximise button beside minimise, and no window style means
"minimise and close only" — so the frame goes (`overrideredirect`), and the
taskbar button, the Alt+Tab entry and the rounded corners are all asked for
again by hand.

**The tray menu is a real menu with owner-drawn items.** Windows keeps the
parts that are easy to get wrong — keyboard navigation, dismissing on a click
somewhere else, multi-monitor placement — and the items are painted in the
app's palette. Its background brush is not optional: Windows 11 still draws a
classic Win32 menu in the light theme even on a fully dark desktop.

**Settings UI is built on demand and thrown away.** The resident app keeps no
GUI toolkit state while it is just sitting in the tray.

### Measured

| | |
| --- | --- |
| Idle CPU | 0 ms over 15 s (below the 15.6 ms clock granularity) |
| Working set | ~25 MB (~12 MB private) |
| Mute latency | ~3 ms for the Core Audio call; hook overhead is sub-millisecond |

### Known limits

- A **fullscreen exclusive** game or app can draw over any topmost window,
  including the badge. Borderless-windowed mode is fine.
- The badge is placed on the **primary** monitor's work area.
- A low-level hook cannot see keystrokes sent to a window running **elevated**
  unless CuteMute is elevated too. Run it as administrator if you need the
  hotkey to work while an admin app has focus.

---

## Layout

```
cutemute/
  app.py          wiring, lifecycle, single instance, CLI
  audio.py        Core Audio mute via raw ctypes COM + the audio thread
  hotkey.py       WH_KEYBOARD_LL listener, chord matching, capture mode
  overlay.py      the layered always-on-top badge window
  tray.py         tray icon and its context menu
  menu.py         that menu, owner-drawn to match the window
  winui.py        the Win32 UI thread hosting overlay + tray
  settings_ui.py  the settings window: one canvas, saves as you touch it
  paint.py        its anti-aliased sprites, built without dependencies
  theme.py        the palette the window and the menu share
  iconart.py      procedural badge rasteriser
  winicon.py      badge -> HICON
  keys.py         virtual-key names, modifier state
  config.py       %APPDATA% JSON settings
  startup.py      run-at-login registry entry
  w32.py          the Win32 ctypes bindings everything else uses
tools/
  make_ico.py     build CuteMute.ico from iconart
  preview_icon.py render a PNG contact sheet of the badge
CuteMute.pyw      console-free entry point
build.ps1         PyInstaller build
```
