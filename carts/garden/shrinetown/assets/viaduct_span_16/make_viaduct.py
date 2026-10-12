"""Writes the shrine town's viaduct recipes: viaduct_span_16, viaduct_curve_16 and
viaduct_underpass (each with its _col companion) into their folders beside this one.
Run once and commit the outputs: python3 carts/garden/shrinetown/assets/viaduct_span_16/make_viaduct.py

The deck is one cross-section swept along the track (a straight line or an arc), so every piece
ends in the same section and they tile end to end. The section, in (z across, y up), deck at 9.0,
parapet tops at 10.2, 12 m wide:

    parapet 0.25 thick (z 5.75..6.0), its top a rail at z = +-5.875, y = 10.2
    deck top at 9.0: walkways with the cable trough (|z| 4.0..5.75), two tracks at z = +-2.0
    fascia (outer face) 10.2 down to 8.55; cantilevered slab; two girders (z +-2.1..3.9) to 7.8

The section's faces carry hand UVs (16 texels a 2 m repeat along the track, a whole number of
repeats a piece), so the textures run on across the joints. A two-column portal (rahmen) bent
with haunches stands at each piece's middle: piers every 16 m.

Asset frame: the track runs along X; +Z is the inner side of the curve. The underpass: the road
runs through the origin at 25 degrees to Z (toward -X as it goes +Z); see its recipe's notes.
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHEET = 'art/concrete.png'                       # relative to viaduct_span_16/

DECK, TOP, EDGE_Y = 9.0, 10.2, 8.55              # deck, parapet top, fascia's foot
REP = {'concrete': 4.0, 'soffit': 4.0, 'fascia': 4.0, 'track': 2.0, 'trough': 2.0}
                                                 # metres a texture repeat along the track
R_CURVE = 16.0 / (math.pi / 6)                   # 30 degrees in 16 m: R 30.56 at the centre line

POLICY = {"required": True, "depth": True, "perspective": True}
LIGHT = {"mode": "vertical", "ambient": 0.5}

# ---------------------------------------------------------------------------- the sections
# Points in ring order (z, y); each edge (to the next point) gets a material and a UV rule.
FULL = [  # level 0
    ((6.0, TOP), 'coping'), ((5.75, TOP), 'concrete'), ((5.75, DECK), 'trough'),
    ((4.0, DECK), 'track'), ((-4.0, DECK), 'trough'), ((-5.75, DECK), 'concrete'),
    ((-5.75, TOP), 'coping'), ((-6.0, TOP), 'fascia'), ((-6.0, EDGE_Y), 'soffit'),
    ((-4.1, 8.3), 'concrete'), ((-3.9, 7.8), 'soffit'), ((-2.1, 7.8), 'concrete'),
    ((-1.9, 8.3), 'soffit'), ((1.9, 8.3), 'concrete'), ((2.1, 7.8), 'soffit'),
    ((3.9, 7.8), 'concrete'), ((4.1, 8.3), 'soffit'), ((6.0, EDGE_Y), 'fascia'),
]
SIMPLE = [  # level 1: no girders, the soffit flat
    ((6.0, TOP), 'coping'), ((5.75, TOP), 'concrete'), ((5.75, DECK), 'trough'),
    ((4.0, DECK), 'track'), ((-4.0, DECK), 'trough'), ((-5.75, DECK), 'concrete'),
    ((-5.75, TOP), 'coping'), ((-6.0, TOP), 'fascia'), ((-6.0, EDGE_Y), 'soffit'),
    ((6.0, EDGE_Y), 'fascia'),
]
RIBBON = [  # level 2: a box, its top the ballast's tone
    ((6.0, TOP), 'soffit'), ((-6.0, TOP), 'fascia'), ((-6.0, EDGE_Y), 'soffit'),
    ((6.0, EDGE_Y), 'fascia'),
]
COLLIDE = [  # collision: the deck slab and parapets as one U
    ((-6.0, 8.3), None), ((6.0, 8.3), None), ((6.0, TOP), None), ((5.75, TOP), None),
    ((5.75, DECK), None), ((-5.75, DECK), None), ((-5.75, TOP), None), ((-6.0, TOP), None),
]


def edge_v(material, a, b):
    """v at the edge's two ends, in repeats."""
    (za, ya), (zb, yb) = a, b
    if material == 'fascia':
        return (TOP - ya) / (TOP - EDGE_Y), (TOP - yb) / (TOP - EDGE_Y)
    if material == 'track':
        return (za + 4.0) / 4.0, (zb + 4.0) / 4.0
    if material == 'trough':
        return (abs(za) - 4.0) / 1.75, (abs(zb) - 4.0) / 1.75
    return 0.0, math.hypot(zb - za, yb - ya) / 2.0


