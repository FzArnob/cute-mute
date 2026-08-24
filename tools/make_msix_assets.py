"""Build the MSIX / Store visual assets from the same badge geometry.

    python tools\\make_msix_assets.py        # -> packaging/msix/Assets/

The Store wants the icon at a few dozen sizes: six logo shapes, each at several
DPI scales, plus the app-list icon at five target sizes in plated and unplated
forms. All of it is the same drawing, so all of it comes out of
`cutemute.iconart` rather than out of an image editor.

iconart's rasteriser is quadratic in the output size -- render(512) takes about
ten seconds -- so rendering forty assets directly would take the better part of
an hour. Instead the badge is rasterised once at MASTER, and every asset is an
area-averaged downsample of that. For anything smaller than MASTER this is
strictly better antialiasing than rendering directly with iconart's own 4x4
supersampling, since the box filter is averaging far more samples per output
pixel.

Pure stdlib.
"""
import math
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cutemute import APP_NAME, iconart  # noqa: E402
from make_brand import write_png  # noqa: E402  -- one PNG writer, not two

OUT = Path(__file__).resolve().parents[1] / "packaging" / "msix" / "Assets"

# Big enough that every asset below is a downsample, never an upsample. The
# largest is Square310x310Logo at scale-200, which is 620 px.
MASTER = 640

# name -> (width, height, padding as a fraction of the short side, scales)
#
# Padding matters: a Windows tile expects the icon to float in its own space
# with the tile's background showing around it, whereas the app-list and taskbar
# icon at 44x44 is the icon, edge to edge. Getting this wrong is the difference
# between a tile that looks designed and one that looks like a screenshot.
LOGOS = {
    "Square44x44Logo":   (44, 44, 0.00, (100, 125, 150, 200, 400)),
    "Square71x71Logo":   (71, 71, 0.14, (100, 125, 150, 200)),
    "Square150x150Logo": (150, 150, 0.16, (100, 125, 150, 200, 400)),
    "Square310x310Logo": (310, 310, 0.20, (100, 125, 150, 200)),
    "Wide310x150Logo":   (310, 150, 0.20, (100, 125, 150, 200)),
    "StoreLogo":         (50, 50, 0.06, (100, 125, 150, 200, 400)),
}

# The app-list icon again, at the exact sizes the shell asks for. "unplated" is
# the one Windows uses where it does not draw a background plate behind the
# icon -- the taskbar, and the Alt+Tab switcher.
TARGET_SIZES = (16, 24, 32, 48, 256)


@lru_cache(maxsize=2)
def master(muted=True):
    """The badge, rasterised once, as straight-alpha RGBA tuples."""
    return iconart.render(MASTER, muted)


@lru_cache(maxsize=64)
def badge(size, muted=True):
    """A square badge of `size` px, area-averaged down from the master.

    Premultiply, average, un-premultiply. Averaging straight alpha would drag
    the transparent black outside the badge into its edge pixels and leave the
    dark fringe you see on carelessly resized PNGs.
    """
    if size >= MASTER:
        return master(muted)

    src = master(muted)
    scale = MASTER / float(size)
    out = []
    for oy in range(size):
        top, bottom = oy * scale, (oy + 1) * scale
        y0, y1 = int(top), min(MASTER, int(math.ceil(bottom)))
        for ox in range(size):
            left, right = ox * scale, (ox + 1) * scale
            x0, x1 = int(left), min(MASTER, int(math.ceil(right)))

            ar = ag = ab = aa = weight_sum = 0.0
            for sy in range(y0, y1):
                # How much of this source row the output pixel actually covers.
                wy = min(sy + 1.0, bottom) - max(float(sy), top)
                if wy <= 0.0:
                    continue
                row = sy * MASTER
                for sx in range(x0, x1):
                    wx = min(sx + 1.0, right) - max(float(sx), left)
                    if wx <= 0.0:
                        continue
                    weight = wx * wy
                    r, g, b, a = src[row + sx]
                    alpha = a / 255.0
                    ar += r * alpha * weight
                    ag += g * alpha * weight
                    ab += b * alpha * weight
                    aa += alpha * weight
                    weight_sum += weight

            if weight_sum <= 0.0 or aa <= 0.0:
                out.append((0, 0, 0, 0))
                continue
            out.append((min(255, int(ar / aa + 0.5)),
                        min(255, int(ag / aa + 0.5)),
                        min(255, int(ab / aa + 0.5)),
                        min(255, int(aa / weight_sum * 255.0 + 0.5))))
    return tuple(out)


def canvas(width, height, pad, muted=True):
    """Transparent RGBA canvas of width x height with the badge centred."""
    size = max(1, int(round(min(width, height) * (1.0 - 2.0 * pad))))
    art = badge(size, muted)
    buf = bytearray(width * height * 4)
    ox, oy = (width - size) // 2, (height - size) // 2
    for y in range(size):
        row = (oy + y) * width + ox
        for x in range(size):
            buf[(row + x) * 4:(row + x) * 4 + 4] = bytes(art[y * size + x])
    return bytes(buf)


def emit(path, width, height, pad):
    return write_png(path, width, height, canvas(width, height, pad),
                     alpha=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("rasterising the master badge at %d px (this is the slow part)"
          % MASTER)
    master()
    made = 0
    total = 0

    for name, (width, height, pad, scales) in sorted(LOGOS.items()):
        for scale in scales:
            # MRT picks the variant by the .scale-N suffix; the manifest only
            # ever names the unsuffixed file.
            suffix = "" if scale == 100 else ".scale-%d" % scale
            out = OUT / ("%s%s.png" % (name, suffix))
            total += emit(out, width * scale // 100, height * scale // 100, pad)
            made += 1
        # scale-100 doubles as the plain name the manifest references.
        plain = OUT / ("%s.png" % name)
        if not plain.exists():
            total += emit(plain, width, height, pad)
            made += 1

    for size in TARGET_SIZES:
        for form in ("", "_altform-unplated"):
            out = OUT / ("Square44x44Logo.targetsize-%d%s.png" % (size, form))
            total += emit(out, size, size, 0.0)
            made += 1

    print("wrote %d assets, %.1f KB, to %s" % (made, total / 1024.0, OUT))
    print("referenced from packaging/msix/AppxManifest.xml as Assets\\<name>.png")
    print("app: %s" % APP_NAME)


if __name__ == "__main__":
    main()
