#!/usr/bin/env python3
"""Writes sento_front.asset.json, sento_front_col.asset.json and sento_front.cameras.json beside
this file: shrine town's public bath by the canal, cut from the lab model
(examples/assets/lab/sento_front) to the town's density limits. Run once and commit the outputs:
python3 carts/garden/shrinetown/assets/sento_front/make_sento.py

Asset frame: origin at the centre of the footprint, the entrance (karahafu porch) facing -Z, the
boiler room and its chimney on the +X side at the back. The design coordinates below are centred
on the main hall; every node is shifted by SHIFT at the end.

Routes: ground -> lower skirt roof (3.55 at its outer edge) -> boiler-room roof (5.0, flat) ->
the chimney's iron ladder (a pole entity, 5.0 -> 19.4) -> the chimney's top (18.2, 1.3 m square:
red coin 7, glide G3). The main roof (eave 6.05, ridge 7.75, 21-22 degrees) is walkable, with
the cat on its ridge."""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
TILE = "../../../shrine/assets/art/arch_tile.png"
STONE = "../../../shrine/assets/art/arch_stone.png"


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
    "tile": {"color": "#565c64", "tag": "roof", "texture": {"image": TILE, "projection": "planar", "axis": "y", "scale": [1.0, 1.0]}},
    # the same tile at a quarter of the density for the far levels: no face needs cutting
    "tile_far": {"color": "#565c64", "tag": "roof", "texture": {"image": TILE, "projection": "planar", "axis": "y", "scale": [4.0, 4.0]}},
    "tile_k": {"color": "#565c64", "tag": "roof", "texture": {"image": TILE, "projection": "planar", "axis": "y", "scale": [1.0, 1.0]}},
    "plaster": {"color": "#e4dccb", "tag": "wall", "texture": {
        "pattern": "speckle", "colors": ["#e4dccb", "#d4cab4", "#ece4d2"], "params": {"density": 0.14, "seed": 3},
        "projection": "box", "scale": [2.0, 2.0]}},
    "boards": {"color": "#6b4a34", "tag": "wall", "texture": {
        "pattern": "stripes", "colors": ["#76523a", "#6a4932", "#5c3f2a", "#6a4932"], "params": {"count": 8},
        "projection": "box", "scale": [1.6, 1.6]}},
    "rafters": {"color": "#4a3020", "texture": {
        "pattern": "stripes", "colors": ["#5a3e2c", "#2c2a28"], "params": {"count": 2},
        "projection": "planar", "axis": "y", "scale": [2.0, 2.0]}},
    "brick": {"color": "#9c4f34", "tag": "wall", "texture": {
        "pattern": "brick", "colors": ["#a4553a", "#b99a7a", "#94492f"], "params": {"courses": 4, "bricks": 2},
        "projection": "box", "scale": [1.2, 0.9]}},
    "brick_far": {"color": "#9c4f34", "tag": "wall", "texture": {
        "pattern": "brick", "colors": ["#a4553a", "#b99a7a", "#94492f"], "params": {"courses": 4, "bricks": 2},
        "projection": "box", "scale": [2.4, 1.8]}},
    "ladder": {"color": "#3e4248", "double_sided": True, "texture": {
        "texels": ["11111111", "10000001", "10000001", "10000001", "10000001", "10000001", "10000001", "10000001"],
        "colors": ["#ff00ff", "#3e4248"], "clear": "#ff00ff", "projection": "planar", "axis": "z", "scale": [0.5, 0.4]}},
    "glass_door": {"color": "#f6ecb4", "class": "emissive", "tag": "door", "texture": {
        "pattern": "lattice", "colors": ["#5a3d28", "#f2e6a8"], "params": {"count": 4, "bar": 1}, "projection": "fit"}},
    "glass_win": {"color": "#d6ecf0", "class": "emissive", "tag": "window", "texture": {
        "pattern": "lattice", "colors": ["#4c4a46", "#c8e4ea"], "params": {"count": 4, "bar": 1}, "projection": "fit"}},
    "glass_up": {"color": "#f6e6a0", "class": "emissive", "tag": "window", "texture": {
        "pattern": "lattice", "colors": ["#4c4a46", "#f0e2a0"], "params": {"count": 4, "bar": 1}, "projection": "fit"}},
    "door_dark": {"color": "#4a3626", "tag": "door", "texture": {
        "pattern": "planks", "colors": ["#4a3626", "#2c2a28", "#56402c"], "params": {"boards": 4}, "projection": "fit"}},
}
sheet = lambda cell, **kw: dict({"sheet": "s", "cell": cell, "projection": "fit"}, **kw)
M["noren_blue"] = {"color": "#2c4d92", "texture": sheet("noren_blue")}
M["noren_red"] = {"color": "#b8352f", "texture": sheet("noren_red")}
M["plaque"] = {"color": "#22397a", "texture": sheet("plaque")}
M["vend"] = {"color": "#c8322a", "class": "emissive", "texture": sheet("vend")}
M["nobori"] = {"color": "#c8322a", "double_sided": True, "texture": sheet("nobori")}
M["bike"] = {"color": "#2f8f86", "double_sided": True, "texture": sheet("bike")}
M["steam"] = {"color": "#f2f4f6", "class": "emissive", "double_sided": True, "texture": sheet("steam")}
M["yu_red"] = {"color": "#c8322a", "texture": sheet("yu_red")}
# palette-backed colours (8 surface, 1 emissive), from the shrine's palette
for name, col in {"dark": "#2c2a28", "cap": "#3e4248", "wood": "#5a3e2c", "white": "#ece4d2",
                  "red": "#a8321e", "leaf": "#3c5a34", "cat": "#e8782a", "pot": "#9a5a2e", "stone": "#b4ae9e"}.items():
    M[name] = {"color": col, "palette": True}
