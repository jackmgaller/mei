#!/usr/bin/env python3
"""Writes sakagura.asset.json, sakagura_col.asset.json and sakagura.cameras.json beside this file:
shrine town's sake brewery by the bamboo grove, cut from the lab model (examples/assets/lab/sakagura)
to the town's density limits. Run once and commit the outputs:
python3 carts/garden/shrinetown/assets/sakagura/make_sakagura.py

Asset frame: origin at the centre of the footprint, the entrance (noren, sugidama, barrels) facing
-Z, the vat and its ladder on the +X end, the brick chimney (top 16.2) behind. Design coordinates
are centred on the kura's walls; every node is shifted by SHIFT at the end. Texture sheet:
art/sakagura_sheet.png, copied from the lab model.

Routes: the door hood (a tiled ledge, top 2.9-3.4) -> the eave (5.7) -> the roof, walkable at
28 degrees in its collision (30 in the render) up to the ridge (8.5)."""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))


def r(v):
    return [round(x, 4) for x in v] if isinstance(v, (list, tuple)) else round(v, 4)


def sub(a, b): return [a[i] - b[i] for i in range(3)]
def cross(a, b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
def dot(a, b): return sum(a[i]*b[i] for i in range(3))


def newell(pts):
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


def orient(verts, faces, outward):
    """Wind each face so its normal points along `outward`: a vector, ('away', point), or
    a list of vectors, one a face."""
    out = []
    for k, f in enumerate(faces):
        pts = [verts[i] for i in f]
        n = newell(pts)
        if isinstance(outward, tuple):
            ctr = [sum(p[j] for p in pts) / len(pts) for j in range(3)]
            ref = sub(ctr, outward[1])
        elif isinstance(outward[0], (list, tuple)):
            ref = outward[k]
        else:
            ref = outward
        out.append(list(f) if dot(n, ref) >= 0 else list(reversed(f)))
    return out


def mesh(id_, mat, verts, faces, outward, mats=None, uvs=None, decals=None):
    n = {"id": id_, "op": "mesh", "vertices": [r(v) for v in verts], "faces": orient(verts, faces, outward)}
    if mats:
        n["face_materials"] = mats
    else:
        n["material"] = mat
    if uvs:
        n["uvs"] = uvs
    if decals:
        n["decals"] = decals
    return n


def box(id_, mat, size, at, open_=None, faces=None, decals=None, rot=None, mods=None):
    n = {"id": id_, "op": "box", "size": r(list(size)), "material": mat, "transform": {"translate": r(list(at))}}
    if rot:
        n["transform"]["rotate"] = r(list(rot))
    if open_:
        n["open"] = list(open_)
    if faces:
        n["faces"] = faces
    if decals:
        n["decals"] = decals
    if mods:
        n["modifiers"] = mods
    return n


def cyl(id_, mat, radius, height, seg, at, caps=True, faces=None, rot=None):
    n = {"id": id_, "op": "cylinder", "radius": radius, "height": height, "segments": seg, "material": mat,
         "transform": {"translate": r(list(at))}}
    if not caps:
        n["caps"] = False
    if faces:
        n["faces"] = faces
    if rot:
        n["transform"]["rotate"] = list(rot)
    return n


def sphere(id_, mat, radius, seg, rings, at, scale=None):
    n = {"id": id_, "op": "sphere", "radius": radius, "segments": seg, "rings": rings, "material": mat,
         "transform": {"translate": r(list(at))}}
    if scale:
        n["transform"]["scale"] = list(scale)
    return n


def quad(id_, mat, cx, cy, cz, w, h, facing):
    """A vertical quad centred on (cx, cy, cz), facing -z, +z, -x or +x."""
    hw, hh = w / 2, h / 2
    if facing in ("-z", "+z"):
        v = [[cx - hw, cy - hh, cz], [cx + hw, cy - hh, cz], [cx + hw, cy + hh, cz], [cx - hw, cy + hh, cz]]
        n = [0, 0, -1 if facing == "-z" else 1]
    else:
        v = [[cx, cy - hh, cz - hw], [cx, cy - hh, cz + hw], [cx, cy + hh, cz + hw], [cx, cy + hh, cz - hw]]
        n = [-1 if facing == "-x" else 1, 0, 0]
    return mesh(id_, mat, v, [[0, 1, 2, 3]], n)


def strip(id_, mat, a, b, w, h):
    """A low gable cap (two sloping quads, 4 triangles) along the line a -> b, h above it."""
    d = sub(b, a)
    side = cross(d, [0, 1, 0])
    ln = math.sqrt(dot(side, side))
    side = [s / ln * w / 2 for s in side]
    v = [[a[0] + side[0], a[1], a[2] + side[2]], [b[0] + side[0], b[1], b[2] + side[2]],
         [b[0], b[1] + h, b[2]], [a[0], a[1] + h, a[2]],
         [a[0] - side[0], a[1], a[2] - side[2]], [b[0] - side[0], b[1], b[2] - side[2]]]
    return mesh(id_, mat, v, [[0, 1, 2, 3], [3, 2, 5, 4]], [[side[0], 1, side[2]], [-side[0], 1, -side[2]]])


def solid(id_, verts, faces):
    """A convex closed collision solid, its faces wound away from its centroid."""
    c = [sum(v[i] for v in verts) / len(verts) for i in range(3)]
    return mesh(id_, "solid", verts, faces, ("away", c))


def cuboid(id_, x0, x1, y0, y1, z0, z1):
    v = [[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1],
         [x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]]
    return solid(id_, v, [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]])


