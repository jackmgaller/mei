"""Per-face materials on primitives (`faces`) and decals baked into a primitive's flat faces
(`decals`) (docs/ASSETKIT.md, "Face materials and decals").

Both work on a primitive's own mesh, in its own coordinates, before its modifiers and transform,
so copies made by modifiers and instances carry them.

A decal is baked into its host face: the face's outline gets the decal's rectangle as a hole, the
ring between them is triangulated again (ear clipping, the hole bridged to the outline), and the
rectangle becomes two faces of the decal's material. The decal is in the host's plane and shares
its edges with the ring, so nothing overlaps (no coplanar overlap, nothing for the depth test or
the ordering table to decide) and nothing has a T-junction (the rectangle's corners are corners
of the ring's triangles, and the outline keeps its own vertices). A face of m corners holding k
decals becomes m + 8k - 2 triangles where it was m - 2: each decal adds 8 triangles and 4
vertices.
"""
import math

from .geometry import AssetError, Face, add, sub, mul, cross, dot, norm

# side names by op; the axis aliases mean the same sides
BOX_SIDES = {'right': (0, 1), 'left': (0, -1), 'top': (1, 1), 'bottom': (1, -1), 'front': (2, 1), 'back': (2, -1)}
BOX_ALIASES = {'-x': 'left', '+x': 'right', '-y': 'bottom', '+y': 'top', '-z': 'back', '+z': 'front'}
CAP_ALIASES = {'+y': 'top', '-y': 'bottom'}
EXTRUDE_ALIASES = {'+z': 'front', '-z': 'back'}
SIDES = {
    'box': (tuple(BOX_SIDES), BOX_ALIASES),
    'cylinder': (('top', 'bottom', 'side'), CAP_ALIASES),
    'cone': (('top', 'bottom', 'side'), CAP_ALIASES),
    'lathe': (('top', 'bottom', 'side'), CAP_ALIASES),
    'loft': (('top', 'bottom', 'side'), CAP_ALIASES),
    'extrude': (('front', 'back', 'side'), EXTRUDE_ALIASES),
}
GAP = 0.001          # units: the least distance between a decal and its face's edge or another decal


def side_names(op):
    names, aliases = SIDES[op]
    return ', '.join(names)+' (or '+', '.join(aliases)+')'


def side_of(mesh, face, op):
    """The side a face of a primitive lies on: a box's by its outward normal; a cap (all corners at
    one y, or one z for an extrusion) top/bottom or front/back by its normal's sign; else side."""
    a, b, c = (mesh.vertices[i] for i in face.indices)
    n = cross(sub(b, a), sub(c, a))
    if op == 'box':
        k = max(range(3), key=lambda i: abs(n[i]))
        return next(s for s, (axis, sign) in BOX_SIDES.items() if axis == k and sign == (1 if n[k] > 0 else -1))
    k = 2 if op == 'extrude' else 1
    if a[k] == b[k] == c[k]:
        if op == 'extrude':
            return 'front' if n[2] > 0 else 'back'
        return 'top' if n[1] > 0 else 'bottom'
    return 'side'


def missing_side(spec, op, side):
    """Why a primitive has no faces on a side it names."""
    if op == 'box':
        return f'Side {side!r} is open (the box\'s open lists it), so it has no faces.'
    if not spec.get('caps', True) and side != 'side':
        return f'caps is false, so the {op} has no {side} cap.'
    if op == 'cone' and side == 'top':
        return 'A cone has no top cap: its top is a point.'
    return f'The {op} has no {side} cap: its profile ends in a point there (radius 0).'


def resolve(spec, op, key, where):
    names, aliases = SIDES[op]
    side = aliases.get(key, key)
    if side not in names:
        raise AssetError(where, f'A {op} has no side {key!r}; its sides are {side_names(op)}.')
    return side


