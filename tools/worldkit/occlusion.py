"""Occlusion zones (WORLDKIT.md, "Occlusion"; WORLDPACK.md, "Occlusion zones").

A world recipe declares occluders (boxes or quads that are solid: inside walls, floors, roofs)
and camera zones (boxes the eye can be in). For each zone the kit works out which placements of
the near cells, and which stand-ins of the far ring, are hidden behind one of the zone's occluders
from every point of the zone; the pack stores those sets per zone, and the reader skips them
while the eye is in the zone: a potentially visible set, worked out here once, so the console's
cost is a box test per zone and a bit test per placement.

What "hidden" means here: every point of the placement's box (the box, in its asset's frame, of
the vertices of every level it can draw, turned by its yaw) lies in the occluder's shadow from
every corner of the zone (the zone clipped to the eye's cell). A shadow from a point is convex
(the occluder's silhouette cone, beyond its faces that look at the point), so a box inside it
holds the mesh inside it; and a point hidden from two eyes is hidden from every eye between them
(the segment from it to each eye crosses the convex occluder, and so does every segment between),
so the zone's corners stand for the whole zone. One occluder hides a placement alone: shadows of
two are not joined. Only the occluder's shape is used: that it is truly opaque (inside solid
geometry that is drawn from the zone) is the author's claim, which the World Checker tests by
casting rays (verify.py, the occlusion check).

Standard library only.
"""
from dataclasses import dataclass
import math
import struct

from kitcore.errors import pointer
from . import pack as P
from .schema import WorldError

MARGIN = 0.01           # units: boxes grown, shadows shrunk, so rounding never decides


@dataclass
class Occluder:
    name: str
    verts: list             # the corners
    faces: list             # (normal (outward, unit), offset): n . x <= d inside
    edges: list             # (a, b, face index, face index)
    layer: str = None


def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(v):
    n = math.sqrt(_dot(v, v))
    return (v[0] / n, v[1] / n, v[2] / n)


def box_occluder(name, lo, hi, yaw=0.0, layer=None):
    """A box, lo..hi in its own frame, turned yaw degrees about its centre's vertical (as mesh_at()
    turns: +Z toward +X)."""
    cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))

    def put(x, y, z):
        x, z = x - cx, z - cz
        return (cx + x * c + z * s, y, cz - x * s + z * c)
    verts = [put(hi[0] if k & 1 else lo[0], hi[1] if k & 2 else lo[1], hi[2] if k & 4 else lo[2]) for k in range(8)]
    centre = tuple(sum(v[a] for v in verts) / 8 for a in range(3))
    quads = [(0, 2, 6, 4), (1, 3, 7, 5), (0, 1, 5, 4), (2, 3, 7, 6), (0, 1, 3, 2), (4, 5, 7, 6)]   # -x +x -y +y -z +z
    faces = []
    for q in quads:
        n = _unit(_cross(_sub(verts[q[1]], verts[q[0]]), _sub(verts[q[2]], verts[q[0]])))
        if _dot(n, _sub(verts[q[0]], centre)) < 0:
            n = (-n[0], -n[1], -n[2])
        faces.append((n, _dot(n, verts[q[0]])))
    edges = []
    for a in range(8):
        for b in range(a + 1, 8):
            if bin(a ^ b).count('1') == 1:
                fs = [f for f, q in enumerate(quads) if a in q and b in q]
                edges.append((verts[a], verts[b], fs[0], fs[1]))
    return Occluder(name, verts, faces, edges, layer)


