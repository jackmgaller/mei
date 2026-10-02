#!/usr/bin/env python3
"""meifont: bakes proportional fonts for Mei carts (the stdlib's font_* functions).

A font is a 4-bit texture atlas of glyphs plus a table of metrics, packed into one blob that a
cart embeds (`embed MYFONT: Font = "my.fnt"`) or that this tool writes as an Akari const array.
The stdlib draws it with font_text() and measures it with text_width(); docs/LANGUAGE.md
("Text") describes the API.

Blob layout (little endian, see `struct Font` in stdlib/font.akr):

    +0   u8   height    glyph cell height in texels (every glyph quad is w x height)
    +1   u8   line      line advance in pixels ('\\n')
    +2   u8   first     first character code in the table
    +3   u8   count     glyphs in the table
    +4   u8   slot      texture slot of the atlas (0-15)
    +5   u8   palette   4-bit palette number (0-255)
    +6   u8   row       first texture row of the atlas
    +7   u8   rows      texture rows stored in the blob (0: none, the cart loads the atlas itself)
    +8   u16  colours[16]   the palette, 15-bit (colour 0 is never drawn); font_load() writes
                            colours 1-15 when rows > 0
    +40  u8 u, u8 v, u8 w, u8 adv  per glyph (w = 0: nothing drawn, only the advance)
    then rows x 128 bytes of texels for texture rows row..row+rows-1 (two per byte, low nibble
    left), when rows > 0

Glyph texels are palette indices: 0 transparent, `ink` for full ink (pixel fonts), 2..15 for
antialiased levels of TrueType fonts, `shadow` for a baked 1-pixel drop shadow. Text colour is
a tint (texel x tint / 128), so ink should be white or light grey.

Fonts:
  --pixel small           the built-in pixel font (7-px caps, 2-px descenders, 10-px line)
  --pixel FILE            a pixel font in text form: a line `= C` (or `= 0x41`) starts glyph C,
                          then its rows of '#' and '.', all the same width
  --ttf FILE --size N     a TrueType/OpenType font, antialiased (4x supersampled)

Examples:
  python3 tools/meifont.py --pixel small --slot 15 --palette 255 --row 48 --ink 1 \\
      --akr __FONT_SMALL -o stdlib/font_small.akr
  python3 tools/meifont.py --ttf Georgia.ttf --size 15 --shadow --slot 3 --palette 40 \\
      -o carts/game/title.fnt --png /tmp/title.png

As a module: pixel_glyphs(), ttf_glyphs(), build_font() and Font.blob() / Font.akr().
"""

import argparse
import math
import struct
import sys

try:
    import numpy as np
except ImportError:     # pragma: no cover
    sys.exit('meifont needs numpy (pip install numpy pillow)')

HEADER = 40          # bytes before the glyph table
ROW_BYTES = 128      # a texture row of 256 4-bit texels

# ---------------------------------------------------------------------------- the built-in font
# The small pixel font: 7-px caps, 5-px x-height, 2-px descenders (rows 0..8), one blank column
# after every glyph. Each glyph: rows of '#' / '.', all rows the same width; missing rows are
# blank. (From Check-In!'s interface font.)

SMALL = {}


def _g(ch, *rows):
    SMALL[ch] = rows


