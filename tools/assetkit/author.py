"""Building Asset Kit recipes from Python: the helpers generator scripts share.

A recipe is plain JSON (`python3 tools/mei_assets.py schema`); this module only makes the same
dictionaries with less typing. Every builder returns a plain dict, so a script can still add or
change any field by hand. `write()` puts the keys in one order, rounds every float to 4 places
(0.1 mm) and checks the recipe against the schema before it writes, so a script's output is
stable from run to run and never something the kit refuses. Standard library only.

    import sys; sys.path.insert(0, 'tools')           # from the repository root
    from assetkit import author as A

    nodes = [A.box('base', [2, 0.2, 2], [0, 0.1, 0], 'stone', open=['bottom']),
             A.cylinder('post', 0.1, 1.8, [0, 1.1, 0], 'wood', segments=6, caps=False)]
    A.write('lamp.asset.json', A.recipe('lamp', MATERIALS, nodes, budget=200,
                                        lod=A.lod([(20, far_nodes)], cull=60)))
    A.write('lamp_col.asset.json', A.collision('lamp_col', [
        A.box_extents('base', -1, 1, 0, 0.2, -1, 1, open=['bottom'])]))

Coordinates are the kit's: Y up, the front faces -Z, degrees, outward counter-clockwise
winding (docs/ASSETKIT.md, "Authoring rules"). Writes nothing itself; `write()` writes where it
is told.
"""
import json
import math
from pathlib import Path

from .schema import validate

PLACES = 4
LIGHTING = {'mode': 'vertical', 'ambient': 0.5}
VERIFY = {'required': True, 'depth': True, 'perspective': True}
SOLID = {'color': '#ffffff', 'palette': True}

# The order write() gives the keys: the recipe's, each operation's, a transform's (the order the
# kit applies them in) and the levels of detail's. Keys not listed follow in their own order.
RECIPE_KEYS = ('format', 'version', 'name', 'budget', 'sheets', 'palette_layout', 'materials',
               'prototypes', 'lighting', 'verification', 'nodes', 'lod')
SHAPE_KEYS = {
    'box': ('size', 'material'),
    'sphere': ('radius', 'rings', 'segments', 'material'),
    'cylinder': ('radius', 'height', 'segments', 'caps', 'material'),
    'cone': ('radius', 'height', 'segments', 'caps', 'material'),
    'lathe': ('profile', 'segments', 'caps', 'material'),
    'extrude': ('points', 'depth', 'material'),
    'loft': ('sections', 'caps', 'material'),
    'mesh': ('material', 'vertices', 'faces', 'face_materials', 'uvs'),
    'group': ('material', 'children'),
    'instance': ('ref', 'material'),
}
NODE_TAIL = ('open', 'faces', 'decals', 'modifiers', 'transform')
TRANSFORM_KEYS = ('pivot', 'scale', 'rotate', 'translate')
LOD_KEYS = ('levels', 'cull', 'band')
LEVEL_KEYS = ('distance', 'nodes')
DECAL_KEYS = ('id', 'face', 'material', 'size', 'at')


# ---- transforms and the common fields ---------------------------------------------------------

def transform(at=None, rotate=None, scale=None, pivot=None):
    """A transform from the parts given (None when none is): scale about `pivot`, rotate X, Y, Z
    in degrees, translate to `at`."""
    t = {}
    for key, value in (('pivot', pivot), ('scale', scale), ('rotate', rotate), ('translate', at)):
        if value is not None:
            t[key] = list(value)
    return t or None


def _node(id, op, fields, material, at, rotate, scale, pivot, open=None, faces=None,
          decals=None, modifiers=None):
    n = {'id': id, 'op': op} if id is not None else {'op': op}
    n.update((k, v) for k, v in fields if v is not None)
    if material is not None:
        n['material'] = material
    for key, value in (('open', open), ('faces', faces), ('decals', decals),
                       ('modifiers', modifiers)):
        if value:
            n[key] = list(value) if key in ('open', 'decals', 'modifiers') else dict(value)
    t = transform(at, rotate, scale, pivot)
    if t:
        n['transform'] = t
    return _ordered(n)


# ---- primitives -------------------------------------------------------------------------------

