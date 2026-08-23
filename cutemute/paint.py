"""Anti-aliased sprites for the settings window, drawn without dependencies.

Tk's canvas cannot anti-alias a rounded corner and Tk 8.6's PhotoImage cannot
even parse an alpha channel, so every rounded shape in the window is rasterised
here instead: coverage from 4x4 supersampling, blended against the known solid
colour the sprite sits on, handed to Tk as a plain RGB image.

Caching happens at two levels, because the window is built and thrown away
every time it is opened. The pixel rows are pure data and are cached for the
life of the process; PhotoImage objects belong to one Tk interpreter, so they
live in a per-window Sprites bag that dies with it.

Only the corners of a rounded rectangle need sampling - the rest is a uniform
row built once and repeated - which keeps a full-width row tile at a couple of
milliseconds instead of a couple of hundred.
"""
import functools
import math
import tkinter as tk

from . import iconart

SS = 4                          # supersamples per axis
_WEIGHT = 1.0 / (SS * SS)


def _rgb(colour):
    """'#rrggbb' -> (r, g, b)."""
    return (int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16))


def _hex(colour):
    return "#%02x%02x%02x" % (int(colour[0] + 0.5), int(colour[1] + 0.5),
                              int(colour[2] + 0.5))


def _over(top, bottom, alpha):
    """Composite `top` over `bottom` with coverage `alpha`."""
    keep = 1.0 - alpha
    return (top[0] * alpha + bottom[0] * keep,
            top[1] * alpha + bottom[1] * keep,
            top[2] * alpha + bottom[2] * keep)


def mix(a, b, t):
    """Blend two '#rrggbb' colours; t=0 is all of `a`, t=1 all of `b`."""
    return _hex(_over(_rgb(b), _rgb(a), max(0.0, min(1.0, t))))


def _rect_coverage(px, py, w, h, r):
    """How much of pixel (px, py) a rounded rect [0,w]x[0,h] of radius r covers.

    Clamping the sample point into the inner rectangle and measuring from there
    is exact for the whole plane, corners included, and costs two comparisons.
    """
    cov = 0.0
    far_x, far_y = w - r, h - r
    for sy in range(SS):
        y = py + (sy + 0.5) / SS
        cy = r if y < r else (far_y if y > far_y else y)
        dy = y - cy
        for sx in range(SS):
            x = px + (sx + 0.5) / SS
            cx = r if x < r else (far_x if x > far_x else x)
            dx = x - cx
            if dx * dx + dy * dy <= r * r:
                cov += _WEIGHT
    return cov


def _disc_coverage(px, py, cx, cy, r):
    cov = 0.0
    for sy in range(SS):
        dy = py + (sy + 0.5) / SS - cy
        for sx in range(SS):
            dx = px + (sx + 0.5) / SS - cx
            if dx * dx + dy * dy <= r * r:
                cov += _WEIGHT
    return cov


def _segment_distance(px, py, ax, ay, bx, by):
    """Distance from a point to a line segment, for round-capped strokes."""
    dx, dy = bx - ax, by - ay
    span = dx * dx + dy * dy
    t = 0.0 if span < 1e-12 else ((px - ax) * dx + (py - ay) * dy) / span
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


@functools.lru_cache(maxsize=512)
def _rounded_rows(w, h, radius, fill, bg, border, border_colour):
    """Rows of hex colours for a rounded rectangle, optionally with a border."""
    r = min(radius, w / 2.0, h / 2.0)
    bg_rgb, fill_rgb = _rgb(bg), _rgb(fill)
    edge_rgb = _rgb(border_colour) if border and border_colour else fill_rgb
    solid, edge = _hex(fill_rgb), _hex(edge_rgb)
    # Sampling is only needed where the curve is; `band` also covers the border
    # so a square-cornered bordered rect still gets its top and bottom edges.
    band = max(int(r + 0.999), border)

    def sample(px, py):
        colour = _over(edge_rgb if border else fill_rgb, bg_rgb,
                       _rect_coverage(px, py, w, h, r))
        if border:
            colour = _over(fill_rgb, colour,
                           _rect_coverage(px - border, py - border,
                                          w - 2 * border, h - 2 * border,
                                          max(r - border, 0.0)))
        return _hex(colour)

    def flat(px, py):
        if border and (px < border or py < border
                       or px >= w - border or py >= h - border):
            return edge
        return solid

    middle = None
    rows = []
    for py in range(h):
        if band <= py < h - band:
            if middle is None:
                middle = " ".join(flat(px, py) for px in range(w))
            rows.append(middle)
            continue
        rows.append(" ".join(
            sample(px, py) if px < band or px >= w - band else flat(px, py)
            for px in range(w)))
    return tuple(rows)


