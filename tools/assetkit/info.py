"""`mei_assets.py info` and `floors` (docs/ASSETKIT.md, "Quick facts"): what placing an asset
costs and where its collision can be stood on, from the recipe alone (nothing is rendered or
written).

    info(recipe, folder)        bounds (drawn and collision), triangles per level of detail and
                                their switch distances, texture bytes per texture with shared
                                tiles and images named, palettes and texture windows
    floors(recipe, folder)      a grid of the collision's top floor heights, with walls and
                                faces too steep to stand on marked

Both take an optional placement (`at`, a position, and `yaw` in degrees, as a world places it:
mesh_at()'s turn, +Z toward +X), and the collision recipe: 'auto' (NAME_col.asset.json beside
the recipe if there is one, else the recipe itself), 'self', or a recipe path.
"""
import math
from pathlib import Path

from kitcore import jsonio
from kitcore.vector import yaw as turn, quantize
from .compiler import compile_recipe, window_order
from .geometry import AssetError, cross, sub, dot
from .textures import describe, MAX_WINDOWS

FLOOR_DEGREES = 45.0         # the World Kit's default floor_max_degrees (a game's probe may set less)
CEILING_DEGREES = 45.0


def texture_windows(mesh):
    """The repeating textures in the order of the mesh's window table: inspect's texture_windows."""
    packing, textures = mesh.textures['packing'], mesh.textures['textures']
    windows = []
    for k, key in enumerate(window_order(mesh, packing), 1):
        users = [t for t in textures.values() if t.tile.key == key]
        windows.append({'window': k, 'texture': describe(users[0]), 'size': [users[0].width, users[0].height],
                        'bits': users[0].bits, 'materials': sorted(t.material for t in users)})
    return {'used': len(windows), 'max': MAX_WINDOWS, 'windows': windows}


def collision_source(recipe, folder, collision='auto'):
    """(name, recipe, folder, how) of the collision to use, or None for 'none'."""
    if collision == 'none':
        return None
    if collision in ('auto', 'self'):
        beside = Path(folder or '.')/f'{recipe["name"]}_col.asset.json'
        if collision == 'auto' and beside.is_file():
            return beside.name[:-len('.asset.json')], jsonio.load(str(beside), AssetError), beside.parent, \
                f'{beside.name} (beside the recipe)'
        return recipe['name'], recipe, folder, 'the recipe itself (self)'
    path = Path(collision)
    if not path.is_file():
        raise AssetError('/arguments/collision', f'No collision recipe {path}: give self, none, auto or a recipe path.')
    return path.name.split('.')[0], jsonio.load(str(path), AssetError), path.resolve().parent, str(path)


def placed(points, at=None, yaw=0.0):
    """Points of the asset's frame where a placement at `at` turned by `yaw` puts them."""
    at = at or (0.0, 0.0, 0.0)
    return [tuple(c + o for c, o in zip(turn(p, yaw), at)) for p in points]


def box(points):
    if not points:
        return None
    return {'min': [round(min(p[k] for p in points), 4) for k in range(3)],
            'max': [round(max(p[k] for p in points), 4) for k in range(3)]}


def kinds(tris, floor_degrees=FLOOR_DEGREES, ceiling_degrees=CEILING_DEGREES):
    """Each triangle (a, b, c) as the World Kit's collision files it: 'floor', 'wall' or 'ceiling'
    (worldkit.pack.classify() of the exported face, whose corners run the other way round:
    the front normal is (b - a) x (c - a) of the recipe's face)."""
    fc, cc = math.cos(math.radians(floor_degrees)), math.cos(math.radians(ceiling_degrees))
    out = []
    for a, b, c in tris:
        n = cross(sub(b, a), sub(c, a))
        nn = dot(n, n)
        if nn == 0:
            out.append(None)
        elif n[1] > 0 and n[1] * n[1] >= fc * fc * nn:
            out.append('floor')
        elif n[1] < 0 and n[1] * n[1] >= cc * cc * nn:
            out.append('ceiling')
        elif n[1] > 1e-9 * math.sqrt(nn):
            out.append('steep')             # faces up, too steep to stand on: a wall to the body
        else:
            out.append('wall')
    return out


def triangles(mesh, at=None, yaw=0.0):
    """The mesh's faces as triangles of exported (16.16) corners, placed."""
    verts = placed([tuple(quantize(c) for c in v) for v in mesh.vertices], at, yaw)
    return [tuple(verts[i] for i in f.indices[:3]) for f in mesh.faces]


