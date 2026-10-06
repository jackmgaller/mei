#!/usr/bin/env python3
"""Writes shrine town's record shop (ほしやレコード): art/recordshop_sheet.png (+ .sheet.json),
recordshop.asset.json and recordshop_col.asset.json.

Adapted from the lab model (examples/assets/lab/recordshop, 5.1 x 4.4 m, 656 triangles), whose
sheet it reads. Widened to the shotengai's shop plot: origin at the centre of a 9 x 14 m
footprint at street level, front (the street) toward -Z, as town_shop_2f_a. Kept: the cream
tile parapet and brown tile pilasters, the navy kanban, the green awning with its scalloped
valance, the glass front full of records with the idol and LIVE posters, the red sode sign, the
cassette billboard on the roof, the prefab room upstairs with the cat in its window, the
laundry, the bargain bin, the chalk board and the gachapon.

The cut: the shelves, mullions, door and kick plates are painted into one glass texture
(the lab modelled each); posters and the door's price card are decals; the billboard's struts
are two posts, the laundry and the bin's legs cutout cards; speaker and LP-by-LP bin dropped.

Routes: awning (3.3 at the wall, 20 degrees) -> roof terrace (5.0, behind a 0.9 m rail) ->
upstairs room's roof (7.3, flat) -> the neighbours' 6.5 roofs over the 1 m gaps.

Run: python3 carts/garden/shrinetown/assets/recordshop/make_recordshop.py   (needs Pillow)
"""
import json
import os

from PIL import Image, ImageColor, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
LABDIR = os.path.join(REPO, "examples", "assets", "lab", "recordshop")
LAB = os.path.join(LABDIR, "art", "recordshop_sheet.png")
LAB_CELLS = json.load(open(LAB.replace(".png", ".sheet.json")))["cells"]
LAB_MATERIALS = json.load(open(os.path.join(LABDIR, "recordshop.asset.json")))["materials"]

# ---- dimensions (metres) ---------------------------------------------------------------
HX = 4.5            # half width (9 m wall in a 10 m plot)
ZF, ZB = -7.0, 7.0  # front (street) and back (service lane) walls
G = 3.2             # top of the shop front opening; the tile band above
T = 5.0             # roof terrace floor
ZH = 1.0            # front wall of the upstairs room
H = 7.2             # upstairs room's walls; its roof slab tops out at 7.3
ROOF = 7.3
GX = 3.6            # the glass front spans -GX..GX, recessed
ZG = -6.65          # the glass plane
TPM = 20            # texels a metre on the glass front

# ---- art -------------------------------------------------------------------------------
NAVY, NAVY_D = "#1c2860", "#141c44"
SHELF = "#6a4a30"
AL, AL_D = "#c4c8cc", "#7a8088"
SLEEVES = ["#e84a8c", "#f4d23c", "#3cb4e6", "#f4f2e8", "#e85a2a", "#64c864", "#c84a3a"]
BROWN = ["#8e5434", "#5a3420", "#9c6040"]


def lab(src, name):
    x, y, w, h = LAB_CELLS[name]
    return src.crop((x, y, x + w, y + h))


def hsh(a, b, s=0):
    v = (a * 374761393 + b * 668265263 + s * 2246822519) & 0xFFFFFFFF
    v = ((v ^ (v >> 13)) * 1274126177) & 0xFFFFFFFF
    return (v ^ (v >> 16)) & 0xFF


def m2t(v):
    return int(round(v * TPM))


