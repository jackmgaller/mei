#!/usr/bin/env python3
"""Writes shrine town's tobacco shop (たばこ): art/tobacco_sheet.png (+ .sheet.json),
tobacco_shop.asset.json and tobacco_shop_col.asset.json.

Adapted from the lab model (examples/assets/lab/tobacco_shop, 4.0 x 4.0 m, 858 triangles),
whose sheet it reads. Grown to the shotengai's shop plot: origin at the centre of a 9 x 14 m
footprint at street level, front (the street) toward -Z, as town_shop_2f_a. It is what the lab
drew, a house with a tobacco window in its corner: cream mortar below, blue-grey siding above,
a kawara gable. Kept: the window with the maneki-neko and the calendar, the showcase of
cigarette packs under the counter, the pink phone, the red たばこ sign, the green awning, the
red and the white vending machines, the ashtray stand, the vertical corner sign, the 塩 sign,
the house door, the laundry pole, the air conditioner, the potted plant and a bench.

The cut: the window, door, upstairs windows and 塩 sign are decals on the walls; the laundry is
one cutout card; the vending machines lose their caps; the phone is one box.

Routes: vending machines (1.8) -> awning (2.4 at the wall) -> the roof's eave (5.0, a double
jump) -> the gable (11 degrees, ridge 6.5 along X, like town_shop_2f_a) -> the neighbours.

Run: python3 carts/garden/shrinetown/assets/tobacco_shop/make_tobacco_shop.py   (needs Pillow)
"""
import json
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
LABDIR = os.path.join(REPO, "examples", "assets", "lab", "tobacco_shop")
LAB = os.path.join(LABDIR, "art", "shop_sheet.png")
LAB_CELLS = json.load(open(LAB.replace(".png", ".sheet.json")))["cells"]

# ---- dimensions (metres) ---------------------------------------------------------------
HX = 4.5            # half width (9 m wall in a 10 m plot)
ZF, ZB = -7.0, 7.0  # front (street) and back (service lane) walls
BELT = 2.85         # the brown belt between the mortar and the siding
WALL = 5.0          # front and back walls' top, under the eaves
RIDGE = 6.5         # roof top along X at z = 0
EZ = 7.6            # eaves 0.6 m beyond the walls, front and back
EX = 4.75           # verges 0.25 m beyond the side walls
TH = 0.12           # roof thickness


def roof_y(z):
    """The roof's top surface at depth z."""
    return RIDGE - (RIDGE - WALL) * abs(z) / EZ


# ---- art -------------------------------------------------------------------------------
def lab(src, name):
    x, y, w, h = LAB_CELLS[name]
    return src.crop((x, y, x + w, y + h))


def draw_laundry():
    """64 x 24: the bamboo pole on its two hangers, a blue towel, a white one, two socks."""
    img = Image.new("RGBA", (64, 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([0, 1, 63, 1], fill="#c8b48a")
    d.line([0, 2, 63, 2], fill="#a8946a")
    d.rectangle([12, 3, 21, 17], fill="#4f7fc8")
    d.line([12, 17, 21, 17], fill="#3a62a0")
    d.rectangle([26, 3, 33, 15], fill="#f2efe6")
    d.line([26, 15, 33, 15], fill="#d0ccc0")
    for x in (40, 44):
        d.rectangle([x, 3, x + 1, 9], fill="#4f7fc8")
        d.rectangle([x, 9, x + 3, 10], fill="#4f7fc8")
    return img


def draw_onigawara():
    """16 x 16: the ridge-end tile's face, a dark disc with a raised rim (holes outside)."""
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, 15, 15], fill="#2c333b")
    d.ellipse([2, 2, 13, 13], fill="#4a5560")
    d.ellipse([6, 6, 9, 9], fill="#2c333b")
    return img


CELLS = {}