def apply(mesh, spec, op, label, materials, path, log):
    """Apply a primitive's faces map and decals to its mesh (its faces already carry the node's
    material, part and local coordinates). log collects the report's entries."""
    if 'faces' in spec and op in SIDES:         # a mesh node's faces are its polygons
        chosen, present = {}, {side_of(mesh, f, op) for f in mesh.faces}
        for key, name in spec['faces'].items():
            where = f'{path}/faces/{key}'
            side = resolve(spec, op, key, where)
            if side in chosen:
                raise AssetError(where, f'Side {side!r} is named twice ({chosen[side][0]!r} and {key!r}); name each side once.')
            if name not in materials:
                raise AssetError(where, f'Unknown material {name!r}.')
            if side not in present:
                raise AssetError(where, missing_side(spec, op, side))
            chosen[side] = (key, name)
        for face in mesh.faces:
            side = side_of(mesh, face, op)
            if side in chosen:
                face.material, face.own = chosen[side][1], True
        log['faces'].append({'part': label.lstrip('/'), 'path': path, 'sides': {side: name for side, (_, name) in sorted(chosen.items())},
                             'triangles': {side: sum(side_of(mesh, f, op) == side for f in mesh.faces) for side in sorted(chosen)}})
    if 'decals' in spec:
        decals(mesh, spec, op, label, materials, path, log)


# ---------------------------------------------------------------------------------------------
# Decals

def decals(mesh, spec, op, label, materials, path, log):
    from .textures import basis, orient, REPEATING
    hosts, ids = {}, set()
    for k, decal in enumerate(spec['decals']):
        where = f'{path}/decals/{k}'
        name = decal.get('id', f'decal_{k}')
        if name in ids:
            raise AssetError(where+'/id', f'Two decals of this node are called {name!r}; give each its own id.')
        ids.add(name)
        if decal['material'] not in materials:
            raise AssetError(where+'/material', f'Unknown material {decal["material"]!r}.')
        tex = materials[decal['material']].get('texture')
        if tex and tex.get('projection', 'box') in REPEATING:
            raise AssetError(where+'/material', f'Material {decal["material"]!r} has a repeating texture ({tex.get("projection", "box")} '
                             'projection, the default): a decal draws its texture once over its rectangle. Give the texture '
                             '"projection": "fit" (a material of its own if another part repeats it).')
        key = decal['face']
        if op == 'mesh':
            if type(key) is not int or not 0 <= key < len(spec['faces']):
                raise AssetError(where+'/face', f'A mesh node\'s decal names a polygon by its index, 0-{len(spec["faces"])-1}.')
            host = key
        else:
            if op not in SIDES:
                raise AssetError(where, f'decals apply to flat faces of box, cylinder, cone, lathe, loft, extrude and mesh nodes, not a {op}.')
            if not isinstance(key, str):
                raise AssetError(where+'/face', f'Name the side the decal is on: {side_names(op)}.')
            host = resolve(spec, op, key, where+'/face')
            if host == 'side' and op != 'box':
                raise AssetError(where+'/face', f'The side of a {op} is {"several faces" if op == "extrude" else "curved"}; '
                                 f'decals go on one flat face: {"front or back" if op == "extrude" else "top or bottom"}. '
                                 'For a label round a curved side, give the side a texture.')
            if not any(side_of(mesh, f, op) == host for f in mesh.faces):
                raise AssetError(where+'/face', missing_side(spec, op, host))
        hosts.setdefault(host, []).append((k, name, decal, where))
    for host, items in hosts.items():
        if op == 'mesh':
            faces = [f for f in mesh.faces if f.polygon == host]
        else:
            faces = [f for f in mesh.faces if side_of(mesh, f, op) == host]
        what = f'polygon {host}' if op == 'mesh' else f'side {host!r}'
        bake(mesh, faces, items, label, host, what, materials, log, basis, orient)