def frustum(id_, lo, hi):
    """lo, hi: (half_x, half_z, y, cx, cz); a box-section frustum (also a tapered chimney)."""
    v = []
    for hx, hz, y, cx, cz in (lo, hi):
        v += [[cx - hx, y, cz - hz], [cx + hx, y, cz - hz], [cx + hx, y, cz + hz], [cx - hx, y, cz + hz]]
    return solid(id_, v, [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]])


def shift(nodes, dx, dz):
    for n in nodes:
        if "transform" in n:
            t = n["transform"].setdefault("translate", [0, 0, 0])
            n["transform"]["translate"] = r([t[0] + dx, t[1], t[2] + dz])
        elif n["op"] == "mesh":
            n["vertices"] = [r([v[0] + dx, v[1], v[2] + dz]) for v in n["vertices"]]
        else:
            n["transform"] = {"translate": [dx, 0, dz]}
    return nodes




# ------------------------------------------------------------------------------- materials
M = {
    "namako": {"color": "#3a3c42", "tag": "wall", "texture": {
        "pattern": "lattice", "colors": ["#ece8dc", "#3a3c44"], "params": {"count": 2, "bar": 2, "diagonal": True},
        "projection": "box", "scale": [0.7, 0.7]}},
    "yakisugi": {"color": "#2a2624", "tag": "wall", "texture": {
        "texels": ["1000200010003000", "1000200010003000", "1000200010003000", "1002200010003000",
                   "1000200010003000", "1000200010003000", "1000200010303000", "1000200010003000",
                   "1000200010003000", "1000220010003000", "1000200010003000", "1000200010003000",
                   "1000200010003030", "1000200010003000", "1000200010003000", "1000200010003000"],
        "colors": ["#2e2a28", "#121010", "#383230", "#262220"], "projection": "box", "scale": [0.6, 1.2]}},
    "kawara": {"color": "#62666e", "tag": "roof", "texture": {"sheet": "kura", "cell": "kawara", "projection": "planar",
                                                              "axis": "y", "scale": [1.0, 1.0]}},
    "kawara_far": {"color": "#62666e", "tag": "roof", "texture": {"sheet": "kura", "cell": "kawara", "projection": "planar",
                                                                  "axis": "y", "scale": [4.0, 4.0]}},
    "kawara_mid": {"color": "#62666e", "tag": "roof", "texture": {"sheet": "kura", "cell": "kawara", "projection": "planar",
                                                                  "axis": "y", "scale": [2.0, 2.0]}},
    "hood_tile": {"color": "#62666e", "tag": "roof", "texture": {"sheet": "kura", "cell": "kawara", "projection": "box",
                                                                 "scale": [0.6, 0.6]}},
    "brick": {"color": "#964030", "texture": {
        "pattern": "brick", "colors": ["#963e2c", "#bcaa96", "#7e3424"], "params": {"courses": 4, "bricks": 2},
        "projection": "box", "scale": [1.3, 1.1]}},
    "koshi": {"color": "#54341e", "texture": {"sheet": "kura", "cell": "koshi", "projection": "planar", "axis": "z",
                                              "scale": [0.4, 0.4]}},
    "taru": {"color": "#d6be82", "texture": {"sheet": "kura", "cell": "taru", "bits": 8, "projection": "cylindrical",
                                             "scale": [1.885, 0.55], "offset": [0.5, 0.5]}},
    "chimney_name": {"color": "#963e2c", "texture": {"sheet": "kura", "cell": "chimney", "projection": "fit"}},
    "kanban": {"color": "#462c1c", "texture": {"sheet": "kura", "cell": "kanban", "bits": 8, "projection": "fit"}},
    "door": {"color": "#604028", "tag": "door", "texture": {"sheet": "kura", "cell": "door", "projection": "fit"}},
    "noren": {"color": "#202c5c", "double_sided": True, "texture": {"sheet": "kura", "cell": "noren", "projection": "fit"}},
    "mushiko": {"color": "#24201e", "tag": "window", "texture": {"sheet": "kura", "cell": "mushiko", "projection": "fit"}},
    "crest": {"color": "#ece8de", "texture": {"sheet": "kura", "cell": "crest", "projection": "fit"}},
    "crate": {"color": "#f0c428", "texture": {"sheet": "kura", "cell": "crate", "projection": "fit"}},
    "staves": {"color": "#a87a4c", "texture": {"sheet": "kura", "cell": "staves", "projection": "fit"}},
    "sugi": {"color": "#6a7a3a", "texture": {"pattern": "speckle", "colors": ["#66783a", "#4c5c2a", "#8a8a48", "#7a6a3a"],
                                             "params": {"density": 0.5, "seed": 2}, "projection": "fit"}},
    "ladder": {"color": "#5a3e2c", "double_sided": True, "texture": {
        "texels": (["10000001"] * 7 + ["11111111"]) * 6,
        "colors": ["#ff00ff", "#5a3e2c"], "clear": "#ff00ff", "projection": "fit"}},
}
# palette-backed colours (8 surface, 1 emissive), from the shrine's palette
for name, col in {"plaster": "#ece4d2", "beam": "#2c2a28", "ridge": "#3e4248", "wood": "#5a3e2c",
                  "rope": "#b08a5e", "gold": "#f0c030", "stone": "#8e887c", "lid": "#8a6446"}.items():
    M[name] = {"color": col, "palette": True}