def draw_art():
    src = Image.open(LAB).convert("RGBA")
    sheet = Image.new("RGBA", (128, 128), (0, 0, 0, 0))

    def put(name, im, x, y):
        sheet.paste(im, (x, y))
        CELLS[name] = [x, y, im.size[0], im.size[1]]

    put("sign", lab(src, "sign"), 0, 0)              # 64 x 16
    put("showcase", lab(src, "showcase"), 64, 0)     # 64 x 16
    put("vend", lab(src, "vend"), 0, 16)             # 32 x 64
    put("window", lab(src, "window"), 32, 16)        # 48 x 32
    put("upwin", lab(src, "upwin"), 80, 16)          # 32 x 24
    put("salt", lab(src, "salt"), 112, 16)           # 16 x 16
    put("ac", lab(src, "ac"), 112, 32)               # 16 x 16
    put("door", lab(src, "door"), 0, 80)             # 24 x 48
    put("vsign", lab(src, "vsign"), 112, 64)         # 16 x 56
    put("laundry", draw_laundry(), 32, 48)           # 64 x 24
    put("onigawara", draw_onigawara(), 96, 48)       # 16 x 16
    os.makedirs(os.path.join(HERE, "art"), exist_ok=True)
    sheet.save(os.path.join(HERE, "art", "tobacco_sheet.png"))
    with open(os.path.join(HERE, "art", "tobacco_sheet.sheet.json"), "w") as f:
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


def cyl(id, radius, height, at, material, segments=6, caps=True):
    n = {"id": id, "op": "cylinder", "radius": radius, "height": r(height), "segments": segments,
         "material": material, "transform": {"translate": [r(a) for a in at]}}
    if not caps:
        n["caps"] = False
    return n


MATERIALS = {
    "plaster": {"color": "#e6dcc4", "tag": "wall", "texture": common("plaster")},
    "siding": {"color": "#7d97a6", "tag": "wall",
               "texture": {"pattern": "stripes", "size": 16,
                           "colors": ["#86a0ae", "#86a0ae", "#86a0ae", "#6a8392"],
                           "params": {"count": 4, "axis": "v"}, "projection": "box",
                           "scale": [1, 1]}},
    "kawara": {"color": "#4a5560", "tag": "roof", "texture": common("kawara")},
    "ridge": {"color": "#3a424b", "palette": True, "tag": "roof"},
    "trim": {"color": "#5b3b2a", "palette": True},
    "counter": {"color": "#c8b58e", "palette": True},
    "phone": {"color": "#f08cb0", "palette": True},
    "vend_red": {"color": "#a8262e", "palette": True},
    "vend_white": {"color": "#e8e4da", "palette": True},
    "pot": {"color": "#b4643c", "palette": True},
    "leaf": {"color": "#4f8f3e", "palette": True},
    "awning": {"color": "#2f7d55", "tag": "awning",
               "texture": {"pattern": "stripes", "size": 16, "colors": ["#2f7d55", "#ece6d2"],
                           "params": {"count": 4, "axis": "u"}, "projection": "box",
                           "scale": [1, 1]}},
    "sign": {"color": "#ce2228", "class": "emissive", "tag": "sign", "texture": sheet("sign")},
    "vsign": {"color": "#fcf8ec", "class": "emissive", "tag": "sign", "texture": sheet("vsign")},
    "showcase": {"color": "#96b6ba", "tag": "window", "texture": sheet("showcase")},
    "vend": {"color": "#e8e4d6", "class": "emissive", "tag": "sign", "texture": sheet("vend")},
    "window": {"color": "#8ca8b0", "class": "emissive", "tag": "shopfront",
               "texture": sheet("window")},
    "upwin": {"color": "#96b0c4", "tag": "window", "texture": sheet("upwin")},
    "salt": {"color": "#1e46a0", "tag": "sign", "texture": sheet("salt")},
    "door": {"color": "#b0b4ba", "tag": "door", "texture": sheet("door")},
    "laundry": {"color": "#4f7fc8", "double_sided": True, "texture": sheet("laundry")},
    "onigawara": {"color": "#2c333b", "texture": sheet("onigawara")},
    "back_door": {"color": "#8e949a", "texture": shopfront("back_door")},
    "back_win": {"color": "#c8d4d8", "tag": "window", "texture": shopfront("back_win")},
    "ac": {"color": "#e2e0d6", "texture": shopfront("ac")},
    "antenna": {"color": "#7a7e84", "double_sided": True, "texture": shopfront("antenna")},
}

KX0, KX1 = -3.8, -1.0       # the tobacco counter
VX = (-0.55, 0.25)          # the vending machines' centres


