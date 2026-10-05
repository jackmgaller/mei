#!/usr/bin/env python3
"""Writes art/schoolhouse_sheet.png (+ .sheet.json) and schoolhouse.asset.json for the old wooden
schoolhouse (run from anywhere; needs Pillow and the macOS Hiragino font)."""
import json
import math
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "art")
os.makedirs(ART, exist_ok=True)
FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc"

INK = (38, 36, 40)
WHITE = (244, 241, 232)
RED = (200, 40, 48)


def hsh(a, b=0, c=0):
    h = (a * 374761393 + b * 668265263 + c * 1442695041 + 777) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return (h ^ (h >> 16)) & 0xFFFF


def box(d, x0, y0, x1, y1, fill):
    d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=fill)


def text(d, xy, s, size, fill):
    d.fontmode = "1"
    d.text(xy, s, font=ImageFont.truetype(FONT, size), fill=fill)


# ------------------------------------------------------------------ sprites

def window():
    """32 x 32, repeating: pale-green sashes, four panes across and three high, teal glass."""
    frame = (176, 202, 178)
    shade = (122, 150, 128)
    im = Image.new("RGB", (32, 32), frame)
    d = ImageDraw.Draw(im)
    box(d, 0, 0, 32, 2, shade)
    box(d, 0, 30, 32, 32, shade)
    box(d, 0, 0, 1, 32, shade)
    box(d, 31, 0, 32, 32, shade)
    glass = [(46, 78, 92), (58, 94, 108), (70, 108, 120), (36, 62, 76)]
    for r in range(3):
        for c in range(4):
            x0 = 2 + c * 7 + (1 if c >= 2 else 0)
            y0 = 2 + r * 9
            g = glass[hsh(r, c, 5) % 4]
            box(d, x0, y0, x0 + 6, y0 + 8, g)
            # a pale glint across the upper left of most panes
            if hsh(r, c, 6) % 3:
                box(d, x0 + 1, y0 + 1, x0 + 3, y0 + 2, (150, 190, 200))
                box(d, x0 + 1, y0 + 2, x0 + 2, y0 + 4, (150, 190, 200))
    # the sashes pass each other at the middle: a thicker rail
    box(d, 15, 0, 17, 32, shade)
    # a curtain in one pane, for life
    box(d, 9, 11, 15, 19, (232, 224, 200))
    box(d, 9, 11, 10, 19, (210, 190, 170))
    return im


def door():
    """48 x 56: the double entrance doors, glazed in the upper part."""
    im = Image.new("RGB", (48, 56), (84, 58, 40))
    d = ImageDraw.Draw(im)
    box(d, 0, 0, 48, 56, (60, 42, 30))
    for half in (0, 1):
        x0 = 2 + half * 23
        box(d, x0, 2, x0 + 21, 56, (112, 78, 52))
        for gx in range(2):
            for gy in range(3):
                bx = x0 + 2 + gx * 9
                by = 4 + gy * 11
                box(d, bx, by, bx + 8, by + 10, (92, 130, 140))
                box(d, bx + 1, by + 1, bx + 3, by + 3, (160, 196, 204))
        box(d, x0 + 1, 38, x0 + 20, 39, (74, 52, 36))
        for k in range(4):
            box(d, x0 + 3 + k * 5, 41, x0 + 4 + k * 5, 56, (96, 66, 44))
    box(d, 21, 28, 22, 34, (226, 190, 84))
    box(d, 26, 28, 27, 34, (226, 190, 84))
    return im


def plaque():
    """128 x 20: a wooden name board, "Hinata Elementary School"."""
    im = Image.new("RGB", (128, 20), (196, 160, 112))
    d = ImageDraw.Draw(im)
    box(d, 0, 0, 128, 2, (90, 62, 40))
    box(d, 0, 18, 128, 20, (90, 62, 40))
    box(d, 0, 0, 2, 20, (90, 62, 40))
    box(d, 126, 0, 128, 20, (90, 62, 40))
    for x in range(3, 125, 2):
        if hsh(x, 1) % 5 == 0:
            box(d, x, 3, x + 1, 17, (184, 148, 102))
    text(d, (10, 1), "ひなた小学校", 18, INK)
    return im