def quad_occluder(name, pts, layer=None, path=''):
    """A flat convex quad (four corners in order): a wall or a roof with no thickness."""
    n = _cross(_sub(pts[1], pts[0]), _sub(pts[2], pts[0]))
    if _dot(n, n) < 1e-12:
        raise WorldError(path, 'An occluder quad\'s first three corners lie on one line.')
    n = _unit(n)
    d = _dot(n, pts[0])
    if any(abs(_dot(n, p) - d) > 0.01 for p in pts):
        raise WorldError(path, 'An occluder quad\'s four corners are not in one plane (within 0.01).')
    for k in range(4):
        a, b, c = pts[k], pts[(k + 1) % 4], pts[(k + 2) % 4]
        if _dot(_cross(_sub(b, a), _sub(c, b)), n) <= 0:
            raise WorldError(path, 'An occluder quad is not convex, or its corners are not in order.')
    faces = [(n, d), ((-n[0], -n[1], -n[2]), -d)]
    edges = [(pts[k], pts[(k + 1) % 4], 0, 1) for k in range(4)]
    return Occluder(name, [tuple(p) for p in pts], faces, edges, layer)


def shadow(occ, e):
    """The half-spaces (m, k), m . x >= k, whose intersection is the occluder's shadow from point e
    (everything a segment from e reaches only through the occluder), shrunk by MARGIN; None when
    e is not strictly outside it (then it hides nothing from there)."""
    front = [_dot(n, e) - d > 1e-6 for n, d in occ.faces]
    if not any(front):
        return None
    planes = []
    for f, (n, d) in enumerate(occ.faces):
        if front[f]:
            planes.append(((-n[0], -n[1], -n[2]), -d + MARGIN))      # beyond the face: n . x <= d
    inside = tuple(sum(v[a] for v in occ.verts) / len(occ.verts) for a in range(3))
    for a, b, f, g in occ.edges:
        if front[f] == front[g]:
            continue
        m = _cross(_sub(a, e), _sub(b, e))
        ln = math.sqrt(_dot(m, m))
        if ln < 1e-9:
            return None
        m = (m[0] / ln, m[1] / ln, m[2] / ln)
        k = _dot(m, e)
        if _dot(m, inside) < k:
            m, k = (-m[0], -m[1], -m[2]), -k
        planes.append((m, k + MARGIN))
    return planes


def hides(planes_list, pts):
    """Whether every point lies in every shadow (each a list of half-spaces)."""
    for planes in planes_list:
        for m, k in planes:
            for p in pts:
                if m[0] * p[0] + m[1] * p[1] + m[2] * p[2] < k:
                    return False
    return True


def _first_hider(shadows, cands):
    """For each candidate (its corner points), the number of the first shadow (a list of half-space
    lists, one per eye) that holds all its points, or -1. With NumPy the same comparisons, made
    on arrays in the same order of operations, so the answers are the same."""
    try:
        import numpy as np
    except ImportError:
        np = None
    if np is None or not cands:
        return [next((k for k, sh in enumerate(shadows) if hides(sh, pts)), -1) for pts in cands]
    pts = np.array(cands, dtype=float)            # (n, 8, 3)
    x, y, z = pts[:, :, 0], pts[:, :, 1], pts[:, :, 2]
    out = np.full(len(cands), -1)
    for k, sh in enumerate(shadows):
        todo = np.flatnonzero(out < 0)
        if not len(todo):
            break
        ok = np.ones(len(todo), dtype=bool)
        xs, ys, zs = x[todo], y[todo], z[todo]
        for planes in sh:
            for m, c in planes:
                ok &= ~((m[0] * xs + m[1] * ys + m[2] * zs) < c).any(axis=1)
        out[todo[ok]] = k
    return [int(v) for v in out]


def _mesh_box(data):
    """The (lo, hi) box of a native mesh's vertices, in units."""
    nv, _, vo, _ = P.mesh_info(data)
    lo, hi = [1 << 40] * 3, [-(1 << 40)] * 3
    for x, y, z, _ in struct.iter_unpack('<4i', data[vo:vo + 16 * nv]):
        for a, v in enumerate((x, y, z)):
            lo[a] = min(lo[a], v)
            hi[a] = max(hi[a], v)
    return [v / P.ONE for v in lo], [v / P.ONE for v in hi]


