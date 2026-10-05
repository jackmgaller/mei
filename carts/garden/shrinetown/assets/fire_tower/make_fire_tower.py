#!/usr/bin/env python3
"""Writes fire_tower.asset.json, fire_tower_col.asset.json, fire_tower.cameras.json and
art/tower_sheet.png (+ .sheet.json) beside this file: shrine town's fire lookout tower (火の見櫓)
in its yard in the back alleys (spec 3.3), cut from the lab model (examples/assets/lab/fire_tower,
1,296 triangles) to the town's density limits. Run once and commit the outputs (needs Pillow):
python3 carts/garden/shrinetown/assets/fire_tower/make_fire_tower.py

Asset frame: origin at the centre of the tower's four footings at the yard's ground, the ladder
on the -Z face (south at yaw 0, where the grey box's pole is), the hose shed on -X, the +X face
clear for the wall-kick pair with the storehouse to the east.

What the player uses (spec 3.3, 5 red coin 2, glide G4):
- The top: a low copper roof, 24 degrees in render and collision, its flat cap (0.6 m square) at
  TOP = 15.2: red coin 2 sits there, and G4 starts from it.
- The ladder is a pole: (0, 0, LAD_Z), 15.2 tall, running up outside the deck and the eave.
- The deck at DECK = 12.0, railed (rail top 12.9), a 0.65 m walk round the lookout cabin.
- The shaft's collision is a solid frustum (the lattice is not to be climbed through); its +X
  face leans 1.9 degrees, x = 1.45 at the ground and 1.07 under the deck: the kick wall.

The lattice (X braces, ring beams and the legs' outlines) is drawn on four cutout faces, one a
side, where the lab built it from 300 boxes; the legs stay as geometry over them."""
import json, math, os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "art")


def r(v):
    return [r(x) for x in v] if isinstance(v, (list, tuple)) else round(v, 4)


def sub(a, b): return [a[i] - b[i] for i in range(3)]
def dot(a, b): return sum(a[i] * b[i] for i in range(3))


def newell(pts):
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


def orient(verts, faces, outward):
    """Wind each face so its normal points along `outward`: a vector, ('away', point), or a
    list of vectors, one a face."""
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


def mesh(id_, mat, verts, faces, outward, mats=None):
    n = {"id": id_, "op": "mesh", "vertices": [r(v) for v in verts], "faces": orient(verts, faces, outward)}
    if mats:
        n["face_materials"] = mats
    else:
        n["material"] = mat
    return n


def box(id_, mat, size, at, open_=None, faces=None, decals=None, rot=None):
    n = {"id": id_, "op": "box", "size": r(list(size)), "material": mat, "transform": {"translate": r(list(at))}}
    if rot:
        n["transform"]["rotate"] = r(list(rot))
    if open_:
        n["open"] = list(open_)
    if faces:
        n["faces"] = faces
    if decals:
        n["decals"] = decals
    return n


def solid(id_, verts, faces):
    c = [sum(v[i] for v in verts) / len(verts) for i in range(3)]
    return mesh(id_, "solid", verts, faces, ("away", c))


def cuboid(id_, x0, x1, y0, y1, z0, z1):
    v = [[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1],
         [x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]]
    return solid(id_, v, [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]])


def frustum(id_, h0, y0, h1, y1):
    """A square frustum centred on the Y axis, half-widths h0 at y0 and h1 at y1."""
    v = []
    for h, y in ((h0, y0), (h1, y1)):
        v += [[-h, y, -h], [h, y, -h], [h, y, h], [-h, y, h]]
    return solid(id_, v, [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]])