def bake(mesh, faces, items, label, host, what, materials, log, basis, orient):
    """Cut the decals' rectangles out of one flat face (its triangles `faces`) and fill them."""
    first = faces[0]
    a, b, c = (mesh.vertices[i] for i in first.indices)
    n = norm(cross(sub(b, a), sub(c, a)))
    right, down = basis(n)
    up = mul(down, -1)
    d = dot(n, a)
    flat = [f for f in faces if max(abs(dot(n, mesh.vertices[i])-d) for i in f.indices) <= 1e-9*(1+abs(d))
            and dot(norm(cross(sub(mesh.vertices[f.indices[1]], mesh.vertices[f.indices[0]]),
                               sub(mesh.vertices[f.indices[2]], mesh.vertices[f.indices[0]]))), n) > 0.999999]
    if len(flat) != len(faces):
        raise AssetError(items[0][3]+'/face', f'The {what} of {label.lstrip("/")!r} is not flat (modifiers come after decals, '
                         'so this is its own shape); decals go on flat faces.')
    xy = {i: (dot(mesh.vertices[i], right), dot(mesh.vertices[i], up)) for f in faces for i in f.indices}
    loop = outline(faces, items[0][3], what, label)
    if area2([xy[i] for i in loop]) < 0:
        loop.reverse()
    xs, ys = [xy[i][0] for i in loop], [xy[i][1] for i in loop]
    # at is measured from the primitive's origin as it projects onto the face: (0, 0) here
    span = f'x {min(xs):.4g} to {max(xs):.4g}, y {min(ys):.4g} to {max(ys):.4g}'
    rects = []
    for k, name, decal, where in items:
        w, h = decal['size']
        at = decal.get('at', [0, 0])
        x0, y0 = at[0]-w/2, at[1]-h/2
        rect = [(x0, y0), (x0+w, y0), (x0+w, y0+h), (x0, y0+h)]
        inside_face(rect, [xy[i] for i in loop], where, what, label, span, at, (w, h))
        for k2, name2, rect2, where2 in rects:
            if not (rect[0][0] >= rect2[2][0]+GAP or rect2[0][0] >= rect[2][0]+GAP or
                    rect[0][1] >= rect2[2][1]+GAP or rect2[0][1] >= rect[2][1]+GAP):
                raise AssetError(where, f'Decal {name!r} overlaps decal {name2!r} on the {what} of {label.lstrip("/")!r} '
                                 f'(or is closer than {GAP} to it): decals on one face are separate rectangles. Move one, or '
                                 'draw both in one texture.')
        rects.append((k, name, rect, where))
    # new vertices: the rectangles' corners, in the face's plane
    def vertex(p):
        mesh.vertices.append(add(add(mul(right, p[0]), mul(up, p[1])), mul(n, d)))
        return len(mesh.vertices)-1
    holes = []
    for _, _, rect, _ in rects:
        ids = [vertex(p) for p in rect]
        for i, p in zip(ids, rect):
            xy[i] = p
        holes.append(ids)
    tris = triangulate(loop, [list(reversed(h)) for h in holes], xy, items[0][3], what, label)
    # a mesh polygon's hand UVs carry over to the ring: the outline's corners keep theirs, and each
    # rectangle corner takes them from the host triangle it lies in
    hand = host_uvs(faces, [i for h in holes for i in h], xy) if first.uv is not None else None

    def oriented(t):
        p, q, r = (mesh.vertices[i] for i in t)
        return t if dot(cross(sub(q, p), sub(r, p)), n) > 0 else (t[0], t[2], t[1])
    made = []
    for t in tris:
        t = oriented(t)
        made.append(Face(t, first.material, first.part, polygon=first.polygon, own=first.own,
                         uv=tuple(hand[i] for i in t) if hand else None))
    for (k, name, rect, where), ids, (_, _, decal, _) in zip(rects, holes, items):
        material = decal['material']
        tex = materials[material].get('texture')
        x0, y0 = rect[0]
        w, h = rect[2][0]-x0, rect[2][1]-y0
        # the texture once over the rectangle, as fit draws it: u right, v down, with the texture's
        # rotate and flip
        turned = {i: orient(xy[i][0]-x0-w/2, -(xy[i][1]-y0-h/2), tex or {}) for i in ids}
        lo = [min(t[j] for t in turned.values()) for j in (0, 1)]
        hi = [max(t[j] for t in turned.values()) for j in (0, 1)]
        uv = {i: ((t[0]-lo[0])/(hi[0]-lo[0]), (t[1]-lo[1])/(hi[1]-lo[1])) for i, t in turned.items()}
        for t in ((ids[0], ids[1], ids[2]), (ids[0], ids[2], ids[3])):
            t = oriented(t)
            made.append(Face(t, material, first.part, polygon=first.polygon, own=True,
                             uv=tuple(uv[i] for i in t) if tex else None, decal=f'{label.lstrip("/")}/{name}'))
        log['decals'].append({'id': f'{label.lstrip("/")}/{name}', 'part': label.lstrip('/'), 'path': where,
                              'face': host, 'material': material,
                              'at': list(decal.get('at', [0, 0])), 'size': list(decal['size'])})
    for face in made:
        face.local = tuple(mesh.vertices[i] for i in face.indices)
    gone = set(map(id, faces))
    at = min(k for k, f in enumerate(mesh.faces) if id(f) in gone)
    mesh.faces[:] = [f for f in mesh.faces[:at] if id(f) not in gone]+made+[f for f in mesh.faces[at:] if id(f) not in gone]


