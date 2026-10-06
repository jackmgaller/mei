"""Writes the machiya recipes: town_machiya_a (lattice front, roof 7.5) beside this file and
town_machiya_b (bengara lattice, side garden wall, roof 7.0) in ../town_machiya_b, each with its
collision companion NAME_col. Run once and commit the outputs:
python3 carts/garden/shrinetown/assets/town_machiya_a/make_machiya.py

Asset frame: origin at the footprint's centre on the street, the front (the lattice) facing -Z,
frontage 10 m along X, depth 14 m along Z. The roof's ridge runs along X, so a row of houses is
a run of roofs with 1.4 m gaps between the eaves. Textures: art/machiya_sheet.png (drawn by
art/draw_machiya.py) and the shrine's roof tile (carts/garden/shrine/assets/art/arch_tile.png)."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.dirname(HERE)


def r(v):
    return round(v, 4)


def newell(pts):
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


def area2(poly):
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly)))


def prism(outline, axis, lo, hi, side_mats, cap_mats, open_edges=(), open_caps=()):
    """A closed prism as mesh vertices, faces and face_materials. outline: 2D points (a, b) of
    the section; axis 'x' maps (a, b) to (z, y), 'z' maps them to (x, y), 'y' to (x, z). The
    section runs from lo to hi along the axis. side_mats[i] is the material of the wall from
    point i to i+1; cap_mats (lo, hi). Faces are wound outward."""
    def p3(a, b, t):
        return {'x': [t, b, a], 'z': [a, b, t], 'y': [a, t, b]}[axis]
    n = len(outline)
    verts = [p3(a, b, lo) for a, b in outline] + [p3(a, b, hi) for a, b in outline]
    verts = [[r(c) for c in v] for v in verts]
    ccw = area2(outline) > 0
    ax = {'x': 0, 'z': 2, 'y': 1}[axis]
    faces, mats = [], []
    centroid2 = (sum(p[0] for p in outline) / n, sum(p[1] for p in outline) / n)

    def outward(face, want):
        nn = newell([verts[i] for i in face])
        return face if sum(x * y for x, y in zip(nn, want)) > 0 else list(reversed(face))
    for i in range(n):
        if i in open_edges:
            continue
        j = (i + 1) % n
        a, b = outline[i], outline[j]
        e = (b[0] - a[0], b[1] - a[1])
        out2 = (e[1], -e[0]) if ccw else (-e[1], e[0])
        want = p3(out2[0], out2[1], 0.0)
        faces.append(outward([i, j, n + j, n + i], want))
        mats.append(side_mats[i] if isinstance(side_mats, list) else side_mats)
    for k, (cap, sgn) in enumerate(((list(range(n)), -1), (list(range(n, 2 * n)), 1))):
        if k in open_caps:
            continue
        want = [0, 0, 0]
        want[ax] = sgn
        faces.append(outward(cap, want))
        mats.append(cap_mats[k])
    return verts, faces, mats


def orient(V, faces, wants):
    """Wind each face of V outward, toward its wanted normal direction."""
    out = []
    for f, want in zip(faces, wants):
        nn = newell([V[i] for i in f])
        out.append(f if sum(x * y for x, y in zip(nn, want)) > 0 else list(reversed(f)))
    return out


def mesh_node(nid, parts, decals=None):
    """Join prisms (each verts, faces, mats) into one mesh node."""
    V, F, M = [], [], []
    for verts, faces, mats in parts:
        off = len(V)
        V += verts
        F += [[i + off for i in f] for f in faces]
        M += mats
    node = {'id': nid, 'op': 'mesh', 'vertices': V, 'faces': F, 'face_materials': M}
    if decals:
        node['decals'] = decals
    return node


def find_face(node, normal_axis, sign, coord, extra=None):
    """Index of the polygon of a mesh node lying in the plane axis = coord facing sign."""
    ax = {'x': 0, 'y': 1, 'z': 2}[normal_axis]
    for k, f in enumerate(node['faces']):
        pts = [node['vertices'][i] for i in f]
        if all(abs(p[ax] - coord) < 1e-6 for p in pts):
            nn = newell(pts)
            if nn[ax] * sign > 0 and (extra is None or extra(pts)):
                return k
    raise ValueError(f'no face {normal_axis}={coord} in {node["id"]}')


def box(nid, size, at, mat, open_=('bottom',), faces=None, decals=None):
    n = {'id': nid, 'op': 'box', 'size': [r(s) for s in size], 'material': mat,
         'transform': {'translate': [r(a) for a in at]}}
    if open_:
        n['open'] = list(open_)
    if faces:
        n['faces'] = faces
    if decals:
        n['decals'] = decals
    return n


# depth: the ground storey's front, the back wall, the upper storey's front; the roof's eaves
# (each slope 7 m, so its tiles need no cut along the slope); the lower eave's outer edge
ZF, ZB, ZU = -6.7, 6.7, -6.3
EF, EB = -7.0, 7.0
HZ1 = -7.3

SHEET = 'art/machiya_sheet.png'
TILE = '../../../shrine/assets/art/arch_tile.png'


def materials(v):
    lattice = 'koshi_dark' if v['name'].endswith('_a') else 'koshi_red'
    door = 'door_a' if v['name'].endswith('_a') else 'door_b'
    m = {
        'koshi': {'color': '#5a3e2c', 'tag': 'wall',
                  'texture': {'sheet': 'machiya', 'cell': lattice, 'projection': 'box',
                              'scale': [v['koshi'], v['h1']], 'offset': [r((-v['x0'] / v['koshi']) % 1.0), 0.0]}},
        'mushiko': {'color': '#ece4d2', 'tag': 'wall',
                    'texture': {'sheet': 'machiya', 'cell': 'mushiko', 'projection': 'box',
                                'scale': [v['bay'], v['h2']],
                                'offset': [r((-v['x0'] / v['bay']) % 1.0), r((v['eave'] / v['h2']) % 1.0)]}},
        'side': {'color': '#ece4d2', 'tag': 'wall',
                 'texture': {'sheet': 'machiya', 'cell': 'side', 'projection': 'box',
                             'scale': [2.0, 7.2], 'offset': [0.5, 0.0]}},
        # the roof tile at 32 texels a metre (a: 1 m a repeat, b: 1.1, so b's 8.6 m roof needs no cut)
        'tile': {'color': '#565c64', 'tag': 'roof',
                 'texture': {'image': TILE, 'projection': 'box', 'scale': [v['tile'], v['tile']],
                             'offset': [r((-(v['x0'] - 0.3) / v['tile']) % 1.0), 0.0]}},
        'door': {'color': '#2a2220', 'tag': 'door',
                 'texture': {'sheet': 'machiya', 'cell': door, 'projection': 'fit'}},
        'inuyarai': {'color': '#8a7a4a',
                     'texture': {'sheet': 'machiya', 'cell': 'inuyarai', 'projection': 'box',
                                 'scale': [0.5, 0.5]}},
        'ac': {'color': '#d8d4c8', 'texture': {'sheet': 'machiya', 'cell': 'ac_unit', 'projection': 'fit'}},
        # the coarser levels draw the same tiles at half the density, so long faces need no cuts
        'koshi_far': {'color': '#5a3e2c', 'tag': 'wall',
                      'texture': {'sheet': 'machiya', 'cell': lattice, 'projection': 'box',
                                  'scale': [2 * v['koshi'], v['h1']], 'offset': [r((-v['x0'] / v['koshi'] / 2) % 1.0), 0.0]}},
        'mushiko_far': {'color': '#ece4d2', 'tag': 'wall',
                        'texture': {'sheet': 'machiya', 'cell': 'mushiko', 'projection': 'box',
                                    'scale': [2 * v['bay'], v['h2']],
                                    'offset': [r((-v['x0'] / v['bay'] / 2) % 1.0), r((v['eave'] / v['h2']) % 1.0)]}},
        # the lower eave's: the same tile, its cut lines moved off the eave
        'tile_h': {'color': '#565c64', 'tag': 'roof',
                   'texture': {'image': TILE, 'projection': 'box', 'scale': [v['tile'], v['tile']],
                               'offset': [r((-(v['x0'] - 0.3) / v['tile']) % 1.0), 6.5]}},
        'tile_far': {'color': '#565c64', 'tag': 'roof', 'texture': {'image': TILE, 'projection': 'box', 'scale': [2.0, 2.0]}},
        'plaster': {'color': '#ece4d2', 'palette': True, 'tag': 'wall'},
        'wood': {'color': '#5a3e2c', 'palette': True},
        'ridge': {'color': '#3e4248', 'palette': True, 'tag': 'roof'},
        'metal': {'color': '#d8d4c8', 'palette': True},
        'glass': {'color': '#3a4450', 'palette': True, 'tag': 'window'},
        'antenna': {'color': '#8e8a84', 'palette': True, 'double_sided': True},
        'lamp': {'color': '#f0c070', 'class': 'emissive', 'tag': 'lantern'},
    }
    if v['garden']:
        m['garden_wall'] = {'color': '#ece4d2', 'tag': 'wall',
                            'texture': {'sheet': 'machiya', 'cell': 'garden_wall', 'projection': 'box',
                                        'scale': [2.0, v['wall_h']]}}
        m['gate'] = {'color': '#7a5a3e', 'tag': 'door',
                     'texture': {'sheet': 'machiya', 'cell': 'gate', 'projection': 'fit'}}
        m['sign'] = {'color': '#5a3e2c', 'texture': {'sheet': 'machiya', 'cell': 'sign_b', 'projection': 'fit'}}
        m['pine'] = {'color': '#2e4a2e', 'palette': True}
        m['trunk'] = {'color': '#5a4a3e', 'palette': True}
    return m


def geometry(v):
    """The section numbers of one variant."""
    zf, zb, zu = ZF, ZB, ZU
    eave = v['eave']                              # the upper storey's wall top under the roof
    R = v['ridge'] - 0.3                          # roof surface at the ridge (cap above it)
    s = (R - (eave + 0.2)) / (0 - zu)             # roof slope: 0.2 above the wall top at zu
    top = lambda z: R - abs(z) * s
    g = dict(zf=zf, zb=zb, zu=zu, eave=eave, R=R, s=s, top=top)
    # body: ground storey, the ledge under the lower eave, the upper storey and the attic, whose
    # slopes stay 0.15 under the roof's surface (inside the roof slab)
    g['body'] = [(zf, 0.0), (zb, 0.0), (zb, top(zb) - 0.15), (0.0, R - 0.15), (zu, top(zu) - 0.15),
                 (zu, v['h1']), (zf, v['h1'])]
    # body side materials by edge: bottom, back wall, back slope, front slope, upper front,
    # ledge, ground front
    g['body_mats'] = ['plaster', 'side', 'plaster', 'plaster', 'mushiko', 'wood', 'koshi']
    ef, eb = EF, EB
    g['roof'] = [(ef, top(ef) - 0.2), (ef, top(ef)), (0.0, R), (eb, top(eb)), (eb, top(eb) - 0.2),
                 (0.0, R - 0.2)]
    g['roof_mats'] = ['wood', 'tile', 'tile', 'wood', 'wood', 'wood']
    h1 = v['h1']
    hz0, hz1 = zu + 0.05, HZ1                     # lower eave (hisashi), from the wall out
    hy0, hy1 = h1 + 0.45, h1 + 0.05
    g['hisashi'] = [(hz1, hy1 - 0.12), (hz1, hy1), (hz0, hy0), (hz0, hy0 - 0.12)]
    g['hisashi_col'] = [(hz1, hy1 - 0.2), (hz1, hy1), (hz0, hy0), (hz0, hy0 - 0.2)]
    g['hisashi_mats'] = ['wood', 'tile_h', 'wood', 'wood']
    return g


def level0(v, g):
    x0, x1 = v['x0'], v['x1']
    nodes = []
    body = mesh_node('body', [prism(g['body'], 'x', x0, x1, g['body_mats'], ['side', 'side'], open_edges=(0,))])
    front = find_face(body, 'z', -1, g['zf'])
    back = find_face(body, 'z', 1, g['zb'])
    dx = v['door_x']
    body['decals'] = [
        {'id': 'door', 'face': front, 'material': 'door', 'size': [1.8, 2.36], 'at': [dx, 1.2]},
        # a lamp on the wall beside the door (lit at night)
        {'id': 'lamp', 'face': front, 'material': 'lamp', 'size': [0.24, 0.34], 'at': [dx + 1.2, 2.2]},
        # the back wall is seen from +Z: right is -X
        {'id': 'back_window', 'face': back, 'material': 'glass', 'size': [1.6, 0.7],
         'at': [-v['back_win_x'], v['h1'] + 0.6]},
    ]
    if v.get('sign_x') is not None:   # the tea shop's sign on the wall beside the door
        body['decals'].append({'id': 'sign', 'face': front, 'material': 'sign', 'size': [0.5, 1.0],
                               'at': [v['sign_x'], 2.3]})
    nodes.append(body)
    gx = 0.3
    nodes.append(mesh_node('roof', [prism(g['roof'], 'x', x0 - gx, x1 + gx, g['roof_mats'], ['wood', 'wood'])]))
    nodes.append(box('ridge', [x1 - x0 + 2 * gx + 0.1, 0.32, 0.42], [(x0 + x1) / 2, g['R'] + 0.14, 0], 'ridge'))
    nodes.append(mesh_node('hisashi', [prism(g['hisashi'], 'x', x0 - 0.15, x1 + 0.15, g['hisashi_mats'], ['wood', 'wood'])]))
    # inuyarai: curved bamboo guards at the foot of the front, either side of the door
    prof = [(ZF + 0.05, 0.0), (ZF + 0.05, 0.85), (ZF - 0.18, 0.72), (ZF - 0.42, 0.38), (ZF - 0.5, 0.0)]
    for k, (a, b) in enumerate(v['inuyarai']):
        nodes.append(mesh_node(f'inuyarai_{k}', [prism(prof, 'x', a, b, ['inuyarai', 'wood', 'inuyarai', 'inuyarai', 'wood'],
                                                       ['wood', 'wood'], open_edges=(4,))]))
    # the air conditioner's outdoor unit at the back
    ax_ = v['ac_x']
    nodes.append(box('ac_unit', [0.8, 0.6, 0.3], [ax_, 0.3, ZB + 0.13], 'metal', faces={'front': 'ac'}))
    if v['garden']:
        return nodes + garden(v)
    # a TV aerial on the back slope: mast, boom and four elements as flat double-sided strips
    tx, tz = v['aerial']
    yb = g['top'](tz) - 0.05
    yt = v['ridge'] + 0.5
    w = 0.03
    quads = [
        [[tx - w, yb, tz], [tx + w, yb, tz], [tx + w, yt, tz], [tx - w, yt, tz]],            # mast
        [[tx, yt - 0.15, tz - 0.6], [tx, yt - 0.15, tz + 0.6], [tx, yt - 0.09, tz + 0.6], [tx, yt - 0.09, tz - 0.6]],  # boom
    ]
    for k, (dz, half) in enumerate(((-0.55, 0.55), (-0.2, 0.45), (0.15, 0.4), (0.5, 0.35))):
        quads.append([[tx - half, yt - 0.1, tz + dz - w], [tx + half, yt - 0.1, tz + dz - w],
                      [tx + half, yt - 0.1, tz + dz + w], [tx - half, yt - 0.1, tz + dz + w]])
    V, F = [], []
    for q in quads:
        F.append([len(V) + i for i in range(4)])
        V += [[r(c) for c in p] for p in q]
    nodes.append({'id': 'aerial', 'op': 'mesh', 'vertices': V, 'faces': F,
                  'face_materials': ['antenna'] * len(F)})
    return nodes


def garden(v):
    """The side garden: a U of plaster wall from the house's side wall round to the plot's edge,
    tile coping, a wicket gate and a pine over the wall."""
    a, b, t, h = v['x1'], 5.0, 0.25, v['wall_h']
    u = [(a, ZF), (b, ZF), (b, ZB), (a, ZB), (a, ZB - t), (b - t, ZB - t), (b - t, ZF + t), (a, ZF + t)]
    # the ends against the house's side wall are left open
    wall = mesh_node('garden_wall', [prism(u, 'y', 0.0, h, 'garden_wall', ['wood', 'plaster'], open_edges=(3, 7), open_caps=(0,))])
    front = find_face(wall, 'z', -1, ZF)
    wall['decals'] = [{'id': 'gate', 'face': front, 'material': 'gate', 'size': [1.0, 1.86],
                       'at': [r((a + b) / 2 + 0.1), 0.95]}]
    nodes = [wall]
    cap = lambda c: [(c - 0.24, h - 0.06), (c + 0.24, h - 0.06), (c, h + 0.2)]
    # the coping's undersides lie inside the wall: open
    nodes.append(mesh_node('coping', [
        prism(cap(ZF + t / 2), 'x', a - 0.05, b + 0.12, ['ridge'] * 3, ['ridge', 'ridge'], open_edges=(0,)),
        prism(cap(ZB - t / 2), 'x', a - 0.05, b + 0.12, ['ridge'] * 3, ['ridge', 'ridge'], open_edges=(0,)),
        prism(cap(b - t / 2), 'z', ZF - 0.12, ZB + 0.12, ['ridge'] * 3, ['ridge', 'ridge'], open_edges=(0,))]))
    px, pz = v['pine']
    nodes.append({'id': 'pine_trunk', 'op': 'cylinder', 'radius': 0.11, 'height': 3.3, 'segments': 5,
                  'caps': False, 'material': 'trunk',
                  'transform': {'rotate': [0, 0, -8], 'translate': [px, 1.7, pz]}})
    for k, (dy, rad, hh, ox) in enumerate(((3.45, 1.15, 0.9, 0.3),)):
        nodes.append({'id': f'pine_{k}', 'op': 'cone', 'radius': rad, 'height': hh, 'segments': 7,
                      'material': 'pine', 'transform': {'translate': [r(px + ox), dy, pz]}})
    return nodes


def lod1(v, g):
    """From 20 m: the body, a three-sided roof, the lower eave as one slab; the garden wall."""
    x0, x1 = v['x0'], v['x1']
    ef, eb = EF, EB
    roof = [(ef, g['top'](ef) - 0.1), (0.0, g['R'] + 0.15), (eb, g['top'](eb) - 0.1)]
    far = {'koshi': 'koshi_far', 'mushiko': 'mushiko_far', 'tile': 'tile_far', 'tile_h': 'tile_far'}
    nodes = [mesh_node('body', [prism(g['body'], 'x', x0, x1, [far.get(m, m) for m in g['body_mats']], ['side', 'side'],
                                      open_edges=(0,))]),
             mesh_node('roof', [prism(roof, 'x', x0 - 0.3, x1 + 0.3, ['tile_far', 'tile_far', 'wood'], ['wood', 'wood'])])]
    nodes.append(mesh_node('hisashi', [prism(g['hisashi'], 'x', x0 - 0.15, x1 + 0.15, [far.get(m, m) for m in g['hisashi_mats']],
                                             ['wood', 'wood'])]))
    if v['garden']:
        a, b, h = x1, 5.0, v['wall_h'] + 0.1
        # the wall's outer faces (front and side) and its top, as one strip
        V = [[a, 0, ZF], [b, 0, ZF], [b, h, ZF], [a, h, ZF], [b, 0, ZB], [b, h, ZB],
             [b - 0.25, h, ZB], [b - 0.25, h, ZF]]
        nodes.append({'id': 'garden_wall', 'op': 'mesh', 'vertices': V,
                      'faces': orient(V, [[0, 3, 2, 1], [1, 2, 5, 4], [2, 7, 6, 5]], [[0, 0, -1], [1, 0, 0], [0, 1, 0]]),
                      'face_materials': ['garden_wall', 'garden_wall', 'ridge']})
    return nodes


def lod2(v, g):
    """From 50 m: four walls and a gable roof, 14 triangles."""
    x0, x1 = v['x0'], v['x1']
    e, R = g['eave'] + 0.2, g['R']
    V = [[x0, 0, ZF], [x1, 0, ZF], [x1, e, ZF], [x0, e, ZF],
         [x0, 0, ZB], [x1, 0, ZB], [x1, e, ZB], [x0, e, ZB],
         [x0, R, 0], [x1, R, 0]]
    F = orient(V, [[0, 3, 2, 1], [5, 6, 7, 4],    # front, back
                   [4, 7, 8, 3, 0], [1, 2, 9, 6, 5],  # sides with the gables
                   [3, 8, 9, 2], [6, 9, 8, 7]],       # roof
               [[0, 0, -1], [0, 0, 1], [-1, 0, 0], [1, 0, 0], [0, 1, -1], [0, 1, 1]])
    return [{'id': 'house', 'op': 'mesh', 'vertices': [[r(c) for c in p] for p in V], 'faces': F,
             'face_materials': ['wood', 'plaster', 'plaster', 'plaster', 'tile_far', 'tile_far']}]


def collision(v, g):
    x0, x1 = v['x0'], v['x1']
    ef, eb = EF, EB
    # the roof as one walkable solid: its slopes (the render's), 0.2 thick at the eaves
    roof = [(ef, g['top'](ef) - 0.2), (ef, g['top'](ef)), (0.0, g['R']), (eb, g['top'](eb)), (eb, g['top'](eb) - 0.2)]
    nodes = [mesh_node('body', [prism(g['body'][:3] + [(0.0, g['R'] - 0.3)] + g['body'][4:], 'x', x0, x1,
                                      'solid', ['solid', 'solid'], open_edges=(0,))]),
             mesh_node('roof', [prism(roof, 'x', x0 - 0.3, x1 + 0.3, 'solid', ['solid', 'solid'])]),
             mesh_node('hisashi', [prism(g['hisashi_col'], 'x', x0 - 0.15, x1 + 0.15, 'solid', ['solid', 'solid'])])]
    # the inuyarai at the front's foot, as drawn: walking up to the front, the body stops at their
    # foot, not 0.5 m into them (alpha review r12 #7)
    prof = [(ZF + 0.05, 0.0), (ZF + 0.05, 0.85), (ZF - 0.18, 0.72), (ZF - 0.42, 0.38), (ZF - 0.5, 0.0)]
    for k, (a, b) in enumerate(v['inuyarai']):
        nodes.append(mesh_node(f'inuyarai_{k}', [prism(prof, 'x', a, b, 'solid', ['solid', 'solid'], open_edges=(4,))]))
    if v['garden']:
        a, b, t, h = x1, 5.0, 0.25, v['wall_h'] + 0.1
        u = [(a, ZF), (b, ZF), (b, ZB), (a, ZB), (a, ZB - t), (b - t, ZB - t), (b - t, ZF + t), (a, ZF + t)]
        nodes.append(mesh_node('garden_wall', [prism(u, 'y', 0.0, h, 'solid', ['solid', 'solid'], open_edges=(3, 7), open_caps=(0,))]))
    return nodes


POLICY = {'required': True, 'depth': True, 'perspective': True}
LIGHT = {'mode': 'vertical', 'ambient': 0.5}


def write(path, recipe):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(recipe, f, indent=1)
        f.write('\n')


def make(v):
    g = geometry(v)
    folder = os.path.join(ASSETS, v['name'])
    sheet = os.path.relpath(os.path.join(HERE, SHEET), folder)
    recipe = {
        'format': 'mei-asset', 'version': 1, 'name': v['name'],
        'budget': {'triangles': 200},
        'sheets': {'machiya': {'image': sheet}},
        'materials': materials(v),
        'lighting': LIGHT,
        'verification': POLICY,
        'lod': {'levels': [{'distance': 20, 'nodes': lod1(v, g)}, {'distance': 50, 'nodes': lod2(v, g)}]},
        'nodes': level0(v, g),
    }
    write(os.path.join(folder, v['name'] + '.asset.json'), recipe)
    col = {'format': 'mei-asset', 'version': 1, 'name': v['name'] + '_col',
           'materials': {'solid': {'color': '#ffffff', 'palette': True}},
           'lighting': LIGHT, 'verification': POLICY, 'nodes': collision(v, g)}
    write(os.path.join(folder, v['name'] + '_col.asset.json'), col)


A = dict(name='town_machiya_a', x0=-5.0, x1=5.0, ridge=7.5, eave=4.75, h1=3.4, h2=1.35, koshi=1.0, tile=1.0, bay=10 / 3,
         door_x=-2.0, back_win_x=1.5, ac_x=-2.6, aerial=(3.2, 2.4),
         inuyarai=[(-4.85, -3.05), (-0.95, 4.85)], garden=False)
B = dict(name='town_machiya_b', x0=-5.0, x1=3.0, ridge=7.0, eave=4.5, h1=3.3, h2=1.2, koshi=8 / 7, tile=1.1, bay=8 / 3,
         door_x=-2.4, back_win_x=-1.0, ac_x=-3.4, aerial=(-3.2, 2.0),
         inuyarai=[(-1.35, 2.95)], garden=True, wall_h=2.3, pine=(4.0, 1.5), sign_x=2.45)

if __name__ == '__main__':
    for v in (A, B):
        make(v)
        print('wrote', v['name'])