M["chochin"] = {"color": "#e0502a", "class": "emissive", "tag": "lantern"}

# ------------------------------------------------------------------------------- dimensions
PL = 0.45                     # plinth top
WALL_TOP = 3.6                # ground storey wall top
SO = (8.9, 5.1, 3.55)         # skirt roof: outer half-width, half-depth, y
SI = (6.0, 2.8, 4.35)         # skirt roof: inner edge (meets the upper storey)
UP_TOP = 5.75                 # upper storey wall top = main eave
RH, RE, RY, RT = (7.4, 4.4), 5.75, 7.75, 3.2   # main roof: eave half sizes, eave y, ridge y, ridge half-length
ZF, ZB, YB, YBASE, HW = -6.6, -2.85, 5.5, 3.05, 4.2   # karahafu: front, back, back-edge y, board foot, half-width
AX0, AX1, AZ0, AZ1, AY = 9.0, 12.4, -1.0, 4.2, 4.8     # boiler room
CH_X, CH_Z, CH_Y0, CH_Y1, CH_W, CH_TAPER = 10.7, 2.9, 4.6, 17.9, 1.5, 0.64
TOP = 18.2                    # the chimney's top: red coin 7, glide G3
SHIFT = (-1.9, 1.35)
RING = [(-1, -1), (1, -1), (1, 1), (-1, 1)]         # design -> asset frame (the footprint's centre)


def curve(x, n=1.6):
    t = abs(x) / HW
    bell = (1 + math.cos(math.pi * t)) / 2
    return YBASE + 0.4 + n * bell ** 1.25


def chw(y):
    return CH_W * (1 + (CH_TAPER - 1.0) * (y - CH_Y0) / (CH_Y1 - CH_Y0))


