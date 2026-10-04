"""The files, Akari loader and manifest entries for placed textures (a kitcore.texpack.Packing):
written by `build` for one asset (its own placement) and by `pack` for a set."""
from kitcore.texpack import SLOT_BYTES


def stride(bits):
    return 128 if bits == 4 else 256


def rgb_hex(c15):
    r, g, b = ((c15 & 31) << 3, ((c15 >> 5) & 31) << 3, ((c15 >> 10) & 31) << 3)
    return f'#{r | r >> 5:02x}{g | g >> 5:02x}{b | b >> 5:02x}'


def outputs(stem, symbol, packing, animations=()):
    """Files and Akari for a packing. stem: the file name prefix; symbol: the Akari prefix
    (ASSET_NAME). animations: [(tile key, label, ticks)] of animated textures. Returns
    (files, embed lines, loader body lines, manifest dict)."""
    files, embeds, body = {}, [], []
    slots = []
    for slot in packing.slots():
        first, data = packing.slot_image(slot)
        bits = packing.slot_bits[slot]
        name = f'{stem}.slot{slot}.tex'
        files[name] = data
        sym = f'{symbol}_TEX{slot}'
        embeds.append(f'embed {sym}: u8 = "{name}"')
        body.append(f'    memcpy((VRAM_TEXTURES + {slot} * TEXTURE_SLOT_SIZE + {first*stride(bits)}) as *u8, {sym}, {len(data)})')
        slots.append({'slot': slot, 'bits': bits, 'file': name, 'first_row': first,
                      'rows': len(data)//stride(bits), 'stride': stride(bits), 'bytes': len(data)})
    runs, words = [], b''
    for bits, palette in sorted(packing.palettes):
        data = packing.palette_bytes(bits, palette)
        first = palette*(16 if bits == 4 else 256)
        if runs and runs[-1]['bits'] == 4 == bits and runs[-1]['first_colour']+runs[-1]['colours'] == first:
            runs[-1]['colours'] += 16
        else:
            runs.append({'bits': bits, 'first_colour': first, 'colours': len(data)//2, 'offset': len(words)//2})
        words += data
    if runs:
        name = f'{stem}.tpal'
        files[name] = words
        embeds.append(f'embed {symbol}_TEXPAL: u16 = "{name}"')
        for run in runs:
            body.append(f'    load_palette({run["first_colour"]}, &{symbol}_TEXPAL[{run["offset"]}], {run["colours"]})')
    manifest = {'slots': slots, 'palettes': {'file': f'{stem}.tpal', 'runs': runs}}
    if animations:
        blob, anims = b'', []
        for key, label, ticks in animations:
            tile, place = packing.tiles[key], packing.placements[key]
            frames = [packing.encode(key, k) for k in range(len(tile.frames))]
            anim = {'tile': key, 'label': label, 'file': f'{stem}.frames', 'offset': len(blob),
                    'frames': len(frames), 'ticks': ticks, 'frame_bytes': len(frames[0]),
                    'row_bytes': tile.row_bytes(), 'rows': tile.alloc_height,
                    'vram': place.slot*SLOT_BYTES+place.y*stride(place.bits)+(place.x//2 if place.bits == 4 else place.x),
                    'stride': stride(place.bits)}
            blob += b''.join(frames)
            anims.append(anim)
        files[f'{stem}.frames'] = blob
        embeds.append(f'embed {symbol}_FRAMES: u8 = "{stem}.frames"')
        for a in anims:
            up = f'{symbol}_{a["label"].upper()}'
            embeds += [f'// {a["label"]}: {a["frames"]} frames of {a["rows"]} rows x {a["row_bytes"]} bytes, {a["ticks"]} ticks each,',
                       f'// copied row by row to VRAM_TEXTURES + {up}_VRAM (rows {a["stride"]} bytes apart).',
                       f'const {up}_AT = {a["offset"]}', f'const {up}_FRAME_BYTES = {a["frame_bytes"]}',
                       f'const {up}_FRAMES = {a["frames"]}', f'const {up}_TICKS = {a["ticks"]}',
                       f'const {up}_ROW_BYTES = {a["row_bytes"]}', f'const {up}_ROWS = {a["rows"]}',
                       f'const {up}_VRAM = {a["vram"]}', f'const {up}_STRIDE = {a["stride"]}']
        manifest['animations'] = anims
    return files, embeds, body, manifest


def texture_entries(mesh, packing, face_runs):
    """The manifest's list: one entry per textured material."""
    out = []
    for name, tex in mesh.textures['textures'].items():
        tile, place = tex.tile, packing.placements[tex.tile.key]
        entry = {'material': name, 'tile': tile.key, 'source': tex.source, 'width': tex.width,
                 'height': tex.height, 'bits': tex.bits, 'projection': tex.projection, 'repeat': tex.repeat,
                 'cutout': tex.cutout, 'colours': [rgb_hex(c) for c in tile.colours()],
                 'slot': place.slot, 'x': place.x, 'y': place.y, 'gutter': tile.gutter,
                 'window': place.halfword() or None, 'palette': place.palette,
                 'first_colour': place.first_colour(),
                 'indices': {rgb_hex(c): i for c, i in sorted(place.index.items(), key=lambda kv: kv[1]) if c in tile.colours()},
                 'vram_bytes': tile.vram_bytes(),
                 'night': 'per_colour' if tex.bits == 4 else 'multiply',
                 'faces': face_runs(mesh, lambda f, n=name: f.material == n)}
        if len(tile.frames) > 1:
            entry['frames'] = len(tile.frames)
            entry['ticks'] = tex.ticks
        out.append(entry)
    return out
