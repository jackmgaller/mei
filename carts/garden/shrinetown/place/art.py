"""The art over the placed level: the ground's textures (art/ground/GROUND.md), the water's
(art/water/APPLY.md) and the edges' real assets in place of the grey box's (the neighbours' backs
and the road-works hoardings). Not a placement zone: the last module the hook calls, after the
five zones, so it sees their cells, operations and paths.

- town(g), from notes/gen_town.py: the grey-box neighbours and hoardings become
  edge_neighbour_KEY and edge_hoarding.
- world(g), from make_world.py: the terrain materials get their textures; the town's ground gets
  the front road's rows, its kerbs and crossing, the sports ground's lines; the shrine's the
  sando and the playground's sand; the water its textures. TOWN CELLS USE TOWN TEXTURES ONLY
  (GROUND.md, "Rules"): what is shrine ground south of the region boundary (z 128) is drawn in
  untextured materials of the textures' far colours, so the paints and cliffs that cross the line
  are split there and the sweeps that started south of it start on it.
"""
import math

BOUNDARY = 128.0                     # the texture regions' line (TEXTURES.md)
G = 'art/ground/'                    # paths relative to the world file
SH = '../shrine/assets/art/terrain_'


def tex(image, scale, span, **extra):
    return {'image': image, 'scale': [scale, scale], 'span': span, **extra}


# ---- the ground: GROUND.md's tables (scale in metres a repeat; span in texels)
TOWN = {
    'street': ('#b7b2a7', tex(G + 'concrete.png', 2.0, 23)),           # alleys, lanes, yards
    'pooldeck': ('#b7b2a7', tex(G + 'concrete.png', 2.0, 23)),
    'asphalt': ('#4a4a51', tex(G + 'asphalt.png', 2.0, 23)),
    'asphalt_line_x': ('#53535a', tex(G + 'asphalt_line.png', 2.0, 23, rotate=90)),
    'asphalt_zebra_x': ('#969696', tex(G + 'asphalt_zebra.png', 2.0, 23, rotate=90)),
    'asphalt_stop': ('#6b6b6f', tex(G + 'asphalt_stop.png', 2.0, 71)),   # 71: never windowed on a quad
    'sidewalk': ('#b2aea2', tex(G + 'sidewalk.png', 2.0, 23)),
    'sidewalk_tactile': ('#b8ab8a', tex(G + 'sidewalk_tactile.png', 2.0, 23)),
    'sidewalk_tactile_x': ('#b8ab8a', tex(G + 'sidewalk_tactile.png', 2.0, 23, rotate=90)),
    'paving': ('#bebaaa', tex(G + 'plaza.png', 4.0, 23)),                # the station plaza
    'sando': ('#bebaaa', tex(G + 'plaza.png', 4.0, 23, offset=[0.5, 0])),  # the shotengai: bands on x 154, 158, ...
    'clay': ('#c39a6a', tex(G + 'ground.png', 2.0, 23)),                 # the sports ground
    'ground_line': ('#c6a173', tex(G + 'ground_line.png', 2.0, 23)),
    'ground_line_x': ('#c6a173', tex(G + 'ground_line.png', 2.0, 23, rotate=90)),
}
BOTH = {                                                                 # the canal and the culvert cross the line
    'bank': ('#807b70', tex(G + 'canal_wall.png', 1.6, 23)),
    'bed': ('#4b4332', tex(SH + 'pond_bed.png', 2.4, 23)),
}
SHRINE = {
    'floor': ('#594325', tex(SH + 'floor.png', 2.4, 87)),
    'litter': ('#7b4825', tex(SH + 'litter.png', 2.4, 87)),
    'moss': ('#56732d', tex(SH + 'moss.png', 2.4, 87)),
    'earth': ('#65452f', tex(SH + 'earth.png', 2.4, 87)),
    'fox_earth': ('#65452f', tex(SH + 'earth.png', 2.4, 87)),
    'path': ('#906f4c', tex(SH + 'path.png', 2.4, 87)),
    'lane': ('#906f4c', tex(SH + 'path.png', 2.4, 87)),
    'gravel': ('#d4cbb9', tex(SH + 'gravel.png', 2.4, 87)),
    'ashlar': ('#d4cbb9', tex(SH + 'gravel.png', 2.4, 87)),              # the precinct's terrace top
    'sando_stone': ('#aba294', tex(SH + 'paving.png', 2.4, 87)),         # the approach, torii to gate
    'steps': ('#908b7f', tex(SH + 'steps.png', 2.4, 87)),
    'stone': ('#848072', tex(SH + 'stone.png', 3.2, 87)),
    'podium': ('#848072', tex(SH + 'stone.png', 3.2, 87)),
    'precinct_wall': ('#848072', tex(SH + 'stone.png', 3.2, 87)),        # canal_stone's terrace and podium walls
    'rock': ('#686157', tex(SH + 'rock.png', 4.8, 87)),
    'cemetery': ('#9b938a', tex(G + 'cemetery_gravel.png', 2.4, 87)),
    'canal_stone': ('#807b70', tex(G + 'canal_wall.png', 2.4, 23)),     # the cemetery's terrace walls (larger
    # stones than the canal's: its long walls stretched the texture at 1.6, terrain_texture_stretched)
    'bamboo_floor': ('#897a4a', tex(G + 'bamboo_floor.png', 2.4, 87)),
    'grass': ('#688436', tex(G + 'park_grass.png', 2.4, 87)),
    'park_sand': ('#d7c69d', tex(G + 'park_sand.png', 2.4, 23)),
}
# shrine ground south of the line: flat, in the far colour of the texture it stands for
FAR = {'grass': 'grass_far', 'floor': 'floor_far', 'gravel': 'gravel_far', 'rock': 'rock_far',
       'path': 'path_far', 'lane': 'path_far', 'steps': 'steps_far'}