# ---- the building ----------------------------------------------------------------------
def shell(level):
    m = Mesh("shell")
    apex = RIDGE - TH
    for x, out in ((-HX, (-1, 0, 0)), (HX, (1, 0, 0))):
        if level == 2:
            m.poly([[x, 0, ZF], [x, WALL, ZF], [x, apex, 0], [x, WALL, ZB], [x, 0, ZB]], out,
                   "siding")
        else:
            m.quad_x(x, ZF, ZB, 0, BELT, out, "plaster")
            m.poly([[x, BELT, ZF], [x, WALL, ZF], [x, apex, 0], [x, WALL, ZB], [x, BELT, ZB]],
                   out, "siding")
    if level == 0:
        m.quad_z(ZF, -HX, HX, 0, BELT, (0, 0, -1), "plaster", decals=[
            decal("window", "window", [2.4, 1.3], [-2.4, 1.58]),
            decal("door", "door", [0.95, 1.95], [3.15, 0.985]),
            decal("salt", "salt", [0.32, 0.32], [2.05, 1.75])])
        m.quad_z(ZF, -HX, HX, BELT, WALL, (0, 0, -1), "siding", decals=[
            decal("upwin_l", "upwin", [1.4, 1.05], [-2.3, 3.95]),
            decal("upwin_r", "upwin", [1.4, 1.05], [1.4, 3.95])])
        m.quad_z(ZB, -HX, HX, 0, BELT, (0, 0, 1), "plaster", decals=[
            decal("back_door", "back_door", [0.9, 2.0], [-2.8, 1.01]),
            decal("back_win", "back_win", [1.0, 1.0], [1.5, 1.6])])
        m.quad_z(ZB, -HX, HX, BELT, WALL, (0, 0, 1), "siding", decals=[
            decal("back_upwin", "back_win", [1.2, 1.0], [0.5, 3.95])])
    elif level == 1:
        m.quad_z(ZF, -HX, HX, 0, BELT, (0, 0, -1), "plaster", decals=[
            decal("window", "window", [2.4, 1.3], [-2.4, 1.58]),
            decal("door", "door", [0.95, 1.95], [3.15, 0.985])])
        m.quad_z(ZF, -HX, HX, BELT, WALL, (0, 0, -1), "siding", decals=[
            decal("upwin_l", "upwin", [1.4, 1.05], [-2.3, 3.95])])
        m.quad_z(ZB, -HX, HX, 0, WALL, (0, 0, 1), "plaster")
    else:
        m.quad_z(ZF, -HX, HX, 0, BELT, (0, 0, -1), "plaster")
        m.quad_z(ZF, -HX, HX, BELT, WALL, (0, 0, -1), "siding")
        m.quad_z(ZB, -HX, HX, 0, WALL, (0, 0, 1), "plaster")
    return m.node()


def roof(full=True):
    m = Mesh("roof")
    e = roof_y(EZ)
    for s in (-1, 1):
        m.poly([[-EX, RIDGE, 0], [EX, RIDGE, 0], [EX, e, s * EZ], [-EX, e, s * EZ]],
               (0, 1, 0.2 * s), "kawara")
    if full:
        for s in (-1, 1):
            m.poly([[-EX, RIDGE - TH, 0], [EX, RIDGE - TH, 0], [EX, e - TH, s * EZ],
                    [-EX, e - TH, s * EZ]], (0, -1, 0), "trim")
            m.poly([[-EX, e, s * EZ], [EX, e, s * EZ], [EX, e - TH, s * EZ],
                    [-EX, e - TH, s * EZ]], (0, 0, s), "ridge")
            m.poly([[s * EX, e, -EZ], [s * EX, RIDGE, 0], [s * EX, e, EZ], [s * EX, e - TH, EZ],
                    [s * EX, RIDGE - TH, 0], [s * EX, e - TH, -EZ]], (s, 0, 0), "ridge")
    else:
        for s in (-1, 1):
            m.poly([[s * EX, e, -EZ], [s * EX, RIDGE, 0], [s * EX, e, EZ]], (s, 0, 0), "ridge")
    return m.node()