def host_uvs(faces, new, xy):
    """Hand UVs for the ring around a face's decals: each corner of the host's triangles keeps its
    own, and each new vertex (a rectangle's corner, inside the face) is interpolated over the host
    triangle that holds it (the one it lies deepest in, should it be on an edge between two)."""
    uv = {}
    for f in faces:
        for i, u in zip(f.indices, f.uv):
            uv.setdefault(i, tuple(u))
    for i in new:
        p, best = xy[i], None
        for f in faces:
            a, b, c = (xy[j] for j in f.indices)
            d = turn(a, b, c)
            s, t = turn(a, p, c)/d, turn(a, b, p)/d
            depth = min(s, t, 1-s-t)
            if best is None or depth > best[0]:
                best = (depth, s, t, f.uv)
        _, s, t, (ua, ub, uc) = best
        uv[i] = tuple(ua[k]+s*(ub[k]-ua[k])+t*(uc[k]-ua[k]) for k in (0, 1))
    return uv


def area2(points):
    return sum(a[0]*b[1]-a[1]*b[0] for a, b in zip(points, points[1:]+points[:1]))


def outline(faces, where, what, label):
    """The vertex loop around a flat face's triangles (its boundary edges, chained)."""
    edges = {(f.indices[k], f.indices[(k+1) % 3]) for f in faces for k in range(3)}
    boundary = {a: b for a, b in edges if (b, a) not in edges}
    if not boundary:
        raise AssetError(where+'/face', f'The {what} of {label.lstrip("/")!r} has no outline.')
    start = min(boundary)
    loop, at = [start], boundary[start]
    while at != start:
        if at in loop or at not in boundary:
            break
        loop.append(at)
        at = boundary[at]
    if at != start or len(loop) != len(boundary):
        raise AssetError(where+'/face', f'The {what} of {label.lstrip("/")!r} is not one polygon without holes; decals '
                         'go on simple flat faces.')
    return loop


def turn(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def segment_distance(p, q, a, b):
    """The least distance between segments pq and ab (0 when they cross)."""
    def side(u, v, w):
        return turn(u, v, w)
    if side(a, b, p)*side(a, b, q) < 0 and side(p, q, a)*side(p, q, b) < 0:
        return 0.0

    def to_segment(x, u, v):
        e = (v[0]-u[0], v[1]-u[1])
        ee = e[0]*e[0]+e[1]*e[1]
        t = 0 if ee == 0 else max(0, min(1, ((x[0]-u[0])*e[0]+(x[1]-u[1])*e[1])/ee))
        return math.hypot(x[0]-u[0]-t*e[0], x[1]-u[1]-t*e[1])
    return min(to_segment(p, a, b), to_segment(q, a, b), to_segment(a, p, q), to_segment(b, p, q))


def inside(point, polygon):
    x, y = point
    hit = False
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:]+polygon[:1]):
        if (y1 > y) != (y2 > y) and x < x1+(y-y1)*(x2-x1)/(y2-y1):
            hit = not hit
    return hit


