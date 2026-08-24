"""Procedural microphone badge, rendered by hand so we need no image files.

One rasteriser feeds three consumers: the layered-window overlay (premultiplied
BGRA), the tray icon (an HICON) and the .ico builder. Rendering is anti-aliased
by 4x4 supersampling and cached, so the whole cost is a few milliseconds once.
"""
import math
from functools import lru_cache

SS = 4  # supersamples per axis

RED = (0xE5, 0x48, 0x4D)
RED_DARK = (0xA3, 0x1D, 0x22)
GREEN = (0x2E, 0x9E, 0x68)
GREEN_DARK = (0x1B, 0x64, 0x42)
WHITE = (0xFF, 0xFF, 0xFF)


def _clamp01(v):
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def _seg_dist(px, py, ax, ay, bx, by):
    """Distance from a point to a line segment: gives us round-capped strokes."""
    dx, dy = bx - ax, by - ay
    span = dx * dx + dy * dy
    t = 0.0 if span < 1e-12 else _clamp01(((px - ax) * dx + (py - ay) * dy) / span)
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _round_rect(px, py, half, radius):
    """Signed-distance test for a rounded square centred on (0.5, 0.5)."""
    dx = abs(px - 0.5) - (half - radius)
    dy = abs(py - 0.5) - (half - radius)
    return math.hypot(max(dx, 0.0), max(dy, 0.0)) <= radius


# Every number the badge is made of, in a 0..1 unit square, in one place. The
# rasteriser below reads it; so does tools/make_brand.py, which writes the same
# mark out as SVG for the website. Two renderers, one geometry, no drift.
SHAPE = {
    "plate":   {"half": 0.500, "radius": 0.300},
    "fill":    {"half": 0.466, "radius": 0.278},
    "capsule": {"seg": (0.5, 0.225, 0.5, 0.400), "width": 0.112},
    "cradle":  {"centre": (0.5, 0.400), "inner": 0.170, "outer": 0.250,
                "below": 0.430},
    "stem":    {"seg": (0.5, 0.635, 0.5, 0.775), "width": 0.050},
    "slash":   {"seg": (0.145, 0.800, 0.855, 0.200), "width": 0.062,
                "cut": 0.148},
}


def _layers(muted):
    """Back-to-front list of (colour, inside-test) in a 0..1 unit square.

    A rounded square rather than a circle: at 20 px it leaves noticeably more
    room for the glyph, which is the difference between a readable mic and a
    red smudge.
    """
    base, edge = (RED, RED_DARK) if muted else (GREEN, GREEN_DARK)
    plate, fill = SHAPE["plate"], SHAPE["fill"]
    capsule, cradle = SHAPE["capsule"], SHAPE["cradle"]
    stem, slash = SHAPE["stem"], SHAPE["slash"]
    cx, cy = cradle["centre"]

    def in_plate(x, y):
        return _round_rect(x, y, plate["half"], plate["radius"])

    def in_fill(x, y):
        return _round_rect(x, y, fill["half"], fill["radius"])

    def in_capsule(x, y):
        return _seg_dist(x, y, *capsule["seg"]) <= capsule["width"]

    def in_cradle(x, y):
        return (cradle["inner"] <= math.hypot(x - cx, y - cy) <= cradle["outer"]
                and y >= cradle["below"])

    def in_stem(x, y):
        return _seg_dist(x, y, *stem["seg"]) <= stem["width"]

    # A wide same-colour "cut" under the white slash keeps the stroke separated
    # from the mic instead of merging into one blob at small sizes.
    def in_slash_cut(x, y):
        return _seg_dist(x, y, *slash["seg"]) <= slash["cut"]

    def in_slash(x, y):
        return _seg_dist(x, y, *slash["seg"]) <= slash["width"]

    out = [(edge, in_plate), (base, in_fill), (WHITE, in_capsule),
           (WHITE, in_cradle), (WHITE, in_stem)]
    if muted:
        out += [(edge, in_slash_cut), (WHITE, in_slash)]
    return out


@lru_cache(maxsize=32)
def render(size, muted):
    """Straight-alpha RGBA tuples, row-major top-down. Cached per (size, state)."""
    layers = _layers(bool(muted))
    step = 1.0 / (size * SS)
    half = step * 0.5
    weight = 1.0 / (SS * SS)
    pixels = []
    for py in range(size):
        for px in range(size):
            # Premultiplied accumulator; converted to straight alpha at the end.
            ar = ag = ab = aa = 0.0
            for colour, inside in layers:
                cov = 0.0
                for sy in range(SS):
                    y = (py * SS + sy) * step + half
                    for sx in range(SS):
                        if inside((px * SS + sx) * step + half, y):
                            cov += weight
                if cov <= 0.0:
                    continue
                keep = 1.0 - cov
                ar = colour[0] * cov + ar * keep
                ag = colour[1] * cov + ag * keep
                ab = colour[2] * cov + ab * keep
                aa = cov + aa * keep
            if aa <= 0.0:
                pixels.append((0, 0, 0, 0))
            else:
                pixels.append((min(255, int(ar / aa + 0.5)),
                               min(255, int(ag / aa + 0.5)),
                               min(255, int(ab / aa + 0.5)),
                               min(255, int(aa * 255.0 + 0.5))))
    return tuple(pixels)


def bgra_premultiplied(size, muted):
    """What UpdateLayeredWindow wants: 32bpp BGRA, alpha already multiplied in."""
    buf = bytearray(size * size * 4)
    for i, (r, g, b, a) in enumerate(render(size, muted)):
        o = i * 4
        buf[o] = b * a // 255
        buf[o + 1] = g * a // 255
        buf[o + 2] = r * a // 255
        buf[o + 3] = a
    return bytes(buf)


def bgra_straight(size, muted):
    """32bpp BGRA with straight alpha, as .ico and HICON colour bitmaps use."""
    buf = bytearray(size * size * 4)
    for i, (r, g, b, a) in enumerate(render(size, muted)):
        o = i * 4
        buf[o] = b
        buf[o + 1] = g
        buf[o + 2] = r
        buf[o + 3] = a
    return bytes(buf)


def rgba(size, muted):
    """Straight RGBA bytes (used by the PNG preview tool)."""
    buf = bytearray(size * size * 4)
    for i, px in enumerate(render(size, muted)):
        buf[i * 4:i * 4 + 4] = bytes(px)
    return bytes(buf)
