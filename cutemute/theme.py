"""One palette, shared by the settings window and the tray menu.

Two very different renderers use these: Tk canvas sprites (paint.py) and raw
GDI (menu.py). Keeping the colours in one place is the only reason the menu
that pops out of the tray looks like it belongs to the panel behind it.
"""

BG = "#0e0e10"              # the window
CAPTION = "#17171a"         # the title bar we draw ourselves
CAPTION_HOVER = "#2a2a31"
CLOSE_HOVER = "#c42b1c"     # Windows' own colour for a close button
TITLE = "#e9e9ec"
TILE = "#1c1c20"            # a row, and the tray menu's background
TILE_HOVER = "#232329"
MENU_HOVER = "#2c2c33"      # a menu row needs more lift than a panel row
FIELD = "#16161a"           # the hotkey box, sunk into its row
CTRL = "#2b2b31"            # small buttons
CTRL_HOVER = "#35353d"
CTRL_DOWN = "#3f3f49"
CTRL_ON = "#3d3d47"         # the chosen corner
BORDER = "#3a3a42"
BORDER_HOVER = "#55555f"
TEXT = "#f3f3f5"
DIM = "#8b8b94"
FAINT = "#5a5a63"
SECTION = "#74747d"
ACCENT = "#2f7ce8"
ACCENT_HOVER = "#3d88f0"
TRACK = "#3b3b43"
TRACK_FILL = "#8b8b94"
KNOB_OFF = "#9b9ba4"
KNOB_ON = "#ffffff"
WARN = "#d9a03a"