_g(' ', '..')
_g('!', '#', '#', '#', '#', '#', '.', '#')
_g('"', '#.#', '#.#')
_g('#', '.#.#.', '.#.#.', '#####', '.#.#.', '#####', '.#.#.', '.#.#.')
_g('$', '..#..', '.####', '#.#..', '.###.', '..#.#', '####.', '..#..')
_g('%', '##..#', '##.#.', '...#.', '..#..', '.#...', '.#.##', '#..##')
_g('&', '.##..', '#..#.', '#.#..', '.#...', '#.#.#', '#..#.', '.##.#')
_g("'", '#', '#')
_g('(', '.#', '#.', '#.', '#.', '#.', '#.', '.#')
_g(')', '#.', '.#', '.#', '.#', '.#', '.#', '#.')
_g('*', '.....', '..#..', '#.#.#', '.###.', '#.#.#', '..#..', '.....')
_g('+', '.....', '..#..', '..#..', '#####', '..#..', '..#..', '.....')
_g(',', '..', '..', '..', '..', '..', '.#', '.#', '#.')
_g('-', '....', '....', '....', '####', '....', '....', '....')
_g('.', '.', '.', '.', '.', '.', '.', '#')
_g('/', '....#', '...#.', '...#.', '..#..', '.#...', '.#...', '#....')
_g('0', '.###.', '#...#', '#...#', '#...#', '#...#', '#...#', '.###.')
_g('1', '..#..', '.##..', '..#..', '..#..', '..#..', '..#..', '.###.')
_g('2', '.###.', '#...#', '....#', '...#.', '..#..', '.#...', '#####')
_g('3', '.###.', '#...#', '....#', '..##.', '....#', '#...#', '.###.')
_g('4', '...#.', '..##.', '.#.#.', '#..#.', '#####', '...#.', '...#.')
_g('5', '#####', '#....', '####.', '....#', '....#', '#...#', '.###.')
_g('6', '..##.', '.#...', '#....', '####.', '#...#', '#...#', '.###.')
_g('7', '#####', '....#', '...#.', '..#..', '.#...', '.#...', '.#...')
_g('8', '.###.', '#...#', '#...#', '.###.', '#...#', '#...#', '.###.')
_g('9', '.###.', '#...#', '#...#', '.####', '....#', '...#.', '.##..')
_g(':', '.', '.', '#', '.', '.', '#', '.')
_g(';', '..', '..', '.#', '..', '..', '.#', '.#', '#.')
_g('<', '....', '...#', '..#.', '.#..', '..#.', '...#', '....')
_g('=', '....', '....', '####', '....', '####', '....', '....')
_g('>', '....', '#...', '.#..', '..#.', '.#..', '#...', '....')
_g('?', '.###.', '#...#', '....#', '...#.', '..#..', '.....', '..#..')
_g('@', '.###.', '#...#', '#.###', '#.#.#', '#.###', '#....', '.###.')
_g('A', '.###.', '#...#', '#...#', '#####', '#...#', '#...#', '#...#')
_g('B', '####.', '#...#', '#...#', '####.', '#...#', '#...#', '####.')
_g('C', '.###.', '#...#', '#....', '#....', '#....', '#...#', '.###.')
_g('D', '####.', '#...#', '#...#', '#...#', '#...#', '#...#', '####.')
_g('E', '####', '#...', '#...', '###.', '#...', '#...', '####')
_g('F', '####', '#...', '#...', '###.', '#...', '#...', '#...')
_g('G', '.###.', '#...#', '#....', '#.###', '#...#', '#...#', '.###.')
_g('H', '#...#', '#...#', '#...#', '#####', '#...#', '#...#', '#...#')
_g('I', '###', '.#.', '.#.', '.#.', '.#.', '.#.', '###')
_g('J', '...#', '...#', '...#', '...#', '...#', '#..#', '.##.')
_g('K', '#...#', '#..#.', '#.#..', '##...', '#.#..', '#..#.', '#...#')
_g('L', '#...', '#...', '#...', '#...', '#...', '#...', '####')
_g('M', '#...#', '##.##', '#.#.#', '#.#.#', '#...#', '#...#', '#...#')
_g('N', '#...#', '##..#', '##..#', '#.#.#', '#..##', '#..##', '#...#')
_g('O', '.###.', '#...#', '#...#', '#...#', '#...#', '#...#', '.###.')
_g('P', '####.', '#...#', '#...#', '####.', '#....', '#....', '#....')
_g('Q', '.###.', '#...#', '#...#', '#...#', '#.#.#', '#..#.', '.##.#')
_g('R', '####.', '#...#', '#...#', '####.', '#.#..', '#..#.', '#...#')
_g('S', '.###.', '#...#', '#....', '.###.', '....#', '#...#', '.###.')
_g('T', '#####', '..#..', '..#..', '..#..', '..#..', '..#..', '..#..')
_g('U', '#...#', '#...#', '#...#', '#...#', '#...#', '#...#', '.###.')
_g('V', '#...#', '#...#', '#...#', '#...#', '.#.#.', '.#.#.', '..#..')
_g('W', '#...#', '#...#', '#...#', '#.#.#', '#.#.#', '##.##', '#...#')
_g('X', '#...#', '#...#', '.#.#.', '..#..', '.#.#.', '#...#', '#...#')
_g('Y', '#...#', '#...#', '.#.#.', '..#..', '..#..', '..#..', '..#..')
_g('Z', '#####', '....#', '...#.', '..#..', '.#...', '#....', '#####')
_g('[', '##', '#.', '#.', '#.', '#.', '#.', '##')
_g('\\', '#....', '.#...', '.#...', '..#..', '...#.', '...#.', '....#')
_g(']', '##', '.#', '.#', '.#', '.#', '.#', '##')
_g('^', '..#..', '.#.#.', '#...#')
_g('_', '.....', '.....', '.....', '.....', '.....', '.....', '.....', '#####')
_g('`', '#.', '.#')
_g('a', '.....', '.....', '.###.', '....#', '.####', '#...#', '.####')
_g('b', '#....', '#....', '####.', '#...#', '#...#', '#...#', '####.')
_g('c', '....', '....', '.###', '#...', '#...', '#...', '.###')
_g('d', '....#', '....#', '.####', '#...#', '#...#', '#...#', '.####')
_g('e', '.....', '.....', '.###.', '#...#', '#####', '#....', '.###.')
_g('f', '..##', '.#..', '####', '.#..', '.#..', '.#..', '.#..')
_g('g', '.....', '.....', '.####', '#...#', '#...#', '#...#', '.####', '....#', '.###.')
_g('h', '#....', '#....', '####.', '#...#', '#...#', '#...#', '#...#')
_g('i', '#', '.', '#', '#', '#', '#', '#')
_g('j', '..#', '...', '..#', '..#', '..#', '..#', '..#', '#.#', '.#.')
_g('k', '#...', '#...', '#..#', '#.#.', '##..', '#.#.', '#..#')
_g('l', '#.', '#.', '#.', '#.', '#.', '#.', '.#')
_g('m', '.....', '.....', '####.', '#.#.#', '#.#.#', '#.#.#', '#.#.#')
_g('n', '.....', '.....', '####.', '#...#', '#...#', '#...#', '#...#')
_g('o', '.....', '.....', '.###.', '#...#', '#...#', '#...#', '.###.')
_g('p', '.....', '.....', '####.', '#...#', '#...#', '#...#', '####.', '#....', '#....')
_g('q', '.....', '.....', '.####', '#...#', '#...#', '#...#', '.####', '....#', '....#')
_g('r', '....', '....', '#.##', '##..', '#...', '#...', '#...')
_g('s', '....', '....', '.###', '#...', '.##.', '...#', '###.')
_g('t', '.#.', '.#.', '###', '.#.', '.#.', '.#.', '..#')
_g('u', '.....', '.....', '#...#', '#...#', '#...#', '#...#', '.####')
_g('v', '.....', '.....', '#...#', '#...#', '#...#', '.#.#.', '..#..')
_g('w', '.....', '.....', '#...#', '#...#', '#.#.#', '#.#.#', '.#.#.')
_g('x', '.....', '.....', '#...#', '.#.#.', '..#..', '.#.#.', '#...#')
_g('y', '.....', '.....', '#...#', '#...#', '#...#', '#...#', '.####', '....#', '.###.')
_g('z', '.....', '.....', '#####', '...#.', '..#..', '.#...', '#####')
_g('{', '.##', '.#.', '.#.', '#..', '.#.', '.#.', '.##')
_g('|', '#', '#', '#', '#', '#', '#', '#', '#')
_g('}', '##.', '.#.', '.#.', '..#', '.#.', '.#.', '##.')
_g('~', '.....', '.....', '.#...', '#.#.#', '...#.')
assert len(SMALL) == 95, len(SMALL)