def karahafu(N, lid="kara"):
    xs = [-HW + 2 * HW * i / N for i in range(N + 1)]
    out = []
    tv = [[x, curve(x), ZF] for x in xs] + [[x, YB, ZB] for x in xs]
    tf = []
    for i in range(N):
        a, b, c, d = i, i + 1, N + 2 + i, N + 1 + i
        tf += [[a, b, c], [a, c, d]]
    out.append(mesh(lid + "_top", "tile_k", tv, tf, [0, 1, -0.2]))
    bv = [[x, curve(x), ZF] for x in xs] + [[x, YBASE, ZF] for x in xs]
    bf = []
    for i in range(N):
        bf += [[i, N + 1 + i, N + 2 + i], [i, N + 2 + i, i + 1]]
    out.append(mesh(lid + "_board", "plaster", bv, bf, [0, 0, -1]))
    uv = [[x, YBASE, ZF] for x in xs] + [[-HW, YBASE, ZB], [HW, YBASE, ZB]]
    uf = [[N + 1, i, i + 1] for i in range(N)] + [[N + 1, N, N + 2]]
    out.append(mesh(lid + "_under", "rafters", uv, uf, [0, -1, 0]))
    for sx, nm in ((-1, "w"), (1, "e")):
        out.append(mesh(lid + "_side_" + nm, "dark", [[sx * HW, curve(HW), ZF], [sx * HW, YB, ZB], [sx * HW, YBASE, ZB],
                                                    [sx * HW, YBASE, ZF]], [[0, 1, 2, 3]], [sx, 0, 0]))
    return out


def main_roof(lid="roof", soffit=True, fascia=True):
    EO = [[-RH[0], RE, -RH[1]], [RH[0], RE, -RH[1]], [RH[0], RE, RH[1]], [-RH[0], RE, RH[1]]]
    EU = [[x, RE + (0.3 if fascia else 0.0), z] for x, _, z in EO]
    out = [mesh(lid, "tile", EU + [[-RT, RY, 0], [RT, RY, 0]], [[0, 4, 5, 1], [2, 5, 4, 3], [3, 4, 0], [1, 5, 2]],
                ("away", [0, RE, 0]))]
    if fascia:
        out.append(mesh(lid + "_fascia", "dark", EO + EU, [[0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]],
                        ("away", [0, RE, 0])))
    if soffit:
        out.append(mesh(lid + "_soffit", "rafters", EO, [[0, 1, 2, 3]], [0, -1, 0]))
    return out


def chimney(lod=0):
    out = [box("chimney", "brick", [CH_W, CH_Y1 - CH_Y0, CH_W], [CH_X, (CH_Y0 + CH_Y1) / 2, CH_Z], ["bottom", "top"],
               mods=[{"op": "taper", "top": CH_TAPER, "bottom": 1.0}],
               decals=[{"id": "yu_e", "face": "right", "material": "yu_red", "size": [0.9, 0.9], "at": [0, 3.2]},
                       {"id": "yu_w", "face": "left", "material": "yu_red", "size": [0.9, 0.9], "at": [0, 3.2]}]
               if lod == 0 else [{"id": "yu_e", "face": "right", "material": "yu_red", "size": [0.9, 0.9], "at": [0, 3.2]}]),
           box("chimney_cap", "cap", [chw(CH_Y1) + 0.35, TOP - CH_Y1 + 0.1, chw(CH_Y1) + 0.35],
               [CH_X, (TOP + CH_Y1 - 0.1) / 2, CH_Z], ["bottom"])]
    if lod <= 1:
        by = CH_Y1 - 1.1
        out.append(box("chimney_band", "white", [chw(by) + 0.12, 0.34, chw(by) + 0.12], [CH_X, by, CH_Z], ["top", "bottom"]))
        # the iron ladder on the front face, 0.12 proud of it, following the taper
        y0, y1 = AY + 0.2, CH_Y1 - 0.05
        z0, z1 = CH_Z - chw(y0) / 2 - 0.12, CH_Z - chw(y1) / 2 - 0.12
        out.append(mesh("ladder", "ladder", [[CH_X - 0.25, y0, z0], [CH_X + 0.25, y0, z0], [CH_X + 0.25, y1, z1],
                                             [CH_X - 0.25, y1, z1]], [[0, 1, 2, 3]], [0, 0, -1]))
        # its stiles run on 1.2 m over the cap, a handhold to step off onto the top (the ladder's
        # pole runs to 19.4: place/canal.py)
        y2, y3, z2 = TOP, TOP + 1.2, CH_Z - (chw(CH_Y1) + 0.35) / 2 - 0.05
        out.append(mesh("ladder_top", "ladder", [[CH_X - 0.25, y2, z2], [CH_X + 0.25, y2, z2], [CH_X + 0.25, y3, z2],
                                                 [CH_X - 0.25, y3, z2]], [[0, 1, 2, 3]], [0, 0, -1]))
    return out


