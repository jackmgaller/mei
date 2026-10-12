#!/usr/bin/env python3
"""Writes shrine town's ramen shop (福来軒): art/ramen_sheet.png (+ .sheet.json),
ramen_shop.asset.json and ramen_shop_col.asset.json.

Adapted from the lab model (examples/assets/lab/ramen_shop, 6.9 x 7.6 m, 1,700 triangles),
whose sheet it reads. Grown to the shotengai's shop plot: origin at the centre of a 9 x 14 m
footprint at street level, front (the street) toward -Z, as town_shop_2f_a. The house is 8 m
wide (x -4.5 to 3.5) and its green steel stair climbs the east metre of the plot to the flat
upstairs, as in the lab. Kept: brown tile shop front, the red 福来軒 kanban under a blue
kawara pent roof, the wooden doors with the らーめん noren, the two red lanterns, the food
sample case, the vending machine and its bin, the planters, the menu board, the cream siding
upstairs with its railed window, the futon over the rail, the laundry, the air conditioner,
the 中華そば sign, the antenna, and the cat on the pent roof.

The cut: doors and windows are decals, the stair's fourteen treads are one cutout slope on
two stringers, its rails cutout lattice; the cat is three low spheres and its ears; the
propane tanks and the side vent are dropped.

Routes: the stair (26.6 degrees) to the landing (3.0) -> the eave (5.0, a double jump) -> the
gable (11 degrees, ridge 6.5 along X). From the street: the pent roof (3.35 at the wall,
16 degrees) is a ledge to stand on, under the cat.

Run: python3 carts/garden/shrinetown/assets/ramen_shop/make_ramen_shop.py   (needs Pillow)
"""
import json
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
LABDIR = os.path.join(REPO, "examples", "assets", "lab", "ramen_shop")
LAB = os.path.join(LABDIR, "art", "ramen_sheet.png")
LAB_CELLS = json.load(open(LAB.replace(".png", ".sheet.json")))["cells"]

# ---- dimensions (metres) ---------------------------------------------------------------
X0, X1 = -4.5, 3.5  # the house's walls; the stair runs x 3.6-4.4
XC = (X0 + X1) / 2
ZF, ZB = -7.0, 7.0  # front (street) and back (service lane) walls
FL = 3.0            # upstairs floor, the landing, the top of the tile front
WALL = 5.0          # front and back walls' top, under the eaves
RIDGE = 6.5         # roof top along X at z = 0
EZ = 7.6            # eaves 0.6 m beyond the walls
EX0, EX1 = X0 - 0.25, X1 + 0.25
TH = 0.12
SX0, SX1 = 3.6, 4.4             # the stair
SZ0, SZ1 = -6.6, -0.6           # its foot and head (rise 3.0 over 6.0: 26.6 degrees)
LZ1 = 1.6                       # the landing's back edge


def roof_y(z):
    return RIDGE - (RIDGE - WALL) * abs(z) / EZ


# ---- art -------------------------------------------------------------------------------
def lab(src, name):
    x, y, w, h = LAB_CELLS[name]
    return src.crop((x, y, x + w, y + h))