# ------------------------------------------------------------------------------- dimensions
LEG_Y0, C0 = 0.42, 1.32          # leg centres: +-C0 at the footings' top (sunk 3 cm into them)
DECK = 12.0                      # the deck's top
C1 = 0.95                        # leg centres under the deck
LEG_W = 0.14                     # leg section
DECK_H = 1.6                     # the deck's half-width
RAIL = 0.9                       # railing height
CAB_H = 0.7                      # the lookout cabin's half-width
EAVE_Y, LIP_Y, TOP = 14.45, 14.6, 15.2
EAVE_H, CAP_H = 1.75, 0.3        # roof half-widths at the eave and at the flat cap
LAD_Z, LAD_W = -1.92, 0.44       # the ladder's plane and width
LAD_TOP = 15.75
RINGS = [0.9, 3.7, 6.5, 9.3]     # ring beams (drawn on the lattice faces); the deck is the fifth
SHED = (-4.3, -1.75, -0.55, 1.35, 2.3)   # x0, x1, z0, z1, wall height


def c_at(y):
    """Leg centre offset at height y."""
    return C0 + (C1 - C0) * (y - LEG_Y0) / (DECK - LEG_Y0)


# ------------------------------------------------------------------------------- textures
STEEL, STEEL_D = (138, 160, 150, 255), (88, 104, 98, 255)
RED, RED_D = (200, 64, 47, 255), (138, 40, 30, 255)
WOOD, WOOD_D = (92, 62, 44, 255), (58, 40, 30, 255)
PLASTER, PLASTER_D = (232, 226, 204, 255), (204, 196, 170, 255)
CLEAR = (0, 0, 0, 0)

BR_W, BR_H = 64, 240           # the lattice face texture
RAIL_W, RAIL_H = 64, 16
CAB_W, CAB_H_TX = 32, 64


def draw_braces():
    """One side of the shaft: the trapezoid between two legs' centre lines, from LEG_Y0 up to the
    deck, as `fit` maps it (its bounding rectangle, the top edge at v = 0)."""
    im = Image.new("RGBA", (BR_W, BR_H), CLEAR)
    d = ImageDraw.Draw(im)
    span = DECK - LEG_Y0

    def row(y):
        return (DECK - y) / span * (BR_H - 1)

    def half(y):
        return c_at(y) / C0 * (BR_W / 2)

    cx = BR_W / 2 - 0.5
    # X braces between ring beams (and from the last ring to the deck)
    levels = RINGS + [DECK - 0.05]
    for a, b in zip(levels, levels[1:]):
        ya, yb = row(a), row(b)
        d.line([(cx - half(a) + 1, ya), (cx + half(b) - 1, yb)], fill=STEEL_D, width=2)
        d.line([(cx + half(a) - 1, ya), (cx - half(b) + 1, yb)], fill=STEEL, width=2)
    # the legs' outlines, so the far levels keep their silhouette
    for s in (-1, 1):
        d.line([(cx + s * half(LEG_Y0), row(LEG_Y0)), (cx + s * half(DECK), row(DECK))], fill=STEEL, width=3)
    # ring beams, red with a shadowed underside
    for y in RINGS:
        y0 = row(y)
        for k, col in ((0, RED), (1, RED), (2, RED_D)):
            yy = int(round(y0)) + k - 1
            hw = half(y)
            d.line([(cx - hw + 1, yy), (cx + hw - 1, yy)], fill=col, width=1)
    return im


def draw_railing():
    im = Image.new("RGBA", (RAIL_W, RAIL_H), CLEAR)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, RAIL_W - 1, 1], fill=RED)
    d.rectangle([0, 2, RAIL_W - 1, 2], fill=RED_D)
    d.rectangle([0, 8, RAIL_W - 1, 8], fill=RED)
    d.rectangle([0, 14, RAIL_W - 1, 15], fill=RED_D)
    for x in list(range(0, RAIL_W, 16)) + [RAIL_W - 2]:
        d.rectangle([x, 0, x + 1, RAIL_H - 1], fill=RED)
    return im