def clock():
    """24 x 24, round with clear corners: the tower clock at ten past three."""
    im = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    for y in range(24):
        for x in range(24):
            r2 = (x - 11.5) ** 2 + (y - 11.5) ** 2
            if r2 < 11.7 ** 2:
                im.putpixel((x, y), (60, 50, 40, 255))
            if r2 < 9.7 ** 2:
                im.putpixel((x, y), (242, 236, 214, 255))
    d = ImageDraw.Draw(im)
    for k in range(12):
        a = k * math.pi / 6
        d.point((int(round(11.5 + 8.3 * math.sin(a))), int(round(11.5 - 8.3 * math.cos(a)))),
                fill=(60, 50, 40, 255))
    for (x, y) in [(11, 11), (11, 10), (11, 9), (11, 8), (11, 7), (11, 6), (12, 11), (12, 12),
                   (13, 12), (14, 12), (15, 12), (16, 12)]:
        d.point((x, y), fill=(40, 36, 36, 255))
    return im


def louver():
    """24 x 24, round-topped belfry opening with slats: not clear, a dark opening."""
    im = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    box(d, 0, 0, 24, 24, (240, 232, 210, 255))
    box(d, 4, 3, 20, 24, (40, 34, 36, 255))
    for y in range(5, 24, 3):
        box(d, 4, y, 20, y + 1, (96, 80, 70, 255))
    return im


def rwin():
    """24 x 24, round with clear corners: the round window in the porch gable."""
    im = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    for y in range(24):
        for x in range(24):
            r2 = (x - 11.5) ** 2 + (y - 11.5) ** 2
            if r2 < 11.7 ** 2:
                im.putpixel((x, y), (176, 202, 178, 255))
            if r2 < 9.0 ** 2:
                im.putpixel((x, y), (70, 108, 120, 255) if (x + y) % 7 else (150, 190, 200, 255))
    d = ImageDraw.Draw(im)
    box(d, 11, 2, 13, 22, (176, 202, 178, 255))
    box(d, 2, 11, 22, 13, (176, 202, 178, 255))
    return im


def dwin():
    """24 x 20: a small dormer window, two sashes."""
    frame = (176, 202, 178)
    shade = (122, 150, 128)
    im = Image.new("RGB", (24, 20), frame)
    d = ImageDraw.Draw(im)
    box(d, 0, 0, 24, 1, shade)
    box(d, 0, 19, 24, 20, shade)
    for c in range(2):
        for r in range(2):
            x0, y0 = 2 + c * 10, 2 + r * 8
            box(d, x0, y0, x0 + 10, y0 + 7, (58, 94, 108) if (r + c) % 2 else (46, 78, 92))
            box(d, x0 + 1, y0 + 1, x0 + 3, y0 + 3, (150, 190, 200))
    box(d, 11, 0, 13, 20, shade)
    return im


def flag():
    """36 x 24: the Hinomaru."""
    im = Image.new("RGB", (36, 24), (246, 244, 238))
    d = ImageDraw.Draw(im)
    for y in range(24):
        for x in range(36):
            if (x - 17.5) ** 2 + (y - 11.5) ** 2 < 7.2 ** 2:
                d.point((x, y), fill=RED)
    box(d, 0, 0, 36, 1, (210, 208, 200))
    box(d, 0, 23, 36, 24, (210, 208, 200))
    return im


def vent():
    """16 x 8: a gable louver, repeating."""
    im = Image.new("RGB", (16, 8), (150, 118, 84))
    d = ImageDraw.Draw(im)
    for y in range(1, 8, 2):
        box(d, 0, y, 16, y + 1, (84, 62, 44))
    return im


def make_art():
    cells = [("window", window()), ("door", door()), ("plaque", plaque()), ("clock", clock()),
             ("louver", louver()), ("rwin", rwin()), ("dwin", dwin()), ("flag", flag())]
    sheet = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    rects = {}
    x = y = row_h = 0
    for name, im in cells:
        im = im.convert("RGBA")
        if x + im.width > 128:
            x, y, row_h = 0, y + row_h, 0
        sheet.paste(im, (x, y))
        rects[name] = [x, y, im.width, im.height]
        x += im.width
        row_h = max(row_h, im.height)
    sheet = sheet.crop((0, 0, 128, y + row_h))
    sheet.save(os.path.join(ART, "schoolhouse_sheet.png"))
    with open(os.path.join(ART, "schoolhouse_sheet.sheet.json"), "w") as f:
        json.dump({"format": "mei-sheet", "version": 1, "cells": rects}, f, indent=1)
        f.write("\n")


