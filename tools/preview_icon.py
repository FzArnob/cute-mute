"""Render the CuteMute badge to a PNG contact sheet so it can be eyeballed.

    python tools\\preview_icon.py out.png

Zoomed rows show the pixel grid; the last row of each panel is 1:1 actual size,
which is the only view that really tells you if 20 px works.
Pure stdlib PNG writer, no Pillow.
"""
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cutemute import iconart  # noqa: E402

ZOOMS = [(20, 8), (32, 5), (64, 2)]
ACTUAL = [16, 20, 24, 32, 48]
GAP = 16
LIGHT = (0xF2, 0xF3, 0xF5)
DARK = (0x1E, 0x20, 0x24)


def write_png(path, width, height, canvas):
    raw = bytearray()
    stride = width * 3
    for r in range(height):
        raw.append(0)                      # filter type 0
        raw.extend(canvas[r * stride:(r + 1) * stride])

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    Path(path).write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b""))


def blit(canvas, cw, x0, y0, size, zoom, muted, bg):
    px = iconart.render(size, muted)
    for sy in range(size * zoom):
        row = px[(sy // zoom) * size:(sy // zoom + 1) * size]
        for sx in range(size * zoom):
            r, g, b, a = row[sx // zoom]
            o = ((y0 + sy) * cw + (x0 + sx)) * 3
            canvas[o] = (r * a + bg[0] * (255 - a)) // 255
            canvas[o + 1] = (g * a + bg[1] * (255 - a)) // 255
            canvas[o + 2] = (b * a + bg[2] * (255 - a)) // 255


def main(out):
    cell = max(s * z for s, z in ZOOMS)
    width = GAP + len(ZOOMS) * (cell + GAP)
    strip = max(ACTUAL) + GAP
    block = GAP + 2 * (cell + GAP) + strip
    height = 2 * block

    canvas = bytearray()
    for bg in (LIGHT, DARK):
        canvas += bytearray(bytes(bg) * (width * block))

    for bi, bg in enumerate((LIGHT, DARK)):
        top = bi * block
        for mi, muted in enumerate((True, False)):
            y = top + GAP + mi * (cell + GAP)
            for ci, (size, zoom) in enumerate(ZOOMS):
                x = GAP + ci * (cell + GAP)
                blit(canvas, width, x + (cell - size * zoom) // 2,
                     y + (cell - size * zoom) // 2, size, zoom, muted, bg)
        # 1:1 strip: muted set then live set, on one baseline
        y = top + GAP + 2 * (cell + GAP)
        x = GAP
        for muted in (True, False):
            for size in ACTUAL:
                blit(canvas, width, x, y + (max(ACTUAL) - size), size, 1, muted, bg)
                x += size + 10
            x += GAP

    write_png(out, width, height, canvas)
    print("wrote %s (%dx%d)" % (out, width, height))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "preview.png")
