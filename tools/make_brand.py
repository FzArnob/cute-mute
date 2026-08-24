"""Build every brand asset the website needs, from the same badge geometry.

    python tools\\make_brand.py            # -> docs/assets/

`cutemute.iconart.SHAPE` is the single definition of the mark. This writes it
out twice: as SVG (those numbers turned into paths, for the page and for anyone
who wants the logo) and as PNG (rasterised by iconart itself, so the favicon is
literally the tray icon). The wordmark on the social card is stroked from
polylines here rather than set in a font, for the same reason the badge is: no
asset to lose, no licence to honour, and it renders identically everywhere.

Pure stdlib. No Pillow, no cairosvg, nothing to install.
"""
import math
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cutemute import APP_NAME, TAGLINE, iconart  # noqa: E402
from cutemute.iconart import (GREEN, GREEN_DARK, RED, RED_DARK,  # noqa: E402
                              SHAPE, WHITE)

OUT = Path(__file__).resolve().parents[1] / "docs" / "assets"

BG = (0x0E, 0x0E, 0x10)         # theme.BG, the site's ground
BG_LIFT = (0x1A, 0x1A, 0x20)    # top of the card's wash
TEXT = (0xF3, 0xF3, 0xF5)       # theme.TEXT
DIM = (0x8B, 0x8B, 0x94)        # theme.DIM

SS = 4  # supersamples per axis, as iconart uses


def hexc(rgb):
    return "#%02x%02x%02x" % rgb


# --------------------------------------------------------------------------- #
# SVG: SHAPE, written out as paths
# --------------------------------------------------------------------------- #

def _cradle_arc():
    """The mic cradle as one SVG elliptical arc.

    iconart tests an annulus clipped to y >= `below`. The same curve as a
    stroke is the mid-radius circle, stroked (outer - inner) wide, drawn
    between the two points where that circle crosses y = below.
    """
    cx, cy = SHAPE["cradle"]["centre"]
    inner, outer = SHAPE["cradle"]["inner"], SHAPE["cradle"]["outer"]
    below = SHAPE["cradle"]["below"]
    radius = (inner + outer) / 2.0
    dy = below - cy
    dx = math.sqrt(max(radius * radius - dy * dy, 0.0))
    sweep = math.degrees(math.pi - 2.0 * math.asin(min(1.0, dy / radius)))
    # Sweep flag 0 keeps the arc on the far side of the chord from the centre:
    # left crossing, round the bottom, right crossing.
    return ("M %.5f %.5f A %.5f %.5f 0 %d 0 %.5f %.5f"
            % (cx - dx, below, radius, radius,
               1 if sweep > 180.0 else 0, cx + dx, below))


def _line(seg, half_width, colour, cap="round"):
    """One of iconart's segment tests, as an SVG stroke of twice the radius."""
    ax, ay, bx, by = seg
    return ('  <line x1="%.5f" y1="%.5f" x2="%.5f" y2="%.5f" stroke="%s" '
            'stroke-width="%.5f" stroke-linecap="%s"/>'
            % (ax, ay, bx, by, hexc(colour), half_width * 2.0, cap))


def svg(muted, size=512):
    """The badge as SVG, on a 0..1 viewBox, so it scales to anything."""
    base, edge = (RED, RED_DARK) if muted else (GREEN, GREEN_DARK)
    cradle, slash = SHAPE["cradle"], SHAPE["slash"]
    state = "muted" if muted else "live"

    def rect(shape, colour):
        half, radius = shape["half"], shape["radius"]
        return ('  <rect x="%.5f" y="%.5f" width="%.5f" height="%.5f" '
                'rx="%.5f" fill="%s"/>'
                % (0.5 - half, 0.5 - half, half * 2, half * 2, radius,
                   hexc(colour)))

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1" '
        'width="%d" height="%d" role="img" aria-label="%s microphone badge, %s">'
        % (size, size, APP_NAME, state),
        "  <title>%s -- microphone %s</title>" % (APP_NAME, state),
        rect(SHAPE["plate"], edge),
        rect(SHAPE["fill"], base),
        _line(SHAPE["capsule"]["seg"], SHAPE["capsule"]["width"], WHITE),
        ('  <path d="%s" fill="none" stroke="%s" stroke-width="%.5f"/>'
         % (_cradle_arc(), hexc(WHITE), cradle["outer"] - cradle["inner"])),
        _line(SHAPE["stem"]["seg"], SHAPE["stem"]["width"], WHITE),
    ]
    if muted:
        parts.append(_line(slash["seg"], slash["cut"], edge))
        parts.append(_line(slash["seg"], slash["width"], WHITE))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