M["plaster"]["tag"] = "wall"
M["ridge"]["tag"] = "roof"
M["chochin"] = {"color": "#d8462a", "class": "emissive", "tag": "lantern"}

# ------------------------------------------------------------------------------- dimensions
W, D = 7.0, 4.0                 # walls: half-width (x), half-depth (z)
EAVE_TOP = 6.0                  # wall top (the eave band)
SK_H = 2.25                     # namako skirt
PITCH = math.tan(math.radians(30))
RZ, RX, RT = 4.86, 7.4, 0.22    # roof: eave half-depth, half-length, thickness
UND_E = EAVE_TOP - (RZ - D) * PITCH          # underside at the eave edge
TOP_E = UND_E + RT                            # top surface at the eave edge
RIDGE = TOP_E + RZ * PITCH                    # top surface at the ridge
CH = (4.8, 5.6)                 # chimney x, z; its top is 16.2
CH_TOP = 16.2
SHIFT = (-0.93, -0.45)


def roof(lid, mat, mat_under="beam"):
    """The gable roof as a closed slab: outline (z, y) extruded along x, faces wound outward."""
    pts = [(-RZ, UND_E), (0, UND_E + RZ * PITCH), (RZ, UND_E), (RZ, TOP_E), (0, RIDGE), (-RZ, TOP_E)]
    v = [[-RX, y, z] for z, y in pts] + [[RX, y, z] for z, y in pts]
    f = [[i, (i + 1) % 6, 6 + (i + 1) % 6, 6 + i] for i in range(6)] + [[0, 1, 4, 5], [1, 2, 3, 4], [6, 7, 10, 11], [7, 8, 9, 10]]
    out = [[0, -1, 0.6], [0, -1, -0.6], [0, 0, 1], [0, 1, 0.6], [0, 1, -0.6], [0, 0, -1], [-1, 0, 0], [-1, 0, 0], [1, 0, 0], [1, 0, 0]]
    mats = [mat_under, mat_under, "beam", mat, mat, "beam", "beam", "beam", "beam", "beam"]
    return mesh(lid, None, v, f, out, mats=mats)