def draw_cabin():
    """A side of the lookout cabin, CAB_H*2 wide and EAVE_Y - DECK tall: a plaster half wall, a
    lattice window band, an open band with the corner posts (the bell shows through), a beam."""
    im = Image.new("RGBA", (CAB_W, CAB_H_TX), CLEAR)
    d = ImageDraw.Draw(im)
    h = EAVE_Y - DECK

    def row(y):   # y above the deck
        return int(round((h - y) / h * CAB_H_TX))

    # half wall 0-0.62 m: plaster with a dark skirting
    d.rectangle([0, row(0.62), CAB_W - 1, CAB_H_TX - 1], fill=PLASTER)
    for k in range(0, CAB_W, 7):
        d.point((k + 2, row(0.4)), fill=PLASTER_D)
        d.point((k + 5, row(0.2)), fill=PLASTER_D)
    d.rectangle([0, CAB_H_TX - 2, CAB_W - 1, CAB_H_TX - 1], fill=WOOD_D)
    # window band 0.62-1.55: frame and lattice, its panes open
    y0, y1 = row(1.55), row(0.62)
    d.rectangle([0, y0, CAB_W - 1, y0 + 1], fill=WOOD)
    d.rectangle([0, y1 - 1, CAB_W - 1, y1], fill=WOOD_D)
    for x in range(0, CAB_W, 6):
        d.line([(x, y0), (x, y1)], fill=WOOD_D)
    for y in range(y0 + 6, y1 - 2, 6):
        d.line([(0, y), (CAB_W - 1, y)], fill=WOOD_D)
    # corner posts all the way, and the beam under the roof
    d.rectangle([0, 0, 1, CAB_H_TX - 1], fill=WOOD_D)
    d.rectangle([CAB_W - 2, 0, CAB_W - 1, CAB_H_TX - 1], fill=WOOD_D)
    d.rectangle([0, 0, CAB_W - 1, row(2.2)], fill=WOOD)
    d.line([(0, row(2.2)), (CAB_W - 1, row(2.2))], fill=WOOD_D)
    return im


def draw_ladder_far():
    """The ladder as one face for the coarse levels: two rails and rungs, open between."""
    im = Image.new("RGBA", (8, 64), CLEAR)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 0, 63], fill=RED)
    d.rectangle([7, 0, 7, 63], fill=RED)
    for y in range(0, 64, 4):
        d.line([(0, y), (7, y)], fill=RED_D)
    return im


def write_sheet():
    cells = {"braces": draw_braces(), "railing": draw_railing(), "cabin": draw_cabin(),
             "ladder": draw_ladder_far()}
    W = BR_W + CAB_W + RAIL_W
    sheet = Image.new("RGBA", (W, BR_H), CLEAR)
    layout, x = {}, 0
    for name in ("braces", "cabin"):
        im = cells[name]
        sheet.paste(im, (x, 0))
        layout[name] = [x, 0, im.width, im.height]
        x += im.width
    sheet.paste(cells["railing"], (x, 0))
    layout["railing"] = [x, 0, RAIL_W, RAIL_H]
    sheet.paste(cells["ladder"], (x, RAIL_H))
    layout["ladder"] = [x, RAIL_H, 8, 64]
    sheet.save(os.path.join(ART, "tower_sheet.png"))
    with open(os.path.join(ART, "tower_sheet.sheet.json"), "w") as fh:
        json.dump({"format": "mei-sheet", "version": 1, "cells": layout}, fh, indent=1)


# ------------------------------------------------------------------------------- materials
def cell(name, bits=4):
    return {"sheet": "tower", "cell": name, "bits": bits, "projection": "fit"}


