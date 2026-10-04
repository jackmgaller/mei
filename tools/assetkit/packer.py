"""`mei_assets.py pack`: several assets (or one) for a cart that draws them without a world.
Their textures go into one set of slots and palettes (kitcore/texpack.py: duplicates removed,
tiles at window-aligned origins, palettes shared while colours fit), their palette-backed
materials into consecutive palettes with one shared swatch, and each mesh is written for that
placement. One Akari file embeds every mesh and loads everything (docs/ASSETKIT.md, "Packing
assets for a cart")."""
import json

from kitcore.texpack import pack as pack_tiles
from .compiler import compile_recipe, native_bytes, face_runs, window_order, SWATCH
from .geometry import AssetError
from . import texout

PACK_FORMAT = 'mei-asset-pack'


def pack(recipes, name, slots, first_palette=0, palette8=14):
    """recipes: [(recipe, folder)]. Returns (files, manifest)."""
    assets, seen = [], set()
    for k, (recipe, folder) in enumerate(recipes):
        try:
            mesh, materials, report = compile_recipe(recipe, folder)
        except AssetError as error:
            raise AssetError(f'/assets/{k}'+error.path, f'{recipe.get("name", k)}: {error}') from error
        if recipe['name'] in seen:
            raise AssetError(f'/assets/{k}', f'Two assets are named {recipe["name"]!r}.')
        seen.add(recipe['name'])
        assets.append((recipe, mesh, materials, report))

    # Palette-backed materials: each asset's palettes, consecutive from first_palette, and one
    # swatch for all at row 0 of the first slot.
    swatch_slot = slots[0]
    palette, colours, palette_files = first_palette, [], b''
    relocated = {}
    for recipe, mesh, _, _ in assets:
        if not mesh.palette:
            continue
        old = mesh.palette
        shift = palette-old['palettes'][0]
        entries = [dict(e, palette=e['palette']+shift, colour=e['colour']+16*shift) for e in old['entries']]
        new = {'layout': {'slot': swatch_slot, 'row': 0, 'first': palette},
               'palettes': [p+shift for p in old['palettes']], 'entries': entries,
               'by_material': {m: e for e in entries for m in e['materials']}}
        relocated[recipe['name']] = new
        words = [0]*16*len(new['palettes'])
        for e in entries:
            words[e['colour']-palette*16] = e['rgb15']
        palette_files += b''.join(w.to_bytes(2, 'little') for w in words)
        colours.append((palette*16, 16*len(new['palettes'])))
        palette += len(new['palettes'])
    if palette > 255:
        raise AssetError('/assets', f'The palette-backed materials need {palette-first_palette} palettes from {first_palette}; palette 255 holds the fonts.')

    tiles = [t.tile for _, mesh, _, _ in assets if mesh.textures for t in mesh.textures['textures'].values()]
    reserved = [(swatch_slot, 0, 0, 16, 8)] if relocated else []
    packing = pack_tiles(tiles, slots=slots, first_palette=palette, palette8=palette8, reserved=reserved,
                         path='/assets') if tiles else None
    eight = [p for b, p in packing.palettes if b == 8] if packing else []
    if eight and palette > 16*min(eight):
        raise AssetError('/assets', f'8-bit palette {min(eight)} covers 4-bit palettes {16*min(eight)}-{16*min(eight)+15}, '
                                    'which the palette-backed materials use. Pass a higher --palette8 or a lower --palette.')

    files, upper = {}, name.upper()
    embeds, body, listing = [], [], []
    for recipe, mesh, materials, report in assets:
        asset = recipe['name']
        lighting = recipe.get('lighting', {})
        mesh.palette = relocated.get(asset, mesh.palette)
        for level, _ in mesh.levels or []:
            level.palette = mesh.palette if level.palette else None
        binary = native_bytes(mesh, materials, lighting, packing)
        levels = [native_bytes(level, materials, lighting, packing) for level, _ in mesh.levels or []]
        files[asset+'.bin'] = binary
        embeds.append(f'embed ASSET_{asset.upper()}: Mesh = "{asset}.bin"')
        for k, data in enumerate(levels, 1):
            files[f'{asset}.lod{k}.bin'] = data
            embeds.append(f'embed ASSET_{asset.upper()}_LOD{k}: Mesh = "{asset}.lod{k}.bin"')
        entry = {'name': asset, 'mesh': asset+'.bin', 'levels': [f'{asset}.lod{k}.bin' for k in range(1, len(levels)+1)],
                 'vertices': report['vertices'], 'triangles': report['triangles']}
        if mesh.palette:
            p = mesh.palette
            entry['palette'] = {'palettes': p['palettes'], 'entries': [{k: e[k] for k in ('colour', 'class', 'color', 'materials')}
                                                                      for e in p['entries']]}
            for kind in ('surface', 'emissive'):
                cs = [e['colour'] for e in p['entries'] if e['class'] == kind]
                if cs:
                    embeds += [f'const ASSET_{asset.upper()}_{kind.upper()} = {cs[0]}',
                               f'const ASSET_{asset.upper()}_{kind.upper()}_COUNT = {cs[-1]-cs[0]+1}']
        if mesh.textures:
            entry['textures'] = texout.texture_entries(mesh, packing, face_runs)
            entry['windows'] = [packing.placements[k].halfword() for k in window_order(mesh, packing)]
        listing.append(entry)

    manifest = {'format': PACK_FORMAT, 'version': 1, 'name': name, 'assets': listing}
    lines = [f'// Mei Asset Kit pack: {", ".join(a["name"] for a in listing)}. Call {name}_load() once before drawing.',
             *embeds]
    if packing:
        animations, seen_keys = [], set()
        for recipe, mesh, _, _ in assets:
            for material, tex in (mesh.textures['textures'].items() if mesh.textures else ()):
                if len(tex.tile.frames) > 1 and tex.tile.key not in seen_keys:
                    seen_keys.add(tex.tile.key)
                    animations.append((tex.tile.key, f'{recipe["name"]}_{material}', tex.ticks))
        tfiles, tembeds, tbody, section = texout.outputs(name, upper, packing, animations)
        files.update(tfiles)
        lines += tembeds
        body += tbody
        manifest['textures'] = {**section, **packing.summary()}
    if relocated:
        files[name+'.pal'] = palette_files
        files[name+'.swatch'] = SWATCH
        lines += [f'embed {upper}_PALETTE: u16 = "{name}.pal"', f'embed {upper}_SWATCH: u8 = "{name}.swatch"']
        body.append(f'    memcpy((VRAM_TEXTURES + {swatch_slot} * TEXTURE_SLOT_SIZE) as *u8, {upper}_SWATCH, {len(SWATCH)})')
        offset = 0
        for first, count in colours:
            body.append(f'    load_palette({first}, &{upper}_PALETTE[{offset}], {count})')
            offset += count
        manifest['swatch'] = {'file': name+'.swatch', 'slot': swatch_slot, 'row': 0, 'texels': 16}
        manifest['palette'] = {'file': name+'.pal', 'runs': [{'first_colour': f, 'colours': c} for f, c in colours]}
    lines += ['', '// Copies the textures, the swatch and the palettes into VRAM.', f'fn {name}_load() {{', *body, '}', '']
    files[name+'.akr'] = '\n'.join(lines).encode()
    files[name+'.pack.json'] = (json.dumps(manifest, indent=2)+'\n').encode()
    return files, manifest
