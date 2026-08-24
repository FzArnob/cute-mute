"""The settings window: one dark, self-drawn panel that saves as you touch it.

ttk cannot be made to look like this on Windows - no rounded rows, no dark
combobox, no switch - so the window is a single Tk canvas and every control is
painted from anti-aliased sprites (see paint.py), with hit-testing done against
a plain list of rectangles. That is less code than fighting the theme engine,
and it looks the same on every Windows build.

There is no Save button. Each change is debounced a few hundred milliseconds,
written to %APPDATA% and pushed straight into the running app - hotkey, badge
and audio all pick it up at once - with a small Saving/Saved indicator so the
write is visible rather than merely promised. Closing the window flushes
anything still pending and leaves CuteMute in the tray.

Hotkey capture still goes through the global keyboard hook rather than Tk key
events: that is what lets it report exact virtual-key codes (including keys Tk
never sees, like media keys) and offer to swallow them.
"""
import queue
import sys
import tkinter as tk

from . import keys, paint, startup
from .theme import (ACCENT, ACCENT_HOVER, BG, BORDER, BORDER_HOVER, CAPTION,
                    CAPTION_HOVER, CLOSE_HOVER, CTRL, CTRL_DOWN, CTRL_HOVER,
                    CTRL_ON, DIM, FAINT, FIELD, KNOB_OFF, KNOB_ON, SECTION,
                    TEXT, TILE, TILE_HOVER, TITLE, TRACK, TRACK_FILL, WARN)
from .w32 import (GA_ROOT, ICON_BIG, ICON_SMALL, WM_SETICON, make_frameless,
                  minimise, primary_work_area, system_dpi, user32)
from .winicon import destroy_hicon, make_hicon

# -- layout, in logical pixels; every number goes through self.s() ---------
WIDTH = 440
BAR = 40                    # title bar height
CAPTION_BUTTON = 46
PAD = 18                    # window edge -> row edge
INSET = 14                  # row edge -> content
GAP = 6                     # between rows
RADIUS = 9
ROW = 46
ROW_TALL = 52
ROW_CAPTION = 62
ROW_HOTKEY = 88

CORNER_ORDER = ("top-left", "top-right", "bottom-left", "bottom-right")
PROMPT = "Press a key or combination"
SAVE_DELAY = 260            # ms of quiet before a change is written
SAVE_SHOWN = 480            # ms the "Saving" state is held, so it can be read


class _Control:
    """One interactive thing on the canvas, hit-tested by rectangle, not by tag.

    Tk generates Enter/Leave per canvas item, so a row built from five items
    flickers as the pointer crosses it. Routing every event through one Motion
    handler and a rectangle list is both simpler and steadier.
    """

    cursor = "hand2"

    def hover(self, on):
        pass

    def press(self, x, y):
        pass

    def drag(self, x, y):
        pass

    def release(self):
        pass

    def wheel(self, steps):
        return False        # not handled: try whatever lies underneath


class _Tile:
    """A rounded row background, which also owns the row's hover highlight."""

    def __init__(self, win, x, y, w, h):
        self._win = win
        self._w, self._h = w, h
        self.hovered = False
        self.item = win.canvas.create_image(x, y, anchor="nw",
                                            image=self._image())

    @property
    def colour(self):
        return TILE_HOVER if self.hovered else TILE

    def _image(self):
        return self._win.sprites.rounded(self._w, self._h,
                                         self._win.s(RADIUS), self.colour, BG)

    def hover(self, on):
        if bool(on) == self.hovered:
            return
        self.hovered = bool(on)
        self._win.canvas.itemconfigure(self.item, image=self._image())