M = {
    "lattice": {"color": "#8aa096", "double_sided": True, "texture": cell("braces")},
    "railing": {"color": "#c8402f", "double_sided": True, "texture": cell("railing")},
    "cabin": {"color": "#e8e2cc", "double_sided": True, "texture": cell("cabin")},
    "rungs": {"color": "#c8402f", "double_sided": True, "texture": {
        "sheet": "tower", "cell": "ladder", "projection": "planar", "axis": "z",
        "scale": [LAD_W, 4.0], "offset": [0.5, 0]}},
    "copper": {"color": "#4f8f78", "tag": "roof", "texture": {
        "pattern": "brick", "colors": ["#58a085", "#2e5e4e", "#4a8870"],
        "params": {"courses": 4, "bricks": 4, "bond": 0.5}, "projection": "box", "scale": [0.5, 0.5]}},
    "deck": {"color": "#8b6a47", "tag": "floor", "texture": {
        "pattern": "planks", "colors": ["#8b6a47", "#4e3822", "#7d5d3d", "#9a7852"],
        "params": {"boards": 4}, "projection": "box", "scale": [1, 1]}},
    "concrete": {"color": "#a8a59c", "texture": {
        "pattern": "speckle", "colors": ["#a9a69d", "#8f8c84", "#bdbab0"], "params": {"density": 0.2},
        "projection": "box", "scale": [1, 1]}},
    "kawara": {"color": "#565c64", "tag": "roof", "texture": {
        "sheet": "town_common", "cell": "kawara", "projection": "box", "scale": [2, 2]}},
    "plaster": {"color": "#e0d6bc", "tag": "wall", "texture": {
        "sheet": "town_common", "cell": "plaster", "projection": "box", "scale": [2, 2]}},
    "shutter": {"color": "#7d8c96", "texture": {
        "pattern": "stripes", "colors": ["#8696a0", "#6d7c86"], "params": {"count": 8, "axis": "v"},
        "projection": "fit"}},
    "board_art": {"color": "#f4f0e2", "texture": {"image": "art/hinoyojin.png", "bits": 8, "projection": "fit"}},
    "banner": {"color": "#f4f0e2", "double_sided": True,
               "texture": {"image": "art/bouka.png", "bits": 8, "projection": "fit"}},
    "shed_sign": {"color": "#be2822", "texture": {"image": "art/shed_sign.png", "bits": 8, "projection": "fit"}},
}
# palette-backed colours (6 surface)
for name, col in {"steel": "#8aa096", "red": "#c8402f", "dark": "#33383c", "bronze": "#c0903c",
                  "horn": "#aeb4ba", "wood": "#5a3e2c"}.items():
    M[name] = {"color": col, "palette": True}


# ------------------------------------------------------------------------------- parts
def legs():
    out = []
    hw = LEG_W / 2
    for k, (sx, sz) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1))):
        v = []
        for y, c in ((LEG_Y0 - 0.03, C0), (DECK - 0.02, C1)):
            cx, cz = sx * c, sz * c
            v += [[cx - hw, y, cz - hw], [cx + hw, y, cz - hw], [cx + hw, y, cz + hw], [cx - hw, y, cz + hw]]
        c = [sx * (C0 + C1) / 2, DECK / 2, sz * (C0 + C1) / 2]
        out.append(mesh("leg_%d" % k, "steel", v, [[0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]],
                        ("away", c)))
    return out


def lattice(y0=LEG_Y0, y1=DECK - 0.02):
    """Four trapezoids through the legs' centre lines, one material, `fit` each."""
    a, b = c_at(y0), c_at(y1)
    v = [[-a, y0, -a], [a, y0, -a], [a, y0, a], [-a, y0, a],
         [-b, y1, -b], [b, y1, -b], [b, y1, b], [-b, y1, b]]
    return mesh("lattice", "lattice", v, [[0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]],
                ("away", [0, DECK / 2, 0]))


def footings():
    return [box("foot_%d" % k, "concrete", [0.5, 0.45, 0.5], [sx * C0, 0.225, sz * C0], ["bottom"])
            for k, (sx, sz) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1)))]


def deck():
    return box("deck", "deck", [2 * DECK_H, 0.15, 2 * DECK_H], [0, DECK - 0.075, 0])


def railing():
    return box("railing", "railing", [2 * DECK_H - 0.16, RAIL, 2 * DECK_H - 0.16], [0, DECK + RAIL / 2 - 0.01, 0],
               ["top", "bottom"])


def cabin():
    return box("cabin", "cabin", [2 * CAB_H, EAVE_Y - DECK + 0.02, 2 * CAB_H], [0, (EAVE_Y + DECK) / 2, 0],
               ["top", "bottom"])