def attic(decals=True):
    n = {"id": "attic", "op": "extrude", "depth": 2 * W, "points": [[-D, 0], [D, 0], [0, round(D * PITCH - 0.05, 4)]],
         "material": "plaster", "transform": {"rotate": [0, 90, 0], "translate": [0, EAVE_TOP, 0]}}
    if decals:
        n["decals"] = [{"id": "crest_w", "face": "back", "material": "crest", "size": [1.1, 1.1], "at": [0, 0.95]},
                       {"id": "crest_e", "face": "front", "material": "crest", "size": [1.1, 1.1], "at": [0, 0.95]}]
    return n


def chimney(lod):
    ch = box("chimney", "brick", [1.3, CH_TOP - 0.3, 1.3], [CH[0], (CH_TOP - 0.3) / 2, CH[1]], ["bottom", "top"],
             mods=[{"op": "taper", "top": 0.55}])
    if lod < 2:
        ch["decals"] = [{"id": "name", "face": "back", "material": "chimney_name", "size": [0.5, 2.8], "at": [0, 3.0]}]
    return [ch, box("chimney_cap", "beam", [0.82, 0.4, 0.82], [CH[0], CH_TOP - 0.2, CH[1]], ["bottom"])]


def lantern(id_, x, y, z, seg=6, s=1.0):
    return cyl(id_, "chochin", 0.2 * s, 0.46 * s, seg, [x, y, z], faces={"top": "beam", "bottom": "beam"})


def vat(seg=8, hoops=True):
    out = [{"id": "vat", "op": "lathe", "profile": [[1.0, 0.0], [1.12, 2.2]], "segments": seg, "material": "staves",
            "faces": {"top": "lid"}, "transform": {"translate": [8.4, 0, 1.0]}}]
    if hoops:
        for k, (y, rad) in enumerate([(0.5, 1.065), (1.75, 1.135)]):
            out.append(cyl("hoop_%d" % k, "rope", rad, 0.1, seg, [8.4, y, 1.0], caps=False))
    return out


def front_skirt(decals):
    d = [{"id": "door", "face": "back", "material": "door", "size": [1.15, 2.2], "at": [-3.05, 0.0]},
         {"id": "doorway", "face": "back", "material": "beam", "size": [0.95, 2.2], "at": [-1.95, 0.0]}]
    return box("skirt", "namako", [2 * W + 0.1, SK_H, 2 * D + 0.1], [0, SK_H / 2, 0], ["bottom"],
               faces={"left": "yakisugi", "right": "yakisugi", "top": "beam"}, decals=d[:decals])


def taru(id_, x, y, z, yaw):
    return cyl(id_, "taru", 0.3, 0.55, 6, [x, y, z], faces={"top": "lid", "bottom": "lid"}, rot=[0, yaw, 0])