def steam(n):
    """Puffs of steam: quads drawn from both sides, the second turned a quarter, so one always
    shows; above the chimney's top and downwind, clear of a player standing there."""
    out = []
    for i, (dx, dy, w) in enumerate([(0.9, 2.3, 3.0), (1.6, 3.6, 2.4)][:n]):
        cx, cy, cz = CH_X + dx, TOP + dy, CH_Z + 0.2 * i
        if i % 2 == 0:
            v = [[cx - w / 2, cy - w / 4, cz], [cx + w / 2, cy - w / 4, cz], [cx + w / 2, cy + w / 4, cz], [cx - w / 2, cy + w / 4, cz]]
            nrm = [0, 0, -1]
        else:
            v = [[cx, cy - w / 4, cz + w / 2], [cx, cy - w / 4, cz - w / 2], [cx, cy + w / 4, cz - w / 2], [cx, cy + w / 4, cz + w / 2]]
            nrm = [1, 0, 0]
        out.append(mesh("steam_%d" % i, "steam", v, [[0, 1, 2, 3]], nrm))
    return out


def vend():
    return box("vend", "red", [1.0, 1.9, 0.8], [-7.2, 0.95, -5.15], ["bottom"], faces={"back": "vend", "top": "cap"})


# ------------------------------------------------------------------------------- level 0
L0 = []
add = L0.append
add(box("plinth", "stone", [17.8, PL, 9.4], [0, PL / 2, 0], ["bottom"]))
# the porch platform and its step, one prism (the outline in z, y), x +-3.6
pz = [(-7.8, 0.0), (-7.8, 0.15), (-7.15, 0.15), (-7.15, 0.3), (-4.6, 0.3), (-4.6, 0.0)]
pv = [[-3.6, y, z] for z, y in pz] + [[3.6, y, z] for z, y in pz]
pf = [[i, i + 1, 7 + i, 6 + i] for i in range(4)] + [[0, 1, 2, 3, 4, 5], [6, 7, 8, 9, 10, 11]]
add(mesh("porch", "stone", pv, pf, [[0, 0, -1], [0, 1, 0], [0, 0, -1], [0, 1, 0], [-1, 0, 0], [1, 0, 0]]))
add(box("wall_low", "boards", [16, 1.5 - PL + 0.01, 8.4], [0, (1.5 + PL - 0.01) / 2, 0], ["bottom", "top"]))
add(box("wall_mid", "plaster", [16, WALL_TOP - 1.5 + 0.02, 8.4], [0, (WALL_TOP + 0.02 + 1.5) / 2, 0], ["bottom", "top"], decals=[
    {"id": "win_w", "face": "back", "material": "glass_win", "size": [2.0, 1.0], "at": [-5.4, 0.1]},
    {"id": "win_e", "face": "back", "material": "glass_win", "size": [2.0, 1.0], "at": [5.4, 0.1]},
    {"id": "win_back_w", "face": "front", "material": "glass_win", "size": [2.0, 1.0], "at": [4.4, 0.1]},
    {"id": "win_back_e", "face": "front", "material": "glass_win", "size": [2.0, 1.0], "at": [-4.4, 0.1]},
    {"id": "win_end_w", "face": "left", "material": "glass_win", "size": [1.6, 1.0], "at": [0, 0.1]},
    {"id": "win_end_e", "face": "right", "material": "glass_win", "size": [1.6, 1.0], "at": [0, 0.1]}]))
# the entrance: a frame of sliding glass doors with the two noren baked onto it
add(box("door_frame", "wood", [6.0, 2.46, 0.3], [0, PL - 0.01 + 1.23, -4.25], ["bottom"], faces={"back": "glass_door"},
        decals=[{"id": "noren_men", "face": "back", "material": "noren_blue", "size": [1.4, 1.85], "at": [-1.5, 0.28]},
                {"id": "noren_women", "face": "back", "material": "noren_red", "size": [1.4, 1.85], "at": [1.5, 0.28]}]))