def roof(lip=True):
    e, c = EAVE_H, CAP_H
    if lip:
        v = [[-e, EAVE_Y, -e], [e, EAVE_Y, -e], [e, EAVE_Y, e], [-e, EAVE_Y, e],
             [-e, LIP_Y, -e], [e, LIP_Y, -e], [e, LIP_Y, e], [-e, LIP_Y, e],
             [-c, TOP, -c], [c, TOP, -c], [c, TOP, c], [-c, TOP, c]]
        f = [[0, 1, 2, 3], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7],
             [4, 5, 9, 8], [5, 6, 10, 9], [6, 7, 11, 10], [7, 4, 8, 11], [8, 9, 10, 11]]
        mats = ["wood", "red", "red", "red", "red", "copper", "copper", "copper", "copper", "copper"]
    else:
        v = [[-e, LIP_Y, -e], [e, LIP_Y, -e], [e, LIP_Y, e], [-e, LIP_Y, e],
             [-c, TOP, -c], [c, TOP, -c], [c, TOP, c], [-c, TOP, c]]
        f = [[0, 1, 2, 3], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7], [4, 5, 6, 7]]
        mats = ["wood", "copper", "copper", "copper", "copper", "copper"]
    return mesh("roof", None, v, f, ("away", [0, (EAVE_Y + TOP) / 2, 0]), mats)


def bell():
    return [{"id": "bell", "op": "lathe", "material": "bronze", "segments": 6,
             "profile": [[0.2, 0.0], [0.19, 0.06], [0.13, 0.26], [0.07, 0.36], [0.0, 0.4]],
             "transform": {"translate": [0, 13.55, 0]}},
            box("bell_hanger", "dark", [0.03, EAVE_Y - 13.9, 0.03], [0, (EAVE_Y + 13.9) / 2 + 0.01, 0],
                ["top", "bottom"])]


def horns():
    out = []
    for k, yaw in enumerate((-35, 35)):
        a = math.radians(yaw)
        x, z = math.sin(a) * (CAB_H + 0.12), -math.cos(a) * (CAB_H + 0.12)
        out.append({"id": "horn_%d" % k, "op": "cone", "material": "horn", "radius": 0.15, "height": 0.34,
                    "segments": 5, "transform": {"rotate": [90, yaw, 0], "translate": r([x, 14.15, z])}})
    return out


def ladder():
    out = []
    for k, x in enumerate((-LAD_W / 2, LAD_W / 2)):
        out.append(box("lad_rail_%d" % k, "red", [0.05, LAD_TOP, 0.05], [x, LAD_TOP / 2, LAD_Z], ["bottom"]))
    out.append(ladder_far())
    # stays from the ladder back to the lattice at three ring beams, and to the deck
    for k, y in enumerate(RINGS[1:]):
        z1 = -c_at(y) + 0.02
        out.append(box("stay_%d" % k, "red", [LAD_W + 0.16, 0.05, z1 - LAD_Z + 0.04],
                       [0, y, (LAD_Z + z1) / 2 - 0.0], ["front", "back"]))
    return out


def ladder_far():
    z = LAD_Z + 0.06
    return mesh("ladder", "rungs", [[-LAD_W / 2, 0, z], [LAD_W / 2, 0, z],
                                     [LAD_W / 2, LAD_TOP, z], [-LAD_W / 2, LAD_TOP, z]],
                [[0, 1, 2, 3]], [0, 0, -1])


def struts():
    """Diagonal struts from the legs out to the deck's corners."""
    out = []
    for k, (sx, sz) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1))):
        y0 = DECK - 1.4
        c0 = c_at(y0)
        a = [sx * c0, y0, sz * c0]
        b = [sx * (DECK_H - 0.12), DECK - 0.16, sz * (DECK_H - 0.12)]
        L = math.dist(a, b)
        mid = [(a[i] + b[i]) / 2 for i in range(3)]
        horiz = math.hypot(b[0] - a[0], b[2] - a[2])
        pitch = math.degrees(math.atan2(b[1] - a[1], horiz))
        yaw = math.degrees(math.atan2(b[0] - a[0], b[2] - a[2]))
        # a thin box along +Z, pitched up (X first), then turned to the diagonal
        out.append(box("strut_%d" % k, "steel", [0.07, 0.07, L], mid, ["front", "back"],
                       rot=[-pitch, yaw, 0]))
    return out