# ------------------------------------------------------------------ recipe

def kawara():
    """16 x 16 texels of staggered roof tiles: 0 base, 1 light edge, 2 shadow, 3 gap."""
    rows = []
    for y in range(16):
        course, ly = divmod(y, 4)
        shift = 4 if course % 2 else 0
        r = ""
        for x in range(16):
            lx = (x + shift) % 8
            if ly == 3:
                c = "2"
            elif lx == 0:
                c = "3"
            elif ly == 0:
                c = "1"
            else:
                c = "0"
            r += c
        rows.append(r)
    return rows


def cell(name, bits=4, double=False, tag=None, emissive=False, color="#ffffff"):
    m = {"color": color, "texture": {"sheet": "art", "cell": name, "bits": bits, "projection": "fit"}}
    if double:
        m["double_sided"] = True
    if tag:
        m["tag"] = tag
    if emissive:
        m["class"] = "emissive"
    return m


def card(id_, size, pos, mat, facing="back", rot=None):
    sides = ["top", "bottom", "left", "right", "back", "front"]
    sides.remove(facing)
    t = {"translate": pos}
    if rot:
        t["rotate"] = rot
    return {"id": id_, "op": "box", "size": size, "open": sides, "material": mat, "transform": t}


def slab(id_, size, pos, mat, open_=("bottom",), rot=None):
    t = {"translate": pos}
    if rot:
        t["rotate"] = rot
    n = {"id": id_, "op": "box", "size": size, "material": mat, "transform": t}
    if open_:
        n["open"] = list(open_)
    return n


def mesh(id_, verts, faces, mat):
    return {"id": id_, "op": "mesh", "material": mat, "vertices": [[round(v, 4) for v in p] for p in verts],
            "faces": faces}