# lower skirt roof (mokoshi), its fascia and its rafters
sk = [[-SO[0], SO[2], -SO[1]], [SO[0], SO[2], -SO[1]], [SO[0], SO[2], SO[1]], [-SO[0], SO[2], SO[1]],
      [-SI[0], SI[2], -SI[1]], [SI[0], SI[2], -SI[1]], [SI[0], SI[2], SI[1]], [-SI[0], SI[2], SI[1]]]
add(mesh("skirt", "tile", sk, [[0, 4, 5, 1], [1, 5, 6, 2], [2, 6, 7, 3], [3, 7, 4, 0]], ("away", [0, 0, 0])))
fz = 0.25
fas = [[x, y - fz, z] for x, y, z in sk[:4]] + sk[:4]
add(mesh("skirt_fascia", "dark", fas, [[0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]], ("away", [0, 0, 0])))
add(mesh("skirt_soffit", "rafters", fas[:4], [[0, 1, 2, 3]], [0, -1, 0]))
# upper storey
add(box("wall_up", "plaster", [12, UP_TOP - SI[2] + 0.1, 5.6], [0, (UP_TOP + SI[2] - 0.1) / 2, 0], ["bottom", "top"], decals=[
    {"id": "win_w", "face": "back", "material": "glass_up", "size": [1.5, 0.8], "at": [-5.0, 0.1]},
    {"id": "win_e", "face": "back", "material": "glass_up", "size": [1.5, 0.8], "at": [5.0, 0.1]},
    {"id": "win_back_w", "face": "front", "material": "glass_up", "size": [1.5, 0.8], "at": [3.0, 0.1]},
    {"id": "win_back_e", "face": "front", "material": "glass_up", "size": [1.5, 0.8], "at": [-3.0, 0.1]}]))
# main hip roof, ridge, onigawara and hip caps
L0 += main_roof()
add(box("ridge", "cap", [7.0, 0.3, 0.5], [0, RY + 0.05, 0], ["bottom"]))
for sx, nm in ((-1, "w"), (1, "e")):
    add(box("oni_" + nm, "cap", [0.5, 0.75, 0.6], [sx * 3.55, RY + 0.3, 0], ["bottom"]))
for sx in (-1, 1):
    for sz in (-1, 1):
        add(strip("hip_%s%s" % ("e" if sx > 0 else "w", "n" if sz > 0 else "s"), "cap",
                  [sx * RT, RY + 0.02, 0], [sx * RH[0], RE + 0.33, sz * RH[1]], 0.24, 0.12))
# karahafu over the entrance, its plaque (the hot-water mark) and lintel
L0 += karahafu(8)
add(quad("kara_plaque", "plaque", 0, YBASE + 1.2, ZF - 0.05, 1.3, 1.3, "-z"))
add(box("kara_lintel", "wood", [8.0, 0.3, 0.34], [0, YBASE, ZF + 0.12], ["top"]))
add(box("kara_ridge", "cap", [0.3, 0.16, math.hypot(ZB - ZF, YB - curve(0))],
        [0, (curve(0) + YB) / 2 + 0.09, (ZF + ZB) / 2], ["bottom"],
        rot=[-math.degrees(math.atan2(YB - curve(0), ZB - ZF)), 0, 0]))
for sx, nm in ((-1, "w"), (1, "e")):
    add(box("post_" + nm, "wood", [0.26, YBASE - 0.25, 0.26], [sx * 3.6, 0.28 + (YBASE - 0.25) / 2, -6.15], ["top", "bottom"]))
    add(cyl("chochin_" + nm, "chochin", 0.3, 0.6, 6, [sx * 3.0, YBASE - 0.55, -6.2], faces={"top": "dark", "bottom": "dark"}))
# boiler room
add(box("boiler", "boards", [AX1 - AX0, AY, AZ1 - AZ0], [(AX0 + AX1) / 2, AY / 2, (AZ0 + AZ1) / 2], ["bottom"], decals=[
    {"id": "door", "face": "back", "material": "door_dark", "size": [1.0, 2.0], "at": [0.4, -1.35]},
    {"id": "window", "face": "right", "material": "glass_win", "size": [1.2, 0.8], "at": [0.6, 0.6]}]))