def path_straight(length, segments):
    return [((-length / 2 + length * i / segments, 0.0), (0.0, 1.0), i / segments)
            for i in range(segments + 1)], (lambda z: length)


def path_arc(radius, degrees, segments):
    """An arc through the origin heading +X at its middle, turning toward +Z."""
    frames = []
    for i in range(segments + 1):
        t = math.radians(-degrees / 2 + degrees * i / segments)
        frames.append(((radius * math.sin(t), radius * (1 - math.cos(t))),
                       (-math.sin(t), math.cos(t)), i / segments))
    return frames, (lambda z: (radius - z) * math.radians(degrees))


def r4(v):
    return round(v + 0.0, 4) + 0.0


def r7(v):
    return round(v + 0.0, 7) + 0.0


def sweep(id_, section, path, textured=True):
    """A mesh node: the section swept along the path, ends open."""
    frames, length_at = path
    pts = [p for p, _ in section]
    area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
               for i in range(len(pts)))
    verts, uvs, faces, mats = [], [], [], []
    for i, (a, mat) in enumerate(section):
        b = pts[(i + 1) % len(pts)]
        dz, dy = b[0] - a[0], b[1] - a[1]
        out2 = (dy, -dz) if area > 0 else (-dy, dz)
        reps = max(1, round(length_at((a[0] + b[0]) / 2) / REP.get(mat, 4.0)))
        va, vb = edge_v(mat, a, b) if textured else (0, 0)
        base = len(verts)
        for (px, pz), (nx, nz), f in frames:
            for (z, y), v in ((a, va), (b, vb)):
                verts.append([r7(px + nx * z), r7(y), r7(pz + nz * z)])
                uvs.append([r4(reps * f), r4(v)])
        for k in range(len(frames) - 1):
            q = [base + 2 * k, base + 2 * k + 1, base + 2 * k + 3, base + 2 * k + 2]
            p0, p1, p3 = verts[q[0]], verts[q[1]], verts[q[3]]
            e1 = [p1[j] - p0[j] for j in range(3)]
            e2 = [p3[j] - p0[j] for j in range(3)]
            n = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2],
                 e1[0] * e2[1] - e1[1] * e2[0]]
            (fx, fz) = frames[k][1]
            out = [fx * out2[0], out2[1], fz * out2[0]]
            if sum(n[j] * out[j] for j in range(3)) < 0:
                q.reverse()
            faces.append(q)
            mats.append(mat or 'solid')
    node = {"id": id_, "op": "mesh", "vertices": verts, "faces": faces, "face_materials": mats}
    if textured:
        node["uvs"] = uvs
    return node


# ---------------------------------------------------------------------------- the bent
COL_Z, COL_X, COL_W = 3.0, 1.0, 1.1              # columns under the girders, 1.0 x 1.1 m
BEAM_X = 1.2                                     # the cross beam 1.2 m thick along the track


def bent(id_, x=0.0, detail=True, plates=True):
    """Two columns and the haunched cross beam (level 0), or the columns alone into the slab."""
    kids = []
    top = 7.5 if detail else 8.65
    for side, sz in (('n', 1), ('s', -1)):
        col = {"id": f"column_{side}", "op": "box", "size": [COL_X, top, COL_W],
               "material": "concrete", "open": ["top", "bottom"],
               "transform": {"translate": [x, top / 2, sz * COL_Z]}}
        if detail and plates:
            col["decals"] = [{"id": "plate", "face": "front" if sz > 0 else "back",
                              "material": "pier_plate", "size": [0.32, 0.16],
                              "at": [0, 2.1 - top / 2]}]
        kids.append(col)
    if detail:
        kids.append({"id": "beam", "op": "extrude", "material": "concrete", "depth": BEAM_X,
                     "points": [[-3.65, 8.35], [3.65, 8.35], [3.65, 7.0], [2.9, 7.0], [2.9, 6.4],
                                [1.65, 7.0], [-1.65, 7.0], [-2.9, 6.4], [-2.9, 7.0], [-3.65, 7.0]],
                     "transform": {"rotate": [0, 90, 0], "translate": [x, 0, 0]}})
    return {"id": id_, "op": "group", "children": kids}


