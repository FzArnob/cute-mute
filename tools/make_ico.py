"""Build CuteMute.ico from the procedural badge (for the exe and shortcuts).

    python tools\\make_ico.py CuteMute.ico [--live]

Writes classic BMP-encoded icon directories, which every Windows shell reads.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cutemute import iconart  # noqa: E402

SIZES = (16, 20, 24, 32, 48, 64, 128, 256)


def _image(size, muted):
    """BITMAPINFOHEADER + bottom-up BGRA + a zeroed 1bpp AND mask."""
    pixels = iconart.bgra_straight(size, muted)
    stride = size * 4
    rows = [pixels[y * stride:(y + 1) * stride] for y in range(size)]
    xor = b"".join(reversed(rows))

    mask_stride = ((size + 31) // 32) * 4
    mask = bytes(mask_stride * size)

    header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0,
                         len(xor) + len(mask), 0, 0, 0, 0)
    return header + xor + mask


def build(path, muted=True):
    images = [(size, _image(size, muted)) for size in SIZES]
    offset = 6 + 16 * len(images)
    directory = b""
    for size, blob in images:
        byte = 0 if size >= 256 else size
        directory += struct.pack("<BBBBHHII", byte, byte, 0, 0, 1, 32,
                                 len(blob), offset)
        offset += len(blob)
    Path(path).write_bytes(struct.pack("<HHH", 0, 1, len(images))
                           + directory + b"".join(b for _, b in images))
    print("wrote %s (%d images, %d bytes)"
          % (path, len(images), Path(path).stat().st_size))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    build(args[0] if args else "CuteMute.ico", muted="--live" not in sys.argv)