def draw_glass():
    """144 x 64: the recessed front, 7.2 x 3.2 m. Shutter case, transom, two windows of record
    shelves either side of a glass door, brown tile kick plates. Posters go on as decals."""
    w, h = m2t(2 * GX), m2t(G)
    img = Image.new("RGBA", (w, h), NAVY)
    d = ImageDraw.Draw(img)
    # shutter case and transom (top 0.45 m)
    for y in range(0, m2t(0.3)):
        d.line([0, y, w - 1, y], fill=AL if y % 2 == 0 else AL_D)
    d.rectangle([0, m2t(0.3), w - 1, m2t(0.45) - 1], fill=NAVY_D)
    win_top, win_bot = m2t(0.45), h - m2t(0.45)          # window glass y range
    door0, door1 = m2t(GX - 0.7), m2t(GX + 0.7)          # door x range
    # record shelves in both windows
    for x0, x1 in ((0, door0), (door1, w)):
        y = win_top + 3
        row = 0
        while y + 8 < win_bot:
            d.line([x0, y + 8, x1 - 1, y + 8], fill=SHELF)
            x = x0 + 2 + (row * 3) % 4
            k = row * 7
            while x + 3 < x1 - 1:
                c = SLEEVES[hsh(x, row, 3) % len(SLEEVES)]
                sw = 3 + hsh(x, row, 5) % 2
                d.rectangle([x, y + 1, x + sw - 1, y + 7], fill=c)
                if hsh(x, row, 9) % 3 == 0:
                    d.point((x + 1, y + 3), fill=NAVY_D)
                x += sw + 1
                k += 1
            y += 10
            row += 1
        # kick plate of brown tile below the window
        for yy in range(win_bot, h):
            for xx in range(x0, x1):
                c = BROWN[0] if ((xx // 3) + (yy // 3)) % 2 == 0 else BROWN[2]
                if xx % 3 == 2 or yy % 3 == 2:
                    c = BROWN[1]
                img.putpixel((xx, yy), ImageColor.getrgb(c) + (255,))
    # the door: dark glass, push bar, a reflection
    d.rectangle([door0, win_top, door1 - 1, h - 1], fill="#3a5070")
    d.line([door0 + 3, m2t(1.95), door1 - 4, m2t(1.95)], fill=AL)
    for i in range(6):
        d.point((door0 + 4 + i, win_top + 14 - i), fill="#6a86a6")
    # frames: outer, door posts, window sills and heads
    for x in (0, door0 - 1, door0, door1 - 1, door1, w - 1):
        d.line([x, m2t(0.3), x, h - 1], fill=AL)
    d.line([0, win_top, w - 1, win_top], fill=AL)
    d.line([0, win_bot, door0, win_bot], fill=AL)
    d.line([door1, win_bot, w - 1, win_bot], fill=AL)
    # reflection streaks on the windows
    for x0 in (m2t(0.5), m2t(GX + 1.4)):
        for i in range(10):
            d.point((x0 + i, win_top + 20 - i), fill="#8aa0c0")
            d.point((x0 + i + 3, win_top + 20 - i), fill="#5a6c96")
    return img


def draw_kanban(src):
    """176 x 32: the lab's kanban (128 x 32) centred on a wider board, its navy and its stripes
    carried out to both ends."""
    cell = lab(src, "kanban")
    img = Image.new("RGBA", (176, 32))
    edge = cell.crop((2, 0, 3, 32))
    for x in range(176):
        img.paste(edge, (x, 0))
    img.paste(cell, (24, 0))
    return img


def draw_valance():
    """16 x 8 tile: two green and two white stripes, a scalloped hem (holes)."""
    img = Image.new("RGBA", (16, 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(4):
        c = "#2e8c5a" if i % 2 == 0 else "#f4f2e8"
        d.rectangle([i * 4, 0, i * 4 + 3, 5], fill=c)
        d.rectangle([i * 4 + 1, 6, i * 4 + 2, 6], fill=c)
    d.line([0, 0, 15, 0], fill="#1e6a42")
    return img


def draw_railing():
    """64 x 8: an aluminium rail, top bar and posts, holes between."""
    img = Image.new("RGBA", (64, 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 63, 0], fill=AL)
    d.rectangle([0, 1, 63, 1], fill=AL_D)
    d.line([0, 5, 63, 5], fill=AL_D)
    for x in range(0, 64, 8):
        d.line([x, 0, x, 7], fill=AL)
    d.line([63, 0, 63, 7], fill=AL)
    return img


def draw_laundry():
    """48 x 32: the drying stand, its aqua pole, a pink towel and a white shirt."""
    img = Image.new("RGBA", (48, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for x in (2, 45):
        d.line([x, 1, x, 31], fill="#8c9096")
        d.line([x - 2, 31, x + 2, 31], fill="#8c9096")
    d.line([0, 1, 47, 1], fill="#5ab4c8")
    d.rectangle([8, 2, 17, 15], fill="#f08cb0")
    d.line([8, 15, 17, 15], fill="#c86a90")
    d.polygon([(26, 2), (32, 2), (36, 5), (34, 8), (32, 7), (32, 15), (26, 15), (26, 7),
               (24, 8), (22, 5)], fill="#f6f6f2")
    d.line([29, 2, 29, 4], fill="#c8ccd0")
    d.rectangle([38, 2, 41, 9], fill="#3c6ab0")
    return img


def draw_gacha():
    """16 x 40: a gachapon machine's front: red lid, clear globe of capsules, red base."""
    img = Image.new("RGBA", (16, 40), "#d8302c")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 15, 2], fill="#a82018")
    d.rectangle([1, 4, 14, 19], fill="#dfe8ee")
    caps = ["#f05a8c", "#f6d23c", "#3cb4e6", "#64c864", "#f4f2e8"]
    for i, (cx, cy) in enumerate([(3, 15), (7, 16), (11, 15), (5, 12), (9, 12), (12, 10),
                                  (3, 8), (7, 9), (10, 6)]):
        d.rectangle([cx - 1, cy - 1, cx + 1, cy + 1], fill=caps[i % len(caps)])
    d.line([2, 5, 2, 8], fill="#ffffff")
    d.rectangle([3, 22, 12, 26], fill="#f4f2e8")                  # label
    d.line([4, 24, 11, 24], fill="#d8302c")
    d.ellipse([5, 28, 10, 33], fill="#8c9096")                    # the knob
    d.line([7, 29, 7, 32], fill="#5a5e64")
    d.rectangle([4, 35, 11, 38], fill="#3a1010")                  # the chute
    return img


def draw_lp_row(src, names):
    """32 x 16: four record sleeves leaning in a row, each overlapping the next."""
    img = Image.new("RGBA", (32, 16), (0, 0, 0, 0))
    for i, n in enumerate(names):
        cov = lab(src, n).resize((10, 14), Image.NEAREST)
        img.paste(cov, (i * 7, 1 + (i % 2)))
    return img


def draw_legs():
    """32 x 16: a pair of steel legs and their cross bar (holes elsewhere)."""
    img = Image.new("RGBA", (32, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for x in (1, 30):
        d.rectangle([x - 1, 0, x, 15], fill="#8c9096")
    d.line([1, 9, 30, 9], fill="#7a7e84")
    return img


def draw_bincard(src):
    """32 x 24: the bin's 300-yen card on its stick."""
    img = Image.new("RGBA", (32, 24), (0, 0, 0, 0))
    img.paste(lab(src, "bargain"), (0, 0))
    ImageDraw.Draw(img).rectangle([15, 16, 16, 23], fill="#8c9096")
    return img


CELLS = {}


def half_width(im):
    return im.resize((im.size[0] // 2, im.size[1]), Image.Resampling.BOX)


def draw_art():
    src = Image.open(LAB).convert("RGBA")
    sheet = Image.new("RGBA", (256, 128), (0, 0, 0, 0))

    def put(name, im, x, y):
        sheet.paste(im, (x, y))
        CELLS[name] = [x, y, im.size[0], im.size[1]]

    # the glass front and the kanban at full width again (they were halved for 1 MB of VRAM)
    put("glass", draw_glass(), 0, 0)                     # 144 x 64
    put("kanban", draw_kanban(src), 0, 64)               # 176 x 32
    put("cassette", lab(src, "cassette"), 144, 0)        # 48 x 32
    put("sode", lab(src, "sode"), 192, 0)                # 16 x 64
    put("poster", lab(src, "poster"), 208, 0)            # 24 x 32
    put("band", lab(src, "band"), 232, 0)                # 24 x 32
    put("chalk", lab(src, "chalk"), 208, 32)             # 32 x 40
    put("home", lab(src, "home"), 144, 32)               # 32 x 24
    put("bargain", lab(src, "bargain"), 176, 64)         # 32 x 16
    put("gacha", draw_gacha(), 240, 32)                  # 16 x 40
    put("laundry", draw_laundry(), 0, 96)                # 48 x 32
    put("railing", draw_railing(), 48, 96)               # 64 x 8
    put("valance", draw_valance(), 48, 104)              # 16 x 8
    put("lp_row_a", draw_lp_row(src, ["lp1", "lp2", "lp3", "lp4"]), 64, 104)
    put("lp_row_b", draw_lp_row(src, ["lp3", "lp4", "lp1", "lp2"]), 112, 96)
    put("legs", draw_legs(), 144, 112)
    put("bincard", draw_bincard(src), 176, 80)
    put("fan", lab(src, "fan"), 208, 80)
    os.makedirs(os.path.join(HERE, "art"), exist_ok=True)
    sheet.save(os.path.join(HERE, "art", "recordshop_sheet.png"))
    with open(os.path.join(HERE, "art", "recordshop_sheet.sheet.json"), "w") as f:
        json.dump({"format": "mei-sheet", "version": 1, "cells": CELLS}, f, indent=1)
        f.write("\n")


# ---- recipe helpers --------------------------------------------------------------------
def r(v):
    return round(v + 0.0, 4)


def box(id, size, at, material, open=None, faces=None, rotate=None, decals=None):
    n = {"id": id, "op": "box", "size": [r(s) for s in size], "material": material}
    if open:
        n["open"] = open
    if faces:
        n["faces"] = faces
    if decals:
        n["decals"] = decals
    t = {}
    if rotate:
        t["rotate"] = rotate
    t["translate"] = [r(a) for a in at]
    n["transform"] = t
    return n


def _normal(pts):
    nx = ny = nz = 0.0
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return nx, ny, nz


class Mesh:
    """A mesh node built polygon by polygon; each polygon is turned to face `out`."""

    def __init__(self, id):
        self.id, self.v, self.f, self.m, self.decals = id, [], [], [], []

    def vert(self, p):
        p = [r(c) for c in p]
        if p not in self.v:
            self.v.append(p)
        return self.v.index(p)

    def poly(self, pts, out, material, decals=None):
        n = _normal(pts)
        if sum(a * b for a, b in zip(n, out)) < 0:
            pts = list(reversed(pts))
        self.f.append([self.vert(p) for p in pts])
        self.m.append(material)
        for dcl in decals or []:
            self.decals.append(dict(dcl, face=len(self.f) - 1))
        return self

    def quad_x(self, x, z0, z1, y0, y1, out, material, decals=None):
        return self.poly([[x, y0, z0], [x, y0, z1], [x, y1, z1], [x, y1, z0]], out, material,
                         decals)

    def quad_y(self, y, x0, x1, z0, z1, out, material):
        return self.poly([[x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1]], out, material)

    def quad_z(self, z, x0, x1, y0, y1, out, material, decals=None):
        return self.poly([[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z]], out, material,
                         decals)

    def node(self, transform=None):
        n = {"id": self.id, "op": "mesh", "vertices": self.v, "faces": self.f,
             "face_materials": self.m}
        if self.decals:
            n["decals"] = self.decals
        if transform:
            n["transform"] = transform
        return n


def decal(id, material, size, at):
    return {"id": id, "material": material, "size": [r(s) for s in size],
            "at": [r(a) for a in at]}


def card(id, material, x0, x1, y0, y1, z, out=(0, 0, -1), transform=None):
    m = Mesh(id).quad_z(z, x0, x1, y0, y1, out, material)
    return m.node(transform)


def sheet(cellname, bits=4):
    t = {"sheet": "art", "cell": cellname, "projection": "fit"}
    if bits == 8:
        t["bits"] = 8
    return t


def common(cell, rotate=None):
    t = {"sheet": "town_common", "cell": cell, "projection": "box", "scale": [2, 2]}
    if rotate:
        t["rotate"] = rotate
    return t


def shopfront(cell):
    return {"sheet": "shopfront", "cell": cell, "projection": "fit"}


MATERIALS = {
    # walls
    "tile": {"color": "#e6dcc2", "tag": "wall",
             "texture": {"pattern": "tile", "size": 16, "colors": ["#e8dec4", "#b4a88e", "#dcd0b4"],
                         "params": {"count": 4, "grout": 1}, "projection": "box",
                         "scale": [0.5, 0.5]}},
    "brown_tile": {"color": "#8e5434", "tag": "wall",
                   "texture": {"pattern": "tile", "size": 16, "colors": BROWN,
                               "params": {"count": 2, "grout": 1}, "projection": "box",
                               "scale": [0.25, 0.25]}},
    "siding": {"color": "#b8c4cc", "tag": "wall",
               "texture": {"pattern": "stripes", "size": 16,
                           "colors": ["#c4ced6", "#c4ced6", "#c4ced6", "#8e9aa4"],
                           "params": {"count": 4, "axis": "v"}, "projection": "box",
                           "scale": [0.5, 0.5]}},
    "mortar": {"color": "#b4ac9c", "tag": "wall", "texture": common("plaster_grey")},
    "roof": {"color": "#7a7670", "palette": True, "tag": "roof"},
    "alu": {"color": "#c4c8cc", "palette": True},
    "navy": {"color": "#1c2860", "palette": True},
    "red": {"color": "#c84a3a", "palette": True},
    # the shop front
    "glass": {"color": "#2c3c54", "class": "emissive", "tag": "shopfront",
              "texture": sheet("glass")},
    "kanban": {"color": "#1c2860", "class": "emissive", "tag": "sign", "texture": sheet("kanban")},
    "sode": {"color": "#faf6e6", "class": "emissive", "tag": "sign", "texture": sheet("sode")},
    "poster": {"color": "#faaac4", "texture": sheet("poster")},
    "band": {"color": "#18182a", "texture": sheet("band")},
    "bargain": {"color": "#fae63c", "texture": sheet("bargain")},
    "awning": {"color": "#2e8c5a", "tag": "awning",
               "texture": {"pattern": "stripes", "size": 16, "colors": ["#2e8c5a", "#f4f2e8"],
                           "params": {"count": 4, "axis": "u"}, "projection": "box",
                           "scale": [1, 1]}},
    "valance": {"color": "#2e8c5a", "double_sided": True,
                "texture": {"sheet": "art", "cell": "valance", "projection": "box",
                            "scale": [1, 0.25]}},
    # the roof
    "cassette": {"color": "#e2dcc8", "texture": sheet("cassette")},
    "home": {"color": "#3c4a60", "tag": "window", "texture": sheet("home")},
    "door": {"color": "#8e949a", "texture": shopfront("back_door")},
    "back_win": {"color": "#c8d4d8", "tag": "window", "texture": shopfront("back_win")},
    "ac": {"color": "#e2e0d6", "texture": shopfront("ac")},
    "antenna": {"color": "#7a7e84", "double_sided": True, "texture": shopfront("antenna")},
    "railing": {"color": "#c4c8cc", "double_sided": True, "texture": sheet("railing")},
    "laundry": {"color": "#f08cb0", "double_sided": True, "texture": sheet("laundry")},
    # the street things
    "gacha": {"color": "#d8302c", "texture": sheet("gacha")},
    "lp_a": {"color": "#2878c8", "double_sided": True, "texture": sheet("lp_row_a")},
    "lp_b": {"color": "#f68c32", "double_sided": True, "texture": sheet("lp_row_b")},
    "legs": {"color": "#8c9096", "double_sided": True, "texture": sheet("legs")},
    "bincard": {"color": "#fae63c", "double_sided": True, "texture": sheet("bincard")},
    "chalk": {"color": "#283c30", "texture": sheet("chalk")},
    "wood": {"color": "#966e46", "palette": True},
}


# ---- the building ----------------------------------------------------------------------
def shell(level):
    """The building's walls, the terrace floor and the upstairs room, as one mesh."""
    m = Mesh("shell")
    # the sides: an L of the shop block (to the terrace) and the upstairs room
    side = [(ZF, 0), (ZF, T), (ZH, T), (ZH, H if level < 2 else ROOF), (ZB, H if level < 2 else ROOF),
            (ZB, 0)]
    for x, out in ((-HX, (-1, 0, 0)), (HX, (1, 0, 0))):
        m.poly([[x, y, z] for z, y in side], out, "mortar")
    top = H if level < 2 else ROOF
    if level == 0:
        m.quad_z(ZF, -HX, HX, G, T, (0, 0, -1), "tile")
        m.quad_z(ZF, -HX, -GX, 0, G, (0, 0, -1), "brown_tile")
        m.quad_z(ZF, GX, HX, 0, G, (0, 0, -1), "brown_tile")
        m.quad_x(-GX, ZF, ZG, 0, G, (1, 0, 0), "brown_tile")
        m.quad_x(GX, ZF, ZG, 0, G, (-1, 0, 0), "brown_tile")
        m.quad_y(G, -GX, GX, ZF, ZG, (0, -1, 0), "alu")
        m.quad_z(ZG, -GX, GX, 0, G, (0, 0, -1), "glass", decals=[
            decal("idol", "poster", [0.75, 1.0], [-2.95, 1.95]),
            decal("live", "band", [0.75, 1.0], [2.95, 2.0]),
            decal("price", "bargain", [0.64, 0.32], [0.0, 1.55])])
    elif level == 1:
        m.quad_z(ZF, -HX, HX, G, T, (0, 0, -1), "tile", decals=[
            decal("kanban", "kanban", [7.6, 1.38], [0.0, 4.11])])
        m.quad_z(ZF, -HX, HX, 0, G, (0, 0, -1), "brown_tile", decals=[
            decal("glass", "glass", [2 * GX, G - 0.02], [0.0, G / 2])])
    else:
        m.quad_z(ZF, -HX, HX, G, T, (0, 0, -1), "kanban")
        m.quad_z(ZF, -HX, HX, 0, G, (0, 0, -1), "glass")
    # the terrace floor and the upstairs room's front
    m.quad_y(T, -HX, HX, ZF, ZH, (0, 1, 0), "roof")
    if level < 2:
        m.quad_z(ZH, -HX, HX, T, top, (0, 0, -1), "siding", decals=[
            decal("home", "home", [1.8, 1.35], [-1.6, 6.15]),
            decal("door", "door", [0.85, 1.95], [1.4, T + 0.995])])
    else:
        m.quad_z(ZH, -HX, HX, T, top, (0, 0, -1), "siding")
    # the back, on the service lane (seen from +Z, so `at` x is -x)
    if level == 0:
        m.quad_z(ZB, -HX, HX, 0, top, (0, 0, 1), "mortar", decals=[
            decal("back_door", "door", [0.9, 2.0], [-2.6, 1.01]),
            decal("back_win", "back_win", [1.0, 1.0], [1.6, 1.7]),
            decal("room_win", "back_win", [1.2, 1.0], [0.0, 6.1])])
    else:
        m.quad_z(ZB, -HX, HX, 0, top, (0, 0, 1), "mortar")
    if level > 0:
        m.quad_y(top, -HX, HX, ZH, ZB, (0, 1, 0), "roof")
    return m.node()


def awning(full=True):
    """Green and white, 3.3 at the wall to 2.85 at its edge 1.2 m out (20 degrees), and the
    scalloped valance below the edge."""
    x = 4.4
    zw, ze = ZF + 0.02, ZF - 1.2
    m = Mesh("awning")
    m.poly([[-x, 3.3, zw], [x, 3.3, zw], [x, 2.85, ze], [-x, 2.85, ze]], (0, 1, -0.3), "awning")
    m.poly([[-x, 2.85, ze], [x, 2.85, ze], [x, 2.6, ze], [-x, 2.6, ze]], (0, 0, -1), "valance")
    if full:
        m.poly([[-x, 2.6, ze], [x, 2.6, ze], [x, 3.12, zw], [-x, 3.12, zw]], (0, -1, 0.3), "awning")
        for s in (-1, 1):
            m.poly([[s * x, 3.3, zw], [s * x, 2.85, ze], [s * x, 2.6, ze], [s * x, 3.12, zw]],
                   (s, 0, 0), "awning")
    return m.node()


def level0():
    n = [shell(0)]
    # coping along the terrace's front edge, 5 cm proud of the tile
    n.append(box("coping", [9.1, 0.16, 0.3], [0, T + 0.04, ZF + 0.1], "roof", open=["bottom"]))
    # the kanban, 22 cm deep, sunk 2 cm into the band
    n.append(box("kanban", [7.6, 1.38, 0.24], [0, 4.11, ZF - 0.1], "navy", open=["front"],
                 faces={"back": "kanban"}))
    n.append(awning())
    # the sode sign at the right end of the band, sunk 2.5 cm into it
    n.append(box("sode", [0.12, 1.8, 0.45], [4.15, 4.3, ZF - 0.2], "red",
                 faces={"left": "sode", "right": "sode"}))
    # the upstairs room's roof slab, 10 cm over its walls
    n.append(box("slab", [9.2, 0.12, 6.2], [0, ROOF - 0.06, (ZH + ZB) / 2], "roof"))
    # the terrace rail: front and both sides
    n.append(card("rail_front", "railing", -4.45, 4.45, T + 0.05, T + 0.95, ZF + 0.15))
    for s in (-1, 1):
        n.append(Mesh(f"rail_{'west' if s < 0 else 'east'}")
                 .quad_x(s * 4.42, ZF + 0.15, ZH - 0.05, T + 0.05, T + 0.95, (s, 0, 0), "railing")
                 .node())
    # the cassette billboard on two posts, behind the rail, leaning back
    n.append(box("cassette", [2.7, 1.8, 0.16], [-2.3, 6.8, ZF + 0.75], "roof",
                 faces={"back": "cassette"}, rotate=[6, 0, 3]))
    for i, x in enumerate((-3.2, -1.4)):
        n.append(box(f"post_{i}", [0.08, 1.05, 0.08], [x, T + 0.52, ZF + 0.9], "alu",
                     open=["top", "bottom"]))
    # the air conditioner by the room's door, the laundry, the antenna
    n.append(box("ac", [0.8, 0.56, 0.3], [3.3, T + 0.27, ZH - 0.16], "alu",
                 open=["bottom", "front"], faces={"back": "ac"}))
    n.append(card("laundry", "laundry", 0.0, 2.3, T - 0.01, T + 1.52, -2.2))
    for z, rot in ((4.0, 0), (4.0, 90)):
        n.append(Mesh(f"antenna_{rot}").quad_z(0, -0.7, 0.7, ROOF - 0.02, ROOF + 1.78, (0, 0, -1),
                                              "antenna")
                 .node({"rotate": [0, rot, 0], "translate": [2.6, 0, z]}))
    # the street: gachapon, bargain bin, chalk board
    n.append(box("gacha", [0.42, 1.05, 0.38], [3.95, 0.53, ZF - 0.24], "red", open=["bottom"],
                 faces={"back": "gacha"}))
    n += bargain_bin()
    n.append(aframe())
    return n


def bargain_bin():
    t = {"rotate": [0, 8, 0], "translate": [-2.0, 0, ZF - 0.75]}
    g = {"id": "bargain_bin", "op": "group", "transform": t, "children": [
        box("bin", [1.1, 0.3, 0.55], [0, 0.7, 0], "red", open=["top"]),
        card("lps_front", "lp_a", -0.5, 0.5, 0.62, 0.98, 0.0,
             transform={"rotate": [-28, 0, 0], "translate": [0, 0, -0.1]}),
        card("lps_back", "lp_b", -0.5, 0.5, 0.62, 0.98, 0.0,
             transform={"rotate": [-20, 0, 0], "translate": [0, 0.02, 0.14]}),
        card("legs_front", "legs", -0.52, 0.52, 0.0, 0.56, -0.24),
        card("legs_back", "legs", -0.52, 0.52, 0.0, 0.56, 0.24),
        card("card", "bincard", 0.3, 0.66, 0.85, 1.4, -0.29),
    ]}
    return [g]


def aframe():
    m = Mesh("aframe")
    w, h, d = 0.28, 0.8, 0.26
    m.poly([[-w, h, 0], [w, h, 0], [w, 0, -d], [-w, 0, -d]], (0, 0.3, -1), "chalk")
    m.poly([[-w, h, 0], [w, h, 0], [w, 0, d], [-w, 0, d]], (0, 0.3, 1), "wood")
    m.poly([[-w, h, 0], [-w, 0, -d], [-w, 0, d]], (-1, 0, 0), "wood")
    m.poly([[w, h, 0], [w, 0, -d], [w, 0, d]], (1, 0, 0), "wood")
    return m.node({"rotate": [0, -15, 0], "translate": [1.75, 0, ZF - 0.85]})


def level1():
    n = [shell(1), awning(full=False)]
    n.append(box("sode", [0.12, 1.8, 0.45], [4.15, 4.3, ZF - 0.2], "red", open=["top", "bottom"],
                 faces={"left": "sode", "right": "sode"}))
    n.append(box("cassette", [2.7, 1.8, 0.16], [-2.3, 6.8, ZF + 0.75], "roof",
                 open=["bottom", "front"], faces={"back": "cassette"}, rotate=[6, 0, 3]))
    n.append(card("rail_front", "railing", -4.45, 4.45, T + 0.05, T + 0.95, ZF + 0.15))
    return n


def level2():
    m = Mesh("awning")
    m.poly([[-4.4, 3.3, ZF + 0.02], [4.4, 3.3, ZF + 0.02], [4.4, 2.75, ZF - 1.2],
            [-4.4, 2.75, ZF - 1.2]], (0, 1, -0.3), "awning")
    return [shell(2), m.node(),
            card("cassette", "cassette", -3.65, -0.95, 5.9, 7.7, ZF + 0.75)]


def recipe():
    return {
        "format": "mei-asset", "version": 1, "name": "recordshop",
        "budget": {"triangles": 450},
        "sheets": {
            "art": {"image": "art/recordshop_sheet.png"},
            "town_common": {"image": "../town_alley_house_a/art/town_common.png"},
            "shopfront": {"image": "../town_shop_2f_a/art/shopfront.png"},
        },
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "materials": MATERIALS,
        "nodes": level0(),
        "lod": {"levels": [{"distance": 24, "nodes": level1()},
                           {"distance": 60, "nodes": level2()}], "band": 2},
    }


# ---- collision -------------------------------------------------------------------------
def solid(id, x0, x1, y0, y1, z0, z1, open=None, material="solid"):
    return box(id, [x1 - x0, y1 - y0, z1 - z0], [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2],
               material, open=open)


def collision():
    aw = Mesh("awning")
    x, zw, ze = 4.4, ZF, ZF - 1.2
    aw.poly([[-x, 3.3, zw], [x, 3.3, zw], [x, 2.85, ze], [-x, 2.85, ze]], (0, 1, -0.3), "solid")
    aw.poly([[-x, 2.85, ze], [x, 2.85, ze], [x, 2.6, ze], [-x, 2.6, ze]], (0, 0, -1), "solid")
    aw.poly([[-x, 2.6, ze], [x, 2.6, ze], [x, 3.12, zw], [-x, 3.12, zw]], (0, -1, 0.3), "solid")
    for s in (-1, 1):
        aw.poly([[s * x, 3.3, zw], [s * x, 2.85, ze], [s * x, 2.6, ze], [s * x, 3.12, zw]],
                (s, 0, 0), "solid")
    n = [
        # the shop block to the terrace floor (5.0), its back face inside the room's
        solid("block", -HX, HX, 0, T, ZF, ZH, open=["bottom", "front"]),
        # the upstairs room, roof 7.3 (the slab's top)
        solid("room", -HX, HX, 0, ROOF, ZH, ZB, open=["bottom"]),
        # the terrace rail, 0.9 high, 0.2 thick: a narrow ledge on top
        solid("rail_front", -HX, HX, T, T + 0.9, ZF, ZF + 0.2, open=["bottom"]),
        solid("rail_west", -HX, -HX + 0.2, T, T + 0.9, ZF + 0.2, ZH, open=["bottom", "back", "front"]),
        solid("rail_east", HX - 0.2, HX, T, T + 0.9, ZF + 0.2, ZH, open=["bottom", "back", "front"]),
        # the kanban stands 22 cm out of the band
        solid("kanban", -3.8, 3.8, 3.42, 4.8, ZF - 0.22, ZF, open=["front"]),
        aw.node(),
        # the billboard to the floor, the air conditioner
        solid("billboard", -3.65, -0.95, T, 7.65, ZF + 0.65, ZF + 0.85, open=["bottom"]),
        solid("ac", 2.9, 3.7, T, T + 0.56, ZH - 0.3, ZH, open=["bottom", "front"]),
        # the gachapon and the bargain bin
        solid("gacha", 3.74, 4.16, 0, 1.05, ZF - 0.43, ZF - 0.05, open=["bottom"]),
        solid("bin", -2.6, -1.4, 0, 0.85, ZF - 1.05, ZF - 0.45, open=["bottom"]),
    ]
    return {
        "format": "mei-asset", "version": 1, "name": "recordshop_col",
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "materials": {"solid": {"color": "#c8c4b8", "palette": True}},
        "nodes": n,
    }


def write(name, data):
    with open(os.path.join(HERE, name), "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    draw_art()
    write("recordshop.asset.json", recipe())
    write("recordshop_col.asset.json", collision())