def info(recipe, folder=None, collision='auto', at=None, yaw=0.0, floor_degrees=FLOOR_DEGREES):
    mesh, materials, report = compile_recipe(recipe, folder, 'warn')
    out = {'ok': True, 'name': recipe['name'], 'triangles': report['triangles'], 'vertices': report['vertices'],
           'mesh_bytes': report['mesh_bytes'], 'bounds': box([tuple(v) for v in mesh.vertices])}
    if at is not None or yaw:
        out['placed'] = {'at': list(at or (0, 0, 0)), 'yaw': yaw,
                         'bounds': box(placed([tuple(v) for v in mesh.vertices], at, yaw))}
    # levels of detail
    lod = report.get('lod')
    out['lod'] = lod if lod else {'levels': [{'level': 0, 'distance': 0, 'triangles': report['triangles'],
                                              'vertices': report['vertices']}], 'cull': None, 'band': None}
    # collision
    src = collision_source(recipe, folder, collision)
    if src is None:
        out['collision'] = {'source': 'none'}
    else:
        name, crecipe, cfolder, how = src
        cmesh = mesh if crecipe is recipe else compile_recipe(crecipe, cfolder, 'warn')[0]
        tris = triangles(cmesh, at, yaw)
        k = kinds(tris, floor_degrees)
        out['collision'] = {'source': how, 'name': name, 'triangles': len(tris),
                            'floors': k.count('floor'), 'walls': k.count('wall'), 'steep': k.count('steep'),
                            'ceilings': k.count('ceiling'), 'floor_max_degrees': floor_degrees,
                            'bounds': box([tuple(quantize(c) for c in v) for v in cmesh.vertices]),
                            **({'placed_bounds': box([p for t in tris for p in t])} if 'placed' in out else {})}
        local = triangles(cmesh)
        tops = [max(p[1] for p in t) for t, kind in zip(local, kinds(local, floor_degrees)) if kind == 'floor']
        out['collision']['top_floor'] = round(max(tops), 4) if tops else None
        if 'placed' in out and tops:
            out['collision']['placed_top_floor'] = round(max(max(p[1] for p in t) for t, kind in zip(tris, k)
                                                             if kind == 'floor'), 4)
    # palettes and textures
    pal = report.get('palette')
    out['palettes'] = {'palette_backed': {'palettes': len(pal['palettes']), 'entries': pal['entries'],
                                          'emissive_entries': pal.get('emissive_entries', 0)} if pal else None}
    if mesh.textures:
        tex = report['textures']
        out['palettes']['texture_4bit'] = len(tex['palettes_4bit'])
        out['palettes']['texture_8bit'] = len(tex['palettes_8bit'])
        textures, tiles, images = [], {}, {}
        for material, t in sorted(mesh.textures['textures'].items()):
            tile = t.tile
            row = {'material': material, 'source': describe(t), 'size': [t.width, t.height], 'bits': t.bits,
                   'repeat': t.repeat, 'stored': tile.vram_bytes(), 'allocated': tile.allocated_bytes(),
                   'tile': tile.key}
            if len(t.frames) > 1:
                row['frames'] = len(t.frames)
            if 'image' in t.source:
                row['image'] = t.source['image']
                images.setdefault(t.source['image'], []).append(material)
            tiles.setdefault(tile.key, []).append(material)
            textures.append(row)
        for row in textures:
            shared = [m for m in tiles[row['tile']] if m != row['material']]
            if shared:
                row['same_tile_as'] = shared
        distinct = {}
        for material, t in mesh.textures['textures'].items():
            distinct[t.tile.key] = t.tile
        out['textures'] = {'textures': textures, 'tiles': len(distinct),
                           'stored': sum(t.vram_bytes() for t in distinct.values()),
                           'allocated': sum(t.allocated_bytes() for t in distinct.values()),
                           'images': [{'image': im, 'materials': ms, 'allocated': sum(
                               tile.allocated_bytes() for tile in {mesh.textures['textures'][m].tile.key:
                                                                    mesh.textures['textures'][m].tile for m in ms}.values())}
                                      for im, ms in sorted(images.items())],
                           'windows': texture_windows(mesh)}
    else:
        out['textures'] = None
    return out


