"""The simple settings window.

tkinter, and created only when the user asks for it, then torn down again -
so the resident app keeps no GUI toolkit state while it is just sitting in the
tray. Hotkey capture is done through the global keyboard hook rather than Tk key
events, which is what lets it report exact virtual-key codes (including keys Tk
never sees, like media keys) and offer to swallow them.
"""
import queue
import tkinter as tk
from tkinter import ttk

from . import keys
from .config import CORNERS
from .w32 import GA_ROOT, ICON_BIG, ICON_SMALL, WM_SETICON, system_dpi, user32
from .winicon import destroy_hicon, make_hicon

CORNER_LABELS = {
    "bottom-right": "Bottom right",
    "bottom-left": "Bottom left",
    "top-right": "Top right",
    "top-left": "Top left",
}
LABEL_TO_CORNER = {v: k for k, v in CORNER_LABELS.items()}

PROMPT = "Press a key or combination...   (Esc cancels)"


class SettingsWindow:
    """Modal-ish settings dialog. run() blocks until the window closes."""

    def __init__(self, cfg, listener, on_apply, on_hwnd=None):
        self._cfg = cfg
        self._listener = listener
        self._on_apply = on_apply
        self._on_hwnd = on_hwnd
        self._captured = queue.Queue()
        self._capturing = False
        self._icon = None
        # Set by the app so a tray "Exit" can close this window from elsewhere.
        self.should_close = None

        self.vk = int(cfg["hotkey"]["vk"])
        self.mods = tuple(cfg["hotkey"]["mods"])

    # -- lifecycle ---------------------------------------------------------
    def run(self):
        self.root = tk.Tk()
        self.root.title("CuteMute")
        self.root.resizable(False, False)
        # The process is per-monitor DPI aware, so Tk needs telling the scale.
        self.root.tk.call("tk", "scaling", system_dpi() / 72.0)
        default = ("Segoe UI", 9)
        self.root.option_add("*Font", default)

        self._build()
        self._centre()
        self.root.protocol("WM_DELETE_WINDOW", self._cancel)
        self.root.bind("<Escape>", lambda _e: self._cancel())
        self.root.after(30, self._drain)

        hwnd = user32.GetAncestor(self.root.winfo_id(), GA_ROOT)
        try:
            self._icon = make_hicon(32, True)
            if self._icon and hwnd:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, self._icon)
                user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, self._icon)
        except Exception:
            pass
        if self._on_hwnd:
            self._on_hwnd(hwnd)
        self.root.lift()
        self.root.focus_force()
        self.root.mainloop()

    def _teardown(self):
        self._capturing = False
        self._listener.cancel_capture()
        if self._on_hwnd:
            self._on_hwnd(None)
        destroy_hicon(self._icon)
        self._icon = None
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _centre(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() - width) // 2
        y = (self.root.winfo_screenheight() - height) // 3
        self.root.geometry("+%d+%d" % (max(0, x), max(0, y)))

    # -- layout ------------------------------------------------------------
    def _build(self):
        pad = {"padx": 10, "pady": 4}
        outer = ttk.Frame(self.root, padding=12)
        outer.grid(sticky="nsew")

        ttk.Label(outer, text="CuteMute",
                  font=("Segoe UI Semibold", 13)).grid(
                      row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(outer, text="One key to mute your microphone.",
                  foreground="#666666").grid(row=1, column=0, columnspan=2,
                                             sticky="w", pady=(0, 10))

        # --- hotkey -------------------------------------------------------
        box = ttk.LabelFrame(outer, text=" Shortcut ", padding=10)
        box.grid(row=2, column=0, columnspan=2, sticky="ew")
        box.columnconfigure(1, weight=1)

        ttk.Label(box, text="Toggle key").grid(row=0, column=0, sticky="w")
        self._chord_var = tk.StringVar(value=keys.chord_text(self.vk, self.mods))
        self._chord_label = ttk.Label(box, textvariable=self._chord_var,
                                      font=("Consolas", 10), anchor="center",
                                      relief="solid", borderwidth=1, padding=(8, 4))
        self._chord_label.grid(row=0, column=1, sticky="ew", padx=8)
        self._change_btn = ttk.Button(box, text="Change", width=10,
                                      command=self._begin_capture)
        self._change_btn.grid(row=0, column=2)

        self._suppress_var = tk.BooleanVar(value=self._cfg["hotkey"]["suppress"])
        ttk.Checkbutton(box, text="Block the key from other apps",
                        variable=self._suppress_var,
                        command=self._hint).grid(row=1, column=0, columnspan=3,
                                                 sticky="w", pady=(8, 0))
        self._hint_label = ttk.Label(box, text="", foreground="#a06000",
                                     wraplength=340, justify="left")
        self._hint_label.grid(row=2, column=0, columnspan=3, sticky="w")

        # --- badge --------------------------------------------------------
        badge = ttk.LabelFrame(outer, text=" Muted badge ", padding=10)
        badge.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        self._overlay_var = tk.BooleanVar(value=self._cfg["overlay"]["enabled"])
        ttk.Checkbutton(badge, text="Show the badge on top of everything "
                                    "while muted",
                        variable=self._overlay_var).grid(row=0, column=0,
                                                         columnspan=4, sticky="w")

        ttk.Label(badge, text="Size").grid(row=1, column=0, sticky="w",
                                           pady=(8, 0))
        self._size_var = tk.IntVar(value=self._cfg["overlay"]["size"])
        ttk.Spinbox(badge, from_=10, to=128, width=5, textvariable=self._size_var,
                    increment=2).grid(row=1, column=1, sticky="w", padx=(6, 16),
                                      pady=(8, 0))

        ttk.Label(badge, text="Margin").grid(row=1, column=2, sticky="w",
                                             pady=(8, 0))
        self._margin_var = tk.IntVar(value=self._cfg["overlay"]["margin"])
        ttk.Spinbox(badge, from_=0, to=400, width=5,
                    textvariable=self._margin_var).grid(row=1, column=3,
                                                        sticky="w", padx=6,
                                                        pady=(8, 0))

        ttk.Label(badge, text="Corner").grid(row=2, column=0, sticky="w",
                                             pady=(6, 0))
        self._corner_var = tk.StringVar(
            value=CORNER_LABELS[self._cfg["overlay"]["corner"]])
        ttk.Combobox(badge, values=[CORNER_LABELS[c] for c in CORNERS],
                     textvariable=self._corner_var, state="readonly",
                     width=14).grid(row=2, column=1, columnspan=3, sticky="w",
                                    padx=6, pady=(6, 0))

        ttk.Label(badge, text="Opacity").grid(row=3, column=0, sticky="w",
                                              pady=(6, 0))
        self._opacity_var = tk.IntVar(value=self._cfg["overlay"]["opacity"])
        self._opacity_text = tk.StringVar()
        scale = ttk.Scale(badge, from_=20, to=100, orient="horizontal",
                          command=self._on_opacity)
        scale.set(self._cfg["overlay"]["opacity"])
        scale.grid(row=3, column=1, columnspan=2, sticky="ew", padx=6,
                   pady=(6, 0))
        ttk.Label(badge, textvariable=self._opacity_text, width=5).grid(
            row=3, column=3, sticky="w", pady=(6, 0))
        self._on_opacity(self._cfg["overlay"]["opacity"])

        # --- behaviour ----------------------------------------------------
        beh = ttk.LabelFrame(outer, text=" Behaviour ", padding=10)
        beh.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self._all_inputs_var = tk.BooleanVar(
            value=self._cfg["audio"]["mute_all_inputs"])
        ttk.Checkbutton(beh, text="Mute every input device, not just the default",
                        variable=self._all_inputs_var).grid(row=0, column=0,
                                                            sticky="w")
        self._sound_var = tk.BooleanVar(value=self._cfg["feedback"]["sound"])
        ttk.Checkbutton(beh, text="Play a short beep when toggling",
                        variable=self._sound_var).grid(row=1, column=0, sticky="w")
        self._startup_var = tk.BooleanVar(value=self._cfg["start_with_windows"])
        ttk.Checkbutton(beh, text="Start CuteMute with Windows",
                        variable=self._startup_var).grid(row=2, column=0,
                                                         sticky="w")

        # --- buttons ------------------------------------------------------
        buttons = ttk.Frame(outer)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Cancel", width=10,
                   command=self._cancel).grid(row=0, column=0, padx=(0, 8))
        self._save_btn = ttk.Button(buttons, text="Save", width=10,
                                    command=self._save)
        self._save_btn.grid(row=0, column=1)
        self.root.bind("<Return>", lambda _e: self._save())

        self._hint()

    def _on_opacity(self, value):
        percent = int(round(float(value)))
        self._opacity_var.set(percent)
        self._opacity_text.set("%d%%" % percent)

    def _hint(self):
        """Warn about the one genuinely awkward default: bare Tab."""
        if self.vk == keys.VK_TAB and not self.mods and not self._suppress_var.get():
            self._hint_label.configure(
                text="Tab still reaches other apps, so it will both indent and "
                     "toggle. Tick the box above, or pick a spare key.")
        elif self._suppress_var.get():
            self._hint_label.configure(
                text="%s will no longer reach any other app."
                     % keys.chord_text(self.vk, self.mods))
        else:
            self._hint_label.configure(text="")

    # -- hotkey capture ----------------------------------------------------
    def _begin_capture(self):
        if self._capturing:
            return
        self._capturing = True
        self._chord_var.set(PROMPT)
        self._change_btn.state(["disabled"])
        self._listener.capture_next(self._captured.put_nowait)

    def _drain(self):
        """Hook thread hands chords over here; Tk stays single-threaded."""
        if self.should_close and self.should_close():
            self._teardown()
            return
        try:
            while True:
                vk, mods, cancelled = self._captured.get_nowait()
                self._capturing = False
                self._change_btn.state(["!disabled"])
                if not cancelled:
                    self.vk, self.mods = vk, tuple(mods)
                self._chord_var.set(keys.chord_text(self.vk, self.mods))
                self._hint()
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(30, self._drain)

    # -- results -----------------------------------------------------------
    def _collect(self):
        def clamp(var, lo, hi, fallback):
            try:
                return max(lo, min(hi, int(var.get())))
            except (tk.TclError, ValueError):
                return fallback

        return {
            "hotkey": {"vk": self.vk, "mods": list(self.mods),
                       "suppress": bool(self._suppress_var.get())},
            "overlay": {
                "enabled": bool(self._overlay_var.get()),
                "size": clamp(self._size_var, 10, 128, 20),
                "margin": clamp(self._margin_var, 0, 400, 8),
                "corner": LABEL_TO_CORNER.get(self._corner_var.get(),
                                              "bottom-right"),
                "opacity": clamp(self._opacity_var, 20, 100, 100),
            },
            "audio": {"mute_all_inputs": bool(self._all_inputs_var.get())},
            "feedback": {"sound": bool(self._sound_var.get())},
            "start_with_windows": bool(self._startup_var.get()),
        }

    def _save(self):
        self._on_apply(self._collect())
        self._teardown()

    def _cancel(self):
        self._teardown()