def box(id, size, at=None, material=None, *, open=None, faces=None, decals=None, modifiers=None,
        rotate=None, scale=None, pivot=None):
    """A box of `size` [x, y, z] centred on `at`. Sides (for `open` and `faces`): top, bottom,
    left (-X), right (+X), back (-Z, the front camera's side), front (+Z)."""
    return _node(id, 'box', [('size', list(size))], material, at, rotate, scale, pivot,
                 open, faces, decals, modifiers)


def box_extents(id, x0, x1, y0, y1, z0, z1, material=None, **kw):
    """The box from x0 to x1, y0 to y1, z0 to z1 (as `box`, by its extents)."""
    return box(id, [x1 - x0, y1 - y0, z1 - z0], [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2],
               material, **kw)


def sphere(id, radius, at=None, material=None, *, rings=None, segments=None, modifiers=None,
           rotate=None, scale=None, pivot=None):
    return _node(id, 'sphere', [('radius', radius), ('rings', rings), ('segments', segments)],
                 material, at, rotate, scale, pivot, modifiers=modifiers)


def cylinder(id, radius, height, at=None, material=None, *, segments=None, caps=None,
             faces=None, decals=None, modifiers=None, rotate=None, scale=None, pivot=None):
    """A cylinder along Y, centred on `at`. `caps=False` leaves both ends open; faces: top,
    bottom, side."""
    return _node(id, 'cylinder', [('radius', radius), ('height', height),
                                  ('segments', segments), ('caps', caps)],
                 material, at, rotate, scale, pivot, None, faces, decals, modifiers)


def cone(id, radius, height, at=None, material=None, *, segments=None, caps=None, faces=None,
         decals=None, modifiers=None, rotate=None, scale=None, pivot=None):
    """A cone along Y, its base `height` / 2 below `at`, its tip as far above."""
    return _node(id, 'cone', [('radius', radius), ('height', height), ('segments', segments),
                              ('caps', caps)],
                 material, at, rotate, scale, pivot, None, faces, decals, modifiers)


def lathe(id, profile, material=None, at=None, *, segments=None, caps=None, faces=None,
          decals=None, modifiers=None, rotate=None, scale=None, pivot=None):
    """`profile`'s [radius, y] points turned about Y."""
    return _node(id, 'lathe', [('profile', [list(p) for p in profile]), ('segments', segments),
                               ('caps', caps)],
                 material, at, rotate, scale, pivot, None, faces, decals, modifiers)


def extrude(id, points, depth, material=None, at=None, *, faces=None, decals=None,
            modifiers=None, rotate=None, scale=None, pivot=None):
    """The outline `points` ([x, y], in the XY plane) extruded `depth` along Z, centred on z = 0;
    faces: front (+Z), back (-Z), side. A prism is an extrusion turned into place."""
    return _node(id, 'extrude', [('points', [list(p) for p in points]), ('depth', depth)],
                 material, at, rotate, scale, pivot, None, faces, decals, modifiers)


def section(y, points):
    """One section of a loft: the outline `points` ([x, z]) at height y."""
    return {'y': y, 'points': [list(p) for p in points]}


def loft(id, sections, material=None, at=None, *, caps=None, faces=None, decals=None,
         modifiers=None, rotate=None, scale=None, pivot=None):
    """Outlines (`section(y, points)`, equal point counts) joined bottom to top."""
    return _node(id, 'loft', [('sections', list(sections)), ('caps', caps)],
                 material, at, rotate, scale, pivot, None, faces, decals, modifiers)


def mesh(id, vertices, faces, material=None, at=None, *, face_materials=None, uvs=None,
         decals=None, modifiers=None, rotate=None, scale=None, pivot=None):
    """Explicit polygons: `faces` index `vertices`, each planar, wound counter-clockwise as seen
    from outside. `face_materials` (one per face) overrides `material`; `uvs` are hand texture
    coordinates, one [u, v] per vertex."""
    return _node(id, 'mesh', [('vertices', [list(v) for v in vertices]),
                              ('faces', [list(f) for f in faces]),
                              ('face_materials', None if face_materials is None
                               else list(face_materials)),
                              ('uvs', None if uvs is None else [list(u) for u in uvs])],
                 material, at, rotate, scale, pivot, decals=decals, modifiers=modifiers)


def quad(id, material, corners, uvs=None):
    """One four-cornered mesh face: corners top-left, top-right, bottom-right, bottom-left as seen
    from the side it faces."""
    return mesh(id, corners, [[0, 1, 2, 3]], material, uvs=uvs)