def info_text(r):
    b = r['bounds']
    size = [round(b['max'][k] - b['min'][k], 3) for k in range(3)]
    out = [f'{r["name"]}: {r["triangles"]:,} triangles, {r["vertices"]:,} vertices, {r["mesh_bytes"]:,} mesh bytes',
           f'bounds (drawn): {b["min"]} .. {b["max"]} (size {size})']
    if 'placed' in r:
        p = r['placed']
        out.append(f'  placed at {p["at"]} yaw {p["yaw"]:g}: {p["bounds"]["min"]} .. {p["bounds"]["max"]}')
    c = r['collision']
    if c['source'] == 'none':
        out.append('collision: none')
    else:
        out.append(f'collision: {c["source"]}: {c["triangles"]} triangles ({c["floors"]} floors, {c["walls"]} walls, '
                   f'{c["steep"]} too steep, {c["ceilings"]} ceilings at floor_max {c["floor_max_degrees"]:g} deg); '
                   f'bounds {c["bounds"]["min"]} .. {c["bounds"]["max"]}; highest floor y {c["top_floor"]}')
        if 'placed_bounds' in c:
            out.append(f'  placed: {c["placed_bounds"]["min"]} .. {c["placed_bounds"]["max"]}; highest floor y '
                       f'{c.get("placed_top_floor")}')
    lod = r['lod']
    out.append('levels of detail: ' + ', '.join(f'L{l["level"]} {l["triangles"]:,} tris from {l["distance"]:g}'
                                                for l in lod['levels'])
               + (f'; cull at {lod["cull"]:g}' if lod.get('cull') else '')
               + (f'; band {lod["band"]:g}' if lod.get('band') else '')
               + ('' if len(lod['levels']) > 1 else ' (no lod)'))
    p = r['palettes']
    pb = p['palette_backed']
    out.append('palettes: ' + (f'{pb["palettes"]} palette-backed ({pb["entries"]} entries, {pb["emissive_entries"]} '
                               'emissive)' if pb else 'no palette-backed materials')
               + (f'; textures {p["texture_4bit"]} 4-bit, {p["texture_8bit"]} 8-bit' if 'texture_4bit' in p else ''))
    t = r['textures']
    if not t:
        out.append('textures: none')
        return '\n'.join(out)
    out.append(f'textures: {t["tiles"]} tiles, {t["stored"]:,} bytes stored, {t["allocated"]:,} allocated on the 8-texel '
               'grid (what a world region\'s budget counts)')
    out.append(f'  {"material":20} {"size":>9} {"bits":>4} {"stored":>7} {"alloc":>7}  source')
    for x in t['textures']:
        out.append(f'  {x["material"][:20]:20} {x["size"][0]:>4}x{x["size"][1]:<4} {x["bits"]:>4} {x["stored"]:>7,} '
                   f'{x["allocated"]:>7,}  {x["source"]}' + (' (repeats)' if x['repeat'] else '')
                   + (f' {x["frames"]} frames' if 'frames' in x else '')
                   + (f'; same tile as {", ".join(x["same_tile_as"])}' if 'same_tile_as' in x else ''))
    for im in t['images']:
        if len(im['materials']) > 1:
            out.append(f'  image {im["image"]}: {len(im["materials"])} textures, {im["allocated"]:,} bytes '
                       f'({", ".join(im["materials"])})')
    w = t['windows']
    out.append(f'texture windows: {w["used"]} of {w["max"]}' + (': ' + '; '.join(
        f'{x["window"]} {x["texture"]} {x["size"][0]}x{x["size"][1]} ({", ".join(x["materials"])})'
        for x in w['windows']) if w['windows'] else ''))
    return '\n'.join(out)