add(box("boiler_roof", "cap", [AX1 - AX0 + 0.5, 0.22, AZ1 - AZ0 + 0.5], [(AX0 + AX1) / 2, 4.91, (AZ0 + AZ1) / 2], ["bottom"]))
L0 += chimney(0)
L0 += steam(2)
# street furniture: vending machine, potted pine, nobori, bicycles, bench
BX, BZ = -5.35, -5.3
add(vend())
add(cyl("pot", "pot", 0.42, 0.6, 6, [5.0, 0.3, -7.0], faces={"top": "dark"}))
add(sphere("pine", "leaf", 0.62, 6, 3, [5.0, 1.05, -7.0], [1.2, 0.8, 1.2]))
add(box("nobori_pole", "wood", [0.06, 3.4, 0.06], [-3.95, 1.7, -7.5], ["bottom"]))
add(quad("nobori", "nobori", -3.45, 1.95, -7.5, 0.9, 2.7, "-z"))
add({"id": "bike_a", "op": "group", "children": [quad("bike", "bike", 0, 0.5, 0, 2.0, 1.0, "-z")],
     "transform": {"translate": [6.6, 0, -5.4]}})
add({"id": "bike_b", "op": "group", "children": [quad("bike", "bike", 0, 0.5, 0, 2.0, 1.0, "-z")],
     "transform": {"rotate": [0, 38, 0], "translate": [4.3, 0, -5.9]}})
add(box("bench_seat", "wood", [1.7, 0.09, 0.5], [BX, 0.52, BZ]))
for sx, nm in ((-1, "w"), (1, "e")):
    add(box("bench_leg_" + nm, "wood", [0.1, 0.49, 0.38], [BX + sx * 0.7, 0.24, BZ], ["bottom", "top"]))
# the cat on the ridge
CX, CY = -1.0, RY + 0.2
add(sphere("cat_body", "cat", 0.38, 6, 3, [CX, CY + 0.3, 0], [1.0, 0.9, 1.2]))
add(sphere("cat_head", "cat", 0.25, 6, 3, [CX, CY + 0.78, -0.2]))
for sx, nm in ((-1, "w"), (1, "e")):
    add({"id": "cat_ear_" + nm, "op": "cone", "radius": 0.1, "height": 0.2, "segments": 3, "material": "dark",
         "transform": {"translate": [CX + sx * 0.13, CY + 1.08, -0.2], "rotate": [0, 0, -sx * 12]}})
add(box("cat_tail", "white", [0.1, 0.1, 0.7], [CX + 0.2, CY + 0.2, 0.62], rot=[60, 0, 18]))

# ------------------------------------------------------------------------------- level 1 (from 24 m)
L1 = [box("plinth", "stone", [17.8, PL, 9.4], [0, PL / 2, 0], ["bottom"]),
      box("walls", "plaster", [16, WALL_TOP - PL + 0.02, 8.4], [0, (WALL_TOP + PL) / 2, 0], ["bottom", "top"], decals=[
          {"id": "win_w", "face": "back", "material": "glass_win", "size": [2.0, 1.0], "at": [-5.4, 0.6]},
          {"id": "win_e", "face": "back", "material": "glass_win", "size": [2.0, 1.0], "at": [5.4, 0.6]}]),
      box("door_frame", "wood", [6.0, 2.46, 0.3], [0, PL - 0.01 + 1.23, -4.25], ["bottom", "front"], faces={"back": "glass_door"},
          decals=[{"id": "noren_men", "face": "back", "material": "noren_blue", "size": [1.4, 1.85], "at": [-1.5, 0.28]},
                  {"id": "noren_women", "face": "back", "material": "noren_red", "size": [1.4, 1.85], "at": [1.5, 0.28]}]),
      mesh("skirt", "tile", sk, [[0, 4, 5, 1], [1, 5, 6, 2], [2, 6, 7, 3], [3, 7, 4, 0]], ("away", [0, 0, 0])),
      box("wall_up", "plaster", [12, UP_TOP - SI[2] + 0.1, 5.6], [0, (UP_TOP + SI[2] - 0.1) / 2, 0], ["bottom", "top"]),
      box("ridge", "cap", [7.0, 0.3, 0.5], [0, RY + 0.05, 0], ["bottom"]),
      quad("kara_plaque", "plaque", 0, YBASE + 1.2, ZF - 0.05, 1.3, 1.3, "-z"),
      box("boiler", "boards", [AX1 - AX0, AY, AZ1 - AZ0], [(AX0 + AX1) / 2, AY / 2, (AZ0 + AZ1) / 2], ["bottom"]),
      box("boiler_roof", "cap", [AX1 - AX0 + 0.5, 0.22, AZ1 - AZ0 + 0.5], [(AX0 + AX1) / 2, 4.91, (AZ0 + AZ1) / 2], ["bottom"]),
      vend()]