# --------------------------------------------------------------------------- #
# PNG
# --------------------------------------------------------------------------- #

def write_png(path, width, height, pixels, alpha):
    """Minimal PNG writer: 8-bit, colour type 6 (RGBA) or 2 (RGB)."""
    channels = 4 if alpha else 3
    stride = width * channels
    raw = bytearray()
    for row in range(height):
        raw.append(0)                                  # filter type: none
        raw.extend(pixels[row * stride:(row + 1) * stride])

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    Path(path).write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8,
                                     6 if alpha else 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b""))
    return Path(path).stat().st_size


def icon_png(path, size, muted=True):
    """The tray icon at `size`, straight from the rasteriser, alpha intact."""
    return write_png(path, size, size, iconart.rgba(size, muted), alpha=True)


# --------------------------------------------------------------------------- #
# The wordmark, stroked from polylines
# --------------------------------------------------------------------------- #

def _arc(cx, cy, radius, start, end, steps=30):
    """A polyline along a circular arc; angles in degrees, screen y down."""
    return [(cx + radius * math.cos(math.radians(a)),
             cy + radius * math.sin(math.radians(a)))
            for a in (start + (end - start) * i / steps
                      for i in range(steps + 1))]


# Each glyph is a list of polylines in its own box, x and y both 0..1 with y
# downwards, plus the advance: how wide that box is relative to the cap height.
# Only five letters spell CUTEMUTE, which is the whole reason this is tractable.

_U_BOWL = 0.47


def _u():
    """The U: verticals down to a bowl that bottoms out on the baseline.

    Swept 180 -> 0, not 180 -> 360, because screen y points down: sin is
    positive *below* the centre, so the second of those would arc over the top
    and give you a rather surprised-looking n.
    """
    cy = 1.0 - _U_BOWL
    return ([[(0.5 - _U_BOWL, 0.0), (0.5 - _U_BOWL, cy)]
             + _arc(0.5, cy, _U_BOWL, 180, 0)
             + [(0.5 + _U_BOWL, 0.0)]], 1.02)


GLYPHS = {
    "C": ([_arc(0.47, 0.5, 0.47, -54, -306)], 0.96),
    "U": _u(),
    "T": ([[(0.0, 0.0), (1.0, 0.0)], [(0.5, 0.0), (0.5, 1.0)]], 1.00),
    "E": ([[(0.94, 0.0), (0.0, 0.0), (0.0, 1.0), (0.94, 1.0)],
           [(0.0, 0.5), (0.80, 0.5)]], 0.92),
    "M": ([[(0.0, 1.0), (0.0, 0.0), (0.5, 0.64), (1.0, 0.0),
            (1.0, 1.0)]], 1.16),
}

TRACKING = 0.15     # letter spacing, as a fraction of the cap height


def _wordmark_ems(text):
    """How wide the word is in cap heights -- so a cap size can be fitted."""
    return (sum(GLYPHS[ch][1] for ch in text)
            + TRACKING * (len(text) - 1))


def _wordmark(text, cap, x, y, weight):
    """(segments, width): the word as absolute (ax, ay, bx, by, half) tuples."""
    segments = []
    pen = x
    for ch in text:
        polylines, advance = GLYPHS[ch]
        for line in polylines:
            points = [(pen + px * advance * cap, y + py * cap)
                      for px, py in line]
            for i in range(len(points) - 1):
                (ax, ay), (bx, by) = points[i], points[i + 1]
                segments.append((ax, ay, bx, by, weight * 0.5))
        pen += advance * cap + cap * TRACKING
    return segments, pen - x - cap * TRACKING


def _rule(x, y, span, thickness):
    """One centred hairline under the wordmark."""
    return [(x - span / 2.0, y, x + span / 2.0, y, thickness / 2.0)]


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    span = dx * dx + dy * dy
    t = 0.0 if span < 1e-12 else ((px - ax) * dx + (py - ay) * dy) / span
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _draw_strokes(canvas, width, height, segments, colour):
    """Composite round-capped anti-aliased strokes, one bounding box at a time."""
    for ax, ay, bx, by, half in segments:
        x0 = max(0, int(min(ax, bx) - half) - 2)
        x1 = min(width, int(max(ax, bx) + half) + 3)
        y0 = max(0, int(min(ay, by) - half) - 2)
        y1 = min(height, int(max(ay, by) + half) + 3)
        for py in range(y0, y1):
            for px in range(x0, x1):
                cov = 0.0
                for sy in range(SS):
                    y = py + (sy + 0.5) / SS
                    for sx in range(SS):
                        if _seg_dist(px + (sx + 0.5) / SS, y,
                                     ax, ay, bx, by) <= half:
                            cov += 1.0 / (SS * SS)
                if cov <= 0.0:
                    continue
                o = (py * width + px) * 3
                for i in range(3):
                    canvas[o + i] = int(colour[i] * cov
                                        + canvas[o + i] * (1.0 - cov) + 0.5)