def floors(recipe, folder=None, step=0.25, collision='auto', at=None, yaw=0.0, floor_degrees=FLOOR_DEGREES,
           area=None, below=None):
    """A grid of the collision's top floor under each point (x, z), over its bounds seen from
    above (or `area`, x0, z0, x1, z1), in the placed frame: the highest floor face's height (at
    or below `below`, if given), every floor's height there (`stacks`), and a mark per point:
    'floor', 'steep' (a face too steep to stand on is above the floor there), 'wall' (a wall
    passes within half a step), or None (nothing)."""
    src = collision_source(recipe, folder, collision)
    if src is None:
        raise AssetError('/arguments/collision', 'Collision none has no floors.')
    name, crecipe, cfolder, how = src
    mesh = compile_recipe(crecipe, cfolder, 'warn')[0]
    if step <= 0:
        raise AssetError('/arguments/step', 'The step is more than 0.')
    tris = triangles(mesh, at, yaw)
    k = kinds(tris, floor_degrees)
    if area is None:
        pts = [p for t in tris for p in t]
        lo = [math.floor(min(p[0] for p in pts) / step) * step, math.floor(min(p[2] for p in pts) / step) * step]
        hi = [math.ceil(max(p[0] for p in pts) / step) * step, math.ceil(max(p[2] for p in pts) / step) * step]
    else:
        lo, hi = [area[0], area[1]], [area[2], area[3]]
    nx, nz = int(round((hi[0] - lo[0]) / step)) + 1, int(round((hi[1] - lo[1]) / step)) + 1
    if nx * nz > 250000:
        raise AssetError('/arguments/step', f'{nx} x {nz} points is too many: a larger step.')
    xs = [round(lo[0] + a * step, 6) for a in range(nx)]
    zs = [round(lo[1] + b * step, 6) for b in range(nz)]
    heights = [[None] * nx for _ in zs]
    marks = [[None] * nx for _ in zs]
    tops = [[None] * nx for _ in zs]                # the highest non-floor face facing up
    stacks = [[[] for _ in xs] for _ in zs]
    limit = math.inf if below is None else below + 1e-9

    def cover(t):
        x0, x1 = min(p[0] for p in t), max(p[0] for p in t)
        z0, z1 = min(p[2] for p in t), max(p[2] for p in t)
        a0, a1 = max(0, math.ceil((x0 - lo[0]) / step - 1e-9)), min(nx - 1, math.floor((x1 - lo[0]) / step + 1e-9))
        b0, b1 = max(0, math.ceil((z0 - lo[1]) / step - 1e-9)), min(nz - 1, math.floor((z1 - lo[1]) / step + 1e-9))
        return a0, a1, b0, b1
    for t, kind in zip(tris, k):
        if kind not in ('floor', 'steep'):
            continue
        a, b, c = t
        n = cross(sub(b, a), sub(c, a))
        a0, a1, b0, b1 = cover(t)
        for bz in range(b0, b1 + 1):
            for ax in range(a0, a1 + 1):
                x, z = xs[ax], zs[bz]
                s = [(t[(e + 1) % 3][0] - t[e][0]) * (z - t[e][2]) - (t[(e + 1) % 3][2] - t[e][2]) * (x - t[e][0])
                     for e in range(3)]
                if not (all(v >= -1e-9 for v in s) or all(v <= 1e-9 for v in s)):
                    continue
                y = a[1] - (n[0] * (x - a[0]) + n[2] * (z - a[2])) / n[1]
                if kind == 'floor':
                    stacks[bz][ax].append(round(y, 4))
                if y > limit:
                    continue
                if kind == 'floor':
                    if heights[bz][ax] is None or y > heights[bz][ax]:
                        heights[bz][ax] = round(y, 4)
                elif tops[bz][ax] is None or y > tops[bz][ax]:
                    tops[bz][ax] = y
    for bz in range(nz):
        for ax in range(nx):
            if heights[bz][ax] is not None:
                marks[bz][ax] = 'floor'
            if tops[bz][ax] is not None and (heights[bz][ax] is None or tops[bz][ax] > heights[bz][ax] + 1e-6):
                marks[bz][ax] = 'steep'
    # walls: their outline seen from above, sampled finer than the grid
    for t, kind in zip(tris, k):
        if kind != 'wall':
            continue
        for e in range(3):
            p, q = t[e], t[(e + 1) % 3]
            ln = math.hypot(q[0] - p[0], q[2] - p[2])
            for s in range(int(ln / (step / 4)) + 2):
                f = min(1.0, s * step / 4 / ln) if ln else 0.0
                x, z = p[0] + (q[0] - p[0]) * f, p[2] + (q[2] - p[2]) * f
                ax, bz = round((x - lo[0]) / step), round((z - lo[1]) / step)
                if 0 <= ax < nx and 0 <= bz < nz and marks[bz][ax] != 'steep':
                    marks[bz][ax] = 'wall'
    out = {'ok': True, 'name': recipe['name'], 'collision': how, 'step': step, 'floor_max_degrees': floor_degrees,
           'below': below, 'x': xs, 'z': zs, 'heights': heights, 'marks': marks,
           'stacks': [[sorted(set(h)) for h in row] for row in stacks],
           'floor_heights': sorted({h for row in heights for h in row if h is not None})}
    if at is not None or yaw:
        out['placed'] = {'at': list(at or (0, 0, 0)), 'yaw': yaw}
    return out


def floors_text(r):
    width = max([5] + [len(f'{h:.2f}') for row in r['heights'] for h in row if h is not None])
    where = (f' placed at {r["placed"]["at"]} yaw {r["placed"]["yaw"]:g}' if 'placed' in r else ' in its own frame')
    where += f', at or below y {r["below"]:g}' if r['below'] is not None else ''
    out = [f'{r["name"]}: collision floors ({r["collision"]}){where}, step {r["step"]:g}, floor_max '
           f'{r["floor_max_degrees"]:g} deg; north (+Z) up', 'heights ("-": no floor)']
    out.append(' ' * 9 + ' '.join(f'{x:>{width}g}' for x in r['x']))
    for z, row in zip(reversed(r['z']), reversed(r['heights'])):
        out.append(f'{z:>8g} ' + ' '.join(f'{h:>{width}.2f}' if h is not None else f'{"-":>{width}}' for h in row))
    out += ['', 'marks ("." floor, "#" a wall within half a step, "^" a face too steep to stand on above the floor, '
            '" " nothing)']
    sym = {'floor': '.', 'wall': '#', 'steep': '^', None: ' '}
    for z, row in zip(reversed(r['z']), reversed(r['marks'])):
        out.append(f'{z:>8g} ' + ''.join(sym[m] for m in row))
    out.append('floor heights: ' + ', '.join(f'{h:g}' for h in r['floor_heights'][:30])
               + (' ...' if len(r['floor_heights']) > 30 else ''))
    return '\n'.join(out)