L1 += main_roof()
L1 += [n for n in karahafu(4) if not n["id"].startswith("kara_side")]
L1 += chimney(1)
L1 += steam(1)

# ------------------------------------------------------------------------------- level 2 (from 60 m)
L2 = [box("body", "plaster", [16, UP_TOP, 8.4], [0, UP_TOP / 2, 0], ["bottom", "top"]),
      box("boiler", "boards", [AX1 - AX0, AY, AZ1 - AZ0], [(AX0 + AX1) / 2, AY / 2, (AZ0 + AZ1) / 2], ["bottom", "left"]),
      box("chimney", "brick", [CH_W, TOP, CH_W], [CH_X, TOP / 2, CH_Z], ["bottom", "top"],
          mods=[{"op": "taper", "top": CH_TAPER, "bottom": 1.0}])]
L2 += main_roof(fascia=False)


def farmats(nodes, mapping):
    for n in nodes:
        if n.get("material") in mapping:
            n["material"] = mapping[n["material"]]
        if "face_materials" in n:
            n["face_materials"] = [mapping.get(m, m) for m in n["face_materials"]]
        if "children" in n:
            farmats(n["children"], mapping)


farmats(L1, {"tile": "tile_far", "tile_k": "tile_far"})
farmats(L2, {"tile": "tile_far", "brick": "brick_far"})

for nodes in (L0, L1, L2):
    shift(nodes, *SHIFT)

recipe = {
    "format": "mei-asset", "version": 1, "name": "sento_front",
    "budget": {"triangles": 700},
    "sheets": {"s": {"image": "art/sento_sheet.png"}},
    "materials": M,
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": L0,
    "lod": {"levels": [{"distance": 24, "nodes": L1}, {"distance": 60, "nodes": L2}], "band": 2},
}

