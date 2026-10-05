"""Writes arch_pagoda_col.asset.json beside this script (python3 make_arch_pagoda_col.py): shrine
town's collision for the shrine's five-storey pagoda (carts/garden/shrine/assets/arch_pagoda),
whose look is reused unchanged. Star 1 (spec 5) is climbed up its tiers.

The collision is one closed solid, a square "lathe" up a profile read from the pagoda's own roof
meshes, so it follows the render:

- the platform (0.9 m) and its front and back steps (0.45 m);
- each storey a wall straight up to the roof above;
- each roof a slab: its underside rising from the storey wall to the eave, a 0.35 m fascia (the
  ledge the hands grab), and its top a hipped slope at the render's 27.9 degrees (walkable: at
  most 28) up to the next storey's wall. The part of each roof outside the eave above it is the
  strip the player stands on (0.7 m wide on every side);
- roof 5 slopes up to the dew basin (roban), a 1.1 m block with a flat top at 21.19 m.

Nothing above the roban: the finial is a `pole` entity (base at the roban's top, 21.19, height
8.8 to the jewel at 30.0), placed by the world. The shrine's own collision walled the finial at
0.55 m, which kept the body 0.85 m from its axis, out of the pole's 0.65 m reach.

The numbers are checked against the pagoda's recipe when this runs; it fails if the render has
moved.
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
VISUAL = HERE.parent.parent.parent / 'shrine' / 'assets' / 'arch_pagoda.asset.json'

POLICY = {'required': True, 'depth': True, 'perspective': True}
MAX_SLOPE = 28.0
FASCIA = 0.35
ROBAN = (0.55, 21.19)           # half width, top
FINIAL_TOP = 30.0


def r4(x):
    return round(x, 4) + 0.0


def roof_profile(node):
    """(storey wall half width, underside at the wall), (eave half width, fascia bottom, eave
    top), (top half width, top) from a roof mesh: the eave from the middle of each side, not
    the turned-up corners."""
    vs = node['vertices']
    re = max(abs(v[0]) for v in vs)
    mids = [v[1] for v in vs if abs(abs(v[0]) - re) < 1e-6 and abs(v[2]) < re * 0.7]
    eave_top, fascia_bottom = max(mids), min(mids)
    ybase = min(v[1] for v in vs)
    rwall = max(abs(v[0]) for v in vs if abs(v[1] - ybase) < 1e-6)
    ytop = max(v[1] for v in vs)
    rtop = max(abs(v[0]) for v in vs if abs(v[1] - ytop) < 1e-6)
    return (rwall, ybase), (re, fascia_bottom, eave_top), (rtop, ytop)


def read_visual():
    d = json.loads(VISUAL.read_text())
    nodes = {n['id']: n for n in d['nodes']}
    roofs = [roof_profile(nodes[f'roof_{k}']) for k in range(1, 6)]
    storeys = []
    for k in range(1, 6):
        vs = nodes[f'storey_{k}']['vertices']
        storeys.append(max(abs(v[0]) for v in vs))
    return roofs, storeys


def profile(roofs, storeys):
    """The solid's outline from the ground up, as (half width, height)."""
    pts = [(4.5, 0.0), (4.5, 0.9)]
    for k, ((rw, yb), (re, fb, et), (rt, yt)) in enumerate(roofs):
        sw = storeys[k]
        assert abs(rw - sw) < 1e-6, (k, rw, sw)
        pts += [(sw, 0.9 if k == 0 else None), (sw, yb), (re, fb), (re, et)]
        # up the roof to the next storey's wall (or the roban), at the render's slope
        inner = storeys[k + 1] if k < 4 else ROBAN[0]
        slope = (yt - et) / (re - rt)
        ang = math.degrees(math.atan(slope))
        assert ang <= MAX_SLOPE, (k, ang)
        pts.append((inner, et + (re - inner) * slope))
    pts += [(ROBAN[0], ROBAN[1]), (0.0, ROBAN[1])]
    # the storey walls start where the slope below meets them
    out = []
    for i, (r, y) in enumerate(pts):
        if y is None:
            y = out[-1][1]
        if out and abs(out[-1][0] - r) < 1e-9 and abs(out[-1][1] - y) < 1e-9:
            continue
        out.append((r, y))
    return out