def awning(full=True):
    x0, x1 = KX0 - 0.05, KX1 + 0.05
    zw, ze = ZF + 0.02, ZF - 0.72
    m = Mesh("awning")
    m.poly([[x0, 2.36, zw], [x1, 2.36, zw], [x1, 2.12, ze], [x0, 2.12, ze]], (0, 1, -0.3),
           "awning")
    if full:
        m.poly([[x0, 2.12, ze], [x1, 2.12, ze], [x1, 1.98, ze], [x0, 1.98, ze]], (0, 0, -1),
               "awning")
        m.poly([[x0, 1.98, ze], [x1, 1.98, ze], [x1, 2.24, zw], [x0, 2.24, zw]], (0, -1, 0.3),
               "awning")
        for x, s in ((x0, -1), (x1, 1)):
            m.poly([[x, 2.36, zw], [x, 2.12, ze], [x, 1.98, ze], [x, 2.24, zw]], (s, 0, 0),
                   "awning")
    return m.node()


def corner_sign(open=None):
    d = 0.26 / 2 ** 0.5
    return box("corner_sign", [0.06, 1.55, 0.45], [-HX - d, 4.2, ZF - d], "trim", open=open,
               faces={"left": "vsign", "right": "vsign"}, rotate=[0, 225, 0])


def level0():
    n = [shell(0), roof()]
    n.append(box("ridge_cap", [9.6, 0.16, 0.34], [0, RIDGE + 0.02, 0], "ridge", open=["bottom"]))
    for s in (-1, 1):
        n.append(Mesh(f"onigawara_{'w' if s < 0 else 'e'}")
                 .quad_x(s * 4.84, -0.21, 0.21, RIDGE - 0.12, RIDGE + 0.3, (s, 0, 0), "onigawara")
                 .node())
    for z, name in ((ZF - 0.03, "belt"), (ZB + 0.03, "belt_back")):
        n.append(box(name, [9.1, 0.14, 0.1], [0, BELT, z], "trim",
                     open=["front"] if z < 0 else ["back"]))
    # the tobacco window: cabinet with its showcase, counter, phone, awning, sign
    kx, kw = (KX0 + KX1) / 2, KX1 - KX0
    n.append(box("cabinet", [kw - 0.2, 0.95, 0.42], [kx, 0.475, ZF - 0.19], "trim",
                 open=["bottom", "front"], faces={"back": "showcase"}))
    n.append(box("counter", [kw, 0.06, 0.57], [kx, 0.97, ZF - 0.265], "counter", open=["front"]))
    n.append(box("phone", [0.26, 0.18, 0.2], [-3.25, 1.085, ZF - 0.3], "phone",
                 open=["bottom"], rotate=[0, 12, 0]))
    n.append(awning())
    n.append(box("sign", [2.5, 0.5, 0.08], [kx, 2.62, ZF - 0.08], "trim", open=["front"],
                 faces={"back": "sign"}))
    n.append(corner_sign())
    # the vending machines, the ashtray stand
    for x, mat in zip(VX, ("vend_red", "vend_white")):
        n.append(box(f"vend_{mat[5:]}", [0.72, 1.8, 0.66], [x, 0.9, ZF - 0.32], mat,
                     open=["bottom", "front"], faces={"back": "vend"}))
    n.append(cyl("ashtray_stand", 0.03, 0.6, [0.95, 0.3, ZF - 0.55], "ridge", 4, caps=False))
    n.append(cyl("ashtray", 0.15, 0.08, [0.95, 0.64, ZF - 0.55], "ridge", 6))
    # the bench under the 塩 sign, the potted plant by the door
    n.append(box("bench_seat", [1.2, 0.06, 0.36], [1.75, 0.42, ZF - 0.25], "trim"))
    for i, x in enumerate((1.23, 2.27)):
        n.append(box(f"bench_leg_{i}", [0.06, 0.39, 0.3], [x, 0.195, ZF - 0.25], "trim",
                     open=["top", "bottom"]))
    n.append(cyl("pot", 0.18, 0.36, [3.95, 0.18, ZF - 0.4], "pot", 5))
    n.append({"id": "bush", "op": "sphere", "radius": 0.26, "segments": 5, "rings": 3,
              "material": "leaf", "transform": {"scale": [1, 1.15, 1],
                                                "translate": [3.95, 0.62, ZF - 0.4]}})
    # upstairs: laundry pole, air conditioner, downpipe, antenna
    n.append(card("laundry", "laundry", -3.5, -1.1, 3.55, 4.45, ZF - 0.4))
    n.append(box("ac", [0.72, 0.52, 0.28], [3.45, 3.2, ZF - 0.15], "vend_white",
                 open=["front"], faces={"back": "ac"}))
    n.append(box("downpipe", [0.1, 4.95, 0.1], [4.38, 2.475, ZF - 0.07], "ridge",
                 open=["top", "bottom"]))
    for rot in (0, 90):
        n.append(Mesh(f"antenna_{rot}").quad_z(0, -0.7, 0.7, RIDGE - 0.02, RIDGE + 1.6,
                                              (0, 0, -1), "antenna")
                 .node({"rotate": [0, rot, 0], "translate": [-2.8, 0, 0]}))
    return n


