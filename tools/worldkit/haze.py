"""Aerial perspective (docs/WORLDKIT.md, "Haze"): far geometry fades toward the colour of the sky at
the horizon, so it recedes instead of reading as dark blocks.

Nothing is computed at run time. What is drawn far off is already separate data, so the kit
bakes the haze into it:

- **levels of detail** (assets', scatter chunks', terrain tiles' and far ground levels): each
  level's faces are moved toward the haze colour by the amount at the distance it is drawn from
  (`at()`), through their vertex colours. An untextured face's colour is mixed exactly. A
  textured or palette-backed face's colour is a tint of its texels (128 is unchanged, at most
  255), so its tint is set to give the face's base colour (its palette entry's, or its tile's
  mean) the hazed colour: t' = t (1 - a) + 128 a S / b, per channel, clamped. Dark colours hazed
  strongly toward a bright sky reach the clamp (twice the texel) and stay a little darker and
  more saturated than true haze. The tint is the first palette variant's (the day's); the other
  variants recolour the palette under the same tint.
- **stand-ins** (the kit's, and authored ones): the same, at `standins` (default: the amount at
  1.5 times the stand-in distance). In a world with several regions the stand-ins draw their
  faces in far colours, palette entries only stand-ins use, and those are hazed exactly in every
  palette variant toward that variant's haze colour (textures.py, palettes.py); only the faces of
  the stand-ins' own texture set (the trees' cards) are tinted.

Emissive faces (lit windows, lamps, signs) are hazed by `emissive` times the amount, so a far lamp
still reads at night.
"""
import math
import struct

from kitcore.errors import pointer
from .schema import WorldError


def hex_rgb(color):
    return tuple(int(color[k:k + 2], 16) for k in (1, 3, 5))


def rgb_hex(c):
    return '#' + ''.join(f'{max(0, min(255, round(v))):02x}' for v in c)


def mix(color, target, a):
    """Hex colour moved toward the hex target by a (0..1)."""
    c, t = hex_rgb(color), hex_rgb(target)
    return rgb_hex(x + (y - x) * a for x, y in zip(c, t))


class Haze:
    def __init__(self, spec, standin_distance):
        self.spec = spec
        self.start = spec.get('start', 0.0)
        self.end = spec['end']
        self.amount = spec['amount']
        self.emissive = spec.get('emissive', 0.5)
        self.elevation = spec.get('elevation', 2.0)
        if self.end <= self.start:
            raise WorldError('/haze/end', f'The haze reaches its amount at {self.end:g}, which must be past where it starts '
                                          f'({self.start:g}).')
        if 'standins' in spec:
            self.standins = spec['standins']
        else:
            self.standins = self.at(1.5 * standin_distance) if standin_distance else self.amount
        self.colours = {}        # region -> {variant: hex}
        self.memo = {}

    def at(self, d):
        """The amount at distance d."""
        return self.amount * max(0.0, min(1.0, (d - self.start) / (self.end - self.start)))

    def region(self, name, spec, sky, variants, multiply):
        """The region's haze colour per variant: the world's `colors` (by variant name), else its
        backdrop's sky at `elevation` (a variant without sky colours takes the first's times its
        surface multiply, as the backdrop does)."""
        given = self.spec.get('colors', {})
        out = {}
        for k, vn in enumerate(variants):
            if vn in given:
                out[vn] = given[vn].lower()
            elif sky is not None:
                cols = sky.sky.get(vn)
                if cols is None:
                    first = next(iter(sky.sky.values()))
                    cols = [multiply(c, variants[vn].get('surface', {}).get('multiply')) for c in first]
                out[vn] = sky_at([math.degrees(e) for e in sky.elevations], cols, self.elevation)
            else:
                raise WorldError(pointer('/haze/colors', vn), f'Region {name!r} has no backdrop to take its haze colour '
                                 f'from in variant {vn!r}; give the colour in haze.colors.')
        self.colours[name] = out
        return out

    def day(self, region):
        return hex_rgb(next(iter(self.colours[region].values())))

    def tint(self, binary, a, base_of, region):
        """The mesh with every face's colours moved toward the region's (first variant's) haze
        colour by a. base_of(tex, pal, uvs, window halfword) -> ((r, g, b), class), or None to
        leave the face as it is; it is asked only for textured faces."""
        if binary is None or a <= 0:
            return binary
        key = (binary, round(a, 4), region)
        if key in self.memo:
            return self.memo[key]
        target = self.day(region)
        nv, nf, voff, foff, woff = struct.unpack_from('<HHIII', binary)
        out = bytearray(binary)
        for k in range(nf):
            at = foff + 36 * k
            flags, _, tex, pal = struct.unpack_from('<BBBB', binary, at)
            cols = list(struct.unpack_from('<4I', binary, at + 12))
            n = 3 if flags & 32 else 4                     # a keyed face's fourth word is its bucket
            if flags & 2:
                uvs = struct.unpack_from('<4H', binary, at + 28)
                win = tex >> 5
                hw = struct.unpack_from('<H', binary, woff + 2 * (win - 1))[0] if win and woff else 0
                got = base_of(tex, pal, uvs[:4 if flags & 4 else 3], hw)
                if got is None:
                    continue
                base, cls = got
                amt = a * (self.emissive if cls == 'emissive' else 1.0)
                for q in range(n):
                    t = [(cols[q] >> s) & 255 for s in (0, 8, 16)]
                    t = [min(255, max(0, round(tc * (1 - amt) + 128 * amt * sc / max(bc, 8))))
                         for tc, sc, bc in zip(t, target, base)]
                    cols[q] = t[0] | t[1] << 8 | t[2] << 16
            else:
                for q in range(n):
                    c = [(cols[q] >> s) & 255 for s in (0, 8, 16)]
                    c = [min(255, max(0, round(cc + (sc - cc) * a))) for cc, sc in zip(c, target)]
                    cols[q] = c[0] | c[1] << 8 | c[2] << 16
            struct.pack_into('<4I', out, at + 12, *cols)
        self.memo[key] = bytes(out)
        return self.memo[key]

    def report(self):
        return {'start': self.start, 'end': self.end, 'amount': self.amount, 'standins': round(self.standins, 4),
                'emissive': self.emissive, 'colors': self.colours, 'levels_hazed': getattr(self, 'levels', 0)}


def sky_at(elevations, colours, e):
    """The sky gradient's colour at elevation e (degrees), interpolated between its stops."""
    if e <= elevations[0]:
        return colours[0].lower()
    for k in range(1, len(elevations)):
        if e <= elevations[k]:
            t = (e - elevations[k - 1]) / (elevations[k] - elevations[k - 1])
            return mix(colours[k - 1], colours[k], t)
    return colours[-1].lower()