def downpipe(x=0.0):
    """A drain pipe from the girder down the north column's -X face."""
    return {"id": "downpipe", "op": "box", "size": [0.16, 7.9, 0.16], "material": "pipe",
            "open": ["top", "bottom"],
            "transform": {"translate": [x - COL_X / 2 - 0.12, 3.95, COL_Z + 0.25]}}


# ---------------------------------------------------------------------------- materials
def materials(sheet_path, extra=()):
    def cell(name, projection='box', scale=None):
        t = {"sheet": "concrete", "cell": name, "projection": projection}
        if scale:
            t["scale"] = scale
        return t
    m = {
        "concrete": {"color": "#b4b0a6", "texture": cell('wall', scale=[4.0, 2.0])},
        "soffit": {"color": "#a29e94", "texture": cell('soffit', scale=[4.0, 2.0])},
        "fascia": {"color": "#b4b0a6", "texture": cell('fascia', scale=[4.0, 1.65])},
        "track": {"color": "#8a8276", "texture": cell('track', scale=[2.0, 4.0])},
        "trough": {"color": "#c4c0b6", "texture": cell('trough', scale=[2.0, 1.75])},
        "coping": {"color": "#c8c4b8", "palette": True},
        "pipe": {"color": "#4a4a50", "palette": True},
        "pier_plate": {"color": "#eceae4", "texture": cell('pier_plate', 'fit')},
    }
    for k in extra:
        m[k] = EXTRA[k]
    return m


EXTRA = {
    "name_plate": {"color": "#eceae4", "texture": {"sheet": "concrete", "cell": "name_plate",
                                                    "projection": "fit"}},
    "plate_edge": {"color": "#3a3a3c", "palette": True},
    "poster_a": {"color": "#c8301e", "texture": {"sheet": "concrete", "cell": "poster_a",
                                                  "projection": "fit"}},
    "poster_b": {"color": "#3a6ab0", "texture": {"sheet": "concrete", "cell": "poster_b",
                                                  "projection": "fit"}},
    "skirt": {"color": "#8e887c", "palette": True},
    "lamp": {"color": "#eef2e2", "class": "emissive", "tag": "lantern"},
}


def recipe(name, budget, sheet_path, mats, nodes, lod=None, notes=None):
    r = {"format": "mei-asset", "version": 1, "name": name, "budget": {"triangles": budget},
         "sheets": {"concrete": {"image": sheet_path}}, "materials": mats,
         "lighting": LIGHT, "verification": POLICY, "nodes": nodes}
    if lod:
        r["lod"] = lod
    return r


def col_recipe(name, nodes):
    return {"format": "mei-asset", "version": 1, "name": name,
            "materials": {"solid": {"color": "#ffffff", "palette": True}},
            "lighting": LIGHT, "verification": POLICY, "nodes": nodes}


def col_box(id_, size, at):
    return {"id": id_, "op": "box", "size": size, "material": "solid", "open": ["bottom"],
            "transform": {"translate": at}}


# ---------------------------------------------------------------------------- the span
def span():
    straight = path_straight(16.0, 1)
    nodes = [sweep("deck", FULL, straight), bent("bent"), downpipe()]
    lod = {"levels": [
        {"distance": 40, "nodes": [sweep("deck", SIMPLE, straight), bent("bent", detail=False)]},
        {"distance": 100, "nodes": [sweep("deck", RIBBON, straight), bent("bent", detail=False)]},
    ], "band": 1}
    r = recipe("viaduct_span_16", 120, SHEET, materials(SHEET), nodes, lod)
    col = col_recipe("viaduct_span_16_col", [
        sweep("deck", COLLIDE, path_straight(16.0, 8), textured=False),
        col_box("column_n", [COL_X, 8.4, COL_W], [0, 4.2, COL_Z]),
        col_box("column_s", [COL_X, 8.4, COL_W], [0, 4.2, -COL_Z])])
    return r, col