def placement_corners(p, cache):
    """The eight corners (world units) of the box that holds every level of a placement as drawn,
    grown by MARGIN."""
    meshes = [p.mesh] + [m for _, m in (p.lod.levels if p.lod else ()) if m is not None]
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    for m in meshes:
        if m not in cache:
            cache[m] = _mesh_box(m)
        a, b = cache[m]
        lo = [min(x, y) for x, y in zip(lo, a)]
        hi = [max(x, y) for x, y in zip(hi, b)]
    lo = [v - MARGIN for v in lo]
    hi = [v + MARGIN for v in hi]
    c, s = math.cos(math.radians(p.yaw)), math.sin(math.radians(p.yaw))
    px, py, pz = (float(v) for v in p.position)
    out = []
    for k in range(8):
        x, y, z = hi[0] if k & 1 else lo[0], hi[1] if k & 2 else lo[1], hi[2] if k & 4 else lo[2]
        out.append((px + x * c + z * s, py + y, pz - x * s + z * c))
    return out


def standin_corners(cell, size, cache):
    m = cell.standin
    if m not in cache:
        cache[m] = _mesh_box(m)
    lo, hi = cache[m]
    cx, cz = cell.i * size + size / 2, cell.j * size + size / 2
    return [(cx + (hi[0] if k & 1 else lo[0]) + (MARGIN if k & 1 else -MARGIN),
             (hi[1] if k & 2 else lo[1]) + (MARGIN if k & 2 else -MARGIN),
             cz + (hi[2] if k & 4 else lo[2]) + (MARGIN if k & 4 else -MARGIN)) for k in range(8)]


def parse(spec, layer_names):
    """The recipe's occlusion section: ({name: Occluder}, [zone dicts]) checked."""
    occs = {}
    for name, o in spec.get('occluders', {}).items():
        path = pointer('/occlusion/occluders', name)
        layer = o.get('layer')
        if layer is not None and layer not in layer_names:
            raise WorldError(path + '/layer', f'No layer {layer!r}.')
        if ('box' in o) == ('quad' in o):
            raise WorldError(path, 'An occluder is a box or a quad.')
        if 'box' in o:
            lo, hi = o['box']
            if not all(a < b for a, b in zip(lo, hi)):
                raise WorldError(path + '/box', 'A box is [[x0, y0, z0], [x1, y1, z1]] with each of x0, y0, z0 '
                                 'below its other.')
            occs[name] = box_occluder(name, lo, hi, o.get('yaw', 0.0), layer)
        else:
            occs[name] = quad_occluder(name, [tuple(q) for q in o['quad']], layer, path + '/quad')
    zones = []
    for name, z in spec.get('zones', {}).items():
        path = pointer('/occlusion/zones', name)
        lo, hi = z['box']
        if not all(a < b for a, b in zip(lo, hi)):
            raise WorldError(path + '/box', 'A box is [[x0, y0, z0], [x1, y1, z1]] with each of x0, y0, z0 below '
                             'its other.')
        layer = z.get('layer')
        if layer is not None and layer not in layer_names:
            raise WorldError(path + '/layer', f'No layer {layer!r}.')
        names = z.get('occluders')
        if names is None:
            names = [n for n, o in occs.items() if o.layer is None or o.layer == layer]
        for k, n in enumerate(names):
            if n not in occs:
                raise WorldError(f'{path}/occluders/{k}', f'No occluder {n!r}.')
            if occs[n].layer is not None and occs[n].layer != layer:
                raise WorldError(f'{path}/occluders/{k}', f'Occluder {n!r} is in layer {occs[n].layer!r}: only a zone '
                                 'of that layer may use it.')
        zones.append({'name': name, 'lo': tuple(lo), 'hi': tuple(hi), 'layer': layer, 'occluders': names})
    return occs, zones


def _q(v):
    """A coordinate as the pack stores it (16.16), back in units."""
    return P.fx(v) / P.ONE