def signboard():
    z = -c_at(1.2) - 0.16
    return [box("board", "steel", [1.5, 0.5, 0.05], [0, 1.25, z], faces={"back": "board_art"}),
            box("board_post_0", "steel", [0.05, 1.0, 0.04], [-0.6, 0.5, z + 0.045], ["top", "bottom"]),
            box("board_post_1", "steel", [0.05, 1.0, 0.04], [0.6, 0.5, z + 0.045], ["top", "bottom"])]


def banner():
    z = -DECK_H - 0.02
    return mesh("banner", "banner", [[0.2, DECK + 0.12, z], [0.8, DECK + 0.12, z], [0.8, DECK + 0.87, z],
                                     [0.2, DECK + 0.87, z]], [[0, 1, 2, 3]], [0, 0, -1])


def shed(detail=True):
    x0, x1, z0, z1, h = SHED
    cx, cz, w, d = (x0 + x1) / 2, (z0 + z1) / 2, x1 - x0, z1 - z0
    decals = None
    if detail:
        decals = [{"id": "shutter", "face": "back", "material": "shutter", "size": [1.6, 1.75], "at": [0, -0.25]},
                  {"id": "sign", "face": "back", "material": "shed_sign", "size": [1.2, 0.3], "at": [0, 0.88]}]
    out = [box("shed", "plaster", [w, h, d], [cx, h / 2, cz], ["bottom"], decals=decals)]
    # the gable roof: a prism along X with eaves, kawara on its slopes, plaster gable ends
    ov = 0.22
    out.append({"id": "shed_roof", "op": "extrude", "material": "kawara", "depth": w + 0.3,
                "points": r([[-d / 2 - ov, -0.1], [d / 2 + ov, -0.1], [0, 0.62]]),
                "faces": {"front": "plaster", "back": "plaster"},
                "transform": {"rotate": [0, 90, 0], "translate": r([cx, h, cz])}})
    return out


# ------------------------------------------------------------------------------- levels
L0 = (footings() + legs() + [lattice(), deck(), railing(), cabin(), roof(), banner()] + bell() + horns()
      + ladder() + struts() + signboard() + shed())

L1 = (legs() + [lattice(), deck(), railing(), cabin(), roof(False), banner(), ladder_far()] + shed(False))

L2 = [lattice(), box("deck", "deck", [2 * DECK_H, 0.15, 2 * DECK_H], [0, DECK - 0.075, 0], ["bottom"]),
      cabin(), roof(False)]

recipe = {
    "format": "mei-asset", "version": 1, "name": "fire_tower",
    "budget": {"triangles": 600},
    "sheets": {"tower": {"image": "art/tower_sheet.png"},
               "town_common": {"image": "../town_alley_house_a/art/town_common.png"}},
    "materials": M,
    "lighting": {"mode": "vertical", "ambient": 0.5},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": L0,
    "lod": {"levels": [{"distance": 24, "nodes": L1}, {"distance": 60, "nodes": L2}], "band": 2},
}