class _Switch(_Control):
    """Pill plus sliding handle. The whole row is the hit box, as in Windows.

    The handle is a separate canvas image moved with coords() rather than a
    sprite per frame: at this size it never quite leaves the pill, so blending
    it against the pill colour is right everywhere the eye can tell, and the
    slide costs nothing to animate.
    """

    STEPS = 7

    def __init__(self, win, tile, x, y, w, h, value, on_toggle):
        self._win = win
        self._tile = tile
        self._x, self._y, self._w, self._h = x, y, w, h
        self._value = bool(value)
        self._on_toggle = on_toggle
        self._pad = max(win.s(3), 2)
        self._knob_d = h - 2 * self._pad
        self._travel = w - 2 * self._pad - self._knob_d
        self._pos = 1.0 if self._value else 0.0
        self._job = None
        canvas = win.canvas
        self._pill = canvas.create_image(x, y, anchor="nw",
                                         image=self._pill_image())
        self._knob = canvas.create_image(self._knob_x(), y + self._pad,
                                         anchor="nw", image=self._knob_image())

    # -- painting ----------------------------------------------------------
    def _track_colour(self):
        if self._value:
            return ACCENT_HOVER if self._tile.hovered else ACCENT
        return CTRL_HOVER if self._tile.hovered else TRACK

    def _pill_image(self):
        return self._win.sprites.pill(self._w, self._h, self._track_colour(),
                                      self._tile.colour)

    def _knob_image(self):
        return self._win.sprites.disc(self._knob_d,
                                      KNOB_ON if self._value else KNOB_OFF,
                                      self._track_colour())

    def _knob_x(self):
        return int(self._x + self._pad + self._pos * self._travel + 0.5)

    def _paint(self):
        canvas = self._win.canvas
        canvas.itemconfigure(self._pill, image=self._pill_image())
        canvas.itemconfigure(self._knob, image=self._knob_image())
        canvas.coords(self._knob, self._knob_x(), self._y + self._pad)

    # -- behaviour ---------------------------------------------------------
    def hover(self, on):
        self._tile.hover(on)
        self._paint()

    def press(self, x=None, y=None):
        self.set(not self._value, notify=True)

    def set(self, value, notify=False):
        if bool(value) == self._value and not notify:
            return
        self._value = bool(value)
        if notify:
            self._on_toggle(self._value)
        self._paint()
        self._slide()

    def stop(self):
        if self._job:
            self._win.after_cancel(self._job)
            self._job = None

    def _slide(self):
        start, target = self._pos, (1.0 if self._value else 0.0)
        if self._job:
            self._win.after_cancel(self._job)
            self._job = None
        if start != target:
            self._step(1, start, target)

    def _step(self, frame, start, target):
        if not self._win.alive():
            return
        t = frame / float(self.STEPS)
        self._pos = start + (target - start) * (1.0 - (1.0 - t) ** 3)
        self._win.canvas.coords(self._knob, self._knob_x(),
                                self._y + self._pad)
        if frame < self.STEPS:
            self._job = self._win.after(14, self._step, frame + 1, start,
                                        target)
        else:
            self._pos = target
            self._job = None


class _Button(_Control):
    """A small rounded button. Whatever sits on top of it is drawn by the row."""

    def __init__(self, win, x, y, w, h, on_click, fill=CTRL, glyph=None,
                 on_wheel=None):
        self._win = win
        self._x, self._y, self._w, self._h = x, y, w, h
        self._on_click = on_click
        self._on_wheel = on_wheel
        self._fill = fill
        self._state = "normal"
        self.item = win.canvas.create_image(x, y, anchor="nw",
                                            image=self._image())
        # Created after the background, so it lands on top of it.
        self.glyph = glyph(x, y, w, h) if glyph else ()

    def _image(self):
        fill = {"normal": self._fill, "hover": CTRL_HOVER,
                "down": CTRL_DOWN}[self._state]
        return self._win.sprites.rounded(self._w, self._h, self._win.s(7),
                                         fill, TILE)

    def _paint(self, state):
        self._state = state
        self._win.canvas.itemconfigure(self.item, image=self._image())

    def set_fill(self, fill):
        self._fill = fill
        self._paint(self._state)

    def hover(self, on):
        self._paint("hover" if on else "normal")

    def press(self, x=None, y=None):
        self._paint("down")
        self._on_click()

    def release(self):
        self._paint("normal")

    def wheel(self, steps):
        if self._on_wheel:
            self._on_wheel(steps)
            return True
        return False


class _Wheel(_Control):
    """An invisible row-wide catcher, so the wheel works anywhere on the row."""

    cursor = ""

    def __init__(self, on_wheel):
        self._on_wheel = on_wheel

    def wheel(self, steps):
        self._on_wheel(steps)
        return True


class _Caption(_Control):
    """The title bar strip: dragging it moves the window, as a frame would."""

    cursor = ""

    def __init__(self, win):
        self._win = win
        self._from = self._at = (0, 0)

    def press(self, x=None, y=None):
        self._from = self._win.pointer
        self._at = (self._win.root.winfo_x(), self._win.root.winfo_y())

    def drag(self, x=None, y=None):
        px, py = self._win.pointer
        self._win.root.geometry("+%d+%d" % (self._at[0] + px - self._from[0],
                                            self._at[1] + py - self._from[1]))


class _CaptionButton(_Control):
    """Minimise and close: square, flush to the corner, Windows' own colours."""

    def __init__(self, win, x, y, w, h, glyph, on_click, hover_fill):
        self._win = win
        self._on_click = on_click
        self._hover_fill = hover_fill
        canvas = win.canvas
        self._back = canvas.create_rectangle(x, y, x + w, y + h, fill=CAPTION,
                                             width=0)
        size = win.s(12)
        self._normal = glyph(CAPTION)
        self._hovered = glyph(hover_fill)
        self._glyph = canvas.create_image(x + (w - size) // 2,
                                          y + (h - size) // 2, anchor="nw",
                                          image=self._normal)

    def hover(self, on):
        canvas = self._win.canvas
        canvas.itemconfigure(self._back,
                             fill=self._hover_fill if on else CAPTION)
        canvas.itemconfigure(self._glyph,
                             image=self._hovered if on else self._normal)

    def press(self, x=None, y=None):
        self._on_click()