# ------------------------------------------------------------------------------- collision
C = [cuboid("plinth", -8.9, 8.9, 0, PL, -4.7, 4.7),
     cuboid("step", -3.55, 3.55, 0, 0.15, -7.8, -7.1),
     cuboid("porch", -3.6, 3.6, 0.1, 0.3, -7.15, -4.6),
     # ground storey under the skirt roof: a box out to the skirt's outer edge, then the skirt
     # itself as a frustum (17-21 degrees, walkable) up to the upper storey
     cuboid("ground_storey", -8.0, 8.0, 0.2, WALL_TOP, -4.2, 4.2),
     solid("skirt", [[sxx * SO[0], SO[2] - 0.25, szz * SO[1]] for sxx, szz in RING] +
           [[sxx * SO[0], SO[2], szz * SO[1]] for sxx, szz in RING] +
           [[sxx * SI[0], SI[2], szz * SI[1]] for sxx, szz in RING],
           [[0, 1, 2, 3], [8, 9, 10, 11]] + [[i, (i + 1) % 4, 4 + (i + 1) % 4, 4 + i] for i in range(4)] +
           [[4 + i, 4 + (i + 1) % 4, 8 + (i + 1) % 4, 8 + i] for i in range(4)]),
     cuboid("upper_storey", -SI[0], SI[0], SI[2] - 0.1, UP_TOP + 0.1, -SI[1], SI[1]),
     # main hip roof (21-22 degrees) from the eave's outline to the ridge
     solid("roof", [[-RH[0], RE, -RH[1]], [RH[0], RE, -RH[1]], [RH[0], RE, RH[1]], [-RH[0], RE, RH[1]],
                    [-RH[0], RE + 0.3, -RH[1]], [RH[0], RE + 0.3, -RH[1]], [RH[0], RE + 0.3, RH[1]], [-RH[0], RE + 0.3, RH[1]],
                    [-RT, RY + 0.2, 0], [RT, RY + 0.2, 0]],
           [[0, 1, 2, 3], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7], [4, 5, 9, 8], [6, 7, 8, 9],
            [7, 4, 8], [5, 6, 9]]),
     # karahafu: a ridge along the axis (the bell's crown) falling to its eaves, 18 degrees
     solid("karahafu", [[-HW, YBASE, ZF], [HW, YBASE, ZF], [HW, YBASE, ZB], [-HW, YBASE, ZB],
                        [-HW, curve(HW), ZF], [HW, curve(HW), ZF], [HW, YB - 0.4, ZB], [-HW, YB - 0.4, ZB],
                        [0, curve(0), ZF], [0, YB, ZB]],
           [[0, 1, 2, 3], [0, 1, 5, 8, 4], [3, 2, 6, 9, 7], [4, 8, 9], [4, 9, 7], [8, 5, 6], [8, 6, 9],
            [0, 3, 7, 4], [1, 2, 6, 5]]),
     cuboid("door_frame", -3.0, 3.0, 0.4, PL + 2.45, -4.4, -4.1),
     cuboid("post_w", -3.75, -3.45, 0.25, YBASE + 0.05, -6.3, -6.0),
     cuboid("post_e", 3.45, 3.75, 0.25, YBASE + 0.05, -6.3, -6.0),
     # boiler room (flat roof at 5.0: the ladder's foot) and the chimney (top 18.2)
     cuboid("boiler", AX0, AX1, 0, 5.02, AZ0, AZ1),
     frustum("chimney", (CH_W / 2, CH_W / 2, 4.9, CH_X, CH_Z), (chw(CH_Y1) / 2, chw(CH_Y1) / 2, CH_Y1, CH_X, CH_Z)),
     cuboid("chimney_cap", CH_X - 0.65, CH_X + 0.65, CH_Y1 - 0.1, TOP, CH_Z - 0.65, CH_Z + 0.65),
     cuboid("vend", -7.7, -6.7, 0, 1.96, -5.55, -4.75),
     cuboid("pot", -0.4 + 5.0, 0.4 + 5.0, 0, 0.6, -7.4, -6.6),
     cuboid("bench", BX - 0.85, BX + 0.85, 0, 0.565, BZ - 0.25, BZ + 0.25)]
shift(C, *SHIFT)
col = {"format": "mei-asset", "version": 1, "name": "sento_front_col",
       "materials": {"solid": {"color": "#ffffff", "palette": True}},
       "lighting": {"mode": "vertical", "ambient": 0.5},
       "verification": {"required": True, "depth": True, "perspective": True},
       "nodes": C}

# ------------------------------------------------------------------------------- views
sx, sz = SHIFT
P = lambda x, y, z: [round(x + sx, 2), y, round(z + sz, 2)]
cams = [
    {"name": "lane", "eye": P(34, 1.6, 6), "target": P(4, 6, 0)},
    {"name": "front", "eye": P(-4, 1.6, -18), "target": P(0, 3.5, -4)},
    {"name": "boiler_roof", "eye": P(10.4, AY + 0.2 + 1.6, -0.6), "target": P(CH_X, 12, CH_Z)},
    {"name": "chimney_top", "eye": P(CH_X - 0.3, TOP + 1.6, CH_Z - 0.3), "target": P(-6, 6, -30)},
    {"name": "roof_ridge", "eye": P(-6.0, RY + 1.6, -1.2), "target": P(CX, RY + 0.5, 0)},
    {"name": "far_40", "eye": P(30, 8, -30), "target": P(2, 6, 0)},
]
with open(os.path.join(HERE, "sento_front.asset.json"), "w") as fh:
    json.dump(recipe, fh, indent=1)
with open(os.path.join(HERE, "sento_front_col.asset.json"), "w") as fh:
    json.dump(col, fh, indent=1)
with open(os.path.join(HERE, "sento_front.cameras.json"), "w") as fh:
    json.dump(cams, fh, indent=1)
print("wrote sento_front, sento_front_col, sento_front.cameras.json")
