"""Region texture sets (docs/WORLDKIT.md, "Textures per region").

Every textured asset drawn in a region (placements and entity meshes) contributes its tiles; the
region's set is packed once with the kits' shared packer (kitcore/texpack.py): duplicate tiles
removed across every asset, palettes shared while colours fit (surface and emissive textures
apart, so a palette variant can tint them differently), tiles at window-aligned origins, in the
region's slots (never 15; the world's swatch row kept free when it shares a slot). Each placed
mesh is then written for that placement (assetkit.compiler.native_bytes), so an asset drawn in
two regions is stored twice. The pack holds each slot's image (from row 0, the swatch row
included), the 4-bit palettes in the region's main colour run (so palette variants recolour them
entry by entry), the 8-bit palettes as extra runs (a variant tints all 256 colours by one
multiply) and the animated tiles' frames.

Regions share slots: entering a region loads its set over the last one (wp_region_enter()).
"""
import copy

from assetkit.compiler import native_bytes
from assetkit.texout import rgb_hex
from kitcore.errors import KitError, pointer
from kitcore.texpack import pack as pack_tiles, SLOT_BYTES, FONT_SLOT, CELL
from . import pack as P
from .schema import WorldError

DEFAULT_SLOTS = tuple(range(13, -1, -1))     # slot 14 holds the swatch row by default, 15 the fonts


def parse_slots(text, path):
    """'13-6' (a range, in that order) or '14,12,10-11' -> [slots] in order of preference."""
    slots = []
    for part in text.split(','):
        a, _, b = part.partition('-')
        a, b = int(a), int(b or a)
        slots += list(range(a, b + 1)) if a <= b else list(range(a, b - 1, -1))
    if any(s > 15 for s in slots) or len(set(slots)) != len(slots):
        raise WorldError(path, 'Texture slots are 0-14, each named once.')
    if FONT_SLOT in slots:
        raise WorldError(path, 'Texture slot 15 holds the fonts.')
    return slots


def allocated(tile):
    """VRAM a tile takes on the packer's 8-texel grid (bytes)."""
    cw, ch = tile.cells()
    return cw * ch * CELL * CELL * tile.bits // 8