def draw_treads():
    """16 x 60: fifteen open steel treads seen from above (holes between)."""
    img = Image.new("RGBA", (16, 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i in range(15):
        y = i * 4
        d.rectangle([0, y, 15, y + 1], fill="#4f7a72")
        d.line([0, y + 2, 15, y + 2], fill="#2f5450")
    return img


def draw_futon():
    """16 x 16: a blue and white checked futon."""
    img = Image.new("RGBA", (16, 16), "#a8c4e4")
    d = ImageDraw.Draw(img)
    for y in range(4):
        for x in range(4):
            if (x + y) % 2:
                d.rectangle([x * 4, y * 4, x * 4 + 3, y * 4 + 3], fill="#f2f0ea")
    return img


CELLS = {}


def draw_art():
    src = Image.open(LAB).convert("RGBA")
    sheet = Image.new("RGBA", (128, 128), (0, 0, 0, 0))

    def put(name, im, x, y):
        sheet.paste(im, (x, y))
        CELLS[name] = [x, y, im.size[0], im.size[1]]

    for name in LAB_CELLS:
        if name != "fan":
            put(name, lab(src, name), *LAB_CELLS[name][:2])
    put("treads", draw_treads(), 96, 64)
    put("futon", draw_futon(), 112, 64)
    os.makedirs(os.path.join(HERE, "art"), exist_ok=True)
    sheet.save(os.path.join(HERE, "art", "ramen_sheet.png"))
    with open(os.path.join(HERE, "art", "ramen_sheet.sheet.json"), "w") as f:
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
    "tile": {"color": "#b08664", "tag": "wall",
             "texture": {"pattern": "tile", "size": 16, "colors": ["#b48a66", "#7a5c44", "#a67c58"],
                         "params": {"count": 4, "grout": 1}, "projection": "box",
                         "scale": [0.5, 0.5]}},
    "mortar": {"color": "#bdb6a6", "tag": "wall", "texture": common("plaster_grey")},
    "siding": {"color": "#e4d8bc", "tag": "wall",
               "texture": {"pattern": "stripes", "size": 16, "colors": ["#e8dcc0", "#d2c4a4"],
                           "params": {"count": 4, "axis": "v"}, "projection": "box",
                           "scale": [1, 1]}},
    "kawara": {"color": "#5a6678", "tag": "roof", "texture": common("kawara_blue")},
    "ridge": {"color": "#353d4b", "palette": True, "tag": "roof"},
    "wood": {"color": "#4a2e1c", "palette": True},
    "steel": {"color": "#3f6a64", "palette": True},
    "white": {"color": "#e8eaec", "palette": True},
    "pot": {"color": "#b0603a", "palette": True},
    "leaves": {"color": "#3f7a3a", "palette": True},
    "bin": {"color": "#3a6ab0", "palette": True},
    "cat": {"color": "#e0923e", "palette": True},
    "lantern": {"color": "#d0362c", "class": "emissive", "tag": "lantern",
                "texture": {"pattern": "stripes", "size": 16, "colors": ["#e04030", "#a82018"],
                            "params": {"count": 4, "axis": "v"}, "projection": "cylindrical",
                            "scale": [1, 0.5]}},
    "rail": {"color": "#3f6a64", "double_sided": True,
             "texture": {"pattern": "lattice", "size": 16, "colors": ["#3f6a64", "#000000"],
                         "clear": "#000000", "params": {"count": 4, "bar": 1},
                         "projection": "box", "scale": [1, 1]}},
    "treads": {"color": "#4f7a72", "double_sided": True, "texture": sheet("treads")},
    "futon": {"color": "#a8c4e4", "texture": sheet("futon")},
    "kanban": {"color": "#a51e22", "class": "emissive", "tag": "sign", "texture": sheet("kanban")},
    "noren": {"color": "#26346b", "double_sided": True, "texture": sheet("noren")},
    "tate": {"color": "#fff4d6", "class": "emissive", "tag": "sign", "texture": sheet("tate")},
    "doors": {"color": "#5a3a22", "class": "emissive", "tag": "shopfront",
              "texture": sheet("doors")},
    "case": {"color": "#3c3a44", "class": "emissive", "tag": "window", "texture": sheet("case")},
    "vend": {"color": "#f2f4f6", "class": "emissive", "tag": "sign", "texture": sheet("vend")},
    "window": {"color": "#4a5a74", "tag": "window", "texture": sheet("window")},
    "flatdoor": {"color": "#d6ccb4", "tag": "door", "texture": sheet("flatdoor")},
    "menu": {"color": "#26402e", "texture": sheet("menu")},
    "laundry": {"color": "#e8eef8", "double_sided": True, "texture": sheet("laundry")},
    "backwin": {"color": "#d4dcd8", "tag": "window", "texture": sheet("backwin")},
    "ac": {"color": "#e2e0d6", "texture": shopfront("ac")},
    "antenna": {"color": "#7a7e84", "double_sided": True, "texture": shopfront("antenna")},
}


# ---- the building ----------------------------------------------------------------------
def shell(level):
    m = Mesh("shell")
    apex = RIDGE - TH
    for x, out in ((X0, (-1, 0, 0)), (X1, (1, 0, 0))):
        if level == 2:
            m.poly([[x, 0, ZF], [x, WALL, ZF], [x, apex, 0], [x, WALL, ZB], [x, 0, ZB]], out,
                   "siding")
            continue
        low = []
        up = []
        if level == 0 and x == X1:
            # seen from +X: `at` x runs toward +Z
            low = [decal("kitchen", "backwin", [0.8, 0.6], [3.0, 1.7])]
            up = [decal("flat_door", "flatdoor", [0.85, 1.94], [0.5, FL + 1.0])]
        m.quad_x(x, ZF, ZB, 0, FL, out, "mortar", decals=low)
        m.poly([[x, FL, ZF], [x, WALL, ZF], [x, apex, 0], [x, WALL, ZB], [x, FL, ZB]], out,
               "siding", decals=up)
    if level == 0:
        m.quad_z(ZF, X0, X1, 0, FL, (0, 0, -1), "tile", decals=[
            decal("doors", "doors", [1.9, 2.1], [XC + 0.3, 1.06])])
        m.quad_z(ZF, X0, X1, FL, WALL, (0, 0, -1), "siding", decals=[
            decal("window", "window", [2.4, 1.4], [XC, 4.15])])
        m.quad_z(ZB, X0, X1, 0, FL, (0, 0, 1), "mortar", decals=[
            decal("back_door", "flatdoor", [0.85, 1.9], [-2.4, 0.97]),
            decal("back_win", "backwin", [0.8, 0.6], [1.0, 1.7])])
        m.quad_z(ZB, X0, X1, FL, WALL, (0, 0, 1), "siding", decals=[
            decal("back_upwin", "window", [1.4, 1.0], [0.5, 4.1])])
    elif level == 1:
        m.quad_z(ZF, X0, X1, 0, FL, (0, 0, -1), "tile", decals=[
            decal("doors", "doors", [1.9, 2.1], [XC + 0.3, 1.06])])
        m.quad_z(ZF, X0, X1, FL, WALL, (0, 0, -1), "siding", decals=[
            decal("window", "window", [2.4, 1.4], [XC, 4.15])])
        m.quad_z(ZB, X0, X1, 0, WALL, (0, 0, 1), "mortar")
    else:
        m.quad_z(ZF, X0, X1, 0, FL, (0, 0, -1), "tile")
        m.quad_z(ZF, X0, X1, FL, WALL, (0, 0, -1), "siding")
        m.quad_z(ZB, X0, X1, 0, WALL, (0, 0, 1), "mortar")
    return m.node()


def roof(full=True):
    m = Mesh("roof")
    e = roof_y(EZ)
    for s in (-1, 1):
        m.poly([[EX0, RIDGE, 0], [EX1, RIDGE, 0], [EX1, e, s * EZ], [EX0, e, s * EZ]],
               (0, 1, 0.2 * s), "kawara")
    if full:
        for s in (-1, 1):
            m.poly([[EX0, RIDGE - TH, 0], [EX1, RIDGE - TH, 0], [EX1, e - TH, s * EZ],
                    [EX0, e - TH, s * EZ]], (0, -1, 0), "wood")
            m.poly([[EX0, e, s * EZ], [EX1, e, s * EZ], [EX1, e - TH, s * EZ],
                    [EX0, e - TH, s * EZ]], (0, 0, s), "ridge")
        for x, s in ((EX0, -1), (EX1, 1)):
            m.poly([[x, e, -EZ], [x, RIDGE, 0], [x, e, EZ], [x, e - TH, EZ],
                    [x, RIDGE - TH, 0], [x, e - TH, -EZ]], (s, 0, 0), "ridge")
    else:
        for x, s in ((EX0, -1), (EX1, 1)):
            m.poly([[x, e, -EZ], [x, RIDGE, 0], [x, e, EZ]], (s, 0, 0), "ridge")
    return m.node()


PX0, PX1 = X0 - 0.1, X1 + 0.05  # the pent roof
PW, PE = 3.35, 3.05              # its height at the wall and at its edge, 1.05 m out


def pent(full=True):
    zw, ze = ZF + 0.02, ZF - 1.05
    m = Mesh("pent_roof")
    m.poly([[PX0, PW, zw], [PX1, PW, zw], [PX1, PE, ze], [PX0, PE, ze]], (0, 1, -0.3), "kawara")
    if full:
        m.poly([[PX0, PE, ze], [PX1, PE, ze], [PX1, PE - 0.1, ze], [PX0, PE - 0.1, ze]],
               (0, 0, -1), "ridge")
        m.poly([[PX0, PE - 0.1, ze], [PX1, PE - 0.1, ze], [PX1, PW - 0.1, zw],
                [PX0, PW - 0.1, zw]], (0, -1, 0.3), "wood")
        for x, s in ((PX0, -1), (PX1, 1)):
            m.poly([[x, PW, zw], [x, PE, ze], [x, PE - 0.1, ze], [x, PW - 0.1, zw]], (s, 0, 0),
                   "ridge")
    return m.node()


def pent_y(z):
    return PW - (PW - PE) * (ZF + 0.02 - z) / 1.07


def stair(level):
    n = []
    run = ((SZ1 - SZ0) ** 2 + FL ** 2) ** 0.5
    ang = -26.565
    zc, yc = (SZ0 + SZ1) / 2, FL / 2
    n.append({"id": "treads", "op": "mesh", "material": "treads",
              "vertices": [[SX0, 0, SZ0], [SX1, 0, SZ0], [SX1, FL, SZ1], [SX0, FL, SZ1]],
              "faces": [[3, 2, 1, 0]]})
    n.append(box("landing", [SX1 - SX0, 0.08, LZ1 - SZ1], [(SX0 + SX1) / 2, FL - 0.04,
                 (SZ1 + LZ1) / 2], "steel", open=None if level == 0 else ["bottom"]))
    if level > 0:
        return n
    for i, x in enumerate((SX0 - 0.03, SX1 + 0.03)):
        n.append(box(f"stringer_{i}", [0.05, 0.2, run], [x, yc - 0.12, zc], "steel",
                     open=["front", "back"], rotate=[ang, 0, 0]))
    n.append(box("handrail", [0.04, 0.04, run], [SX1 + 0.1, yc + 0.85, zc], "steel",
                 open=["front", "back"], rotate=[ang, 0, 0]))
    for i, z in enumerate((SZ1 + 0.05, LZ1 - 0.05)):
        n.append(box(f"landing_post_{i}", [0.06, FL + 0.9, 0.06], [SX1 + 0.1, (FL + 0.9) / 2, z],
                     "steel", open=["bottom"]))
    n.append(Mesh("landing_rail").quad_x(SX1 + 0.1, SZ1 + 0.08, LZ1 - 0.08, FL + 0.05,
                                         FL + 0.9, (1, 0, 0), "rail").node())
    n.append(Mesh("landing_end").quad_z(LZ1 - 0.03, SX0 + 0.02, SX1 - 0.06, FL + 0.05, FL + 0.9,
                                        (0, 0, 1), "rail").node())
    n.append(box("stair_post", [0.04, 0.85, 0.04], [SX1 + 0.1, 0.43, SZ0 + 0.1], "steel",
                 open=["top", "bottom"]))
    return n


def cat():
    t = {"rotate": [0, 25, 0], "translate": [1.6, pent_y(ZF - 0.5) - 0.03, ZF - 0.5]}
    return {"id": "cat", "op": "group", "transform": t, "children": [
        {"id": "body", "op": "sphere", "radius": 1, "rings": 3, "segments": 6, "material": "cat",
         "transform": {"scale": [0.13, 0.17, 0.15], "translate": [0, 0.15, 0]}},
        {"id": "head", "op": "sphere", "radius": 0.095, "rings": 3, "segments": 5,
         "material": "cat", "transform": {"translate": [0, 0.36, -0.05]}},
        {"id": "ear_l", "op": "cone", "radius": 0.035, "height": 0.08, "segments": 3,
         "material": "cat", "transform": {"translate": [-0.05, 0.46, -0.04]}},
        {"id": "ear_r", "op": "cone", "radius": 0.035, "height": 0.08, "segments": 3,
         "material": "cat", "transform": {"translate": [0.05, 0.46, -0.04]}},
        {"id": "tail", "op": "cylinder", "radius": 0.022, "height": 0.32, "segments": 3,
         "caps": False, "material": "cat",
         "transform": {"rotate": [0, 0, 80], "translate": [0.2, 0.05, 0.06]}},
    ]}


def lantern(i, x, segments=6):
    n = cyl(f"lantern_{i}", 0.17, 0.48, [x, 1.95, ZF - 0.45], "lantern", segments)
    n["faces"] = {"top": "ridge", "bottom": "ridge"}
    return n


def level0():
    n = [shell(0), roof(), pent()]
    n.append(box("ridge_cap", [EX1 - EX0 + 0.1, 0.16, 0.34], [XC, RIDGE + 0.02, 0], "ridge",
                 open=["bottom"]))
    for rot in (0, 90):
        n.append(Mesh(f"antenna_{rot}").quad_z(0, -0.7, 0.7, RIDGE - 0.02, RIDGE + 1.7,
                                              (0, 0, -1), "antenna")
                 .node({"rotate": [0, rot, 0], "translate": [1.5, 0, 0.6]}))
    # the shop front: kanban, noren on its rod, sample case, lanterns
    n.append(box("kanban", [4.6, 0.6, 0.12], [XC + 0.3, 2.62, ZF - 0.04], "wood",
                 open=["front"], faces={"back": "kanban"}))
    n.append(box("noren_rod", [2.0, 0.04, 0.04], [XC + 0.3, 2.2, ZF - 0.2], "wood",
                 open=["left", "right"]))
    n.append(card("noren", "noren", XC + 0.3 - 0.9, XC + 0.3 + 0.9, 1.3, 2.18, ZF - 0.22))
    n.append(box("case", [1.3, 0.8, 0.3], [-2.75, 1.3, ZF - 0.13], "wood", open=["front"],
                 faces={"back": "case"}))
    n.append(lantern(0, -1.55))
    n.append(lantern(1, 0.85))
    # the vending machine and its bin, planters, menu board
    n.append(box("vending", [0.9, 1.8, 0.7], [-3.95, 0.9, ZF - 0.36], "white",
                 open=["bottom", "front"], faces={"back": "vend"}))
    n.append(cyl("bin", 0.16, 0.6, [-3.3, 0.3, ZF - 0.5], "bin", 6))
    for i, x in enumerate((-1.75, 1.15)):
        n.append(cyl(f"planter_{i}", 0.17, 0.34, [x, 0.17, ZF - 0.32], "pot", 5))
        n.append({"id": f"shrub_{i}", "op": "sphere", "radius": 0.27, "rings": 3, "segments": 5,
                  "material": "leaves", "transform": {"scale": [1, 0.8, 1],
                                                      "translate": [x, 0.5, ZF - 0.32]}})
    n.append(aframe())
    # upstairs: the window rail with the futon, laundry, air conditioner, the tate sign
    n.append(card("window_rail", "rail", XC - 1.25, XC + 1.25, 3.45, 3.95, ZF - 0.2))
    n.append(box("futon", [1.0, 0.6, 0.04], [XC + 0.45, 3.7, ZF - 0.24], "futon",
                 rotate=[-6, 0, 0]))
    n.append(box("laundry_pole", [2.8, 0.04, 0.04], [XC, 4.82, ZF - 0.42], "white",
                 open=["left", "right"]))
    n.append(card("laundry", "laundry", XC - 1.0, XC + 0.6, 4.0, 4.8, ZF - 0.42))
    n.append(box("ac", [0.75, 0.55, 0.28], [2.45, 3.75, ZF - 0.12], "white",
                 open=["front"], faces={"back": "ac"}))
    n.append(box("tate", [0.12, 1.45, 0.4], [-3.9, 4.17, ZF - 0.18], "ridge",
                 faces={"left": "tate", "right": "tate"}))
    n.append(box("downpipe", [0.1, 4.95, 0.1], [X0 + 0.1, 2.475, ZF - 0.07], "ridge",
                 open=["top", "bottom"]))
    n.append(cat())
    n += stair(0)
    return n


def aframe():
    m = Mesh("menu_board")
    w, h, d = 0.23, 0.75, 0.16
    m.poly([[-w, h, 0], [w, h, 0], [w, 0, -d], [-w, 0, -d]], (0, 0.3, -1), "menu")
    m.poly([[-w, h, 0], [w, h, 0], [w, 0, d], [-w, 0, d]], (0, 0.3, 1), "wood")
    m.poly([[-w, h, 0], [-w, 0, -d], [-w, 0, d]], (-1, 0, 0), "wood")
    m.poly([[w, h, 0], [w, 0, -d], [w, 0, d]], (1, 0, 0), "wood")
    return m.node({"rotate": [0, 10, 0], "translate": [2.4, 0, ZF - 0.75]})


def level1():
    n = [shell(1), roof(full=False), pent(full=False)]
    n.append(box("kanban", [4.6, 0.6, 0.12], [XC + 0.3, 2.62, ZF - 0.04], "wood",
                 open=["front", "top", "bottom"], faces={"back": "kanban"}))
    n.append(box("case", [1.3, 0.8, 0.3], [-2.75, 1.3, ZF - 0.13], "wood",
                 open=["front", "top", "bottom"], faces={"back": "case"}))
    lan = [cyl(f"lantern_{i}", 0.17, 0.48, [x, 1.95, ZF - 0.45], "lantern", 4, caps=False)
           for i, x in enumerate((-1.55, 0.85))]
    n += lan
    n.append(box("vending", [0.9, 1.8, 0.7], [-3.95, 0.9, ZF - 0.36], "white",
                 open=["bottom", "front"], faces={"back": "vend"}))
    n.append(box("tate", [0.12, 1.45, 0.4], [-3.9, 4.17, ZF - 0.18], "ridge",
                 open=["top", "bottom"], faces={"left": "tate", "right": "tate"}))
    n.append({"id": "cat", "op": "sphere", "radius": 0.15, "rings": 2, "segments": 4,
              "material": "cat", "transform": {"scale": [1, 1.4, 1],
                                               "translate": [1.6, pent_y(ZF - 0.5) + 0.15,
                                                             ZF - 0.5]}})
    n += stair(1)
    return n


def level2():
    m = Mesh("pent_roof")
    m.poly([[PX0, PW, ZF + 0.02], [PX1, PW, ZF + 0.02], [PX1, PE, ZF - 1.05],
            [PX0, PE, ZF - 1.05]], (0, 1, -0.3), "kawara")
    return [shell(2), roof(full=False), m.node(),
            card("kanban", "kanban", XC + 0.3 - 2.3, XC + 0.3 + 2.3, 2.32, 2.92, ZF - 0.1),
            {"id": "treads", "op": "mesh", "material": "treads",
             "vertices": [[SX0, 0, SZ0], [SX1, 0, SZ0], [SX1, FL, SZ1], [SX0, FL, SZ1]],
             "faces": [[3, 2, 1, 0]]}]


def recipe():
    return {
        "format": "mei-asset", "version": 1, "name": "ramen_shop",
        "budget": {"triangles": 600},
        "sheets": {
            "art": {"image": "art/ramen_sheet.png"},
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
        rf.poly([[EX0, RIDGE, 0], [EX1, RIDGE, 0], [EX1, e, s * EZ], [EX0, e, s * EZ]],
                (0, 1, 0.2 * s), "solid")
    for x, s in ((EX0, -1), (EX1, 1)):
        rf.poly([[x, e, -EZ], [x, RIDGE, 0], [x, e, EZ]], (s, 0, 0), "solid")
    rf.poly([[EX0, e, -EZ], [EX1, e, -EZ], [EX1, e, EZ], [EX0, e, EZ]], (0, -1, 0), "solid")
    pr = Mesh("pent_roof")
    zw, ze = ZF, ZF - 1.05
    pr.poly([[PX0, PW, zw], [PX1, PW, zw], [PX1, PE, ze], [PX0, PE, ze]], (0, 1, -0.3), "solid")
    pr.poly([[PX0, PE, ze], [PX1, PE, ze], [PX1, PE - 0.2, ze], [PX0, PE - 0.2, ze]],
            (0, 0, -1), "solid")
    pr.poly([[PX0, PE - 0.2, ze], [PX1, PE - 0.2, ze], [PX1, PW - 0.2, zw], [PX0, PW - 0.2, zw]],
            (0, -1, 0.3), "solid")
    for x, s in ((PX0, -1), (PX1, 1)):
        pr.poly([[x, PW, zw], [x, PE, ze], [x, PE - 0.2, ze], [x, PW - 0.2, zw]], (s, 0, 0),
                "solid")
    n = [
        solid("walls", X0, X1, 0, WALL, ZF, ZB, open=["bottom", "top"]),
        rf.node(),
        pr.node(),
        solid("kanban", XC + 0.3 - 2.3, XC + 0.3 + 2.3, 2.32, 2.92, ZF - 0.2, ZF,
              open=["front"]),
        solid("case", -3.4, -2.1, 0, 1.7, ZF - 0.3, ZF, open=["bottom", "front"]),
        solid("vending", -4.4, -3.5, 0, 1.8, ZF - 0.71, ZF, open=["bottom", "front"]),
        # the stair: a wedge 0.8 wide, 26.6 degrees, and the landing at 3.0 with its rails
        {"id": "stair", "op": "extrude", "material": "solid", "depth": SX1 - SX0,
         "points": [[SZ0, 0], [SZ1, FL], [SZ1, 0]],
         "transform": {"rotate": [0, -90, 0], "translate": [(SX0 + SX1) / 2, 0, 0]}},
        solid("landing", X1, SX1, FL - 0.2, FL, SZ1 - 0.3, LZ1, open=["left", "right"]),
        solid("landing_rail", SX1 - 0.2, SX1, FL, FL + 0.9, SZ1, LZ1, open=["bottom"]),
        solid("landing_end", X1, SX1 - 0.2, FL, FL + 0.9, LZ1 - 0.2, LZ1,
              open=["bottom", "left", "right"]),
    ]
    return {
        "format": "mei-asset", "version": 1, "name": "ramen_shop_col",
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
    write("ramen_shop.asset.json", recipe())
    write("ramen_shop_col.asset.json", collision())