# ---------------------------------------------------------------------------- glyph sources


def _rows_to_mask(rows, height):
    w = len(rows[0]) if rows else 0
    m = np.zeros((height, w), bool)
    for y, r in enumerate(rows):
        if len(r) != w:
            raise ValueError('glyph rows differ in width: %r' % (rows,))
        for x, c in enumerate(r):
            m[y, x] = c == '#'
    return m


def parse_pixel_file(path):
    """Reads a pixel font in text form: `= C` lines start a glyph, then rows of '#' and '.'."""
    glyphs = {}
    cur = None
    with open(path) as f:
        for line in f:
            line = line.rstrip('\n')
            if line.startswith('= '):
                key = line[2:]
                code = int(key, 0) if len(key) > 1 else ord(key)
                cur = []
                glyphs[chr(code)] = cur
            elif cur is not None and line and set(line) <= set('#.'):
                cur.append(line)
    return {k: tuple(v) for k, v in glyphs.items()}


def pixel_glyphs(table, ink=15, shadow=None, gap=1, first=32, count=95):
    """Glyph images from a pixel table {char: rows}. Returns (glyphs, height, line), where glyphs
    is a list of (image or None, advance) per code first..first+count-1."""
    height = max(len(r) for r in table.values())
    out = []
    for code in range(first, first + count):
        rows = table.get(chr(code))
        if rows is None:
            out.append((None, 0))
            continue
        m = _rows_to_mask(rows, height)
        w = m.shape[1]
        if not m.any():
            out.append((None, w + gap))
            continue
        out.append((_shade(m.astype(np.float32), ink, shadow), w + gap))
    h = height + (1 if shadow is not None else 0)
    return out, h, height + 1