# --------------------------------------------------------------------------- #
# The social card
# --------------------------------------------------------------------------- #

def paint_card(path, width=1200, height=630):
    """The 1200x630 og:image: the badge, the wordmark, and a hairline.

    A vertical wash for the ground, a radial bloom in the badge's own red
    behind it, the badge composited over that with its real alpha, then
    anti-aliased strokes for the wordmark. The three sit as one centred block,
    and the cap height is fitted to the width left over, so the word cannot
    run off the edge if a letter's advance is ever retuned.

    No tagline. The alphabet here is the five letters that spell CUTEMUTE, and
    a card mostly seen as a chat thumbnail is better with nothing under the
    wordmark than with type too small to resolve.
    """
    canvas = bytearray(width * height * 3)

    word = APP_NAME.upper()
    cap = min(96.0, (width - 2 * 132) / _wordmark_ems(word))
    badge, gap, rule_gap = 212, 76, 46

    bx = (width - badge) // 2
    by = int((height - (badge + gap + cap + rule_gap)) / 2)
    bloom_x, bloom_y = bx + badge / 2.0, by + badge / 2.0
    bloom_r = badge * 3.0

    for py in range(height):
        wash = py / (height - 1.0)
        row = (py * width) * 3
        for px in range(width):
            r = BG_LIFT[0] + (BG[0] - BG_LIFT[0]) * wash
            g = BG_LIFT[1] + (BG[1] - BG_LIFT[1]) * wash
            b = BG_LIFT[2] + (BG[2] - BG_LIFT[2]) * wash
            # Quadratic falloff, so the glow has no visible edge.
            d = math.hypot(px - bloom_x, py - bloom_y)
            if d < bloom_r:
                k = (1.0 - d / bloom_r) ** 2 * 0.32
                r += (RED[0] - r) * k
                g += (RED[1] - g) * k
                b += (RED[2] - b) * k
            o = row + px * 3
            canvas[o] = int(r + 0.5)
            canvas[o + 1] = int(g + 0.5)
            canvas[o + 2] = int(b + 0.5)

    art = iconart.render(badge, True)
    for y in range(badge):
        for x in range(badge):
            sr, sg, sb, sa = art[y * badge + x]
            if not sa:
                continue
            o = ((by + y) * width + (bx + x)) * 3
            canvas[o] = (sr * sa + canvas[o] * (255 - sa)) // 255
            canvas[o + 1] = (sg * sa + canvas[o + 1] * (255 - sa)) // 255
            canvas[o + 2] = (sb * sa + canvas[o + 2] * (255 - sa)) // 255

    word_y = by + badge + gap
    run = _wordmark_ems(word) * cap
    strokes, run = _wordmark(word, cap, (width - run) / 2.0, word_y,
                             cap * 0.185)
    hairline = _rule(width / 2.0, word_y + cap + rule_gap, run * 0.94, 5)

    _draw_strokes(canvas, width, height, strokes, TEXT)
    _draw_strokes(canvas, width, height, hairline, DIM)

    return write_png(path, width, height, canvas, alpha=False)


# --------------------------------------------------------------------------- #

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    made = []

    for muted, name in ((True, "mark-muted.svg"), (False, "mark-live.svg")):
        # An explicit LF, plus the `*.svg eol=lf` rule in .gitattributes, keeps
        # these byte-identical wherever they are generated. Left to itself,
        # write_text would emit CRLF on Windows and LF elsewhere, and
        # build.yml's staleness diff would fail on every run for no reason.
        (OUT / name).write_text(svg(muted), encoding="utf-8", newline="\n")
        made.append((name, (OUT / name).stat().st_size))

    for size in (32, 180, 512):
        made.append(("icon-%d.png" % size,
                     icon_png(OUT / ("icon-%d.png" % size), size)))
    made.append(("icon-live-512.png",
                 icon_png(OUT / "icon-live-512.png", 512, muted=False)))
    made.append(("og.png", paint_card(OUT / "og.png")))

    for name, size in made:
        print("  %-20s %8d bytes" % (name, size))
    print("wrote %d files to %s" % (len(made), OUT))
    print('tagline, for the page: "%s"' % TAGLINE)


if __name__ == "__main__":
    main()