def square_lathe(prof):
    """Square rings of the profile's half widths, joined by quads, wound outward; a ring of
    half width 0 is a point (the top's centre)."""
    verts, faces = [], []
    index = {}

    def vert(p):
        key = tuple(r4(c) for c in p)
        if key not in index:
            index[key] = len(verts)
            verts.append(list(key))
        return index[key]

    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]   # -Z side first, anticlockwise from above

    def ring(r, y):
        if r == 0:
            return [vert((0, y, 0))] * 4
        return [vert((sx * r, y, sz * r)) for sx, sz in corners]

    rings = [ring(r, y) for r, y in prof]
    # the bottom: open (it stands on the terrace)
    for k in range(len(prof) - 1):
        a, b = rings[k], rings[k + 1]
        for i in range(4):
            j = (i + 1) % 4
            quad = [a[i], a[j], b[j], b[i]]
            if b[i] == b[j]:
                faces.append([a[i], a[j], b[i]])
            else:
                faces.append(quad)
    # wind outward: the corners go anticlockwise seen from above, so [a_i, a_j, b_j] faces in;
    # reverse each face
    faces = [f[::-1] for f in faces]
    return verts, faces


def box_faces(verts, faces, lo, hi, open_sides=()):
    """A box's faces, outward; open_sides from 'bottom', 'top', '-x', '+x', '-z', '+z'."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    base = len(verts)
    for p in [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1),
              (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)]:
        verts.append([r4(c) for c in p])
    sides = {'bottom': [0, 1, 2, 3], 'top': [4, 7, 6, 5], '-z': [0, 4, 5, 1], '+z': [2, 6, 7, 3],
             '-x': [0, 3, 7, 4], '+x': [1, 5, 6, 2]}
    for name, f in sides.items():
        if name in open_sides:
            continue
        faces.append([base + i for i in f])


def main():
    roofs, storeys = read_visual()
    prof = profile(roofs, storeys)
    verts, faces = square_lathe(prof)
    # the platform's front and back steps, sunk into the platform's side by 0.1
    box_faces(verts, faces, (-1.2, 0.0, -5.1), (1.2, 0.45, -4.4), ('bottom', '+z'))
    box_faces(verts, faces, (-1.2, 0.0, 4.4), (1.2, 0.45, 5.1), ('bottom', '-z'))
    recipe = {
        'format': 'mei-asset', 'version': 1, 'name': 'arch_pagoda_col',
        'materials': {'solid': {'color': '#ffffff', 'palette': True}},
        'lighting': {'mode': 'vertical', 'ambient': 0.5},
        'verification': POLICY,
        'nodes': [{'id': 'body', 'op': 'mesh', 'vertices': verts, 'faces': faces,
                   'face_materials': ['solid'] * len(faces)}],
    }
    (HERE / 'arch_pagoda_col.asset.json').write_text(json.dumps(recipe, indent=1) + '\n')
    tris = sum(len(f) - 2 for f in faces)
    print(f'arch_pagoda_col: {tris} triangles')
    print('profile (half width, height):')
    for r, y in prof:
        print(f'  {r:6.3f} {y:7.4f}')
    print('roofs: eave top, strip (half widths), slope')
    for k, ((rw, yb), (re, fb, et), (rt, yt)) in enumerate(roofs):
        inner = roofs[k + 1][1][0] if k < 4 else ROBAN[0]
        print(f'  roof {k + 1}: eave top {et:.2f}, fascia {fb:.2f}-{et:.2f}, stands from {re:.2f} '
              f'in to {inner:.2f}, slope {math.degrees(math.atan((yt - et) / (re - rt))):.1f}')
    print(f'finial pole: base {ROBAN[1]}, height {FINIAL_TOP - ROBAN[1]:.2f}')


if __name__ == '__main__':
    main()