@functools.lru_cache(maxsize=64)
def _handle_rows(d, band, left, right, fill, bg):
    """A slider handle with its own slice of the track baked in.

    The track either side of the handle is a plain rectangle, so the handle has
    to carry those same colours across its middle: anti-aliasing the disc
    against the row background instead leaves a pale seam where the line meets
    it.
    """
    disc, base_bg = _rgb(fill), _rgb(bg)
    base_left, base_right = _rgb(left), _rgb(right)
    centre = d / 2.0
    top = (d - band) // 2
    rows = []
    for py in range(d):
        in_band = top <= py < top + band
        cells = []
        for px in range(d):
            base = base_bg
            if in_band:
                base = base_left if px + 0.5 < centre else base_right
            cov = _disc_coverage(px, py, centre, centre, centre)
            cells.append(_hex(_over(disc, base, cov)) if cov else _hex(base))
        rows.append(" ".join(cells))
    return tuple(rows)


@functools.lru_cache(maxsize=128)
def _stroke_rows(w, h, segments, width, colour, bg):
    """Round-capped anti-aliased strokes: the close cross, and anything else
    that is not axis-aligned enough to look right as a plain rectangle."""
    ink, base = _rgb(colour), _rgb(bg)
    flat, half = _hex(base), width / 2.0
    rows = []
    for py in range(h):
        cells = []
        for px in range(w):
            cov = 0.0
            for sy in range(SS):
                y = py + (sy + 0.5) / SS
                for sx in range(SS):
                    x = px + (sx + 0.5) / SS
                    for ax, ay, bx, by in segments:
                        if _segment_distance(x, y, ax, ay, bx, by) <= half:
                            cov += _WEIGHT
                            break
            cells.append(_hex(_over(ink, base, cov)) if cov else flat)
        rows.append(" ".join(cells))
    return tuple(rows)


@functools.lru_cache(maxsize=16)
def _badge_rows(size, muted, bg):
    """The mic badge itself, flattened onto a solid colour.

    Same rasteriser as the tray icon and the overlay, so the title bar cannot
    drift away from the rest of the app.
    """
    base = _rgb(bg)
    pixels = iconart.render(size, muted)
    rows = []
    for py in range(size):
        cells = []
        for px in range(size):
            r, g, b, a = pixels[py * size + px]
            cells.append(_hex(_over((r, g, b), base, a / 255.0)))
        rows.append(" ".join(cells))
    return tuple(rows)


class Sprites:
    """The PhotoImages one settings window is using; dropped with the window."""

    def __init__(self):
        self._images = {}

    def rounded(self, w, h, radius, fill, bg, border=0, border_colour=None):
        return self._image(_rounded_rows, (int(w), int(h), float(radius), fill,
                                           bg, int(border), border_colour))

    def pill(self, w, h, fill, bg):
        return self.rounded(w, h, h / 2.0, fill, bg)

    def disc(self, d, fill, bg):
        return self.rounded(d, d, d / 2.0, fill, bg)

    def handle(self, d, band, left, right, fill, bg):
        return self._image(_handle_rows, (int(d), int(band), left, right,
                                          fill, bg))

    def strokes(self, w, h, segments, width, colour, bg):
        return self._image(_stroke_rows, (int(w), int(h), tuple(segments),
                                          float(width), colour, bg))

    def badge(self, size, muted, bg):
        return self._image(_badge_rows, (int(size), bool(muted), bg))

    def clear(self):
        self._images.clear()

    def _image(self, builder, key):
        image = self._images.get((builder, key))
        if image is None:
            rows = builder(*key)
            image = tk.PhotoImage(width=key[0], height=len(rows))
            image.put("{%s}" % "} {".join(rows))
            self._images[(builder, key)] = image
        return image