def quad_z(id, material, x0, x1, y0, y1, z, facing=-1):
    """A rectangle in the plane z, facing -Z (toward the front camera) or, `facing=1`, +Z."""
    if facing < 0:
        return quad(id, material, [[x0, y1, z], [x1, y1, z], [x1, y0, z], [x0, y0, z]])
    return quad(id, material, [[x1, y1, z], [x0, y1, z], [x0, y0, z], [x1, y0, z]])


def quad_x(id, material, z0, z1, y0, y1, x, facing=1):
    """A rectangle in the plane x, facing +X or, `facing=-1`, -X."""
    if facing > 0:
        return quad(id, material, [[x, y1, z0], [x, y1, z1], [x, y0, z1], [x, y0, z0]])
    return quad(id, material, [[x, y1, z1], [x, y1, z0], [x, y0, z0], [x, y0, z1]])


def quad_y(id, material, x0, x1, z0, z1, y, up=True):
    """A rectangle in the plane y, facing up or, `up=False`, down."""
    if up:
        return quad(id, material, [[x0, y, z1], [x1, y, z1], [x1, y, z0], [x0, y, z0]])
    return quad(id, material, [[x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1]])


def group(id, children, at=None, *, material=None, modifiers=None, rotate=None, scale=None,
          pivot=None):
    """Children moved together (a part); `material` is the default for children without one."""
    return _node(id, 'group', [('children', list(children))], material, at, rotate, scale, pivot,
                 modifiers=modifiers)


def instance(id, ref, at=None, *, material=None, modifiers=None, rotate=None, scale=None,
             pivot=None):
    """A copy of the prototype `ref` (the recipe's `prototypes`)."""
    return _node(id, 'instance', [('ref', ref)], material, at, rotate, scale, pivot,
                 modifiers=modifiers)


def decal(id, face, material, size, at=None):
    """A rectangle baked into a flat face (`decals=[...]` on a primitive): `face` a side name or
    a mesh's polygon index, `at` its centre from the face's centre, right and up from outside."""
    d = {'id': id, 'face': face, 'material': material, 'size': list(size)}
    if at is not None:
        d['at'] = list(at)
    return d


# ---- modifiers --------------------------------------------------------------------------------

def _mod(op, **fields):
    return dict({'op': op}, **{k: v for k, v in fields.items() if v is not None})


def mirror(axis, offset=None, keep_original=None):
    return _mod('mirror', axis=axis, offset=offset, keep_original=keep_original)


def array(count, step):
    return _mod('array', count=count, step=list(step))


def radial(count, axis=None, degrees=None):
    return _mod('radial', count=count, axis=axis, degrees=degrees)


def taper(top, bottom=None):
    return _mod('taper', top=top, bottom=bottom)


def twist(degrees):
    return _mod('twist', degrees=degrees)


def subdivide(levels):
    return _mod('subdivide', levels=levels)


# ---- a mesh built face by face ----------------------------------------------------------------

class Mesh:
    """One `mesh` node built a polygon at a time, each with its material and, optionally, its
    corners' UVs. Corners are kept per face (so each face can carry its own UVs) unless
    `share=True`, which reuses a vertex with the same position and UV."""

    def __init__(self, id, share=False):
        self.id, self.share = id, share
        self.vertices, self.faces, self.materials, self.uvs = [], [], [], []
        self._index = {}

    def vertex(self, p, uv=None):
        p, uv = list(p), None if uv is None else list(uv)
        key = (tuple(round(c, PLACES) for c in p),
               None if uv is None else tuple(round(c, PLACES) for c in uv))
        if self.share and key in self._index:
            return self._index[key]
        self.vertices.append(p)
        self.uvs.append(uv)
        self._index[key] = len(self.vertices) - 1
        return len(self.vertices) - 1

    def face(self, material, pts, uvs=None, out=None):
        """A planar polygon, corners counter-clockwise as seen from outside (top-left,
        top-right, bottom-right, bottom-left for a quad seen from outside and upright). With
        `out` (a direction), the corners are reversed if they face away from it."""
        if out is not None and _dot(newell(pts), out) < 0:
            pts = list(reversed(pts))
            uvs = None if uvs is None else list(reversed(uvs))
        self.faces.append([self.vertex(p, None if uvs is None else uvs[k])
                           for k, p in enumerate(pts)])
        self.materials.append(material)
        return len(self.faces) - 1

    def box(self, material, x0, x1, y0, y1, z0, z1, open=()):
        """An axis-aligned box's sides as faces; `material` one name or a dict by side (`'*'` for
        the rest); sides as `box`'s."""
        for side, pts in box_sides(x0, x1, y0, y1, z0, z1).items():
            if side not in open:
                mat = material.get(side, material.get('*')) if isinstance(material, dict) \
                    else material
                self.face(mat, pts)

    def triangles(self):
        return sum(len(f) - 2 for f in self.faces)

    def node(self):
        """The `mesh` node, with `face_materials` (a face without a material takes the
        collision's, in `collision()`), and `uvs` when any face has them (the others' corners
        get [0, 0])."""
        uvs = None
        if any(u is not None for u in self.uvs):
            uvs = [u if u is not None else [0, 0] for u in self.uvs]
        return mesh(self.id, self.vertices, self.faces, face_materials=self.materials, uvs=uvs)


