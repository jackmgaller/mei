"""Scatter: seeded props over an area, set on the ground, cut per cell (WORLDKIT.md, "Scatter").

    items, report = scatter_items(world, terrain, cell_size, cells, warnings)
    items[(i, j)]   [Item]: an asset at a position and yaw in the cell, with its scatter's name

A scatter lays a lattice of candidate squares `spacing` units a side over its area's bounds (on
the world's lattice, so editing one part of an area does not move the rest); each square keeps a
candidate with probability `fill`, moved from the square's centre by up to `jitter` of the
spacing. A candidate is dropped outside the area, inside an exclusion, on water, within
`clearance` of a sweep, where nothing it may stand on (`on`) is under it, or on ground steeper
than `max_slope`. Its asset is chosen by weight, its yaw at random (whole degrees) unless the
scatter gives one, and its ID is NAME_I_J from its square, stable while the square keeps it.
Every choice comes from SHA-256 of the seed, the scatter's name and the square: the same recipe
scatters the same props on every machine.

World.py merges each cell's props per scatter, layer and chunk (`chunk` units a side) into one
mesh, as merged scatter is; a chunk can carry a coarser level (its assets' level 1, from
`coarse`) and a cull distance (`cull`), so a forest costs only the chunks near the eye.
"""
from dataclasses import dataclass
import hashlib
import math
import struct

from kitcore.errors import pointer
from .schema import WorldError
from .terrain import Area, Polyline, TAG_FIELD, TAG_SWEEP, q16


@dataclass
class Item:
    scatter: str
    id: str
    asset: str
    position: tuple
    yaw: float
    collision: str
    layer: str
    chunk: tuple            # (scatter, layer, chunk i, chunk j)
    path: str               # JSON Pointer of the scatter's asset entry


def randoms(seed, name, i, j):
    """Six numbers in [0, 1) for square (i, j) of scatter name."""
    h = hashlib.sha256(f'{seed}:{name}:{i}:{j}'.encode()).digest()
    return [v / 2 ** 32 for v in struct.unpack('<8I', h)][:6]


def bounds(spec, paths):
    """(x0, z0, x1, z1) of an area spec."""
    if 'rect' in spec:
        r = spec['rect']
        return (min(r[0], r[2]), min(r[1], r[3]), max(r[0], r[2]), max(r[1], r[3]))
    if 'circle' in spec:
        x, z, r = spec['circle']
        return (x - r, z - r, x + r, z + r)
    if 'polygon' in spec:
        xs, zs = [p[0] for p in spec['polygon']], [p[1] for p in spec['polygon']]
        return (min(xs), min(zs), max(xs), max(zs))
    pts = paths[spec['path']]['points']
    h = spec.get('width', 0) / 2
    xs, zs = [p[0] for p in pts], [p[-1] for p in pts]
    return (min(xs) - h, min(zs) - h, max(xs) + h, max(zs) + h)