def curve():
    arc = path_arc(R_CURVE, 30, 3)
    nodes = [sweep("deck", FULL, arc), bent("bent", plates=False)]
    lod = {"levels": [
        {"distance": 40, "nodes": [sweep("deck", SIMPLE, path_arc(R_CURVE, 30, 2)),
                                   bent("bent", detail=False)]},
        {"distance": 100, "nodes": [sweep("deck", RIBBON, path_arc(R_CURVE, 30, 2)),
                                    bent("bent", detail=False)]},
    ], "band": 1}
    sheet = '../viaduct_span_16/' + SHEET
    r = recipe("viaduct_curve_16", 160, sheet, materials(sheet), nodes, lod)
    col = col_recipe("viaduct_curve_16_col", [
        sweep("deck", COLLIDE, path_arc(R_CURVE, 30, 8), textured=False),
        col_box("column_n", [COL_X, 8.4, COL_W], [0, 4.2, COL_Z]),
        col_box("column_s", [COL_X, 8.4, COL_W], [0, 4.2, -COL_Z])])
    return r, col


# ---------------------------------------------------------------------------- the underpass
SKEW = 25.0                                      # the road's angle to the asset's Z
ROAD_HALF = 7.0                                  # road and sidewalks, 14 m
WALL_T = 1.2
WALL_TOP = 8.6                                   # into the slab (soffit 8.3, fascia foot 8.55)
WALL_OUT = [[-16.2, 0.0], [9.1, 0.0], [9.1, 3.0], [3.1, WALL_TOP], [-10.2, WALL_TOP],
            [-16.2, 3.0]]                        # along the road (s), up; 3.0 m wing ends
WALL_OUT_L2 = [[-16.2, 0.0], [9.1, 0.0], [3.1, WALL_TOP], [-10.2, WALL_TOP]]
END_BENT_X = 11.3


def wall_frame():
    """Rotation and translation that put the wall's outline (x along the road, extruded along z)
    on the road's +n side, its front (+z) toward the road."""
    a = math.radians(SKEW)
    off = ROAD_HALF + WALL_T / 2
    return {"rotate": [0, -(90 + SKEW), 0],
            "translate": [r4(off * math.cos(a)), 0, r4(off * math.sin(a))]}


def walls(level):
    """The two abutments with their wing walls, a point-symmetric pair (radial 2)."""
    out = WALL_OUT if level < 2 else WALL_OUT_L2
    wall = {"id": "wall", "op": "extrude", "material": "concrete", "depth": WALL_T,
            "points": out}
    kids = [wall]
    if level == 0:
        # On the road face (front): a stained plinth, two lamps, two bills; a drain pipe.
        wall["decals"] = [
            {"id": "skirt", "face": "front", "material": "skirt", "size": [25.0, 1.0],
             "at": [3.45, 0.51]},
            {"id": "lamp_w", "face": "front", "material": "lamp", "size": [1.2, 0.18],
             "at": [6.4, 4.6]},
            {"id": "lamp_e", "face": "front", "material": "lamp", "size": [1.2, 0.18],
             "at": [0.0, 4.6]},
            {"id": "poster_a", "face": "front", "material": "poster_a", "size": [0.6, 0.9],
             "at": [4.0, 1.75]},
            {"id": "poster_b", "face": "front", "material": "poster_b", "size": [0.6, 0.9],
             "at": [4.75, 1.65]},
        ]
        kids.append({"id": "wall_pipe", "op": "box", "size": [0.16, 8.6, 0.16],
                     "material": "pipe", "open": ["top", "bottom"],
                     "transform": {"translate": [1.8, 4.3, WALL_T / 2 + 0.12]}})
    return {"id": "abutments", "op": "group", "children": [
        {"id": "south", "op": "group", "children": kids, "transform": wall_frame()}],
        "modifiers": [{"op": "radial", "count": 2}]}