def inside_face(rect, polygon, where, what, label, span, at, size):
    """A decal's rectangle must lie inside its face, at least GAP from the face's edges."""
    near = min(segment_distance(p, q, a, b) for p, q in zip(rect, rect[1:]+rect[:1])
               for a, b in zip(polygon, polygon[1:]+polygon[:1]))
    if near >= GAP and inside(rect[0], polygon):
        return
    xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
    past = []
    for text, value in (('left', min(xs)-rect[0][0]), ('right', rect[2][0]-max(xs)),
                        ('bottom', min(ys)-rect[0][1]), ('top', rect[2][1]-max(ys))):
        if value > -GAP:
            past.append(f'its {text} edge is {"%.4g past" % value if value > 0 else "within %g of" % GAP} the face\'s {text} edge')
    why = '; '.join(past) if past else 'it crosses the face\'s outline'
    raise AssetError(where, f'The decal at {list(at)}, size {list(size)}, does not fit inside the {what} of '
                     f'{label.lstrip("/")!r}: {why}. In at\'s coordinates (right and up as seen from outside, '
                     f'from the primitive\'s origin) the face spans {span}; a decal lies inside its face, at least {GAP} from its edges. Move or shrink it, or '
                     'give the whole side the material (faces).')


# ---------------------------------------------------------------------------------------------
# Triangulation of a polygon with holes: each hole is bridged to the polygon, then ears are clipped.

def triangulate(loop, holes, xy, where, what, label):
    """Triangles (vertex ids) of the counterclockwise loop with the clockwise holes taken out."""
    poly = list(loop)
    pts = [xy[i] for i in loop]+[xy[i] for h in holes for i in h]
    extent = max(max(p[k] for p in pts)-min(p[k] for p in pts) for k in (0, 1))
    eps = extent*extent*1e-12
    # holes farthest right first (then any that can be joined): the polygon to the right of a
    # hole's rightmost corner is then the outline or holes already joined, which it can see
    left = sorted(range(len(holes)), key=lambda k: (-max(xy[i][0] for i in holes[k]), k))
    while left:
        for k in left:
            joined = bridge(poly, holes[k], [holes[m] for m in left], xy, eps)
            if joined:
                poly = joined
                left.remove(k)
                break
        else:
            raise AssetError(where, f'Could not join the decals of the {what} of {label.lstrip("/")!r} to its outline; '
                             'move them a little apart.')
    tris = []
    while len(poly) > 3:
        best = None
        # only these can lie in an ear: reflex or straight corners, and the bridges' ends (which
        # appear twice, each time with part of their angle)
        twice = {i for i in poly if poly.count(i) > 1}
        flat = [k for k in range(len(poly)) if poly[k] in twice
                or turn(xy[poly[k-1]], xy[poly[k]], xy[poly[(k+1) % len(poly)]]) <= eps]
        for k in range(len(poly)):
            a, b, c = poly[k-1], poly[k], poly[(k+1) % len(poly)]
            pa, pb, pc = xy[a], xy[b], xy[c]
            if turn(pa, pb, pc) <= NEAR*math.hypot(pc[0]-pa[0], pc[1]-pa[1]):
                continue
            if any(poly[j] not in (a, b, c) and covers(pa, pb, pc, xy[poly[j]], eps) for j in flat):
                continue
            quality = min_angle(pa, pb, pc)
            if best is None or quality > best[0]+1e-12:
                best = (quality, k)
        if best is None:
            raise AssetError(where, f'Could not triangulate the {what} of {label.lstrip("/")!r} around its decals; '
                             'move them a little.')
        k = best[1]
        tris.append((poly[k-1], poly[k], poly[(k+1) % len(poly)]))
        del poly[k]
    tris.append(tuple(poly))
    return tris