def compute(spec, world, size, layer_names, warnings):
    """Adds each cell's P.Zone records to world.cells from the recipe's occlusion section; returns
    the report entry."""
    occs, zones = parse(spec, layer_names)
    by_key = {(c.i, c.j): c for c in world.cells}
    cache = {}
    corners_of = {}

    def corners(p):
        if id(p) not in corners_of:
            corners_of[id(p)] = placement_corners(p, cache)
        return corners_of[id(p)]
    report = []
    for z in zones:
        lo, hi = z['lo'], z['hi']
        entry = {'zone': z['name'], 'occluders': list(z['occluders']), 'cells': [], 'placements': 0,
                 'faces': 0, 'standins': 0}
        used = {}           # occluder -> what it hides first (placements and stand-ins, over the cells)
        if z['layer']:
            entry['layer'] = z['layer']
        for ci in range(math.floor(lo[0] / size), math.ceil(hi[0] / size)):
            for cj in range(math.floor(lo[2] / size), math.ceil(hi[2] / size)):
                cell = by_key.get((ci, cj))
                if cell is None:
                    continue
                clo = (_q(max(lo[0], ci * size)), _q(lo[1]), _q(max(lo[2], cj * size)))
                chi = (_q(min(hi[0], (ci + 1) * size)), _q(hi[1]), _q(min(hi[2], (cj + 1) * size)))
                if not all(a < b for a, b in zip(clo, chi)):
                    continue
                eyes = [(chi[0] if k & 1 else clo[0], chi[1] if k & 2 else clo[1], chi[2] if k & 4 else clo[2])
                        for k in range(8)]
                shadows, shadow_names = [], []
                for n in z['occluders']:
                    vs = occs[n].verts
                    meets = all(min(v[a] for v in vs) < chi[a] and max(v[a] for v in vs) > clo[a] for a in range(3))
                    sh = None if meets else [shadow(occs[n], e) for e in eyes]
                    if sh is None or any(s is None for s in sh):
                        warnings.append({'code': 'zone_meets_occluder', 'zone': z['name'], 'occluder': n,
                                         'cell': [ci, cj],
                                         'message': 'The zone overlaps the occluder\'s box, or a corner of the zone lies '
                                                    'on its plane, so it hides nothing from the zone.'})
                        continue
                    shadows.append(sh)
                    shadow_names.append(n)
                cands = []          # (placement or stand-in cell, its corners)
                for dj in (-1, 0, 1):
                    for di in (-1, 0, 1):
                        near = by_key.get((ci + di, cj + dj))
                        cands += [(p, corners(p)) for p in (near.placements if near else ())]
                nplace = len(cands)
                for dj in range(-P.ZONE_FAR, P.ZONE_FAR + 1):
                    for di in range(-P.ZONE_FAR, P.ZONE_FAR + 1):
                        far = by_key.get((ci + di, cj + dj))
                        if far is not None and far.standin is not None:
                            cands.append(((far.i, far.j), standin_corners(far, size, cache)))
                first = _first_hider(shadows, [pts for _, pts in cands])
                hidden, standins, why = [], [], []
                faces = 0
                for k, ((what, _), f) in enumerate(zip(cands, first)):
                    if f < 0:
                        continue
                    by = shadow_names[f]
                    used[by] = used.get(by, 0) + 1
                    if k < nplace:
                        hidden.append(what)
                        why.append(by)
                        faces += struct.unpack_from('<H', what.mesh, 2)[0]
                    else:
                        standins.append(what)
                        why.append(by)
                if not hidden and not standins:
                    continue
                zone = P.Zone(clo, chi, z['layer'], hidden, standins)
                zone.why = why          # the occluder that hides each (hidden, then stand-ins): for reports
                zone.name = z['name']
                cell.zones.append(zone)
                entry['cells'].append([ci, cj])
                entry['placements'] += len(hidden)
                entry['faces'] += faces
                entry['standins'] += len(standins)
        entry['hidden_by'] = {n: used[n] for n in z['occluders'] if n in used}
        if not entry['cells']:
            warnings.append({'code': 'zone_hides_nothing', 'zone': z['name'],
                             'message': 'No placement or stand-in is hidden from the whole zone by one of its '
                                        'occluders: the zone is left out of the pack.'})
        report.append(entry)
    return report