# ------------------------------------------------------------------------------- collision
RAIL_T = 0.25
H_IN = DECK_H - RAIL_T
C = [
    # the shaft: legs and lattice as one solid; its sides lean 1.9 degrees (the kick walls)
    frustum("shaft", C0 + LEG_W / 2 + 0.06, 0, C1 + LEG_W / 2 + 0.05, DECK - 0.19),
    cuboid("deck", -DECK_H, DECK_H, DECK - 0.2, DECK, -DECK_H, DECK_H),
    # the railing: four walls 0.25 thick, top 12.9
    cuboid("rail_s", -DECK_H + 0.02, DECK_H - 0.02, DECK - 0.01, DECK + RAIL, -DECK_H + 0.01, -H_IN),
    cuboid("rail_n", -DECK_H + 0.02, DECK_H - 0.02, DECK - 0.01, DECK + RAIL, H_IN, DECK_H - 0.01),
    cuboid("rail_w", -DECK_H + 0.01, -H_IN, DECK - 0.02, DECK + RAIL - 0.01, -H_IN - 0.01, H_IN + 0.01),
    cuboid("rail_e", H_IN, DECK_H - 0.01, DECK - 0.02, DECK + RAIL - 0.01, -H_IN - 0.01, H_IN + 0.01),
    cuboid("cabin", -CAB_H, CAB_H, DECK - 0.01, EAVE_Y + 0.01, -CAB_H, CAB_H),
    # the roof: eave slab and four 24-degree planes up to the flat cap at TOP
    solid("roof", [[-EAVE_H, EAVE_Y, -EAVE_H], [EAVE_H, EAVE_Y, -EAVE_H], [EAVE_H, EAVE_Y, EAVE_H], [-EAVE_H, EAVE_Y, EAVE_H],
                   [-EAVE_H, LIP_Y, -EAVE_H], [EAVE_H, LIP_Y, -EAVE_H], [EAVE_H, LIP_Y, EAVE_H], [-EAVE_H, LIP_Y, EAVE_H],
                   [-CAP_H, TOP, -CAP_H], [CAP_H, TOP, -CAP_H], [CAP_H, TOP, CAP_H], [-CAP_H, TOP, CAP_H]],
          [[0, 1, 2, 3], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7],
           [4, 5, 9, 8], [5, 6, 10, 9], [6, 7, 11, 10], [7, 4, 8, 11], [8, 9, 10, 11]]),
    cuboid("shed", SHED[0], SHED[1], 0, SHED[4] + 0.01, SHED[2], SHED[3]),
    solid("shed_roof", [[SHED[0] - 0.15, SHED[4], SHED[2] - 0.2], [SHED[1] + 0.15, SHED[4], SHED[2] - 0.2],
                        [SHED[1] + 0.15, SHED[4], SHED[3] + 0.2], [SHED[0] - 0.15, SHED[4], SHED[3] + 0.2],
                        [SHED[0] - 0.15, SHED[4] + 0.5, (SHED[2] + SHED[3]) / 2],
                        [SHED[1] + 0.15, SHED[4] + 0.5, (SHED[2] + SHED[3]) / 2]],
          [[0, 1, 2, 3], [0, 1, 5, 4], [3, 2, 5, 4], [0, 4, 3], [1, 5, 2]]),
]
col = {"format": "mei-asset", "version": 1, "name": "fire_tower_col",
       "materials": {"solid": {"color": "#ffffff", "palette": True}},
       "lighting": {"mode": "vertical", "ambient": 0.5},
       "verification": {"required": True, "depth": True, "perspective": True},
       "nodes": C}

cams = [
    {"name": "yard", "eye": [-2.5, 1.6, -9.0], "target": [0, 6.0, 0]},
    {"name": "alley_far", "eye": [6.0, 1.6, -22.0], "target": [0, 8.0, 0]},
    {"name": "kura_roof", "eye": [5.6, 9.6, -1.5], "target": [0.6, 12.5, 0]},
    {"name": "on_deck", "eye": [-1.15, DECK + 1.5, -1.15], "target": [1.2, DECK + 1.6, 1.2]},
    {"name": "on_top", "eye": [0, TOP + 1.5, -1.0], "target": [0, TOP - 2, 8.0]},
    {"name": "ladder_climb", "eye": [0.6, 13.0, -3.6], "target": [0, 14.2, -1.6]},
    {"name": "danchi_roof", "eye": [-24, 20.4, -40], "target": [0, 9, 0]},
]

if __name__ == "__main__":
    os.makedirs(ART, exist_ok=True)
    write_sheet()
    for name, data in (("fire_tower.asset.json", recipe), ("fire_tower_col.asset.json", col),
                       ("fire_tower.cameras.json", cams)):
        with open(os.path.join(HERE, name), "w") as fh:
            json.dump(data, fh, indent=1)
            fh.write("\n")
    print("wrote fire_tower, fire_tower_col, fire_tower.cameras.json, art/tower_sheet.png")
