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

A stand-in is drawn whichever region is loaded, so in a world with several regions the kit's
stand-ins draw each textured face in its tile's **far colour** (the mean of its texels, as a
textured terrain field's coarse level does): far_asset() gives the region a palette entry per
colour, far_faces() rewrites a mesh's textured faces to them.

The stand-ins' own texture set (standins.textures, CommonTextures): the 4-bit cutout tiles the
stand-ins draw (the trees' far cards) are packed once into slots no region uses and written into
every region's set at the same places, so they are in VRAM whichever region is loaded; each
region holds its own copies of their palettes (its variants tint them), and a stand-in keeps
those faces textured instead of drawing them solid in a far colour.
"""
import copy
import struct

from assetkit.compiler import native_bytes
from assetkit.texout import rgb_hex
from assetkit.textures import quantise, rgb_of
from kitcore.errors import KitError, pointer
from kitcore.texpack import pack as pack_tiles, SLOT_BYTES, FONT_SLOT, FONT_PALETTE
from . import pack as P
from .schema import WorldError

DEFAULT_SLOTS = tuple(range(13, -1, -1))     # slot 14 holds the swatch row by default, 15 the fonts
FAR_COLOURS = {'surface': 30, 'emissive': 15}  # a region's far colours at most (stand-ins, several regions)


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
    return tile.allocated_bytes()


class CommonTextures:
    """The stand-ins' texture set (standins.textures): tiles every region's set holds at the same
    places, so a stand-in may draw them whichever region is loaded."""

    def __init__(self, spec, path):
        self.path = path
        self.slots = parse_slots(spec.get('slots', '0'), pointer(path, 'slots'))
        self.budget = spec.get('budget', len(self.slots) * SLOT_BYTES)
        self.tiles = {}             # key -> Tile
        self.users = {}             # key -> {(asset, material)}
        self.classes = {}           # key -> 'surface' or 'emissive'
        self.packing = None

    def add(self, asset, material, tile, cls):
        self.tiles.setdefault(tile.key, tile)
        self.users.setdefault(tile.key, set()).add((asset, material))
        self.classes[tile.key] = 'emissive' if 'emissive' in (cls, self.classes.get(tile.key)) else 'surface'

    def pack(self, swatch):
        need = sum(allocated(t) for t in self.tiles.values())
        if need > self.budget:
            lines = ', '.join(f'{"/".join(sorted(f"{a}.{m}" for a, m in self.users[k]))} {allocated(t):,}'
                              for k, t in sorted(self.tiles.items(), key=lambda kv: -allocated(kv[1])))
            raise WorldError(self.path, f'The stand-ins\' texture set needs {need:,} bytes of VRAM; its budget is '
                                        f'{self.budget:,} (slots {",".join(map(str, self.slots))}). By texture: {lines}.')
        reserved = [(swatch[0], 0, swatch[1], 16, 1)] if swatch and swatch[0] in self.slots else []
        try:
            self.packing = pack_tiles(list(self.tiles.values()), slots=self.slots, first_palette=0, palette8=14,
                                      reserved=reserved, path=self.path, group=lambda k: self.classes[k])
        except KitError as error:
            raise WorldError(self.path, f'The stand-ins\' texture set: {error}') from error
        return self.packing

    def report(self):
        summary = self.packing.summary()
        return {'slots_given': self.slots, 'budget_bytes': self.budget, 'vram_bytes': summary['vram_bytes'],
                'vram_bytes_allocated': summary['vram_bytes_allocated'], 'tiles': summary['tiles'],
                'palettes_4bit': len(summary['palettes_4bit']),
                'by_material': {f'{a}.{m}': allocated(self.tiles[k]) for k in self.tiles
                                for a, m in sorted(self.users[k])}}


class RegionTextures:
    def __init__(self, name, spec, path, world_spec):
        self.name = name
        self.spec = {**(world_spec or {}), **spec.get('textures', {})}
        self.path = pointer(path, 'textures') if 'textures' in spec else '/textures'
        self.assets = {}            # name -> Asset (textured)
        self.packing = None
        self.own = None             # the region's own tiles' packing (without the stand-ins' set)
        self.common = None          # CommonTextures whose tiles the region's set also holds
        self.common_keys = set()
        self.common_haze = {}       # region copy of a stand-ins' palette -> its hazed copy (haze)
        self.haze = False           # set by the world when it has haze and several regions
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

    def pack(self, warnings, first_palette, palette8, swatch, common=None):
        """Packs the region's tiles. swatch: (slot, row) of the world's swatch row, or None.
        common: the stand-ins' set (CommonTextures, packed): its tiles are left out of the
        region's own packing and its slots out of the region's; the packing meshes are written
        with holds them too, at their places, with the region's copies of their palettes."""
        shared = common.tiles if common and common.packing else {}
        slots = [s for s in self.slots if not (shared and s in common.slots)]
        if not slots:
            raise WorldError(self.path, f'Region {self.name!r} has no texture slot the stand-ins\' set does not use.')
        budget = self.spec.get('budget', len(slots) * SLOT_BYTES)
        tiles, seen = [], {}
        for a, material, tex in self.uses():
            key = tex.tile.key
            cls = a.materials[material].get('class', 'surface')
            self.classes.setdefault(key, set()).add(cls)
            self.users.setdefault(key, []).append((a.name, material))
            if key not in seen and key not in shared:
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
        self.own = self.packing
        self.swatch = swatch if reserved else None
        self.budget, self.slots_given = budget, slots
        if shared:
            self.packing = self.with_common(common, first_palette)
            if swatch and swatch[0] in common.slots:
                self.swatch = swatch
        return self.packing

    def with_common(self, common, first_palette):
        """The region's packing with the stand-ins' tiles added at their places, and copies of
        the palettes of those the region draws after the region's own palettes. The slots'
        images hold every shared tile, so the set is whole whichever region was entered last."""
        own, cp = self.own, common.packing
        used = {tex.tile.key for _, _, tex in self.uses()} & set(cp.placements)
        mine = [p for b, p in own.palettes if b == 4]
        nxt = (max(mine) + 1) if mine else first_palette
        renumber = {}
        for key in [k for k in cp.placements if k in used]:
            pal = cp.placements[key].palette
            if pal not in renumber:
                renumber[pal] = nxt
                nxt += 1
        # with haze, a second copy of each for the stand-ins, which the palette variants haze
        self.common_haze = {}
        if self.haze:
            for new in list(renumber.values()):
                self.common_haze[new] = nxt
                nxt += 1
        limit = min([FONT_PALETTE] + [16 * p for b, p in own.palettes if b == 8])
        if nxt > limit:
            raise WorldError(self.path, f'Region {self.name!r}: the copies of the stand-ins\' texture palettes run '
                                        f'to palette {nxt - 1}, into {limit}.')
        tiles, placements, palettes = dict(own.tiles), dict(own.placements), dict(own.palettes)
        for key, place in cp.placements.items():
            tiles[key] = cp.tiles[key]
            placements[key] = copy.copy(place)
            # a tile the region does not draw keeps the common palette number, which no face uses
            placements[key].palette = renumber.get(place.palette, place.palette)
        for old, new in renumber.items():
            palettes[4, new] = cp.palettes[4, old]
            if new in self.common_haze:
                palettes[4, self.common_haze[new]] = cp.palettes[4, old]
        self.common, self.common_keys = common, set(cp.placements)
        self.common_drawn = used
        slot_bits = dict(own.slot_bits)
        slot_bits.update(cp.slot_bits)
        return type(own)(tiles, placements, palettes, slot_bits)

    # ---- far colours (stand-ins in a world with several regions)

    def far_asset(self, entries=None):
        """A stand-in for an asset whose palette entries are the far colours of the region's tiles,
        for RegionPalette.add_asset(); None without tiles. A tile's far colour is the mean of its
        texels (frame 0, holes left out); the means of each class are then reduced to at most
        FAR_COLOURS of them (the Asset Kit's median cut), so they take a few palettes, not one entry
        a tile. Records tile key -> (class, colour) in self.far.

        With entries (the region's palette-backed entries, RegionPalette.by_key, when the world has
        haze), their colours join the reduction too, and the far colours become entries of their
        own (separate, marked haze), which only stand-ins draw: the palette variants haze them."""
        self.far_entries = {}
        classes, means = {}, {}
        keep = set(self.common.tiles) if self.common else set()
        for a, material, tex in self.uses():
            if tex.tile.key in keep:
                continue
            classes.setdefault(tex.tile.key, set()).add(a.materials[material].get('class', 'surface'))
            if tex.tile.key not in means:
                means[tex.tile.key] = tile_mean(tex.tile)
        for key, e in (entries or {}).items():
            if e.get('haze'):
                continue
            classes[('entry', key)] = {e['class']}
            means[('entry', key)] = tuple(int(e['color'][k:k + 2], 16) for k in (1, 3, 5))
        self.far, entries_out = {}, {}
        for cls, cap in FAR_COLOURS.items():
            keys = [k for k in means if ('emissive' if 'emissive' in classes[k] else 'surface') == cls]
            if not keys:
                continue
            reduced = quantise([[[means[k] for k in keys]]], cap)[0][0][0]
            for k, c in zip(keys, reduced):
                self.far[k] = (cls, rgb_hex(c))
        for a, material, tex in self.uses():
            if tex.tile.key in self.far:
                entries_out.setdefault(self.far[tex.tile.key], []).append(f'{a.name}.{material}')
        for key in (entries or {}):
            if ('entry', key) in self.far:
                self.far_entries[key] = self.far[('entry', key)]
                mats = [f'{a}.{m}' for a, m in entries[key]['owners']]
                entries_out.setdefault(self.far[('entry', key)], []).extend(mats)
        if not entries_out:
            return None
        haze = entries is not None
        rows = []
        self.far_rpkey = {}
        for k, ((cls, colour), mats) in enumerate(sorted(entries_out.items())):
            rows.append({'colour': k + 1, 'class': cls, 'color': colour, 'materials': [f'far{k}'] if haze else mats,
                         **({'separate': True, 'haze': True} if haze else {})})
            self.far_rpkey[cls, colour] = (cls, colour, 'far', (f'far{k}',)) if haze else (cls, colour)
        manifest = {'entries': rows}
        return type('FarColours', (), {'name': 'far', 'manifest': manifest})()

    def far_faces(self, binary, rp, slot, row):
        """The mesh with every face that samples this region's texture set drawn instead in its
        tile's far colour: a palette-backed face (the world's swatch at slot and row) of the region
        entry far_asset() added. Faces are found by their texture's slot, depth and palette, then by
        their texture window or, without one, the tile holding their texture coordinates."""
        if not self.packing or not getattr(self, 'far', None):
            return binary
        nv, nf, voff, foff, woff = struct.unpack_from('<HHIII', binary)
        out = bytearray(binary)
        # palette-backed faces of the region's entries, when they have far colours (haze)
        entry_far = {e['colour']: self.far_entries[key] for key, e in rp.by_key.items()
                     if key in getattr(self, 'far_entries', {})}
        places = {}
        for key, place in self.packing.placements.items():
            if key in self.common_keys:
                continue                 # the stand-ins' set: drawn textured whichever region is loaded
            places.setdefault((place.slot, place.bits, place.palette), []).append((key, place))
        for k in range(nf):
            at = foff + 36 * k
            flags, _, tex, pal = struct.unpack_from('<BBBB', binary, at)
            if not flags & 2:
                continue
            bits = 4 if tex & 16 else 8
            uvs = struct.unpack_from('<4H', binary, at + 28)[:4 if flags & 4 else 3]
            if self.common_haze and bits == 4 and pal in self.common_haze and tex & 15 in self.common.slots:
                struct.pack_into('<B', out, at + 3, self.common_haze[pal])     # a card: its hazed palette
                continue
            if entry_far and bits == 4 and tex & 15 == slot and all(c >> 8 == row and c & 255 < 16 for c in uvs):
                far = entry_far.get(pal * 16 + (uvs[0] & 15))
                if far:
                    colour = rp.by_key[self.far_rpkey[far]]['colour']
                    struct.pack_into('<BB', out, at + 2, (slot & 15) | 16, colour // 16)
                    struct.pack_into('<4H', out, at + 28, *([colour % 16 | row << 8] * 4))
                continue
            group = places.get((tex & 15, bits, pal))
            if not group:
                continue                 # a palette-backed face (the swatch), or not this region's
            win = tex >> 5
            hit = None
            if win and woff:
                hw = struct.unpack_from('<H', binary, woff + 2 * (win - 1))[0]
                hit = next((key for key, p in group if p.window and p.halfword() == hw), None)
            if hit is None:
                u = sum(c & 255 for c in uvs) / len(uvs)
                v = sum(c >> 8 for c in uvs) / len(uvs)
                inside = [key for key, p in group if not p.window and p.x <= u < p.x + p.width + 1
                          and p.y <= v < p.y + p.height + 1]
                hit = inside[0] if inside else group[0][0]
            colour = rp.by_key[self.far_rpkey[self.far[hit]]]['colour']
            struct.pack_into('<BB', out, at + 2, (slot & 15) | 16, colour // 16)
            struct.pack_into('<4H', out, at + 28, *([colour % 16 | row << 8] * 4))
        return bytes(out)

    def face_base(self, rp, slot, row):
        """For haze.tint(): a function (tex, pal, uvs, window halfword) -> ((r, g, b), class), the
        colour a textured face's tint multiplies: its palette entry's (a palette-backed face of the
        world's swatch at slot and row) or its tile's mean brightness; None for a face the haze
        leaves alone (a far colour or card palette the palette variants haze, or a face this region
        does not know)."""
        by_colour = {e['colour']: e for e in rp.entries}
        hazed = set(self.common_haze.values())
        places = {}
        for key, place in (self.packing.placements.items() if self.packing else ()):
            places.setdefault((place.slot, place.bits, place.palette), []).append((key, place))
        means = {}

        def base(tex, pal, uvs, hw):
            bits = 4 if tex & 16 else 8
            if bits == 4 and tex & 15 == slot and all(c >> 8 == row and c & 255 < 16 for c in uvs):
                e = by_colour.get(pal * 16 + (uvs[0] & 15))
                if e is None or e.get('haze'):
                    return None
                return tuple(int(e['color'][k:k + 2], 16) for k in (1, 3, 5)), e['class']
            if pal in hazed and bits == 4:
                return None
            group = places.get((tex & 15, bits, pal))
            if not group:
                return None
            hit = next((key for key, p in group if p.window and p.halfword() == hw), None) if hw else None
            if hit is None:
                u = sum(c & 255 for c in uvs) / len(uvs)
                v = sum(c >> 8 for c in uvs) / len(uvs)
                inside = [key for key, p in group if not p.window and p.x <= u < p.x + p.width + 1
                          and p.y <= v < p.y + p.height + 1]
                hit = inside[0] if inside else group[0][0]
            if hit not in means:
                # a tile's texels share one tint, so it is set for their mean brightness (grey):
                # a texture of several colours (a card's trunk and leaves) keeps its hues
                m = tile_mean(self.packing.tiles[hit])
                lum = 0.299 * m[0] + 0.587 * m[1] + 0.114 * m[2]
                means[hit] = (lum, lum, lum)
            cls = self.common.classes[hit] if hit in self.common_keys else self.group(hit)
            return means[hit], cls
        return base

    # ---- what goes into the pack

    def palettes4(self):
        """{4-bit palette: (class, [15-bit colours, index 1 first])}."""
        groups = {(p.bits, p.palette): (self.common.classes[k] if k in self.common_keys else self.group(k))
                  for k, p in self.packing.placements.items()}
        for src, dst in self.common_haze.items():
            groups[4, dst] = groups[4, src]
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
        summary = (self.own or pk).summary()
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


def tile_mean(tile):
    """A tile's mean colour (frame 0, holes left out), 8 bits a channel."""
    texels = [rgb_of(c) for row in tile.frames[0] for c in row if c is not None]
    return tuple(round(sum(t[k] for t in texels) / len(texels)) for k in range(3))


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