# ---- the water: art/water/APPLY.md
WATER = {
    'water': ('#3f7393', tex('art/water/water.png', 4.8, 23)),
    'stream_water': ('#3f7393', tex('art/water/water.png', 7.2, 23)),
    'pond_water': ('#2f4c46', tex('art/water/pond_water.png', 4.8, 23)),
    'falls': ('#dce8f0', {'image': 'art/water/falls.png', 'scale': [3.0, 6.4], 'span': 23}),
}

# ---- the edges: (face width, height) come from the recipes; the side fixes the yaw
EDGE_YAW = {'s': 180.0, 'e': 90.0, 'w': 270.0}


def town(g):
    """The neighbours' backs and the hoardings: the grey box's placements, the same places."""
    n = 0
    for c in g['cells'].values():
        for p in c['placements']:
            pid = p['id']
            if pid.startswith('neighbour_') and pid[10] in EDGE_YAW:
                p['asset'], p['collision'] = f'edge_{pid}', 'self'
                p['yaw'] = EDGE_YAW[pid[10]]
                n += 1
            elif pid in ('hoarding_w', 'hoarding_e'):
                p['asset'], p['collision'] = 'edge_hoarding', 'self'
                p['yaw'] = 270.0 if pid == 'hoarding_w' else 90.0
                n += 1
    assert n == 17, n


def _rect(op):
    return op.get('area', {}).get('rect')


def _paint(rect, material):
    return {'op': 'paint', 'area': {'rect': rect}, 'material': material}


def _band(p, q, half):
    """A polygon half wide either side of the segment p-q (x, z)."""
    dx, dz = q[0] - p[0], q[1] - p[1]
    k = half / math.hypot(dx, dz)
    nx, nz = -dz * k, dx * k
    return [[round(a, 3), round(b, 3)] for a, b in
            ((p[0] + nx, p[1] + nz), (q[0] + nx, q[1] + nz), (q[0] - nx, q[1] - nz), (p[0] - nx, p[1] - nz))]


def _front_road():
    """GROUND.md, "Markings": the front road's rows (z 104-118) as far east as x 286, where the
    road bends under the viaduct (station's asphalt polygon); the crossing at the shotengai's
    mouth; the stop lines."""
    X0, X1 = 0, 286
    rows = [(104, 'sidewalk_tactile_x'), (106, 'sidewalk'), (110, 'asphalt_line_x'),
            (114, 'sidewalk'), (116, 'sidewalk_tactile_x')]
    ops = [_paint([X0, z, X1, z + 2], m) for z, m in rows]
    ops += [_paint([X0, 108, X1, 110], 'asphalt'), _paint([X0, 112, X1, 114], 'asphalt')]
    ops += [_paint([158, 108, 162, 114], 'asphalt_zebra_x'),
            _paint([158, 104, 160, 108], 'sidewalk_tactile'), _paint([158, 114, 160, 118], 'sidewalk_tactile'),
            _paint([154, 112, 156, 114], 'asphalt_stop'), _paint([164, 108, 166, 110], 'asphalt_stop')]
    return ops


def _kerbs():
    """Kerb sweeps, 0.15 m, along z 108 and 114, broken at the canal's bridge, the culvert, the
    crossing and the road's bend."""
    prof = {'profile': [[-0.1, 0], [-0.1, 0.15], [0.1, 0.15], [0.1, 0]], 'material': 'kerb', 'caps': True}
    runs = [(0.4, 43.6), (52.4, 157.6), (162.4, 233.6), (238.4, 286.0)]
    out = {}
    for z in (108.0, 114.0):
        for k, (a, b) in enumerate(runs):
            out[f'kerb_{int(z)}_{k}'] = {'points': [[a, 0.0, z], [b, 0.0, z]], 'sweep': dict(prof)}
    return out