def _shade(a, ink, shadow, levels=None):
    """a: coverage 0..1 (h, w). Returns palette indices, with a drop shadow one pixel down-right
    when `shadow` is an index (the image grows by one row and column)."""
    if levels is None:
        idx = np.where(a > 0.5, ink, 0).astype(np.uint8)
    else:
        lo, hi = levels
        lvl = np.clip(np.round(lo + a * (hi - lo)), lo, hi).astype(np.uint8)
        idx = np.where(a > 0.18, lvl, 0).astype(np.uint8)
    if shadow is None:
        return idx
    h, w = idx.shape
    out = np.zeros((h + 1, w + 1), np.uint8)
    sh = np.zeros((h + 1, w + 1), bool)
    sh[1:, 1:] = idx > 0
    out[sh] = shadow
    out[:h, :w][idx > 0] = idx[idx > 0]
    return out


def ttf_glyphs(path, size, index=0, shadow=None, track=0, first=32, count=95, mono_digits=False):
    """Antialiased glyphs from a TrueType/OpenType font: levels 2..15 (15 full ink)."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(path, size, index=index)
    S = 4
    big = ImageFont.truetype(path, size * S, index=index)
    asc, desc = font.getmetrics()
    H = asc + desc
    digit_adv = max(font.getlength(str(d)) for d in range(10))
    out = []
    for code in range(first, first + count):
        ch = chr(code)
        adv = font.getlength(ch)
        ox = 1.0
        if mono_digits and ch.isdigit():
            ox += (digit_adv - adv) / 2
            adv = digit_adv
        cw = int(math.ceil(adv)) + 4
        img = Image.new('L', (cw * S, H * S), 0)
        ImageDraw.Draw(img).text((ox * S, 0), ch, font=big, fill=255)
        a = np.asarray(img.resize((cw, H), Image.BOX), np.float32) / 255.0
        a = np.clip((a - 0.1) / 0.75, 0, 1)        # firm the edges up a little
        idx = _shade(a, 15, shadow, levels=(2, 15))
        cols = np.where(idx.any(axis=0))[0]
        if len(cols) == 0:
            out.append((None, int(round(adv)) + track))
            continue
        idx = idx[:, :int(cols.max()) + 1]
        out.append((idx, int(round(adv)) + track))
    h = H + (1 if shadow is not None else 0)
    return out, h, H + 1


# ---------------------------------------------------------------------------- packing


class Font:
    def __init__(self, glyphs, height, line, first, slot, palette, row, colours, atlas, rows):
        self.glyphs = glyphs        # [(u, v, w, adv)]
        self.height = height
        self.line = line
        self.first = first
        self.slot = slot
        self.palette = palette
        self.row = row
        self.colours = colours      # 16 15-bit colours
        self.atlas = atlas          # (rows, 256) uint8 palette indices
        self.rows = rows            # rows stored in the blob

    def blob(self):
        b = bytearray(struct.pack('<8B', self.height, self.line, self.first, len(self.glyphs),
                                  self.slot, self.palette, self.row, self.rows))
        b += struct.pack('<16H', *self.colours)
        for u, v, w, a in self.glyphs:
            b += struct.pack('<4B', u, v, w, a)
        if self.rows:
            t = self.atlas[:self.rows]
            packed = (t[:, 0::2] & 15) | ((t[:, 1::2] & 15) << 4)
            b += packed.astype(np.uint8).tobytes()
        while len(b) % 4:
            b.append(0)
        return bytes(b)

    def akr(self, name, comment=''):
        b = self.blob()
        words = struct.unpack('<%dI' % (len(b) // 4), b)
        L = ['// Generated by tools/meifont.py - do not edit.%s' % (' ' + comment if comment else ''),
             '// A Font blob (stdlib/font.akr): %d glyphs from %d, %d px tall, line %d; atlas in slot %d '
             'rows %d-%d, palette %d.' % (len(self.glyphs), self.first, self.height, self.line, self.slot,
                                          self.row, self.row + max(self.rows, 1) - 1, self.palette),
             'const %s: [%d]u32 = [' % (name, len(words))]
        for i in range(0, len(words), 8):
            L.append('    ' + ', '.join('0x%08X' % w for w in words[i:i + 8]) + ',')
        L[-1] = L[-1].rstrip(',')
        L.append(']')
        return '\n'.join(L) + '\n'

    def preview(self, path, text=None):
        from PIL import Image
        pal = [((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3) for c in self.colours]
        pal[0] = (40, 0, 60)
        img = np.array([[pal[i] for i in row] for row in self.atlas], np.uint8)
        Image.fromarray(img).resize((img.shape[1] * 2, img.shape[0] * 2), Image.NEAREST).save(path)


def build_font(glyphs, height, line, first=32, slot=15, palette=255, row=0, colours=None,
               include_texels=True, width=255):
    """Packs glyph images into atlas rows starting at texture row `row` (shelves of `height`
    texels, one texel apart). Returns a Font. A glyph's far edge (u + w, v + height) must stay
    within 255, the largest 8-bit texture coordinate, so the last column and row are not used."""
    atlas = np.zeros((256 - row, 256), np.uint8)
    x = y = 0
    metrics = []
    for img, adv in glyphs:
        if img is None:
            metrics.append((0, 0, 0, adv))
            continue
        h, w = img.shape
        if x + w > width:
            x = 0
            y += height + 1
        if row + y + height > 255:
            raise ValueError('the font does not fit below texture row %d' % row)
        atlas[y:y + h, x:x + w] = img
        if w > 255 or adv > 255:
            raise ValueError('glyph too wide')
        metrics.append((x, row + y, w, adv))
        x += w + 1
    used = y + height if metrics else 0
    if colours is None:
        colours = default_colours()
    return Font(metrics, height, line, first, slot, palette, row, list(colours), atlas[:used],
                used if include_texels else 0)


def rgb15(r, g, b):
    return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)


def default_colours(ink=15, shadow=None, shadow_rgb=(16, 14, 36)):
    """White ink at `ink`, a ramp for antialiased levels 2..15, the shadow colour at `shadow`."""
    cols = [0] * 16
    for i in range(2, 16):
        k = ((i - 1) / 14.0) ** 0.85
        cols[i] = rgb15(*(int(shadow_rgb[c] + (255 - shadow_rgb[c]) * k) for c in range(3)))
    cols[ink] = rgb15(255, 255, 255)
    if shadow is not None:
        cols[shadow] = rgb15(*shadow_rgb)
    return cols


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--pixel', help="'small' (built in) or a pixel font text file")
    src.add_argument('--ttf', help='a TrueType/OpenType font file')
    ap.add_argument('--size', type=int, default=12, help='TrueType size in pixels')
    ap.add_argument('--index', type=int, default=0, help='face index in a .ttc collection')
    ap.add_argument('--track', type=int, default=0, help='extra advance per glyph (TrueType)')
    ap.add_argument('--mono-digits', action='store_true', help='give digits one advance (TrueType)')
    ap.add_argument('--first', type=int, default=32, help='first character code (default 32)')
    ap.add_argument('--count', type=int, default=95, help='characters (default 95: up to 126)')
    ap.add_argument('--ink', type=int, default=15, help='palette index of full ink (pixel fonts)')
    ap.add_argument('--shadow', nargs='?', type=int, const=1, default=None,
                    help='bake a 1-px drop shadow in this palette index (default 1)')
    ap.add_argument('--slot', type=int, default=15)
    ap.add_argument('--palette', type=int, default=255)
    ap.add_argument('--row', type=int, default=0, help='first texture row of the atlas')
    ap.add_argument('--no-texels', action='store_true', help='leave the atlas out of the blob')
    ap.add_argument('--akr', metavar='NAME', help='write Akari source (a const [N]u32 NAME)')
    ap.add_argument('-o', '--out', required=True, help='output .fnt blob (or .akr with --akr)')
    ap.add_argument('--png', help='also write a preview of the atlas')
    a = ap.parse_args(argv)
    if a.ttf:
        glyphs, h, line = ttf_glyphs(a.ttf, a.size, a.index, a.shadow, a.track, a.first, a.count,
                                     a.mono_digits)
    else:
        table = SMALL if a.pixel == 'small' else parse_pixel_file(a.pixel)
        glyphs, h, line = pixel_glyphs(table, a.ink, a.shadow, first=a.first, count=a.count)
    font = build_font(glyphs, h, line, a.first, a.slot, a.palette, a.row,
                      default_colours(a.ink, a.shadow), not a.no_texels)
    if a.akr:
        with open(a.out, 'w') as f:
            f.write(font.akr(a.akr, '(%s)' % ' '.join(sys.argv[1:] if argv is None else argv)))
    else:
        with open(a.out, 'wb') as f:
            f.write(font.blob())
    if a.png:
        font.preview(a.png)
    print('%s: %d glyphs, height %d, line %d, atlas rows %d-%d, %d bytes' % (
        a.out, len(font.glyphs), font.height, font.line, font.row, font.row + len(font.atlas) - 1,
        len(font.blob())))


if __name__ == '__main__':
    main()