def level1():
    kx, kw = (KX0 + KX1) / 2, KX1 - KX0
    return [shell(1), roof(full=False), awning(full=False),
            box("cabinet", [kw - 0.2, 0.95, 0.42], [kx, 0.475, ZF - 0.19], "trim",
                open=["bottom", "front"], faces={"back": "showcase"}),
            box("sign", [2.5, 0.5, 0.08], [kx, 2.62, ZF - 0.08], "trim", open=["front"],
                faces={"back": "sign"}),
            box("vend", [1.52, 1.8, 0.66], [-0.15, 0.9, ZF - 0.32], "vend_red",
                open=["bottom", "front"], faces={"back": "vend"}),
            corner_sign(open=["top", "bottom"])]


def level2():
    kx = (KX0 + KX1) / 2
    m = Mesh("awning")
    m.poly([[KX0, 2.36, ZF + 0.02], [KX1, 2.36, ZF + 0.02], [KX1, 2.04, ZF - 0.72],
            [KX0, 2.04, ZF - 0.72]], (0, 1, -0.3), "awning")
    return [shell(2), roof(full=False), m.node(),
            card("sign", "sign", kx - 1.25, kx + 1.25, 2.37, 2.87, ZF - 0.12),
            card("vend", "vend", -0.91, 0.61, 0.0, 1.8, ZF - 0.66)]


def recipe():
    return {
        "format": "mei-asset", "version": 1, "name": "tobacco_shop",
        "budget": {"triangles": 450},
        "sheets": {
            "art": {"image": "art/tobacco_sheet.png"},
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
    rf = Mesh("roof")
    e = roof_y(EZ)
    for s in (-1, 1):
        rf.poly([[-EX, RIDGE, 0], [EX, RIDGE, 0], [EX, e, s * EZ], [-EX, e, s * EZ]],
                (0, 1, 0.2 * s), "solid")
        rf.poly([[s * EX, e, -EZ], [s * EX, RIDGE, 0], [s * EX, e, EZ]], (s, 0, 0), "solid")
    rf.poly([[-EX, e, -EZ], [EX, e, -EZ], [EX, e, EZ], [-EX, e, EZ]], (0, -1, 0), "solid")
    aw = Mesh("awning")
    x0, x1, zw, ze = KX0 - 0.05, KX1 + 0.05, ZF, ZF - 0.72
    aw.poly([[x0, 2.36, zw], [x1, 2.36, zw], [x1, 2.12, ze], [x0, 2.12, ze]], (0, 1, -0.3), "solid")
    aw.poly([[x0, 2.12, ze], [x1, 2.12, ze], [x1, 1.98, ze], [x0, 1.98, ze]], (0, 0, -1), "solid")
    aw.poly([[x0, 1.98, ze], [x1, 1.98, ze], [x1, 2.24, zw], [x0, 2.24, zw]], (0, -1, 0.3), "solid")
    for x, s in ((x0, -1), (x1, 1)):
        aw.poly([[x, 2.36, zw], [x, 2.12, ze], [x, 1.98, ze], [x, 2.24, zw]], (s, 0, 0), "solid")
    n = [
        solid("walls", -HX, HX, 0, WALL, ZF, ZB, open=["bottom", "top"]),
        rf.node(),
        aw.node(),
        # counter, vending machines (a 1.8 m step to the awning), bench
        solid("counter", KX0, KX1, 0, 1.0, ZF - 0.55, ZF, open=["bottom", "front"]),
        solid("vending", -0.91, 0.61, 0, 1.8, ZF - 0.65, ZF, open=["bottom", "front"]),
        solid("bench", 1.15, 2.35, 0, 0.45, ZF - 0.43, ZF - 0.07, open=["bottom"]),
    ]
    return {
        "format": "mei-asset", "version": 1, "name": "tobacco_shop_col",
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
    write("tobacco_shop.asset.json", recipe())
    write("tobacco_shop_col.asset.json", collision())