class _KeyField(_Control):
    """The hotkey box: the current chord, plus a keyboard glyph to say it is a
    button. Clicking anywhere in the row starts a capture."""

    def __init__(self, win, tile, x, y, w, h, text, on_click):
        self._win = win
        self._tile = tile
        self._w, self._h = w, h
        self._on_click = on_click
        self._hovered = False
        canvas = win.canvas
        self._box = canvas.create_image(x, y, anchor="nw", image=self._image())
        self._label = canvas.create_text(x + w // 2, y + h // 2, text=text,
                                         anchor="center", fill=TEXT,
                                         font=win.font(13, "semibold"))
        self._glyph = self._keyboard(x + w - win.s(INSET) - win.s(20),
                                     y + (h - win.s(14)) // 2)

    def _image(self):
        return self._win.sprites.rounded(
            self._w, self._h, self._win.s(RADIUS - 1), FIELD,
            self._tile.colour, max(1, self._win.s(1)),
            BORDER_HOVER if self._hovered else BORDER)

    def _keyboard(self, x, y):
        """A 20x14 keyboard: its own outline, three keys and a space bar."""
        win = self._win
        w, h = win.s(20), win.s(14)
        items = [win.canvas.create_image(
            x, y, anchor="nw",
            image=win.sprites.rounded(w, h, win.s(3), FIELD, FIELD,
                                      max(1, win.s(1)), DIM))]
        key = max(2, win.s(2))
        for index in range(3):
            kx = x + win.s(4) + index * (key + max(1, win.s(2)))
            items.append(win.canvas.create_rectangle(
                kx, y + win.s(4), kx + key, y + win.s(4) + key,
                fill=DIM, width=0))
        items.append(win.canvas.create_rectangle(
            x + win.s(4), y + h - win.s(6), x + w - win.s(4),
            y + h - win.s(6) + key, fill=DIM, width=0))
        return tuple(items)

    def set_text(self, text, dim=False):
        self._win.canvas.itemconfigure(self._label, text=text,
                                       fill=DIM if dim else TEXT)

    def hover(self, on):
        self._hovered = bool(on)
        self._tile.hover(on)
        self._win.canvas.itemconfigure(self._box, image=self._image())

    def press(self, x=None, y=None):
        self._on_click()


class _Slider(_Control):
    """Track drawn as two rectangles; the handle sprite carries its own seam."""

    def __init__(self, win, x, cy, w, lo, hi, value, on_change):
        self._win = win
        self._x, self._cy, self._w = x, cy, w
        self._lo, self._hi = lo, hi
        self._value = value
        self._on_change = on_change
        self._d = win.s(16)
        self._band = max(3, win.s(4))
        canvas = win.canvas
        half = self._band // 2
        self._filled = canvas.create_rectangle(x, cy - half, x, cy + half,
                                               fill=TRACK_FILL, width=0)
        self._rest = canvas.create_rectangle(x, cy - half, x + w, cy + half,
                                             fill=TRACK, width=0)
        self._handle = canvas.create_image(
            x, cy - self._d // 2, anchor="nw",
            image=win.sprites.handle(self._d, self._band, TRACK_FILL, TRACK,
                                     KNOB_ON, TILE))
        self._paint()

    def _centre(self):
        span = float(self._hi - self._lo)
        frac = (self._value - self._lo) / span if span else 0.0
        return self._x + self._d / 2.0 + frac * (self._w - self._d)

    def _paint(self):
        canvas = self._win.canvas
        cx, half = self._centre(), self._band // 2
        canvas.coords(self._filled, self._x, self._cy - half, cx,
                      self._cy + half)
        canvas.coords(self._rest, cx, self._cy - half, self._x + self._w,
                      self._cy + half)
        canvas.coords(self._handle, int(cx - self._d / 2.0 + 0.5),
                      self._cy - self._d // 2)

    def _set(self, value):
        value = max(self._lo, min(self._hi, int(value)))
        if value != self._value:
            self._value = value
            self._paint()
            self._on_change(value)

    def press(self, x, y=None):
        travel = self._w - self._d
        frac = (x - (self._x + self._d / 2.0)) / travel if travel else 0.0
        self._set(round(self._lo
                        + max(0.0, min(1.0, frac)) * (self._hi - self._lo)))

    def drag(self, x, y=None):
        self.press(x)

    def wheel(self, steps):
        self._set(self._value + steps * 5)
        return True


class SettingsWindow:
    """The window. run() blocks until it is closed, as before."""

    def __init__(self, cfg, listener, on_apply, on_hwnd=None):
        self._cfg = cfg
        self._listener = listener
        self._on_apply = on_apply
        self._on_hwnd = on_hwnd
        self._captured = queue.Queue()
        self._capturing = False
        self._icon = None
        # Set by the app so a tray "Exit CuteMute" can close this window.
        self.should_close = None

        # Live values: the controls read and write these and nothing else.
        self.vk = int(cfg["hotkey"]["vk"])
        self.mods = tuple(cfg["hotkey"]["mods"])
        self.suppress = bool(cfg["hotkey"]["suppress"])
        overlay = cfg["overlay"]
        self.badge = bool(overlay["enabled"])
        self.size = int(overlay["size"])
        self.margin = int(overlay["margin"])
        self.corner = overlay["corner"]
        self.opacity = int(overlay["opacity"])
        self.mute_all = bool(cfg["audio"]["mute_all_inputs"])
        self.beep = bool(cfg["feedback"]["sound"])
        self.startup = bool(cfg["start_with_windows"])

        self._scale = 1.0
        self._hwnd = None
        self.pointer = (0, 0)
        self._hits = []
        self._hover = None
        self._active = None
        self._cursor = ""
        self._dirty = False
        self._save_job = None
        self._drain_job = None
        self._status_jobs = []
        self._save_seq = 0

    # -- small helpers -----------------------------------------------------
    def s(self, value):
        return int(round(value * self._scale))

    def font(self, px, weight="normal"):
        family = "Segoe UI Semibold" if weight == "semibold" else "Segoe UI"
        return (family, -self.s(px))

    def alive(self):
        try:
            return bool(self.root.winfo_exists())
        except tk.TclError:
            return False

    def after(self, delay, callback, *args):
        return self.root.after(delay, callback, *args)

    def after_cancel(self, job):
        try:
            self.root.after_cancel(job)
        except tk.TclError:
            pass

    # -- lifecycle ---------------------------------------------------------
    def run(self):
        self.root = tk.Tk()
        self.root.withdraw()            # no light-themed flash before we paint
        self.root.title("CuteMute")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.overrideredirect(True)     # we draw the title bar ourselves
        self.sprites = paint.Sprites()
        self.canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0, bd=0)
        self.canvas.pack()

        self._scale = system_dpi() / 96.0
        self._layout()
        self._bind()

        self.root.update_idletasks()
        hwnd = self._hwnd = user32.GetAncestor(self.root.winfo_id(), GA_ROOT)
        if hwnd:
            make_frameless(hwnd)
            try:
                # Still worth setting: it is the taskbar button's icon.
                self._icon = make_hicon(32, True)
                if self._icon:
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, self._icon)
                    user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, self._icon)
            except Exception:
                pass
        if self._on_hwnd:
            self._on_hwnd(hwnd)

        self._centre()
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        if hwnd:
            user32.SetForegroundWindow(hwnd)
        self._drain_job = self.after(30, self._drain)
        self.root.mainloop()

    def _teardown(self):
        self._capturing = False
        self._listener.cancel_capture()
        if self._save_job:
            self.after_cancel(self._save_job)
            self._save_job = None
        self._flush(final=True)         # never lose a change to a fast close
        # Every timer has to go before the interpreter does, or Tcl complains
        # about the vanished callback on stderr as the window closes.
        self._stop_status()
        if self._drain_job:
            self.after_cancel(self._drain_job)
            self._drain_job = None
        for switch in getattr(self, "_switches", {}).values():
            switch.stop()
        if self._on_hwnd:
            self._on_hwnd(None)
        destroy_hicon(self._icon)
        self._icon = None
        self.sprites.clear()
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _centre(self):
        self.root.update_idletasks()
        width = self.canvas.winfo_reqwidth()
        height = self.canvas.winfo_reqheight()
        left, top, right, bottom = primary_work_area()
        x = left + ((right - left) - width) // 2
        y = top + max(0, ((bottom - top) - height) // 2 - self.s(12))
        self.root.geometry("%dx%d+%d+%d" % (width, height, max(left, x),
                                            max(top, y)))

    # -- layout ------------------------------------------------------------
    def _layout(self):
        """Build once; if it would not fit the screen, shrink and build again."""
        height = self._build()
        _, top, _, bottom = primary_work_area()
        room = (bottom - top) - self.s(72)
        if height > room > 0:
            self._scale *= float(room) / height
            height = self._build()
        self.canvas.configure(width=self.s(WIDTH), height=height)

    def _build(self):
        self.canvas.delete("all")
        self._hits = []
        self._hover = self._active = None
        self._switches = {}
        self._corner_buttons = {}

        y = self._caption_bar()
        self._text(self.s(PAD), y, "CuteMute", self.font(20, "semibold"), TEXT)
        y += self.s(29)
        self._text(self.s(PAD), y, "One key to mute your microphone",
                   self.font(12), DIM)
        y += self.s(26)

        y = self._section(y, "Shortcut")
        y = self._hotkey_row(y)
        y = self._switch_row(y, "Block the key from other apps", "suppress",
                             caption=True, on_change=self._refresh_caption)

        y = self._section(y, "Muted badge")
        y = self._switch_row(y, "Show badge while muted", "badge")
        y = self._stepper_row(y, "Size", "size", 10, 128, 2, "px")
        y = self._stepper_row(y, "Margin", "margin", 0, 400, 2, "px")
        y = self._corner_row(y)
        y = self._opacity_row(y)

        y = self._section(y, "Behaviour")
        y = self._switch_row(y, "Mute every input device", "mute_all")
        y = self._switch_row(y, "Play a short beep when toggling", "beep")
        if startup.managed_by_windows():
            # A Store install's startup entry is Windows', not ours -- see
            # cutemute/packaged.py. A switch here could only lie.
            y = self._managed_row(
                y, "Start CuteMute with Windows",
                "Windows manages this for Store installs — "
                "Settings › Apps › Startup")
        else:
            y = self._switch_row(y, "Start CuteMute with Windows", "startup")

        return self._status_row(y + self.s(4))

    def _caption_bar(self):
        """Our own title bar: the badge, the name, minimise and close.

        Drawn rather than left to Windows because a window that says it cannot
        be maximised still gets a greyed-out maximise button next to minimise,
        and two buttons is what this window needs.
        """
        height, width = self.s(BAR), self.s(WIDTH)
        self.canvas.create_rectangle(0, 0, width, height, fill=CAPTION, width=0)
        icon = self.s(16)
        self.canvas.create_image(self.s(14), (height - icon) // 2, anchor="nw",
                                 image=self.sprites.badge(icon, True, CAPTION))
        self._text(self.s(38), height // 2, "CuteMute", self.font(12), TITLE,
                   anchor="w")

        self._hits.append((0, 0, width, height, _Caption(self)))
        button = self.s(CAPTION_BUTTON)
        buttons = ((((1.0, 6.0, 11.0, 6.0),), self._minimise, CAPTION_HOVER),
                   (((1.7, 1.7, 10.3, 10.3), (10.3, 1.7, 1.7, 10.3)),
                    self._teardown, CLOSE_HOVER))
        for index, (segments, action, hover) in enumerate(buttons):
            x = width - (len(buttons) - index) * button
            control = _CaptionButton(
                self, x, 0, button, height,
                lambda fill, seg=segments: self._glyph(seg, fill), action,
                hover)
            self._hits.append((x, 0, x + button, height, control))
        return height + self.s(14)

    def _glyph(self, segments, bg):
        """A caption glyph: strokes given in a 12x12 box, scaled and anti-aliased."""
        size = self.s(12)
        scaled = tuple(tuple(v * self._scale for v in segment)
                       for segment in segments)
        return self.sprites.strokes(size, size, scaled,
                                    max(1.3, 1.3 * self._scale), TITLE, bg)

    def _minimise(self):
        if self._hwnd:
            minimise(self._hwnd)

    def _text(self, x, y, text, font, fill, anchor="nw"):
        return self.canvas.create_text(x, y, text=text, font=font, fill=fill,
                                       anchor=anchor)

    def _section(self, y, title):
        self._text(self.s(PAD + 2), y, title, self.font(11), SECTION)
        return y + self.s(21)

    def _tile(self, y, height):
        return _Tile(self, self.s(PAD), y, self.s(WIDTH - 2 * PAD),
                     self.s(height))

    def _hit(self, y, height, control):
        self._hits.append((self.s(PAD), y, self.s(WIDTH - PAD),
                           y + self.s(height), control))

    def _row_title(self, y, height, title):
        """A single-line row label, vertically centred."""
        return self._text(self.s(PAD + INSET), y + self.s(height) // 2, title,
                          self.font(13, "semibold"), TEXT, anchor="w")

    # -- rows --------------------------------------------------------------
    def _hotkey_row(self, y):
        tile = self._tile(y, ROW_HOTKEY)
        self._text(self.s(PAD + INSET), y + self.s(15), "Toggle key",
                   self.font(13, "semibold"), TEXT)
        self.field = _KeyField(self, tile, self.s(PAD + INSET), y + self.s(42),
                               self.s(WIDTH - 2 * PAD - 2 * INSET), self.s(34),
                               keys.chord_text(self.vk, self.mods),
                               self._begin_capture)
        self._hit(y, ROW_HOTKEY, self.field)
        return y + self.s(ROW_HOTKEY) + self.s(GAP)

    def _switch_row(self, y, title, attr, caption=False, on_change=None):
        height = ROW_CAPTION if caption else ROW
        tile = self._tile(y, height)
        if caption:
            self._text(self.s(PAD + INSET), y + self.s(14), title,
                       self.font(13, "semibold"), TEXT)
            self._caption = self._text(self.s(PAD + INSET), y + self.s(34), "",
                                       self.font(11), DIM)
        else:
            self._row_title(y, height, title)

        def toggled(value):
            setattr(self, attr, value)
            if on_change:
                on_change()
            self._changed()

        sw, sh = self.s(42), self.s(24)
        control = _Switch(self, tile, self.s(WIDTH - PAD - INSET) - sw,
                          y + (self.s(height) - sh) // 2, sw, sh,
                          getattr(self, attr), toggled)
        self._switches[attr] = control
        self._hit(y, height, control)
        if caption:
            self._refresh_caption()
        return y + self.s(height) + self.s(GAP)

    def _managed_row(self, y, title, caption):
        """A row with no control, because the setting is not ours to set.

        Deliberately inert. The tray menu's "Start with Windows..." item
        opens the Settings page; a switch drawn here would have to either
        do nothing or guess at a state it cannot read.
        """
        self._tile(y, ROW_CAPTION)
        self._text(self.s(PAD + INSET), y + self.s(14), title,
                   self.font(13, "semibold"), DIM)
        self._text(self.s(PAD + INSET), y + self.s(34), caption,
                   self.font(11), FAINT)
        return y + self.s(ROW_CAPTION) + self.s(GAP)

    def _stepper_row(self, y, title, attr, lo, hi, step, unit):
        self._tile(y, ROW)
        self._row_title(y, ROW, title)
        bw, bh = self.s(30), self.s(24)
        top = y + (self.s(ROW) - bh) // 2
        plus_x = self.s(WIDTH - PAD - INSET) - bw
        minus_x = plus_x - bw - self.s(5)
        value_item = self._text(minus_x - self.s(12), y + self.s(ROW) // 2,
                                "%d %s" % (getattr(self, attr), unit),
                                self.font(12), DIM, anchor="e")

        def bump(steps):
            value = max(lo, min(hi, getattr(self, attr) + steps * step))
            if value != getattr(self, attr):
                setattr(self, attr, value)
                self.canvas.itemconfigure(value_item,
                                          text="%d %s" % (value, unit))
                self._changed()

        def minus_glyph(x, ry, w, h):
            bar = self.s(1) + 1
            return (self.canvas.create_rectangle(
                x + w // 2 - self.s(5), ry + h // 2 - bar // 2,
                x + w // 2 + self.s(5), ry + h // 2 - bar // 2 + bar,
                fill=TEXT, width=0),)

        def plus_glyph(x, ry, w, h):
            bar = self.s(1) + 1
            cx, cy = x + w // 2, ry + h // 2
            return (self.canvas.create_rectangle(
                        cx - self.s(5), cy - bar // 2, cx + self.s(5),
                        cy - bar // 2 + bar, fill=TEXT, width=0),
                    self.canvas.create_rectangle(
                        cx - bar // 2, cy - self.s(5), cx - bar // 2 + bar,
                        cy + self.s(5), fill=TEXT, width=0))

        self._hit(y, ROW, _Wheel(bump))
        for x, glyph, delta in ((minus_x, minus_glyph, -1),
                                (plus_x, plus_glyph, 1)):
            button = _Button(self, x, top, bw, bh, lambda d=delta: bump(d),
                             glyph=glyph, on_wheel=bump)
            self._hits.append((x, top, x + bw, top + bh, button))
        return y + self.s(ROW) + self.s(GAP)

    def _corner_row(self, y):
        self._tile(y, ROW_TALL)
        self._row_title(y, ROW_TALL, "Corner")
        size, gap = self.s(28), self.s(5)
        top = y + (self.s(ROW_TALL) - size) // 2
        first = self.s(WIDTH - PAD - INSET) - 4 * size - 3 * gap

        for index, corner in enumerate(CORNER_ORDER):
            x = first + index * (size + gap)
            button = _Button(
                self, x, top, size, size,
                lambda c=corner: self._choose_corner(c),
                fill=CTRL_ON if corner == self.corner else CTRL,
                glyph=lambda bx, by, w, h, c=corner: self._corner_glyph(
                    bx, by, w, h, c))
            self._corner_buttons[corner] = button
            self._hits.append((x, top, x + size, top + size, button))
        return y + self.s(ROW_TALL) + self.s(GAP)

    def _corner_glyph(self, x, y, w, h, corner):
        """A screen outline with a filled block in the corner it stands for."""
        pad = self.s(7)
        x0, y0, x1, y1 = x + pad, y + pad, x + w - pad, y + h - pad
        tick = max(2, self.s(3))
        items = []
        for cx, sx in ((x0, 1), (x1, -1)):
            for cy, sy in ((y0, 1), (y1, -1)):
                items.append(self.canvas.create_line(cx, cy, cx + sx * tick,
                                                     cy, fill=FAINT))
                items.append(self.canvas.create_line(cx, cy, cx,
                                                     cy + sy * tick,
                                                     fill=FAINT))
        block = max(3, self.s(5))
        bx = x0 if corner.endswith("left") else x1 - block
        by = y0 if corner.startswith("top") else y1 - block
        items.append(self.canvas.create_rectangle(
            bx, by, bx + block, by + block, width=0,
            fill=TEXT if corner == self.corner else DIM))
        return tuple(items)

    def _choose_corner(self, corner):
        if corner == self.corner:
            return
        self.corner = corner
        for name, button in self._corner_buttons.items():
            button.set_fill(CTRL_ON if name == corner else CTRL)
            for item in button.glyph:
                if self.canvas.type(item) == "rectangle":
                    self.canvas.itemconfigure(
                        item, fill=TEXT if name == corner else DIM)
        self._changed()

    def _opacity_row(self, y):
        self._tile(y, ROW)
        self._row_title(y, ROW, "Opacity")
        centre = y + self.s(ROW) // 2
        percent = self._text(self.s(WIDTH - PAD - INSET), centre,
                             "%d%%" % self.opacity, self.font(12), DIM,
                             anchor="e")
        left = self.s(PAD + INSET + 86)
        width = self.s(WIDTH - PAD - INSET - 46) - left

        def changed(value):
            self.opacity = value
            self.canvas.itemconfigure(percent, text="%d%%" % value)
            self._changed()

        slider = _Slider(self, left, centre, width, 20, 100, self.opacity,
                         changed)
        self._hit(y, ROW, _Wheel(slider.wheel))
        self._hits.append((left - self.s(8), y, left + width + self.s(8),
                           y + self.s(ROW), slider))
        return y + self.s(ROW) + self.s(GAP)

    def _status_row(self, y):
        """The Saving/Saved indicator that took the Save button's place."""
        self._dot = self.s(6)
        gap = self.s(5)
        right = self.s(WIDTH - PAD)
        centre = y + self.s(13)
        self._dots = []
        for index in range(3):
            x = right - self._dot - (2 - index) * (self._dot + gap)
            self._dots.append(self.canvas.create_image(
                x, centre - self._dot // 2, anchor="nw",
                image=self.sprites.disc(self._dot, BG, BG)))
        self._status_text = self._text(
            right - 3 * (self._dot + gap) - self.s(4), centre, "",
            self.font(11), DIM, anchor="e")
        return y + self.s(28)

    # -- events ------------------------------------------------------------
    def _bind(self):
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda _e: self._set_hover(None))
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.root.protocol("WM_DELETE_WINDOW", self._teardown)
        self.root.bind("<Escape>", lambda _e: self._escape())
        # A frameless window has no system menu, so Alt+F4 needs binding.
        self.root.bind("<Alt-F4>", lambda _e: self._teardown())

    def _escape(self):
        """Esc cancels a capture. It does not close the window - that is what
        the X is for, and losing the panel mid-edit surprised people.

        During a capture the hook swallows Esc and reports it as a cancel, so
        this only runs when the hook never saw the key: no hook installed, or an
        elevated window in the way. It still has to get the user out of the
        prompt.
        """
        if self._capturing:
            self._cancel_capture()

    def _find(self, x, y):
        for x0, y0, x1, y1, control in reversed(self._hits):
            if x0 <= x < x1 and y0 <= y < y1:
                return control
        return None

    def _set_hover(self, control):
        if control is self._hover:
            return
        if self._hover:
            self._hover.hover(False)
        self._hover = control
        if control:
            control.hover(True)
        cursor = control.cursor if control else ""
        if cursor != self._cursor:
            self._cursor = cursor
            self.canvas.configure(cursor=cursor)

    def _on_motion(self, event):
        if self._active is None:
            self._set_hover(self._find(event.x, event.y))

    def _on_press(self, event):
        self.pointer = (event.x_root, event.y_root)
        self._active = self._find(event.x, event.y)
        if self._active:
            self._set_hover(self._active)
            self._active.press(event.x, event.y)

    def _on_drag(self, event):
        self.pointer = (event.x_root, event.y_root)
        if self._active:
            self._active.drag(event.x, event.y)

    def _on_release(self, event):
        if self._active:
            self._active.release()
            self._active = None
        self._set_hover(self._find(event.x, event.y))

    def _on_wheel(self, event):
        steps = 1 if event.delta > 0 else -1
        for x0, y0, x1, y1, control in reversed(self._hits):
            if x0 <= event.x < x1 and y0 <= event.y < y1:
                if control.wheel(steps):
                    return

    # -- hotkey capture ----------------------------------------------------
    def _begin_capture(self):
        """Arm the hook: the next real chord it sees becomes the hotkey."""
        if self._capturing:                 # clicking again means "never mind"
            self._cancel_capture()
            return
        self._capturing = True
        self.field.set_text("%s   (Esc cancels)" % PROMPT, dim=True)
        # The hook calls back with three arguments, from its own thread, so the
        # chord is parked in a queue for _drain: Tk gets touched by one thread.
        self._listener.capture_next(
            lambda vk, mods, cancelled: self._captured.put_nowait(
                (vk, mods, cancelled)))

    def _cancel_capture(self):
        self._capturing = False
        self._listener.cancel_capture()
        self.field.set_text(keys.chord_text(self.vk, self.mods))

    def _drain(self):
        """The hook thread hands chords over here; Tk stays single-threaded."""
        if not self.alive():
            return
        if self.should_close and self.should_close():
            self._teardown()
            return
        try:
            while True:
                vk, mods, cancelled = self._captured.get_nowait()
                self._capturing = False
                if not cancelled:
                    self.vk, self.mods = vk, tuple(mods)
                    self._changed()
                self.field.set_text(keys.chord_text(self.vk, self.mods))
                self._refresh_caption()
        except queue.Empty:
            pass
        # The tray can flip "Start with Windows" while this window is open, and
        # both read the same cfg dict, so mirror it instead of fighting over it.
        if self._save_job is None and not self._dirty:
            wanted = bool(self._cfg["start_with_windows"])
            if wanted != self.startup:
                self.startup = wanted
                self._switches["startup"].set(wanted)
        self._drain_job = self.after(30, self._drain)

    def _refresh_caption(self):
        """Says what the switch does - except for the one awkward default,
        bare Tab, where what it does not do is the useful thing to know."""
        if not self.suppress and self.vk == keys.VK_TAB and not self.mods:
            text, fill = ("Tab still reaches other apps: it indents and "
                          "toggles", WARN)
        else:
            text, fill = "Nothing else will see this keystroke", DIM
        self.canvas.itemconfigure(self._caption, text=text, fill=fill)

    # -- saving ------------------------------------------------------------
    def _collect(self):
        return {
            "hotkey": {"vk": self.vk, "mods": list(self.mods),
                       "suppress": self.suppress},
            "overlay": {"enabled": self.badge, "size": self.size,
                        "margin": self.margin, "corner": self.corner,
                        "opacity": self.opacity},
            "audio": {"mute_all_inputs": self.mute_all},
            "feedback": {"sound": self.beep},
            "start_with_windows": self.startup,
        }

    def _changed(self):
        """Every control calls this. The write itself is debounced."""
        self._dirty = True
        if self._save_job:
            self.after_cancel(self._save_job)
        self._save_job = self.after(SAVE_DELAY, self._flush)

    def _flush(self, final=False):
        self._save_job = None
        if not self._dirty:
            return
        self._dirty = False
        self._save_seq += 1
        if final:
            self._write()               # closing down: no time for animation
            return
        self._show_saving()
        self.root.update_idletasks()    # paint "Saving" before touching disk
        self.after(20, self._write, self._save_seq)

    def _write(self, seq=None):
        ok = True
        try:
            self._on_apply(self._collect())
        except Exception as exc:
            ok = False
            print("CuteMute (settings): could not save: %s" % exc,
                  file=sys.stderr)
        if seq is not None and self.alive():
            # Hold the animation briefly: a status that flickers past unread is
            # worse than no status at all.
            self._status_jobs.append(
                self.after(SAVE_SHOWN, self._show_saved, seq, ok))

    def _stop_status(self):
        for job in self._status_jobs:
            self.after_cancel(job)
        self._status_jobs = []

    def _show_saving(self):
        self._stop_status()
        self.canvas.itemconfigure(self._status_text, text="Saving", fill=DIM)
        self._pulse(0)

    def _pulse(self, tick):
        if not self.alive():
            return
        for index, item in enumerate(self._dots):
            colour = TEXT if tick % 3 == index else BORDER
            self.canvas.itemconfigure(
                item, image=self.sprites.disc(self._dot, colour, BG))
        self._status_jobs.append(self.after(150, self._pulse, tick + 1))

    def _show_saved(self, seq, ok):
        if not self.alive() or seq != self._save_seq:
            return
        self._stop_status()
        self.canvas.itemconfigure(self._status_text,
                                  text="Saved" if ok else "Could not save",
                                  fill=DIM if ok else WARN)
        for index, item in enumerate(self._dots):
            colour = (ACCENT if ok else WARN) if index == 0 else BG
            self.canvas.itemconfigure(
                item, image=self.sprites.disc(self._dot, colour, BG))
        self._status_jobs.append(self.after(1400, self._fade, 1, ok))

    def _fade(self, step, ok):
        """Let the confirmation retire quietly instead of sitting there."""
        if not self.alive():
            return
        t = step / 8.0
        self.canvas.itemconfigure(self._status_text,
                                  fill=paint.mix(DIM if ok else WARN, BG, t))
        self.canvas.itemconfigure(
            self._dots[0],
            image=self.sprites.disc(
                self._dot, paint.mix(ACCENT if ok else WARN, BG, t), BG))
        if step < 8:
            self._status_jobs.append(self.after(45, self._fade, step + 1, ok))
        else:
            self.canvas.itemconfigure(self._status_text, text="")