class RegionTextures:
    def __init__(self, name, spec, path, world_spec):
        self.name = name
        self.spec = {**(world_spec or {}), **spec.get('textures', {})}
        self.path = pointer(path, 'textures') if 'textures' in spec else '/textures'
        self.assets = {}            # name -> Asset (textured)
        self.packing = None
        self.classes = {}           # tile key -> {'surface', 'emissive'}
        self.users = {}             # tile key -> [(asset, material)]
        self.slots = (parse_slots(self.spec['slots'], pointer(self.path, 'slots')) if 'slots' in self.spec
                      else list(DEFAULT_SLOTS))

    def add_asset(self, asset):
        if getattr(asset, 'textured', False):
            self.assets.setdefault(asset.name, asset)

    def uses(self):
        out = []
        for name in sorted(self.assets):
            a = self.assets[name]
            for material, tex in a.mesh.textures['textures'].items():
                out.append((a, material, tex))
        return out

    def group(self, key):
        return 'emissive' if 'emissive' in self.classes.get(key, ()) else 'surface'

    def asset_bytes(self):
        """Per asset: VRAM of the distinct tiles it uses (a tile shared by two assets counts for both)."""
        out = {}
        for a, material, tex in self.uses():
            out.setdefault(a.name, {})[tex.tile.key] = tex.tile
        return {n: (sum(allocated(t) for t in tiles.values()), len(tiles)) for n, tiles in out.items()}

    def overflow(self, need, budget, slots, reason):
        lines = ', '.join(f'{n} {b:,} bytes ({k} tile{"s" if k > 1 else ""})'
                          for n, (b, k) in sorted(self.asset_bytes().items(), key=lambda kv: -kv[1][0]))
        return WorldError(self.path, f'Region {self.name!r} needs {need:,} bytes of texture VRAM; {reason} '
                                     f'(slots {",".join(map(str, slots))}, budget {budget:,} bytes). By asset: {lines}. '
                                     'Use fewer or smaller textures, 4-bit rather than 8-bit, more slots, or split the region.')

    def pack(self, warnings, first_palette, palette8, swatch):
        """Packs the region's tiles. swatch: (slot, row) of the world's swatch row, or None."""
        slots = self.slots
        budget = self.spec.get('budget', len(slots) * SLOT_BYTES)
        tiles, seen = [], {}
        for a, material, tex in self.uses():
            key = tex.tile.key
            cls = a.materials[material].get('class', 'surface')
            self.classes.setdefault(key, set()).add(cls)
            self.users.setdefault(key, []).append((a.name, material))
            if key not in seen:
                seen[key] = tex.tile
                tiles.append(tex.tile)
        for key, cls in self.classes.items():
            if len(cls) > 1:
                warnings.append({'code': 'texture_class_shared', 'region': self.name,
                                 'materials': [f'{a}.{m}' for a, m in self.users[key]],
                                 'message': 'One texture is used by surface and emissive materials; it is tinted as '
                                            'emissive in every palette variant.'})
        need = sum(allocated(t) for t in tiles)
        if need > budget:
            raise self.overflow(need, budget, slots, 'that is over its budget')
        reserved = [(swatch[0], 0, swatch[1], 16, 1)] if swatch and swatch[0] in slots else []
        try:
            self.packing = pack_tiles(tiles, slots=slots, first_palette=first_palette, palette8=palette8,
                                      reserved=reserved, path=self.path, group=self.group)
        except KitError as error:
            if 'do not fit' in str(error):
                raise self.overflow(need, budget, slots, 'the tiles do not fit in its slots') from error
            raise WorldError(self.path, f'Region {self.name!r}: {error}') from error
        self.swatch = swatch if reserved else None
        self.budget, self.slots_given = budget, slots
        return self.packing

    # ---- what goes into the pack

    def palettes4(self):
        """{4-bit palette: (class, [15-bit colours, index 1 first])}."""
        groups = {(p.bits, p.palette): self.group(k) for k, p in self.packing.placements.items()}
        return {pal: (groups[4, pal], cols) for (bits, pal), cols in sorted(self.packing.palettes.items()) if bits == 4}

    def palettes8(self):
        groups = {(p.bits, p.palette): self.group(k) for k, p in self.packing.placements.items()}
        return {pal: (groups[8, pal], cols) for (bits, pal), cols in sorted(self.packing.palettes.items()) if bits == 8}

    def slot_textures(self, swatch_bytes):
        out = []
        for slot in self.packing.slots():
            first, data = self.packing.slot_image(slot)
            bits = self.packing.slot_bits[slot]
            stride = 128 if bits == 4 else 256
            image = bytearray(first * stride) + data
            if self.swatch and slot == self.swatch[0] and swatch_bytes:
                at = self.swatch[1] * 128
                if len(image) < at + len(swatch_bytes):
                    image += bytes(at + len(swatch_bytes) - len(image))
                image[at:at + len(swatch_bytes)] = swatch_bytes
            out.append(P.Texture(slot, bytes(image), bits == 4))
        return out

    def animations(self):
        out, seen = [], set()
        for a, material, tex in self.uses():
            key = tex.tile.key
            if len(tex.tile.frames) < 2 or key in seen:
                continue
            seen.add(key)
            place = self.packing.placements[key]
            stride = 128 if place.bits == 4 else 256
            frames = [self.packing.encode(key, k) for k in range(len(tex.tile.frames))]
            out.append((f'{a.name}.{material}', P.Animation(b''.join(frames), len(frames), tex.ticks, tex.tile.row_bytes(),
                                                           tex.tile.alloc_height,
                                                           place.slot * SLOT_BYTES + place.y * stride +
                                                           (place.x // 2 if place.bits == 4 else place.x), stride)))
        return out

    def texel_owners(self):
        """(asset, material) -> (bits, palette, {15-bit colour: index}) of each textured material."""
        out = {}
        for a, material, tex in self.uses():
            place = self.packing.placements[tex.tile.key]
            out[a.name, material] = (place.bits, place.palette,
                                     {c: place.index[c] for c in tex.tile.colours()})
        return out

    def binary(self, asset, palette, level=None):
        """The asset's mesh (or level of detail `level`, 1..) placed for this region's packing,
        its palette-backed faces through `palette` (relocated_palette(), or None)."""
        mesh = asset.mesh if level is None else asset.mesh.levels[level - 1][0]
        m = copy.copy(mesh)
        m.palette = palette if mesh.palette else None
        return native_bytes(m, asset.materials, asset.recipe.get('lighting', {}), self.packing)

    def report(self):
        pk = self.packing
        summary = pk.summary()
        slots = []
        for slot in pk.slots():
            first, data = pk.slot_image(slot)
            stride = 128 if pk.slot_bits[slot] == 4 else 256
            slots.append({'slot': slot, 'bits': pk.slot_bits[slot], 'rows': first + len(data) // stride,
                          'rom_bytes': first * stride + len(data)})
        anims = self.animations()
        return {'slots_given': self.slots_given, 'budget_bytes': self.budget,
                'vram_bytes': summary['vram_bytes'], 'vram_bytes_allocated': summary['vram_bytes_allocated'],
                'tiles': summary['tiles'], 'slots': slots,
                'palettes_4bit': summary['palettes_4bit'], 'palettes_8bit': summary['palettes_8bit'],
                'by_asset': {n: {'vram_bytes': b, 'tiles': k} for n, (b, k) in sorted(self.asset_bytes().items())},
                'animations': [{'material': label, 'frames': a.frames, 'ticks': a.ticks,
                                'rom_bytes': len(a.data), 'bytes_a_frame': a.rows * a.row_bytes} for label, a in anims]}


def relocated_palette(asset, rp, slot, row):
    """A textured asset's palette-backed materials moved to the region's entries and the world's
    swatch, in the shape native_bytes() reads (as `mei_assets.py pack` relocates)."""
    pal = asset.mesh.palette
    if not pal:
        return None
    mapping = rp.mapping(asset)
    entries = []
    for e in pal['entries']:
        c = mapping[e['colour']]
        entries.append(dict(e, colour=c, palette=c // 16, index=c % 16))
    return {'layout': {'slot': slot, 'row': row, 'first': entries[0]['palette']},
            'palettes': sorted({e['palette'] for e in entries}), 'entries': entries,
            'by_material': {m: e for e in entries for m in e['materials']}}


def colour_hex(c15):
    return rgb_hex(c15)