def recipe():
    mats = {
        "siding": {"color": "#7a5a40", "tag": "wall",
                   "texture": {"pattern": "planks", "size": 16,
                               "colors": ["#7d5d42", "#4f3a28", "#6e5038", "#8a6a4c"],
                               "params": {"boards": 4, "joint": 1, "seed": 2}, "projection": "box",
                               "scale": [4.0, 1.0]}},
        "siding_ds": {"color": "#7a5a40", "tag": "wall", "double_sided": True,
                      "texture": {"pattern": "planks", "size": 16,
                                  "colors": ["#7d5d42", "#4f3a28", "#6e5038", "#8a6a4c"],
                                  "params": {"boards": 4, "joint": 1, "seed": 2}, "projection": "box",
                                  "scale": [4.0, 1.0]}},
        "kawara": {"color": "#5c6670", "tag": "roof", "double_sided": True,
                   "texture": {"texels": kawara(), "colors": ["#5a646e", "#7e8a94", "#3c444c", "#2e343a"],
                               "projection": "box", "scale": [2.0, 2.0]}},
        "stone": {"color": "#8a8a82", "tag": "floor",
                  "texture": {"pattern": "speckle", "size": 16,
                              "colors": ["#8e8e86", "#7a7a74", "#a0a098", "#6c7466"],
                              "params": {"density": 0.3, "seed": 8}, "projection": "box",
                              "scale": [1.0, 1.0]}},
        "copper": {"color": "#5a8a7a", "tag": "roof",
                   "texture": {"pattern": "stripes", "size": 16, "colors": ["#5d9482", "#4a7868"],
                               "params": {"count": 8, "axis": "u"}, "projection": "box",
                               "scale": [1.0, 1.0]}},
        "brick": {"color": "#8a4a38", "tag": "wall",
                  "texture": {"pattern": "brick", "size": 16, "colors": ["#94503a", "#b5a894", "#7c402e"],
                              "params": {"courses": 4, "bricks": 2}, "projection": "box",
                              "scale": [1.0, 1.0]}},
        "window": {"color": "#b0cab0", "texture": {"sheet": "art", "cell": "window", "bits": 4,
                                                   "projection": "box", "scale": [2.0, 2.0]}},
        "plaster": {"color": "#e4dcc4", "tag": "wall"},
        "trim": {"color": "#d8cfb4"},
        "frame": {"color": "#b0cab0"},
        "dark_wood": {"color": "#4a3828"},
        "post": {"color": "#6a4c34"},
        "metal": {"color": "#8c9096"},
        "gold": {"color": "#d8b24a"},
        "door": cell("door", 4, tag="door"),
        "plaque": cell("plaque", 4),
        "clock": cell("clock", 4, double=False),
        "louver": cell("louver", 4),
        "rwin": cell("rwin", 4),
        "dwin": cell("dwin", 4),
        "flag": cell("flag", 4, double=True),
        "lamp": {"color": "#f4d27a", "class": "emissive"},
        "rail": {"color": "#8a5a40"},
        "blossom": {"color": "#f0b4c8", "smooth": True},
        "blossom2": {"color": "#e89ab4", "smooth": True},
        "bark": {"color": "#5a4638"},
        "petals": {"color": "#f4c4d4"},
        "bundle": {"color": "#a8884e"},
        "cloth": {"color": "#4a5a78"},
        "skin": {"color": "#c8a888"},
    }
    N = []
    WALL_Y0, WALL_Y1 = 0.6, 7.2
    # ---- body
    N += [
        slab("foundation", [26.5, 0.6, 9.5], [0, 0.3, 0], "stone"),
        slab("walls", [26, WALL_Y1 - WALL_Y0, 9], [0, (WALL_Y0 + WALL_Y1) / 2, 0], "siding",
             ("bottom", "top")),
        slab("belt", [26.3, 0.25, 9.3], [0, 4.0, 0], "trim", ()),
    ]
    # ---- the hip roof: eaves at 7.0, ridge at 10.4
    ex, ez, rx = 14.2, 5.7, 8.2
    N += [mesh("roof", [(-ex, 7.0, -ez), (ex, 7.0, -ez), (ex, 7.0, ez), (-ex, 7.0, ez),
                        (-rx, 10.4, 0), (rx, 10.4, 0)],
               [[0, 4, 5, 1], [2, 5, 4, 3], [0, 3, 4], [1, 5, 2]], "kawara")]
    # ---- windows: strips of repeating sashes, a little proud of the wall
    wy1, wy2 = 2.5, 5.7
    WH = 2.0
    N += [
        card("win_front_low_l", [8, WH, 0.01], [-8.4, wy1, -4.58], "window"),
        card("win_front_low_r", [8, WH, 0.01], [8.4, wy1, -4.58], "window"),
        card("win_front_up_l", [8, WH, 0.01], [-8.4, wy2, -4.58], "window"),
        card("win_front_up_r", [8, WH, 0.01], [8.4, wy2, -4.58], "window"),
        card("win_back_low", [16, WH, 0.01], [4, wy1, 4.58], "window", facing="front"),
        card("win_back_up", [16, WH, 0.01], [4, wy2, 4.58], "window", facing="front"),
    ]
    # the end strips: a front-facing card turned to face +X / -X
    for sx, face in ((13.08, "back"), (-13.08, "back")):
        yaw = -90 if sx > 0 else 90
        for nm, wy in (("low", wy1), ("up", wy2)):
            N.append(card(f"win_end_{nm}_{'r' if sx > 0 else 'l'}", [8, WH, 0.01], [sx, wy, 0],
                          "window", facing=face, rot=[0, yaw, 0]))
    # sills under every strip (long thin boards)
    for nm, x, wy, w in (("fl", -8.4, wy1, 8.4), ("fr", 8.4, wy1, 8.4), ("ul", -8.4, wy2, 8.4),
                         ("ur", 8.4, wy2, 8.4)):
        N.append(slab(f"sill_front_{nm}", [w, 0.12, 0.3], [x, wy - 1.06, -4.64], "trim", ()))
    N += [slab("sill_back_low", [16.4, 0.12, 0.3], [4, wy1 - 1.06, 4.64], "trim", ()),
          slab("sill_back_up", [16.4, 0.12, 0.3], [4, wy2 - 1.06, 4.64], "trim", ())]
    # ---- the porch and its gable
    N += [
        slab("porch", [6.4, 5.0, 4.0], [0, 3.1, -6.3], "siding", ("bottom", "top")),
        mesh("porch_roof", [(-3.9, 5.4, -8.9), (0, 7.4, -8.9), (3.9, 5.4, -8.9),
                            (-3.9, 5.4, -4.4), (0, 7.4, -4.4), (3.9, 5.4, -4.4)],
             [[0, 3, 4, 1], [1, 4, 5, 2]], "kawara"),
        mesh("pediment", [(-3.2, 5.6, -8.32), (3.2, 5.6, -8.32), (0, 7.28, -8.32)], [[0, 2, 1]], "plaster"),
        card("rwin", [1.1, 1.1, 0.01], [0, 6.2, -8.34], "rwin"),
        card("door", [3.6, 2.9, 0.01], [0, 1.65, -8.32], "door"),
        card("plaque", [3.8, 0.6, 0.01], [0, 4.3, -8.34], "plaque"),
        slab("step_a", [4.8, 0.22, 0.95], [0, 0.11, -8.625], "stone"),
        slab("step_b", [4.2, 0.22, 0.62], [0, 0.329, -8.49], "stone"),
        slab("step_c", [3.8, 0.22, 0.365], [0, 0.549, -8.3925], "stone"),
        {"id": "porch_posts", "op": "group", "children": [
            {"id": "porch_post", "op": "box", "size": [0.3, 4.7, 0.3], "open": ["bottom"],
             "material": "post", "transform": {"translate": [3.35, 2.95, -8.7]}}],
         "modifiers": [{"op": "mirror", "axis": "x"}]},
    ]
    # ---- lean-to roofs over the lower windows, on posts
    for side, sx in (("l", -1), ("r", 1)):
        x0, x1 = sx * 3.9, sx * 13.4
        lo, hi = (min(x0, x1), max(x0, x1))
        N.append(mesh(f"hisashi_{side}", [(lo, 3.5, -5.9), (hi, 3.5, -5.9), (hi, 4.0, -4.5),
                                          (lo, 4.0, -4.5)],
                      [[0, 3, 2, 1]], "kawara"))
        for k, px in enumerate((4.6, 7.4, 10.2, 13.0)):
            N.append({"id": f"hpost_{side}{k}", "op": "box", "size": [0.18, 3.4, 0.18], "open": ["bottom"],
                      "material": "post", "transform": {"translate": [sx * px, 1.8, -5.75]}})
    # ---- the clock tower
    N += [
        slab("tower", [3.6, 6.2, 3.6], [0, 10.6, -2.8], "plaster", ("bottom",)),
        slab("tower_band", [3.9, 0.3, 3.9], [0, 13.5, -2.8], "trim", ()),
        slab("belfry", [2.8, 1.8, 2.8], [0, 14.5, -2.8], "plaster", ()),
        {"id": "tower_roof", "op": "cone", "radius": 2.5, "height": 3.2, "segments": 4, "caps": False,
         "material": "copper", "transform": {"rotate": [0, 45, 0], "translate": [0, 17.0, -2.8]}},
        {"id": "finial", "op": "sphere", "radius": 0.18, "rings": 3, "segments": 6, "material": "gold",
         "transform": {"translate": [0, 18.7, -2.8]}},
        {"id": "finial_rod", "op": "cylinder", "radius": 0.05, "height": 1.1, "segments": 4, "caps": False,
         "material": "metal", "transform": {"translate": [0, 18.2, -2.8]}},
        card("clock_front", [1.7, 1.7, 0.01], [0, 11.9, -4.61], "clock"),
        card("clock_back", [1.7, 1.7, 0.01], [0, 11.9, -0.99], "clock", facing="front"),
        card("clock_left", [1.7, 1.7, 0.01], [-1.81, 11.9, -2.8], "clock", facing="left", rot=[0, 0, 0]),
        card("clock_right", [1.7, 1.7, 0.01], [1.81, 11.9, -2.8], "clock", facing="right"),
        card("louver_front", [1.2, 1.2, 0.01], [0, 14.5, -4.21], "louver"),
        card("louver_back", [1.2, 1.2, 0.01], [0, 14.5, -1.39], "louver", facing="front"),
        card("louver_left", [0.01, 1.2, 1.2], [-1.41, 14.5, -2.8], "louver", facing="left"),
        card("louver_right", [0.01, 1.2, 1.2], [1.41, 14.5, -2.8], "louver", facing="right"),
    ]
    # ---- ridge ornaments and chimney
    N += [
        slab("ridge_end_l", [0.6, 0.7, 0.6], [-8.2, 10.7, 0], "dark_wood", ()),
        slab("ridge_end_r", [0.6, 0.7, 0.6], [8.2, 10.7, 0], "dark_wood", ()),
        {"id": "chimney", "op": "cylinder", "radius": 0.55, "height": 11.0, "segments": 8, "caps": False,
         "material": "brick", "modifiers": [{"op": "taper", "top": 0.75}],
         "transform": {"translate": [9.5, 5.5, 6.6]}},
    ]
    # ---- dormers on the front slope
    for sx, nm in ((-6.0, "l"), (6.0, "r")):
        N += [
            slab(f"dormer_{nm}", [1.9, 1.5, 1.3], [sx, 8.75, -3.0], "siding", ("bottom", "top")),
            mesh(f"dormer_roof_{nm}", [(sx - 1.25, 9.45, -3.95), (sx, 10.3, -3.95), (sx + 1.25, 9.45, -3.95),
                                       (sx - 1.25, 9.45, -2.3), (sx, 10.3, -2.3), (sx + 1.25, 9.45, -2.3)],
                 [[0, 3, 4, 1], [1, 4, 5, 2]], "kawara"),
            mesh(f"dormer_ped_{nm}", [(sx - 0.95, 9.5, -3.66), (sx + 0.95, 9.5, -3.66), (sx, 10.22, -3.66)],
                 [[0, 2, 1]], "plaster"),
            card(f"dormer_win_{nm}", [1.3, 1.0, 0.01], [sx, 8.8, -3.67], "dwin"),
        ]
    # ---- eave boards, ridge cap, downpipes
    N += [
        slab("fascia_front", [28.5, 0.24, 0.16], [0, 6.92, -5.72], "dark_wood", ()),
        slab("fascia_back", [28.5, 0.24, 0.16], [0, 6.92, 5.72], "dark_wood", ()),
        slab("fascia_l", [0.16, 0.24, 11.5], [-14.22, 6.9, 0], "dark_wood", ()),
        slab("fascia_r", [0.16, 0.24, 11.5], [14.22, 6.9, 0], "dark_wood", ()),
        slab("ridge_cap", [16.6, 0.28, 0.5], [0, 10.5, 0], "dark_wood", ()),
        {"id": "downpipes", "op": "group", "children": [
            {"id": "downpipe", "op": "cylinder", "radius": 0.07, "height": 6.3, "segments": 4, "caps": False,
             "material": "metal", "transform": {"translate": [13.4, 3.75, -4.78]}}],
         "modifiers": [{"op": "mirror", "axis": "x"}]},
    ]
    # ---- the rear wing, to the left: a second gable crossing the hip roof
    N += [
        slab("wing_walls", [8.9, 6.4, 10.6], [-8.5, 3.8, 9.7], "siding", ("bottom", "top")),
        mesh("wing_roof", [(-13.7, 7.0, 4.3), (-8.5, 9.7, 4.3), (-3.3, 7.0, 4.3),
                           (-13.7, 7.0, 16.0), (-8.5, 9.7, 16.0), (-3.3, 7.0, 16.0)],
             [[0, 3, 4, 1], [1, 4, 5, 2]], "kawara"),
        mesh("wing_gable", [(-13.0, 7.05, 15.0), (-4.0, 7.05, 15.0), (-8.5, 9.55, 15.0)], [[0, 2, 1]], "siding_ds"),
        card("wing_win_back_low", [4, WH, 0.01], [-8.5, wy1, 15.08], "window", facing="front"),
        card("wing_win_back_up", [4, WH, 0.01], [-8.5, wy2 - 0.2, 15.08], "window", facing="front"),
        card("wing_rwin", [1.2, 1.2, 0.01], [-8.5, 8.3, 15.02], "rwin", facing="front"),
        card("wing_win_low_l", [8, WH, 0.01], [-13.03, wy1, 10.2], "window", facing="back", rot=[0, 90, 0]),
        card("wing_win_up_l", [8, WH, 0.01], [-13.03, wy2, 10.2], "window", facing="back", rot=[0, 90, 0]),
        card("wing_win_low_r", [8, WH, 0.01], [-3.97, wy1, 10.2], "window", facing="back", rot=[0, -90, 0]),
        card("wing_win_up_r", [8, WH, 0.01], [-3.97, wy2, 10.2], "window", facing="back", rot=[0, -90, 0]),
        slab("wing_foundation", [9.3, 0.6, 10.9], [-8.5, 0.3, 9.7], "stone", ("top",)),
    ]
    # ---- the yard: the gate posts, the woodcutter-boy statue
    N += [
        {"id": "gate", "op": "group", "children": [
            slab("gate_post", [0.5, 1.7, 0.5], [2.4, 0.85, -14.0], "stone"),
            slab("gate_cap", [0.64, 0.14, 0.64], [2.4, 1.765, -14.0], "stone", ())],
         "modifiers": [{"op": "mirror", "axis": "x"}]},
        slab("statue_plinth", [0.9, 0.5, 0.9], [-4.6, 0.25, -11.0], "stone"),
        {"id": "statue_body", "op": "cylinder", "radius": 0.2, "height": 0.62, "segments": 6, "caps": True,
         "material": "cloth", "transform": {"translate": [-4.6, 0.805, -11.0]}},
        {"id": "statue_head", "op": "sphere", "radius": 0.14, "rings": 3, "segments": 6, "material": "skin",
         "transform": {"translate": [-4.6, 1.26, -11.0]}},
        slab("statue_wood", [0.55, 0.14, 0.16], [-4.6, 0.95, -10.82], "bundle", (), rot=[-10, 0, 0]),
        slab("statue_book", [0.2, 0.03, 0.14], [-4.6, 0.98, -11.2], "trim", (), rot=[-35, 0, 0]),
    ]
    # ---- tower pilasters, porch lamps
    N += [
        {"id": "pilasters_x", "op": "group", "children": [
            {"id": "pilasters_z", "op": "group", "children": [
                slab("pilaster", [0.24, 6.0, 0.24], [1.72, 10.5, -1.08], "trim")],
             "modifiers": [{"op": "mirror", "axis": "z", "offset": -2.8}]}],
         "modifiers": [{"op": "mirror", "axis": "x"}]},
        {"id": "lamps", "op": "group", "children": [
            {"id": "lamp_arm", "op": "box", "size": [0.08, 0.08, 0.5], "material": "dark_wood",
             "transform": {"translate": [2.7, 4.0, -8.52]}},
            {"id": "lamp", "op": "sphere", "radius": 0.22, "rings": 3, "segments": 6, "material": "lamp",
             "transform": {"translate": [2.7, 3.72, -8.85]}}],
         "modifiers": [{"op": "mirror", "axis": "x"}]},
    ]
    # ---- the iron fire stair on the right end wall
    ang = math.degrees(math.atan2(0.28, 0.45))
    N += [
        slab("landing", [1.4, 0.1, 2.4], [13.8, 3.85, 2.0], "rail", ()),
        {"id": "stair_steps", "op": "box", "size": [1.2, 0.06, 0.42], "open": ["bottom"], "material": "rail",
         "modifiers": [{"op": "array", "count": 14, "step": [0, -0.28, -0.45]}],
         "transform": {"translate": [13.8, 3.7, 0.55]}},
        {"id": "stringers", "op": "group", "children": [
            {"id": "stringer", "op": "box", "size": [0.08, 0.2, 6.9], "material": "dark_wood",
             "transform": {"rotate": [-ang, 0, 0], "translate": [14.4, 1.86, -2.4]}}],
         "modifiers": [{"op": "mirror", "axis": "x", "offset": 13.8}]},
        {"id": "stair_rails", "op": "group", "children": [
            {"id": "stair_rail", "op": "box", "size": [0.05, 0.07, 6.9], "material": "dark_wood",
             "transform": {"rotate": [-ang, 0, 0], "translate": [14.4, 2.8, -2.4]}}],
         "modifiers": [{"op": "mirror", "axis": "x", "offset": 13.8}]},
        {"id": "landing_rails", "op": "box", "size": [0.05, 0.9, 2.4], "open": ["bottom"], "material": "dark_wood",
         "transform": {"translate": [14.52, 4.45, 2.0]}},
    ]
    # ---- the horizontal bars in the yard
    N += [
        {"id": "bars_posts", "op": "group", "children": [
            {"id": "bar_post", "op": "cylinder", "radius": 0.04, "height": 1.3, "segments": 4, "caps": False,
             "material": "metal", "transform": {"translate": [-1.0, 0.65, 0.0]}}],
         "modifiers": [{"op": "mirror", "axis": "x"}], "transform": {"translate": [5.6, 0, -12.6]}},
        {"id": "bar_a", "op": "cylinder", "radius": 0.035, "height": 2.2, "segments": 4, "caps": False,
         "material": "rail", "transform": {"rotate": [0, 0, 90], "translate": [5.6, 1.3, -12.6]}},
        {"id": "bars_posts_low", "op": "group", "children": [
            {"id": "bar_post_low", "op": "cylinder", "radius": 0.04, "height": 1.0, "segments": 4,
             "caps": False, "material": "metal", "transform": {"translate": [-1.0, 0.5, 0.0]}}],
         "modifiers": [{"op": "mirror", "axis": "x"}], "transform": {"translate": [8.0, 0, -12.6]}},
        {"id": "bar_b", "op": "cylinder", "radius": 0.035, "height": 2.2, "segments": 4, "caps": False,
         "material": "rail", "transform": {"rotate": [0, 0, 90], "translate": [8.0, 1.0, -12.6]}},
    ]
    # ---- the cherry tree
    N += [
        {"id": "trunk", "op": "cylinder", "radius": 0.34, "height": 3.4, "segments": 6, "caps": False,
         "material": "bark", "modifiers": [{"op": "taper", "top": 0.6}],
         "transform": {"translate": [-11.0, 1.7, -9.2]}},
        {"id": "crown_a", "op": "sphere", "radius": 2.5, "rings": 4, "segments": 8, "material": "blossom",
         "transform": {"translate": [-11.0, 5.2, -9.2], "scale": [1, 0.8, 1]}},
        {"id": "crown_b", "op": "sphere", "radius": 1.9, "rings": 4, "segments": 8, "material": "blossom2",
         "transform": {"translate": [-12.6, 4.6, -8.4], "scale": [1, 0.8, 1]}},
        {"id": "crown_c", "op": "sphere", "radius": 1.8, "rings": 4, "segments": 8, "material": "blossom",
         "transform": {"translate": [-9.5, 4.4, -10.0], "scale": [1, 0.8, 1]}},
        {"id": "petals", "op": "cylinder", "radius": 3.2, "height": 0.03, "segments": 8, "caps": True,
         "material": "petals", "transform": {"translate": [-11.0, 0.02, -9.2]}},
    ]
    # ---- the flagpole in the yard
    N += [
        {"id": "pole", "op": "cylinder", "radius": 0.07, "height": 9.0, "segments": 5, "caps": False,
         "material": "metal", "transform": {"translate": [10.5, 4.5, -11.0]}},
        {"id": "pole_ball", "op": "sphere", "radius": 0.15, "rings": 3, "segments": 6, "material": "gold",
         "transform": {"translate": [10.5, 9.1, -11.0]}},
        card("flag_cloth", [2.1, 1.4, 0.01], [9.35, 8.0, -11.0], "flag"),
        slab("yard_path", [4.0, 0.06, 5.0], [0, 0.03, -11.5], "stone", ("bottom",)),
    ]
    return {
        "format": "mei-asset", "version": 1, "name": "schoolhouse",
        "budget": {"vertices": 1500, "triangles": 1800},
        "sheets": {"art": {"image": "art/schoolhouse_sheet.png"}},
        "materials": mats,
        "lighting": {"mode": "vertical", "ambient": 0.55},
        "verification": {"required": True, "depth": True, "perspective": True, "scale": "world", "far": 200},
        "nodes": N,
    }


if __name__ == "__main__":
    make_art()
    with open(os.path.join(HERE, "schoolhouse.asset.json"), "w") as f:
        json.dump(recipe(), f, indent=1)
        f.write("\n")
