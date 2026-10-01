#!/usr/bin/env python3
"""Builds a memory card save's metadata record (docs/MEMCARD.md): title + 16x16 icon of 1-3
frames with a 16-colour palette, 452 bytes, ready for `embed ICON: SaveMeta = "icon.bin"`.

    python3 tools/mei_icon.py frame1.png [frame2.png frame3.png] -o save_icon.bin --title "My Game"

Each PNG is one 16x16 frame, or a horizontal strip of 2-3 frames (32x16, 48x16). Pixels with
alpha below 128 are transparent (colour 0); the rest may use at most 15 distinct colours
(after reduction to 15 bits) across all frames. --quantize reduces bigger images to 15 colours
instead of failing.

As a module:

    from mei_icon import make_meta
    blob = make_meta([img1, img2], title="My Game")   # PIL images or numpy arrays

Frames may be PIL images, RGBA (16,16,4) / RGB (16,16,3) uint8 arrays, a stack of those
(n,16,16,c), or (16,16) integer arrays of palette indices 0-15 together with
palette=[(r, g, b), ...] (index 0 is transparent and its colour is ignored).
"""
import argparse
import struct
import sys

META_SIZE = 452
FRAME_BYTES = 128
MAX_FRAMES = 3


class IconError(ValueError):
    pass


def c15(r, g, b):
    """24-bit colour -> 15-bit framebuffer colour (red in the low bits), like rgb15()."""
    return (int(r) >> 3) | ((int(g) >> 3) << 5) | ((int(b) >> 3) << 10)


def _to_arrays(frames):
    """Normalises the input to a list of (16,16,4) uint8 RGBA arrays or (16,16) index arrays."""
    import numpy as np
    out = []
    for f in frames:
        if hasattr(f, 'convert') and hasattr(f, 'size'):      # a PIL image
            a = np.asarray(f.convert('RGBA'))
        else:
            a = np.asarray(f)
        if a.ndim == 4 or (a.ndim == 3 and a.shape[0] != 16 and a.shape[-1] not in (3, 4)):
            out.extend(_to_arrays(list(a)))                   # a stack of frames
            continue
        if a.ndim == 3 and a.shape[0] == 16 and a.shape[1] in (32, 48) and a.shape[2] in (3, 4):
            out.extend(_to_arrays([a[:, k * 16:(k + 1) * 16] for k in range(a.shape[1] // 16)]))
            continue
        if a.ndim == 3 and a.shape[2] == 3:
            a = np.concatenate([a, np.full(a.shape[:2] + (1,), 255, a.dtype)], axis=2)
        if a.shape[:2] != (16, 16):
            raise IconError('icon frames must be 16x16 pixels (got %dx%d)' % (a.shape[1], a.shape[0]))
        out.append(a)
    return out


def _quantize(frames, ncol):
    """Reduces RGBA frames to at most ncol opaque colours (PIL median cut over all frames)."""
    import numpy as np
    from PIL import Image
    strip = np.concatenate(frames, axis=1)
    opaque = strip[:, :, 3] >= 128
    q = Image.fromarray(np.ascontiguousarray(strip[:, :, :3]), 'RGB').quantize(ncol)
    pal = list(q.getpalette() or [])
    pal += [0] * (768 - len(pal))
    idx = np.asarray(q)
    rgb = np.array([pal[3 * i:3 * i + 3] for i in range(256)], np.uint8)[idx]
    out = np.concatenate([rgb, np.where(opaque, 255, 0).astype(np.uint8)[:, :, None]], axis=2)
    return [out[:, k * 16:(k + 1) * 16] for k in range(len(frames))]


def make_meta(frames, title='', palette=None, quantize=False):
    """Returns the 452-byte metadata record for 1-3 icon frames and a title."""
    import numpy as np
    if not isinstance(frames, (list, tuple)):
        frames = [frames]
    try:
        tb = title.encode('ascii')
    except UnicodeEncodeError:
        raise IconError('the title must be ASCII')
    if len(tb) > 32:
        raise IconError('the title is longer than 32 characters')
    arrs = _to_arrays(frames)
    if not 1 <= len(arrs) <= MAX_FRAMES:
        raise IconError('an icon has 1-3 frames (got %d)' % len(arrs))

    pal15 = [0] * 16
    indexed = [a.ndim == 2 for a in arrs]
    if any(indexed):
        if not all(indexed):
            raise IconError('mix of index and colour frames')
        if palette is None:
            raise IconError('index frames need palette=[(r, g, b), ...]')
        if len(palette) > 16:
            raise IconError('the palette has more than 16 colours')
        for i, c in enumerate(palette):
            pal15[i] = c15(*c[:3]) if i else 0
        idx = [np.asarray(a, np.int64) for a in arrs]
        for a in idx:
            if a.min() < 0 or a.max() > 15:
                raise IconError('palette indices must be 0-15')
            if a.max() >= max(len(palette), 1):
                raise IconError('index %d is beyond the %d-colour palette' % (a.max(), len(palette)))
    else:
        if quantize:
            arrs = _quantize(arrs, 15)
        colours = {}
        idx = []
        for a in arrs:
            fi = np.zeros((16, 16), np.int64)
            for y in range(16):
                for x in range(16):
                    r, g, b, al = (int(v) for v in a[y, x])
                    if al < 128:
                        continue
                    c = c15(r, g, b)
                    if c not in colours:
                        colours[c] = len(colours) + 1
                    fi[y, x] = colours[c]
            idx.append(fi)
        if len(colours) > 15:
            raise IconError('the icon uses %d colours; the limit is 15 plus transparent '
                            '(use --quantize / quantize=True to reduce it)' % len(colours))
        for c, i in colours.items():
            pal15[i] = c

    pixels = bytearray(FRAME_BYTES * MAX_FRAMES)
    for k, fi in enumerate(idx):
        for y in range(16):
            for x in range(0, 16, 2):
                pixels[k * FRAME_BYTES + y * 8 + x // 2] = int(fi[y, x]) | (int(fi[y, x + 1]) << 4)
    blob = tb.ljust(32, b'\0') + struct.pack('<I', len(idx)) + struct.pack('<16H', *pal15) + bytes(pixels)
    assert len(blob) == META_SIZE
    return blob


def main(argv=None):
    ap = argparse.ArgumentParser(description='Build a Mei save metadata record (title + icon), 452 bytes.')
    ap.add_argument('frames', nargs='+', help='PNG frames (16x16 each, or a 32x16 / 48x16 strip)')
    ap.add_argument('-o', '--output', required=True, help='output .bin')
    ap.add_argument('--title', default='', help='save title shown in the OS (ASCII, up to 32 characters)')
    ap.add_argument('--quantize', action='store_true', help='reduce to 15 colours instead of failing')
    args = ap.parse_args(argv)
    from PIL import Image
    try:
        blob = make_meta([Image.open(p) for p in args.frames], args.title, quantize=args.quantize)
    except IconError as e:
        print('mei_icon: %s' % e, file=sys.stderr)
        return 1
    with open(args.output, 'wb') as f:
        f.write(blob)
    return 0


if __name__ == '__main__':
    sys.exit(main())