# ------------------------------------------------------------------------------- level 0
L0 = []
add = L0.append
add(box("walls", "plaster", [2 * W, EAVE_TOP - SK_H + 0.05, 2 * D], [0, (EAVE_TOP + SK_H - 0.05) / 2, 0], ["bottom", "top"],
        decals=[{"id": "win_f1", "face": "back", "material": "mushiko", "size": [0.9, 0.62], "at": [1.6, 0.5]},
                {"id": "win_f2", "face": "back", "material": "mushiko", "size": [0.9, 0.62], "at": [4.6, 0.5]},
                {"id": "win_f3", "face": "back", "material": "mushiko", "size": [0.9, 0.62], "at": [-5.8, 0.5]},
                {"id": "win_w", "face": "left", "material": "mushiko", "size": [0.9, 0.62], "at": [-1.8, 0.5]},
                {"id": "win_e", "face": "right", "material": "mushiko", "size": [0.9, 0.62], "at": [-1.8, 0.5]}]))
add(front_skirt(2))
add(box("eave_band", "beam", [2 * W + 0.12, 0.32, 2 * D + 0.12], [0, EAVE_TOP - 0.16, 0], ["top", "bottom"]))
add(attic())
add(roof("roof", "kawara"))
add(box("ridge", "ridge", [2 * RX + 0.2, 0.45, 0.6], [0, RIDGE + 0.1, 0], ["bottom"]))
for sx, nm in ((-1, "w"), (1, "e")):
    add(box("oni_" + nm, "ridge", [0.35, 0.85, 0.75], [sx * (RX + 0.1), RIDGE + 0.32, 0], ["bottom"]))
add(box("kanban", "wood", [4.4, 1.45, 0.14], [-2.5, 4.3, -4.05], ["front"], faces={"back": "kanban"}))
# the entrance: posts, lintel, a little tiled hood, the step, the noren, the sugidama
for x, nm in ((-3.75, "w"), (-1.25, "e")):
    add(box("door_post_" + nm, "wood", [0.2, 2.5, 0.3], [x, 1.25, -4.1], ["bottom", "top"]))
add(box("lintel", "wood", [2.9, 0.26, 0.4], [-2.5, 2.5, -4.1], ["front"]))
add(box("hood", "hood_tile", [3.9, 0.12, 1.35], [-2.5, 3.05, -4.62], rot=[-20, 0, 0]))
add(box("step", "stone", [1.8, 0.15, 0.6], [-2.5, 0.075, -4.4], ["bottom"]))
add(quad("noren", "noren", -2.5, 2.235, -4.36, 2.2, 0.97, "-z"))
add(box("sugi_rope", "rope", [0.03, 0.42, 0.03], [-0.75, 2.85, -5.0], ["bottom", "top"]))
add(sphere("sugidama", "sugi", 0.42, 6, 4, [-0.75, 2.3, -5.0]))
# the shop front: a lattice panel, its beam, posts and hood
add(box("shop_koshi", "koshi", [3.8, 1.9, 0.12], [4.5, 1.2, -4.08], ["front", "bottom"]))
add(box("shop_beam", "wood", [4.1, 0.16, 0.28], [4.5, 2.23, -4.1], ["front", "bottom"]))
for x, nm in ((2.45, "w"), (6.55, "e")):
    add(box("shop_post_" + nm, "wood", [0.14, 2.3, 0.18], [x, 1.15, -4.1], ["bottom", "top"]))
add(box("shop_hood", "hood_tile", [4.6, 0.1, 0.95], [4.5, 2.62, -4.45], rot=[-20, 0, 0]))
add(lantern("lantern_door", -4.15, 2.0, -4.5, s=1.3))
add(lantern("lantern_shop_w", 3.0, 2.05, -4.6, s=1.15))
add(lantern("lantern_shop_e", 6.0, 2.05, -4.6, s=1.15))
# bench, barrels, beer crates
add(box("bench_seat", "wood", [1.7, 0.06, 0.45], [4.4, 0.45, -4.75]))
for x, nm in ((3.7, "w"), (5.1, "e")):
    add(box("bench_leg_" + nm, "wood", [0.06, 0.44, 0.36], [x, 0.215, -4.75], ["bottom", "top"]))