def _sports_lines():
    lines = [_paint([246, 18, 248, 52], 'ground_line'), _paint([288, 18, 290, 52], 'ground_line'),
             _paint([266, 18, 268, 52], 'ground_line'),
             _paint([244, 20, 292, 22], 'ground_line_x'), _paint([244, 48, 292, 50], 'ground_line_x')]
    return lines


def world(g):
    w = g['world']
    mats = w['terrain']['materials']
    ops = w['terrain']['fields']['ground']['operations']
    paths = w['paths']

    # ---- materials
    for table in (TOWN, BOTH, SHRINE, WATER):
        for name, (colour, texture) in table.items():
            spec = dict(mats.get(name, {}), color=colour, texture=texture)
            if name in WATER:
                spec.update(water=True)
                if name != 'falls':
                    spec['tag'] = 'water'
            mats[name] = spec
    for name, flat in FAR.items():
        mats[flat] = {'color': SHRINE[name][0]}
    # the kerb is flat: textured, a sweep is cut wherever it would pass its stored repeats (every
    # 1.4 m at a 1 m scale: 2,800 triangles for the road's kerbs); the texture is kept in art/ground
    mats['kerb'] = {'color': '#bbb7ab'}

    # ---- the town's ground: split what crosses the line, flat south of it
    out = []
    for op in ops:
        m, r = op.get('material'), _rect(op)
        if m in FAR and op['op'] in ('paint', 'cliff') and r and r[1] < BOUNDARY:
            if r[3] <= BOUNDARY:
                out.append(dict(op, material=FAR[m]))
            else:
                out.append(dict(op, area={'rect': [r[0], r[1], r[2], BOUNDARY]}, material=FAR[m]))
                out.append(dict(op, area={'rect': [r[0], BOUNDARY, r[2], r[3]]}))
            continue
        if m == 'canal_stone' and r and r[0] < 250:                        # the precinct's terrace wall
            out.append(dict(op, material='precinct_wall'))
            continue
        out.append(op)
        if op.get('material') == 'pooldeck' and op['op'] == 'paint':      # after the town's own paints
            out += _front_road() + _sports_lines()
    assert len(out) > len(ops), 'the town part has no pooldeck paint to follow'
    ops[:] = out

    # sweeps that began south of the line now begin on it; their first 9 m are painted flat
    for name in ('trail_west', 'core_canal_lane'):
        pts = paths[name]['points']
        (x0, z0), (x1, z1) = pts[0][:2], pts[1][:2]
        assert z0 < BOUNDARY < z1, (name, pts[:2])
        xb = x0 + (x1 - x0) * (BOUNDARY - z0) / (z1 - z0)
        pts[0] = [round(xb, 3), BOUNDARY]
        ops.append({'op': 'paint', 'area': {'polygon': _band((x0, z0), (xb, BOUNDARY - 0.01), 1.6)},
                    'material': 'path_far'})
    for name in ('core_walkway_stair', 'core_cem_stair_0'):                 # town stairs (all or partly)
        s = paths[name]['sweep']
        s['materials'] = ['steps_far' if m == 'steps' else m for m in s['materials']]
    paths.update(_kerbs())

    # ---- the shrine's ground
    ops += [_paint([156, BOUNDARY, 164, 152], 'sando_stone'),              # torii to the gate stair
            _paint([6, 130, 40, 146], 'park_sand')]                        # under the playground

    # ---- the water (art/water/APPLY.md, 2): the ponds and the falls pool, the brook
    circles = [o for o in ops if o['op'] == 'water' and 'circle' in o['area']]
    assert len(circles) == 3, circles
    for o in circles:
        o['material'] = 'pond_water'
    assert paths['stream']['sweep']['material'] == 'water'
    paths['stream']['sweep']['material'] = 'stream_water'
    # the north pond reaches z 123.2: its cap south of the line is the town's, in `water`
    north = min(circles, key=lambda o: o['area']['circle'][1])
    cx, cz, r = north['area']['circle']
    half = math.sqrt(r * r - (BOUNDARY - cz) ** 2)
    cap = [[round(cx - half, 3), BOUNDARY], [round(cx + half, 3), BOUNDARY]]
    cap += [[round(cx + r * math.cos(a), 3), round(cz + r * math.sin(a), 3)]
            for a in (math.radians(d) for d in range(350, 180, -10)) if cz + r * math.sin(a) < BOUNDARY]
    ops.append({'op': 'water', 'area': {'polygon': cap}, 'level': north['level'], 'material': 'water'})