def name_plates():
    """The bridge's name over the road on both faces, 4 cm proud of the fascia."""
    a = math.radians(SKEW)
    x = r4(6.0 * math.tan(a))                    # where the road's centre line meets z = -6
    plates = []
    for side, z, x0, face, hidden in (('w', -6.0, x, 'back', 'front'),
                                      ('e', 6.0, -x, 'front', 'back')):
        plates.append({"id": f"name_plate_{side}", "op": "box", "size": [2.4, 0.6, 0.08],
                       "material": "plate_edge", "open": [hidden],
                       "faces": {face: "name_plate"},
                       "transform": {"translate": [x0, 9.6, z]}})
    return {"id": "name_plates", "op": "group", "children": plates}


def underpass():
    straight = path_straight(24.0, 1)
    nodes = [sweep("deck", FULL, straight), walls(0), name_plates(),
             bent("bent_s", END_BENT_X), bent("bent_n", -END_BENT_X)]
    simple = [sweep("deck", SIMPLE, straight), walls(1),
              bent("bent_s", END_BENT_X, detail=False), bent("bent_n", -END_BENT_X, detail=False)]
    ribbon = [sweep("deck", RIBBON, straight), walls(2)]
    lod = {"levels": [{"distance": 48, "nodes": simple}, {"distance": 120, "nodes": ribbon}],
           "band": 1}
    sheet = '../viaduct_span_16/' + SHEET
    r = recipe("viaduct_underpass", 600, sheet,
               materials(sheet, ("name_plate", "plate_edge", "poster_a", "poster_b", "skirt",
                                 "lamp")), nodes, lod)
    col_wall = {"id": "abutments", "op": "group", "children": [
        {"id": "south", "op": "extrude", "material": "solid", "depth": WALL_T, "points": WALL_OUT,
         "transform": wall_frame()}], "modifiers": [{"op": "radial", "count": 2}]}
    col = col_recipe("viaduct_underpass_col", [
        sweep("deck", COLLIDE, path_straight(24.0, 12), textured=False), col_wall,
        col_box("column_sn", [COL_X, 8.4, COL_W], [END_BENT_X, 4.2, COL_Z]),
        col_box("column_ss", [COL_X, 8.4, COL_W], [END_BENT_X, 4.2, -COL_Z]),
        col_box("column_nn", [COL_X, 8.4, COL_W], [-END_BENT_X, 4.2, COL_Z]),
        col_box("column_ns", [COL_X, 8.4, COL_W], [-END_BENT_X, 4.2, -COL_Z])])
    return r, col


# ---------------------------------------------------------------------------- writing
def dump(obj, ind=0):
    """JSON with short number lists on one line."""
    sp = '  ' * ind
    if isinstance(obj, dict):
        items = [f'{sp}  {json.dumps(k)}: {dump(v, ind + 1).lstrip()}' for k, v in obj.items()]
        return sp + '{\n' + ',\n'.join(items) + '\n' + sp + '}'
    if isinstance(obj, list):
        if all(not isinstance(v, (dict, list)) for v in obj) or \
           all(isinstance(v, list) and all(not isinstance(w, (dict, list)) for w in v) for v in obj):
            flat = json.dumps(obj, separators=(', ', ': '))
            if len(flat) < 92:
                return sp + flat
            rows, line = [], []
            for v in obj:
                s = json.dumps(v, separators=(', ', ': '))
                if line and len(', '.join(line + [s])) > 90:
                    rows.append(', '.join(line))
                    line = []
                line.append(s)
            rows.append(', '.join(line))
            return sp + '[\n' + ',\n'.join(f'{sp}  {r}' for r in rows) + '\n' + sp + ']'
        return sp + '[\n' + ',\n'.join(dump(v, ind + 1) for v in obj) + '\n' + sp + ']'
    return sp + json.dumps(obj)


if __name__ == '__main__':
    for name, (r, col) in (('viaduct_span_16', span()), ('viaduct_curve_16', curve()),
                           ('viaduct_underpass', underpass())):
        folder = os.path.join(ROOT, name)
        os.makedirs(folder, exist_ok=True)
        for rec in (r, col):
            path = os.path.join(folder, rec['name'] + '.asset.json')
            with open(path, 'w') as f:
                f.write(dump(rec) + '\n')
            print('wrote', os.path.relpath(path, ROOT))