for k, (x, y, yaw) in enumerate([(0.0, 0.275, 0), (0.62, 0.275, 12), (1.24, 0.275, -9),
                                 (0.31, 0.835, 20), (0.93, 0.835, -15), (0.62, 1.395, 5)]):
    add(taru("taru_%d" % k, x - 0.35, y, -4.55, yaw))
add(box("crate_low", "gold", [0.42, 0.3, 0.34], [6.6, 0.15, -4.5], ["bottom"], faces={"top": "crate"}))
add(box("crate_high", "gold", [0.46, 0.3, 0.38], [6.62, 0.44, -4.49], faces={"top": "crate"}, rot=[0, 8, 0]))
# the vat and its ladder at the east end; the chimney behind
L0 += vat()
add(mesh("ladder", "ladder", [[8.18, 0.0, -0.62], [8.62, 0.0, -0.62], [8.62, 2.52, 0.0], [8.18, 2.52, 0.0]],
         [[0, 1, 2, 3]], [0, 0.25, -1]))
L0 += chimney(0)

# ------------------------------------------------------------------------------- level 1 (from 24 m)
L1 = [box("walls", "plaster", [2 * W, EAVE_TOP - SK_H + 0.05, 2 * D], [0, (EAVE_TOP + SK_H - 0.05) / 2, 0], ["bottom", "top"]),
      front_skirt(1), attic(False), roof("roof", "kawara_mid"),
      box("ridge", "ridge", [2 * RX + 0.2, 0.45, 0.6], [0, RIDGE + 0.1, 0], ["bottom"]),
      box("kanban", "wood", [4.4, 1.45, 0.14], [-2.5, 4.3, -4.05], ["front"], faces={"back": "kanban"}),
      box("hood", "hood_tile", [3.9, 0.12, 1.35], [-2.5, 3.05, -4.62], rot=[-20, 0, 0]),
      quad("noren", "noren", -2.5, 2.235, -4.3, 2.2, 0.97, "-z"),
      box("shop_koshi", "koshi", [3.8, 1.9, 0.12], [4.5, 1.2, -4.08], ["front", "bottom"]),
      sphere("sugidama", "sugi", 0.42, 5, 3, [-0.75, 2.3, -5.0]),
      lantern("lantern_door", -4.15, 2.0, -4.5, seg=4, s=1.3)]
L1 += vat(6, False)
L1 += chimney(1)

# ------------------------------------------------------------------------------- level 2 (from 60 m)
pts = [(-RZ, TOP_E), (RZ, TOP_E), (0, RIDGE)]
L2 = [box("walls", "plaster", [2 * W, TOP_E, 2 * D], [0, TOP_E / 2, 0], ["bottom", "top"]),
      mesh("roof", None, [[-RX, y, z] for z, y in pts] + [[RX, y, z] for z, y in pts],
           [[0, 1, 4, 3], [1, 2, 5, 4], [2, 0, 3, 5], [0, 1, 2], [3, 4, 5]],
           [[0, -1, 0], [0, 1, 0.6], [0, 1, -0.6], [-1, 0, 0], [1, 0, 0]],
           mats=["beam", "kawara_far", "kawara_far", "plaster", "plaster"])]
L2 += chimney(2)

for nodes in (L0, L1, L2):
    shift(nodes, *SHIFT)

recipe = {
    "format": "mei-asset", "version": 1, "name": "sakagura",
    "budget": {"triangles": 700},
    "sheets": {"kura": {"image": "art/sakagura_sheet.png"}},
    "materials": M,
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": L0,
    "lod": {"levels": [{"distance": 24, "nodes": L1}, {"distance": 60, "nodes": L2}], "band": 2},
}