NEAR = 1/8192       # units: a corner this close to a new edge counts as on it (8 steps of 16.16)


def covers(a, b, c, p, eps):
    """Whether p lies in triangle abc or within NEAR of it (where 16.16 rounding could put it on
    an edge: a T-junction)."""
    for u, v in ((a, b), (b, c), (c, a)):
        if turn(u, v, p) < -NEAR*math.hypot(v[0]-u[0], v[1]-u[1]):
            return False
    return True


def min_angle(a, b, c):
    def angle(p, q, r):
        u, v = (q[0]-p[0], q[1]-p[1]), (r[0]-p[0], r[1]-p[1])
        return abs(math.atan2(u[0]*v[1]-u[1]*v[0], u[0]*v[0]+u[1]*v[1]))
    return min(angle(a, b, c), angle(b, c, a), angle(c, a, b))


def bridge(poly, hole, holes, xy, eps):
    """The polygon with the hole joined in by the shortest edge from a hole corner to a polygon
    vertex that crosses nothing and leaves no three points in a line at its ends."""
    edges = [(poly[k], poly[(k+1) % len(poly)]) for k in range(len(poly))]
    edges += [(h[k], h[(k+1) % len(h)]) for h in holes for k in range(len(h))]
    best = None
    for j, v in enumerate(hole):
        for k, u in enumerate(poly):
            pu, pv = xy[u], xy[v]
            length = math.hypot(pu[0]-pv[0], pu[1]-pv[1])
            if best is not None and length >= best[0]:
                continue
            # strictly inside the polygon's corner at u, and outside the hole's corner at v
            prev, nxt = xy[poly[k-1]], xy[poly[(k+1) % len(poly)]]
            if not in_wedge(prev, pu, nxt, pv, eps):
                continue
            hp, hn = xy[hole[j-1]], xy[hole[(j+1) % len(hole)]]
            if not in_wedge(hp, pv, hn, pu, eps):
                continue
            if any(segment_hits(pu, pv, xy[a], xy[b], eps) for a, b in edges if u not in (a, b) and v not in (a, b)):
                continue
            if any(w not in (u, v) and segment_distance(pu, pv, xy[w], xy[w]) < NEAR for w in set(poly) | {i for h in holes for i in h}):
                continue
            best = (length, j, k)
    if best is None:
        return None
    _, j, k = best
    return poly[:k+1]+hole[j:]+hole[:j+1]+poly[k:]


def in_wedge(prev, at, nxt, p, eps):
    """Whether p lies strictly inside the interior angle prev-at-nxt of a counterclockwise polygon
    (strictly: not on either edge's line)."""
    a, b = turn(prev, at, p), turn(at, nxt, p)
    if abs(a) <= eps or abs(b) <= eps:
        return False
    if turn(prev, at, nxt) > 0:
        return a > 0 and b > 0
    return a > 0 or b > 0


def segment_hits(p, q, a, b, eps):
    """Whether segments pq and ab touch or cross (ab sharing no endpoint with pq)."""
    d1, d2, d3, d4 = turn(a, b, p), turn(a, b, q), turn(p, q, a), turn(p, q, b)
    if ((d1 > eps and d2 < -eps) or (d1 < -eps and d2 > eps)) and ((d3 > eps and d4 < -eps) or (d3 < -eps and d4 > eps)):
        return True

    def on(u, v, w, dv):
        return abs(dv) <= eps and min(u[0], v[0])-1e-12 <= w[0] <= max(u[0], v[0])+1e-12 and \
            min(u[1], v[1])-1e-12 <= w[1] <= max(u[1], v[1])+1e-12
    return on(a, b, p, d1) or on(a, b, q, d2) or on(p, q, a, d3) or on(p, q, b, d4)