def scatter_items(w, terrain, size, cells, warnings):
    specs = w.get('scatter', {})
    if not specs:
        return {}, {}
    if terrain is None:
        raise WorldError('/scatter', 'Scatter sets props on the ground: it needs terrain (a field or a sweep).')
    paths = w.get('paths', {})
    floors = terrain.floors()
    # every sweep's corridor: its line and how far its profile reaches from it
    corridors = []
    for pname, p in paths.items():
        if 'sweep' in p:
            pts = terrain.paths.get(pname, p['points'])
            reach = max(abs(q[0]) for q in p['sweep']['profile'])
            corridors.append((Polyline([tuple(q) for q in pts], bool(p.get('closed'))), reach))
    out, report = {}, {}
    for name, sc in specs.items():
        sp = pointer('/scatter', name)
        area = Area(sc['area'], paths, sp + '/area')
        excludes = [Area(e, paths, f'{sp}/exclude/{k}') for k, e in enumerate(sc.get('exclude', []))]
        layer = sc.get('layer')
        if layer is not None and layer not in w.get('layers', {}):
            raise WorldError(sp + '/layer', f'No layer {layer!r}. Declare it in the world\'s layers.')
        yaw = sc.get('yaw', 'random')
        if not (yaw == 'random' or (type(yaw) in (int, float) and -360 <= yaw <= 360)):
            raise WorldError(sp + '/yaw', 'yaw is degrees (-360 to 360) or "random".')
        weights = [a.get('weight', 1.0) for a in sc['assets']]
        total = sum(weights)
        spacing, fill, jitter = sc['spacing'], sc.get('fill', 1.0), sc.get('jitter', 0.8)
        seed = sc.get('seed', 0)
        clearance = sc.get('clearance', 1.0)
        slope_cos = math.cos(math.radians(sc.get('max_slope', 35)))
        on = sc.get('on', 'terrain')
        tags = {'terrain': (TAG_FIELD,), 'sweeps': (TAG_SWEEP,), 'both': (TAG_FIELD, TAG_SWEEP)}[on]
        chunk = sc.get('chunk', 16)
        if chunk > size:
            raise WorldError(sp + '/chunk', f'A chunk is at most a cell ({size}).')
        x0, z0, x1, z1 = bounds(sc['area'], paths)
        squares = (math.floor(x1 / spacing) - math.floor(x0 / spacing) + 1) * (math.floor(z1 / spacing) - math.floor(z0 / spacing) + 1)
        if squares > 1_000_000:
            raise WorldError(sp + '/spacing', f'{squares:,} candidate squares; at most 1,000,000. Raise the spacing.')
        dropped = {'area': 0, 'excluded': 0, 'water': 0, 'sweep': 0, 'no_ground': 0, 'steep': 0, 'cell': 0}
        placed, by_asset, by_cell = 0, {}, {}
        for j in range(math.floor(z0 / spacing), math.floor(z1 / spacing) + 1):
            for i in range(math.floor(x0 / spacing), math.floor(x1 / spacing) + 1):
                u = randoms(seed, name, i, j)
                if u[0] >= fill:
                    continue
                x = q16((i + 0.5 + (u[1] - 0.5) * jitter) * spacing)
                z = q16((j + 0.5 + (u[2] - 0.5) * jitter) * spacing)
                if area.distance(x, z) > 0:
                    dropped['area'] += 1
                    continue
                if any(e.distance(x, z) <= 0 for e in excludes):
                    dropped['excluded'] += 1
                    continue
                key = (math.floor(x / size), math.floor(z / size))
                if key not in cells:
                    dropped['cell'] += 1
                    continue
                if any(line.nearest(x, z)[0] <= reach + clearance for line, reach in corridors):
                    dropped['sweep'] += 1
                    continue
                hit = floors.at(x, z)
                if hit is None or hit[1] not in tags:
                    dropped['no_ground'] += 1
                    continue
                level = terrain.water_level(x, z)
                if level is not None and level > hit[0]:
                    dropped['water'] += 1
                    continue
                if hit[2] < slope_cos:
                    dropped['steep'] += 1
                    continue
                pick, acc = 0, u[3] * total
                while pick < len(weights) - 1 and acc >= weights[pick]:
                    acc -= weights[pick]
                    pick += 1
                a = sc['assets'][pick]
                lift = a.get('lift', sc.get('lift', 0.0))
                turn = float(math.floor(u[4] * 360)) if yaw == 'random' else float(yaw)
                c = (name, layer, math.floor(x / chunk), math.floor(z / chunk))
                out.setdefault(key, []).append(Item(name, f'{name}_{i}_{j}', a['asset'], (x, q16(hit[0] + lift), z),
                                                    turn, a.get('collision', 'none'), layer, c, f'{sp}/assets/{pick}'))
                placed += 1
                by_asset[a['asset']] = by_asset.get(a['asset'], 0) + 1
                by_cell[f'{key[0]},{key[1]}'] = by_cell.get(f'{key[0]},{key[1]}', 0) + 1
        report[name] = {'placed': placed, 'assets': by_asset, 'cells': by_cell,
                        'dropped': {k: v for k, v in dropped.items() if v}}
        if not placed:
            warnings.append({'code': 'scatter_empty', 'scatter': name,
                             'message': 'Nothing was placed: check the area, exclusions, on and max_slope.'})
    return out, report