# ------------------------------------------------------------------------------- collision
# The roof's collision is 28 degrees (walkable) under the render's 30, from the eave's top edge.
C_R = TOP_E + RZ * math.tan(math.radians(28))
hood_a = math.radians(20)
C = [cuboid("body", -W - 0.05, W + 0.05, 0, EAVE_TOP, -D - 0.05, D + 0.05),
     solid("roof", [[-RX, UND_E, -RZ], [RX, UND_E, -RZ], [RX, UND_E, RZ], [-RX, UND_E, RZ],
                    [-RX, TOP_E, -RZ], [RX, TOP_E, -RZ], [RX, TOP_E, RZ], [-RX, TOP_E, RZ],
                    [-RX, C_R, 0], [RX, C_R, 0]],
           [[0, 1, 2, 3], [0, 1, 5, 4], [3, 2, 6, 7], [4, 5, 9, 8], [7, 6, 9, 8], [0, 4, 8], [0, 8, 7, 3],
            [1, 5, 9], [1, 9, 6, 2]]),
     cuboid("ridge", -RX - 0.1, RX + 0.1, C_R - 0.3, RIDGE + 0.32, -0.3, 0.3),
     # the door hood: a tiled ledge (20 degrees) 3 m up, a step toward the eave
     solid("hood", [[-4.45, 2.75, -5.25], [-0.55, 2.75, -5.25], [-0.55, 3.25, -3.9], [-4.45, 3.25, -3.9],
                    [-4.45, 2.93, -5.25], [-0.55, 2.93, -5.25], [-0.55, 3.43, -3.9], [-4.45, 3.43, -3.9]],
           [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]),
     cuboid("step", -3.4, -1.6, 0, 0.15, -4.7, -4.1),
     cuboid("taru_row", -0.65, 1.19, 0, 0.55, -4.87, -4.23),
     cuboid("taru_mid", -0.34, 0.88, 0.5, 1.12, -4.83, -4.27),
     cuboid("taru_top", -0.03, 0.57, 1.07, 1.67, -4.79, -4.31),
     cuboid("bench", 3.55, 5.25, 0, 0.48, -4.98, -4.52),
     cuboid("crates", 6.35, 6.88, 0, 0.59, -4.72, -4.27),
     cuboid("vat", 7.3, 9.5, 0, 2.2, -0.1, 2.1),
     frustum("chimney", (0.65, 0.65, 0, CH[0], CH[1]), (0.36, 0.36, CH_TOP - 0.3, CH[0], CH[1])),
     cuboid("chimney_cap", CH[0] - 0.41, CH[0] + 0.41, CH_TOP - 0.4, CH_TOP, CH[1] - 0.41, CH[1] + 0.41)]
shift(C, *SHIFT)
col = {"format": "mei-asset", "version": 1, "name": "sakagura_col",
       "materials": {"solid": {"color": "#ffffff", "palette": True}},
       "lighting": {"mode": "vertical", "ambient": 0.5},
       "verification": {"required": True, "depth": True, "perspective": True},
       "nodes": C}

sx, sz = SHIFT
P = lambda x, y, z: [round(x + sx, 2), y, round(z + sz, 2)]
cams = [
    {"name": "hero", "eye": P(-11, 5, -15), "target": P(0, 4.5, 0)},
    {"name": "door", "eye": P(1.0, 1.6, -8.0), "target": P(-1.0, 1.6, -4)},
    {"name": "grove_path", "eye": P(-20, 3.0, -8), "target": P(0, 5, 0)},
    {"name": "from_park", "eye": P(6, 2.0, -30), "target": P(0, 7, 0)},
    {"name": "on_hood", "eye": P(-2.5, 3.2 + 1.6, -4.9), "target": P(-2.5, 6.5, 0)},
    {"name": "on_roof", "eye": P(-5, C_R + 1.0, -1.0), "target": P(CH[0], 12, CH[1])},
]
with open(os.path.join(HERE, "sakagura.asset.json"), "w") as fh:
    json.dump(recipe, fh, indent=1)
with open(os.path.join(HERE, "sakagura_col.asset.json"), "w") as fh:
    json.dump(col, fh, indent=1)
with open(os.path.join(HERE, "sakagura.cameras.json"), "w") as fh:
    json.dump(cams, fh, indent=1)
print("wrote sakagura, sakagura_col, sakagura.cameras.json")