def box_sides(x0, x1, y0, y1, z0, z1):
    """The six sides of a box as outward quads (top-left, top-right, bottom-right, bottom-left
    from outside), by the kit's side names."""
    return {
        'back': [(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)],
        'front': [(x1, y1, z1), (x0, y1, z1), (x0, y0, z1), (x1, y0, z1)],
        'right': [(x1, y1, z0), (x1, y1, z1), (x1, y0, z1), (x1, y0, z0)],
        'left': [(x0, y1, z1), (x0, y1, z0), (x0, y0, z0), (x0, y0, z1)],
        'top': [(x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)],
        'bottom': [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
    }


def newell(pts):
    """A polygon's normal by Newell's method (right for concave polygons too), not normalised."""
    n = [0.0, 0.0, 0.0]
    for k, p in enumerate(pts):
        q = pts[(k + 1) % len(pts)]
        n[0] += (p[1] - q[1]) * (p[2] + q[2])
        n[1] += (p[2] - q[2]) * (p[0] + q[0])
        n[2] += (p[0] - q[0]) * (p[1] + q[1])
    return n


def wind(vertices, face, out):
    """`face` (indices into `vertices`) in the order whose normal points along `out`."""
    n = newell([vertices[i] for i in face])
    return list(face) if _dot(n, out) >= 0 else list(reversed(face))


def outward(vertices, faces):
    """`faces` (lists of indices into `vertices`), each reversed where it faces the centre of
    the vertices: for a convex solid listed without care for winding."""
    c = [sum(v[i] for v in vertices) / len(vertices) for i in range(3)]
    out = []
    for f in faces:
        pts = [vertices[i] for i in f]
        mid = [sum(p[i] for p in pts) / len(pts) - c[i] for i in range(3)]
        out.append(list(f) if _dot(newell(pts), mid) > 0 else list(reversed(f)))
    return out


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


# ---- recipes ----------------------------------------------------------------------------------

def level(distance, nodes):
    """One coarser level of detail, drawn from `distance` on."""
    return {'distance': distance, 'nodes': list(nodes)}


def lod(levels=(), cull=None, band=None):
    """Levels of detail: `levels` as `level()`s or (distance, nodes) pairs; `cull` the distance
    from which nothing is drawn; `band` the hysteresis (the kit's default 1)."""
    out = {}
    if levels:
        out['levels'] = [lv if isinstance(lv, dict) else level(*lv) for lv in levels]
    if cull is not None:
        out['cull'] = cull
    if band is not None:
        out['band'] = band
    return out


def recipe(name, materials, nodes, *, budget=None, sheets=None, prototypes=None,
           lighting=LIGHTING, verification=VERIFY, lod=None, **extra):
    """A recipe. `budget` is a triangle count or a dict ({'triangles': ..., 'vertices': ...});
    `lighting` and `verification` default to the depth-mode game's (vertical shading, ambient
    0.5; the Asset Checker required, depth and perspective), None leaves either out; `lod` from
    `lod()`; `extra` (palette_layout, ...) is copied in. A `Mesh` among the nodes becomes its
    node, and one without faces is left out."""
    r = {'format': 'mei-asset', 'version': 1, 'name': name}
    if budget is not None:
        r['budget'] = budget if isinstance(budget, dict) else {'triangles': budget}
    if sheets:
        r['sheets'] = sheets
    if materials:
        r['materials'] = materials
    if prototypes:
        r['prototypes'] = prototypes
    if lighting is not None:
        r['lighting'] = dict(lighting)
    if verification is not None:
        r['verification'] = dict(verification)
    r['nodes'] = _nodes(nodes)
    if lod:
        lod = dict(lod)
        if 'levels' in lod:
            lod['levels'] = [dict(lv, nodes=_nodes(lv['nodes'])) for lv in lod['levels']]
        r['lod'] = lod
    r.update(extra)
    return _ordered(r)


def collision(name, nodes, *, material='solid', color=None, budget=None, **kw):
    """A collision recipe (`NAME_col.asset.json` beside the drawn one) from the same builders:
    every node, and every mesh face, without a material gets `material`, a palette-backed white
    unless `color` (or a `materials` dict in `kw`) says otherwise."""
    materials = kw.pop('materials', None) or {
        material: SOLID if color is None else {'color': color, 'palette': True}}
    return recipe(name, materials, [_fill(n, material) for n in _nodes(nodes)], budget=budget,
                  **kw)


def _fill(n, material):
    n = dict(n)
    if n.get('op') == 'group':
        n['children'] = [_fill(c, material) for c in n['children']]
    elif n.get('op') == 'mesh' and 'face_materials' in n:
        n['face_materials'] = [m or material for m in n['face_materials']]
    elif 'material' not in n and n.get('op') != 'instance':
        n['material'] = material
    return _ordered(n)


def _nodes(nodes):
    out = []
    for n in nodes:
        if isinstance(n, Mesh):
            if n.faces:
                out.append(n.node())
        else:
            out.append(n)
    return out


# ---- writing ----------------------------------------------------------------------------------

def _order(d, keys):
    out = {k: d[k] for k in keys if k in d}
    out.update((k, v) for k, v in d.items() if k not in out)
    return out


def _ordered(n):
    """A node or recipe dict (and what it holds) with its keys in write()'s order."""
    if not isinstance(n, dict):
        return n
    if 'format' in n and 'nodes' in n:
        n = _order(n, RECIPE_KEYS)
        n['nodes'] = [_ordered(c) for c in n['nodes']]
        if isinstance(n.get('prototypes'), dict):
            n['prototypes'] = {k: _ordered(v) for k, v in n['prototypes'].items()}
        if isinstance(n.get('lod'), dict):
            n['lod'] = _order(n['lod'], LOD_KEYS)
            if 'levels' in n['lod']:
                n['lod']['levels'] = [dict(_order(lv, LEVEL_KEYS),
                                           nodes=[_ordered(c) for c in lv['nodes']])
                                      for lv in n['lod']['levels']]
        return n
    op = n.get('op')
    n = _order(n, ('id', 'op') + SHAPE_KEYS.get(op, ('material',)) + NODE_TAIL)
    if isinstance(n.get('transform'), dict):
        n['transform'] = _order(n['transform'], TRANSFORM_KEYS)
    if isinstance(n.get('decals'), list):
        n['decals'] = [_order(d, DECAL_KEYS) if isinstance(d, dict) else d for d in n['decals']]
    if op == 'group' and isinstance(n.get('children'), list):
        n['children'] = [_ordered(c) for c in n['children']]
    return n


def tidy(value, places=PLACES):
    """`value` with every float rounded to `places` (-0.0 written as 0.0) and, for a recipe,
    its keys in write()'s order. Integers stay integers."""
    def rnd(v):
        if isinstance(v, bool):
            return v
        if isinstance(v, float):
            if not math.isfinite(v):
                raise ValueError(f'not a finite number: {v}')
            return round(v, places) + 0.0
        if isinstance(v, dict):
            return {k: rnd(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [rnd(x) for x in v]
        return v
    return rnd(_ordered(value))


def dumps(r, places=PLACES):
    """The recipe as write() writes it: tidied, checked against the schema, indented by one
    space, with a newline at the end."""
    r = tidy(r, places)
    validate(r)
    return json.dumps(r, indent=1) + '\n'


def write(path, r, places=PLACES):
    """Write the recipe to `path` (dumps()'s text); returns the path. Raises the kit's
    AssetError, naming the field, if the recipe does not fit the schema."""
    path = Path(path)
    path.write_text(dumps(r, places))
    return path
