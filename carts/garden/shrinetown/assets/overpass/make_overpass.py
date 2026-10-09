#!/usr/bin/env python3
"""Writes shrine town's pedestrian overpass over the front road: art/overpass_sheet.png (+ .sheet.json),
overpass.asset.json and overpass_col.asset.json.

Adapted from the lab model (examples/assets/lab/overpass, 1,362 triangles, deck 5.2, 20 m) to
the grey box's plan (notes/town.md, 10): the deck at 7.0 over the road, 30 m long, and two
straight stairs that leave it at opposite ends and opposite sides (a Z in plan), 14.5 m each at
25.8 degrees, so the stairs are walkable slopes. Kept from the lab: the pale sea-green paint, the
cutout bar railings, the blue direction sign over the road (its texture resampled from 56 to 48
texels high, TEXTURES.md), the 交通安全 banner, the めい歩道橋 name
plates, the bicycle channel beside each stair, and the cat asleep on the deck. Dropped: the curve
mirror (the town has its own), the switchback stairs (each flight was a 40-point extrusion).

Coordinates: the deck runs along x (-15 to 15), 3 m wide (z -1.5 to 1.5), its walkway at 7.0.
The stair at +x leaves the deck's front (-Z) side and comes down to the ground at z -16; the
stair at -x leaves the back (+Z) side and lands at z +16. The front (-Z, the blue sign's side)
is the long face the east route sees as it comes along the front road from the spawn.
Placed at (262, 0, 111) with yaw 90 the deck runs north-south over the road (z 96-126), the
school stair comes down west to x 246 at z 96-99 and the cemetery stair east to x 278 at z
123-126, as the grey box's ramps do.

Routes: the walkway (7.0) and the stairs; the handrails at 8.1 along both sides of the deck and
stairs are rails to grind, and the railings' collision is a 0.2 m wall to stand on.

Levels: L1 from 24 m, L2 from 60 m (spec 8.2 for hero pieces), culled at 200 m.

Run: python3 carts/garden/shrinetown/assets/overpass/make_overpass.py   (needs Pillow)
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
LAB = os.path.join(REPO, "examples", "assets", "lab", "overpass", "art")
ART = os.path.join(HERE, "art")

DECK = 7.0           # walkway
GIRDER = 0.6         # deck depth: underside at 6.4 (6.4 m of headroom over the road)
HX = 15.0            # deck half length
HZ = 1.5             # deck half width
RAIL = 1.1           # railing height over the walk / tread
FOOT = 16.0          # the stairs reach the ground at z = -16 (front) and +16 (back)
SX0, SX1 = 12.0, 15.0  # the front stair's x range (the back one is mirrored through the origin)
SLOPE = DECK / (FOOT - HZ)   # 0.483, 25.8 degrees
STAIR_T = 0.4        # the stair slab's depth, measured vertically


SIGN_H = 48          # the sign's cell height: the lab's 56 resampled to 48 (TEXTURES.md, the east zone's cut)


def draw_art():
    """The lab's sheet (sign, plate, banner); the sign's cell, 128 x 56 there, resampled to
    128 x 48 (it saves 512 bytes of the town's texture budget)."""
    from PIL import Image
    os.makedirs(ART, exist_ok=True)
    sheet = Image.open(os.path.join(LAB, "sheet.png")).convert("RGBA")
    with open(os.path.join(LAB, "sheet.sheet.json")) as f:
        cells = json.load(f)
    x, y, w, h = cells["cells"]["sign"]
    sign = sheet.crop((x, y, x + w, y + h)).resize((w, SIGN_H), Image.LANCZOS)
    sheet.paste((0, 0, 0, 0), (x, y, x + w, y + h))
    sheet.paste(sign, (x, y))
    sheet.save(os.path.join(ART, "overpass_sheet.png"))
    cells["cells"]["sign"] = [x, y, w, SIGN_H]
    with open(os.path.join(ART, "overpass_sheet.sheet.json"), "w") as f:
        json.dump(cells, f, indent=1)
        f.write("\n")


# ---- helpers ---------------------------------------------------------------------------
def r4(v):
    return [round(a, 4) for a in v]


def box(id, size, pos, mat, open=None, faces=None, decals=None, rot=None):
    n = {"id": id, "op": "box", "size": r4(size), "material": mat,
         "transform": {"translate": r4(pos)}}
    if rot:
        n["transform"]["rotate"] = rot
    for k, v in (("open", open), ("faces", faces), ("decals", decals)):
        if v:
            n[k] = v
    return n


def solid(id, x0, x1, y0, y1, z0, z1, mat="solid", open=None):
    return box(id, [x1 - x0, y1 - y0, z1 - z0], [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2],
               mat, open=open)


def outward(verts, faces):
    """Turns each face so it winds outward from the solid's centre."""
    c = [sum(v[i] for v in verts) / len(verts) for i in range(3)]
    out = []
    for f in faces:
        a, b, d = (verts[f[0]], verts[f[1]], verts[f[2]])
        u = [b[i] - a[i] for i in range(3)]
        w = [d[i] - a[i] for i in range(3)]
        n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
        fc = [sum(verts[k][i] for k in f) / len(f) for i in range(3)]
        dot = sum(n[i] * (fc[i] - c[i]) for i in range(3))
        out.append(list(f) if dot > 0 else list(reversed(f)))
    return out


def prism(id, x0, x1, zy, mats, open_sides=()):
    """A prism across x from x0 to x1 whose side outline is the four (z, y) points zy (in order
    round the outline). mats: the material of each outline edge (edge k from point k to k+1),
    then the two caps (-x, +x). open_sides: edge indices or 'x0'/'x1' to leave out."""
    v = [[x0, y, z] for z, y in zy] + [[x1, y, z] for z, y in zy]
    faces, fm = [], []
    n = len(zy)
    for k in range(n):
        if k in open_sides:
            continue
        j = (k + 1) % n
        faces.append([k, j, n + j, n + k])
        fm.append(mats[k])
    if "x0" not in open_sides:
        faces.append(list(range(n)))
        fm.append(mats[n])
    if "x1" not in open_sides:
        faces.append([n + k for k in range(n)])
        fm.append(mats[n + 1])
    return {"id": id, "op": "mesh", "vertices": [r4(p) for p in v],
            "faces": outward(v, faces), "face_materials": fm}


def quad(id, mat, corners):
    return {"id": id, "op": "mesh", "material": mat, "vertices": [r4(c) for c in corners],
            "faces": [[0, 1, 2, 3]]}


def turn(n):
    """The node turned 180 degrees about the origin: the back stair from the front one."""
    n = json.loads(json.dumps(n))
    t = n.setdefault("transform", {})
    if "rotate" in t or "translate" in t:
        return {"id": n["id"] + "_b", "op": "group", "children": [n],
                "transform": {"rotate": [0, 180, 0]}}
    n["id"] += "_b"
    t["rotate"] = [0, 180, 0]
    return n


# ---- the parts -------------------------------------------------------------------------
def deck(detail=True):
    decals = None
    if detail:
        decals = [{"id": "plate_f", "face": "back", "material": "plate", "size": [0.9, 0.24],
                   "at": [8.0, 0.0]},
                  {"id": "plate_b", "face": "front", "material": "plate", "size": [0.9, 0.24],
                   "at": [8.0, 0.0]},
                  {"id": "banner", "face": "front", "material": "banner", "size": [2.0, 0.45],
                   "at": [0.0, 0.0]}]
    return box("deck", [2 * HX, GIRDER, 2 * HZ], [0, DECK - GIRDER / 2, 0], "fascia",
               faces={"top": "walk", "bottom": "under"}, decals=decals)


def stair_outline(top=DECK, t=STAIR_T):
    """(z, y) of the front stair's slab: the tread from the deck's edge down to the ground,
    the underside parallel to it, cut off level at the ground."""
    z_under_foot = -HZ - (top - t) / SLOPE
    return [(-HZ, top), (-FOOT, 0.0), (z_under_foot, 0.0), (-HZ, top - t)]


def stair():
    # edges: tread, foot (on the ground, open), underside, top end (against the deck, open)
    return prism("stair", SX0, SX1, stair_outline(),
                 ["tread", "under", "under", "under", "paint", "paint"], open_sides=(1, 3))


def bike_channel():
    """The bicycle channel: a narrow ramp beside the treads, 6 cm over them."""
    zy = [(-HZ - 0.05, DECK + 0.06), (-FOOT + 0.2, 0.06 + 0.2 * SLOPE),
          (-FOOT + 0.2, 0.2 * SLOPE - 0.04), (-HZ - 0.05, DECK - 0.04)]
    return prism("bike_ramp", SX1 - 0.32, SX1 - 0.1, zy, ["ramp"] * 6, open_sides=(1, 3))


def rails():
    """Bar railings (cutout, double-sided) and their handrails, the deck's and the front stair's."""
    n = []
    y0, y1 = DECK, DECK + RAIL
    # the deck's front side, open over the stair (x SX0..SX1); back side open over -SX1..-SX0
    n.append(quad("rail_front", "bars", [[-HX, y1, -HZ + 0.05], [SX0, y1, -HZ + 0.05],
                                         [SX0, y0, -HZ + 0.05], [-HX, y0, -HZ + 0.05]]))
    n.append(quad("rail_end", "bars", [[HX - 0.05, y1, -HZ], [HX - 0.05, y1, HZ],
                                       [HX - 0.05, y0, HZ], [HX - 0.05, y0, -HZ]]))
    # the stair's two sides, following the slope
    zt, zb = -HZ, -FOOT + 0.3
    yt, yb = DECK, DECK - SLOPE * (-zb - HZ)
    for x, nm in ((SX0 + 0.05, "in"), (SX1 - 0.05, "out")):
        n.append(quad(f"rail_stair_{nm}", "bars", [[x, yt + RAIL, zb], [x, yt + RAIL, zt],
                                                   [x, yt, zt], [x, yt, zb]]))
        n[-1]["vertices"] = r4s([[x, yb + RAIL, zb], [x, yt + RAIL, zt], [x, yt, zt], [x, yb, zb]])
    return n


def r4s(vs):
    return [r4(v) for v in vs]


def handrails():
    """Round handrails on the railings' tops: the grind rails."""
    y = DECK + RAIL + 0.02
    out = []

    def bar(id, a, b):
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        mid = [(a[i] + b[i]) / 2 for i in range(3)]
        # a cylinder along Y, turned to lie along a->b
        yaw = math.degrees(math.atan2(dx, dz))
        pitch = math.degrees(math.atan2(math.hypot(dx, dz), dy))
        return {"id": id, "op": "cylinder", "radius": 0.045, "height": round(length, 4),
                "segments": 4, "caps": False, "material": "paint",
                "transform": {"rotate": [round(pitch, 4), round(yaw, 4), 0], "translate": r4(mid)}}

    out.append(bar("hand_front", [-HX, y, -HZ + 0.05], [SX0, y, -HZ + 0.05]))
    out.append(bar("hand_end", [HX - 0.05, y, -HZ], [HX - 0.05, y, HZ]))
    zt, zb = -HZ, -FOOT + 0.3
    yb = DECK - SLOPE * (-zb - HZ) + RAIL + 0.02
    for x, nm in ((SX0 + 0.05, "in"), (SX1 - 0.05, "out")):
        out.append(bar(f"hand_stair_{nm}", [x, y, zt], [x, yb, zb]))
    return out


def piers(segments=6):
    n = []
    for x in (-10.0, 10.0):
        for z in (-0.9, 0.9):
            n.append({"id": f"pier_{'w' if x < 0 else 'e'}{'f' if z < 0 else 'b'}", "op": "cylinder",
                      "radius": 0.2, "height": DECK - GIRDER + 0.05, "segments": segments,
                      "caps": False, "material": "paint",
                      "transform": {"translate": [x, (DECK - GIRDER + 0.05) / 2, z]}})
    # one post under each stair's middle
    zm = -HZ - (DECK / 2) / SLOPE
    h = DECK / 2 - STAIR_T + 0.05
    n.append({"id": "stair_post", "op": "cylinder", "radius": 0.18, "height": round(h, 4),
              "segments": segments, "caps": False, "material": "paint",
              "transform": {"translate": r4([(SX0 + SX1) / 2, h / 2, zm])}})
    return n


def sign():
    """The blue direction sign on the deck's front, over the road, on two brackets."""
    z = -HZ - 0.2
    n = [box("sign", [4.0, 1.8, 0.06], [0, DECK - 0.35, z], "sign_back", faces={"back": "sign"})]
    for x in (-1.5, 1.5):
        n.append(box(f"bracket_{'l' if x < 0 else 'r'}", [0.1, 0.1, 0.2], [x, DECK - 0.95, -HZ - 0.08],
                     "sign_back"))
    return n


def cat():
    """Asleep on the walkway, curled toward the railing."""
    return {"id": "cat", "op": "group", "transform": {"rotate": [0, 20, 0], "translate": [-4.0, DECK - 0.02, -0.9]},
            "children": [
                {"id": "body", "op": "sphere", "radius": 1, "rings": 3, "segments": 6, "material": "cat",
                 "transform": {"scale": [0.13, 0.1, 0.19], "translate": [0, 0.09, 0]}},
                {"id": "head", "op": "sphere", "radius": 0.08, "rings": 3, "segments": 5, "material": "cat",
                 "transform": {"translate": [0, 0.15, -0.17]}},
                {"id": "ears", "op": "group", "modifiers": [{"op": "mirror", "axis": "x"}], "children": [
                    {"id": "ear", "op": "cone", "radius": 0.03, "height": 0.06, "segments": 3, "material": "cat",
                     "transform": {"rotate": [0, 0, -15], "translate": [0.045, 0.23, -0.17]}}]},
                {"id": "tail", "op": "box", "size": [0.035, 0.035, 0.24], "material": "cat_stripe",
                 "transform": {"rotate": [0, 35, 0], "translate": [0.1, 0.06, 0.12]}}]}


# ---- materials -------------------------------------------------------------------------
def cell(name):
    return {"color": "#ffffff", "texture": {"sheet": "art", "cell": name, "projection": "fit"}}


MATERIALS = {
    "paint": {"color": "#86b8c4", "palette": True},
    "under": {"color": "#5f8a96", "palette": True},
    "fascia": {"color": "#86b8c4", "texture": {
        "texels": ["2222222222222222", "2222222222222222", "1111111111111111", "1113111111131111",
                   "1111111111111111", "1111111111111111", "1111111111111111", "1111111111111111",
                   "1111111111111111", "1111111111111111", "1111111111111111", "1111111111111111",
                   "1113111111131111", "1111111111111111", "0000000000000000", "0000000000000000"],
        "colors": ["#5f8a96", "#86b8c4", "#a8d0da", "#6a96a2"], "projection": "box",
        "scale": [1.0, 0.6], "offset": [0, 0.5]}},
    "walk": {"color": "#6f8a6a", "tag": "floor", "texture": {
        "pattern": "speckle", "colors": ["#6f8a6a", "#5f7a5c", "#83a07c"], "params": {"density": 0.3},
        "projection": "box", "scale": [0.5, 0.5]}},
    # two steps a repeat: the green non-slip tread, a pale nosing, the riser's shadow
    "tread": {"color": "#6f8a6a", "tag": "stairs", "texture": {
        "texels": ["11111111", "00000000", "00000000", "02000200", "00000000", "00000000",
                   "00020002", "33333333", "11111111", "00000000", "00000000", "02000200",
                   "00000000", "00000000", "00020002", "33333333"],
        "colors": ["#6f8a6a", "#c8d0c0", "#5f7a5c", "#465a46"], "projection": "box",
        "scale": [1.0, 0.625]}},
    "ramp": {"color": "#9aa49a", "palette": True},
    "bars": {"color": "#86b8c4", "double_sided": True, "texture": {
        "texels": ["11000000"] * 8, "colors": ["#000000", "#86b8c4"], "clear": "#000000",
        "projection": "box", "scale": [0.2, 0.2]}},
    "sign": cell("sign"),
    "sign_back": {"color": "#8a9094", "palette": True},
    "plate": cell("plate"),
    "banner": cell("banner"),
    "cat": {"color": "#e39a4a", "palette": True},
    "cat_stripe": {"color": "#b8702e", "palette": True},
}
MATERIALS["sign"]["color"] = "#1f4f9c"
MATERIALS["plate"]["color"] = "#ece8d8"
MATERIALS["banner"]["color"] = "#f4f4ee"


def front_half():
    """What the front stair end has; the back end is the same turned 180 degrees."""
    return [stair(), bike_channel()] + rails() + handrails()


def level0():
    n = [deck()] + piers() + sign() + [cat()]
    half = front_half()
    n += half + [turn(p) for p in half]
    return n


def level1():
    stair1 = prism("stair", SX0, SX1, stair_outline(),
                   ["tread", "under", "under", "under", "paint", "paint"], open_sides=(1, 3))
    half = [stair1] + rails()
    n = [deck(False)] + half + [turn(p) for p in half]
    n += [box(f"pier_{i}", [0.4, DECK - GIRDER + 0.05, 2.2], [x, (DECK - GIRDER + 0.05) / 2, 0],
              "paint", open=["top", "bottom"]) for i, x in enumerate((-10.0, 10.0))]
    n.append(box("sign", [4.0, 1.8, 0.06], [0, DECK - 0.35, -HZ - 0.2], "sign_back", faces={"back": "sign"}))
    return n


def level2():
    st = prism("stair", SX0, SX1, stair_outline(DECK + RAIL, STAIR_T + RAIL),
               ["paint", "under", "under", "under", "paint", "paint"], open_sides=(1, 3))
    return [box("deck", [2 * HX, GIRDER + RAIL, 2 * HZ], [0, DECK - GIRDER + (GIRDER + RAIL) / 2, 0],
                "paint", faces={"bottom": "under"}), st, turn(st)]


def recipe():
    return {
        "format": "mei-asset", "version": 1, "name": "overpass",
        "budget": {"vertices": 600, "triangles": 600},
        "sheets": {"art": {"image": "art/overpass_sheet.png"}},
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "materials": MATERIALS,
        "nodes": level0(),
        "lod": {"levels": [{"distance": 24, "nodes": level1()},
                           {"distance": 60, "nodes": level2()}], "cull": 200, "band": 2},
    }


# ---- collision -------------------------------------------------------------------------
def collision():
    t = 0.2
    y0, y1 = DECK, DECK + RAIL
    half = [
        # the stair: a 25.8-degree slab, its underside 0.4 below
        prism("stair", SX0, SX1, stair_outline(), ["solid"] * 6, open_sides=(1, 3)),
        # its railings: walls 0.2 thick, 1.1 over the treads, standing on them
        prism("stair_wall_in", SX0 + 0.04, SX0 + 0.04 + t,
              [(-HZ - 0.02, y1), (-FOOT + 0.3, DECK - SLOPE * (FOOT - 0.3 - HZ) + RAIL),
               (-FOOT + 0.3, DECK - SLOPE * (FOOT - 0.3 - HZ) - 0.1), (-HZ - 0.02, y0 - 0.1)], ["solid"] * 6),
        prism("stair_wall_out", SX1 - 0.04 - t, SX1 - 0.04,
              [(-HZ - 0.02, y1), (-FOOT + 0.3, DECK - SLOPE * (FOOT - 0.3 - HZ) + RAIL),
               (-FOOT + 0.3, DECK - SLOPE * (FOOT - 0.3 - HZ) - 0.1), (-HZ - 0.02, y0 - 0.1)], ["solid"] * 6),
        # the deck's railings on this half: the front side up to the stair, and the end
        solid("wall_front", -HX + t, SX0, y0, y1, -HZ, -HZ + t, open=["bottom", "left"]),
        solid("wall_end", HX - t, HX, y0, y1, -HZ, HZ, open=["bottom"]),
        solid("pier", 9.8, 10.2, 0, DECK - GIRDER, -1.1, 1.1, open=["top", "bottom"]),
    ]
    # the deck in three pieces split where the stairs meet it (x = -SX0 and SX0), so that each
    # stair's top edge meets a deck edge of the same length (no T-junction for the World Checker)
    deck = [solid(f"deck_{k}", a, b, DECK - GIRDER, DECK, -HZ, HZ, open=o)
            for k, (a, b, o) in enumerate(((-HX, -SX0, ["right"]), (-SX0, SX0, ["left", "right"]),
                                           (SX0, HX, ["left"])))]
    n = deck + half + [turn(p) for p in half]
    # the sign hangs below the deck's edge: a wall a vehicle-height player can hit
    n.append(solid("sign", -2.0, 2.0, DECK - 1.25, DECK - GIRDER, -HZ - 0.25, -HZ))
    return {
        "format": "mei-asset", "version": 1, "name": "overpass_col",
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        # tag "metal": the footsteps' surface byte 8 (carts/garden/README.md, "Surfaces")
        "materials": {"solid": {"color": "#c8c4b8", "tag": "metal"}},
        "nodes": n,
    }


def write(name, data):
    with open(os.path.join(HERE, name), "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    draw_art()
    write("overpass.asset.json", recipe())
    write("overpass_col.asset.json", collision())
