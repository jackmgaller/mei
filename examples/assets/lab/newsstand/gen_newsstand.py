#!/usr/bin/env python3
"""Writes art/newsstand_sheet.png (+ .sheet.json), art/cat_face.png and newsstand.asset.json
for the station newsstand (run from anywhere; needs Pillow and the macOS Hiragino font)."""
import json
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "art")
os.makedirs(ART, exist_ok=True)
FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc"

BLUE = (42, 108, 180)
DBLUE = (27, 72, 128)
WHITE = (242, 239, 230)
YELLOW = (240, 196, 60)
RED = (216, 64, 47)
INK = (40, 38, 44)


def hsh(a, b=0, c=0):
    h = (a * 374761393 + b * 668265263 + c * 1442695041 + 12345) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return (h ^ (h >> 16)) & 0xFFFF


def font(size):
    return ImageFont.truetype(FONT, size)


def text(d, xy, s, size, fill):
    d.fontmode = "1"
    d.text(xy, s, font=font(size), fill=fill)


def box(d, x0, y0, x1, y1, fill):
    d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=fill)


# ------------------------------------------------------------------ sprites

def sign():
    """160 x 24: the fascia. Blue board, yellow rule, white katakana."""
    im = Image.new("RGB", (168, 24), BLUE)
    d = ImageDraw.Draw(im)
    box(d, 0, 0, 168, 2, WHITE)
    box(d, 0, 22, 168, 24, WHITE)
    text(d, (41, 1), "キオスク", 21, WHITE)
    box(d, 3, 4, 35, 20, YELLOW)
    text(d, (3, 4), "新聞", 16, INK)
    box(d, 132, 4, 164, 20, YELLOW)
    text(d, (132, 4), "雑誌", 16, INK)
    return im


def goods():
    """128 x 56: the wall of shelves behind the counter. Three shelves of small boxes and tins."""
    im = Image.new("RGB", (128, 56), (74, 56, 44))
    d = ImageDraw.Draw(im)
    pal = [(216, 64, 47), (240, 196, 60), (60, 140, 90), (232, 232, 220), (60, 110, 190),
           (230, 130, 150), (240, 150, 50), (110, 80, 160), (150, 200, 220), (180, 60, 90)]
    for shelf in range(3):
        y_bot = 18 + shelf * 18
        x = 1
        n = 0
        while x < 126:
            w = 5 + hsh(shelf, n, 1) % 6
            h = 7 + hsh(shelf, n, 2) % 8
            c = pal[hsh(shelf, n, 3) % len(pal)]
            kind = hsh(shelf, n, 4) % 3
            if kind == 0:
                # a small box with a lighter label band
                box(d, x, y_bot - h, x + w, y_bot, c)
                box(d, x + 1, y_bot - h // 2 - 1, x + w - 1, y_bot - h // 2 + 2, (240, 236, 224))
            elif kind == 1:
                # a tin with a lid
                box(d, x, y_bot - h, x + w, y_bot, c)
                box(d, x, y_bot - h, x + w, y_bot - h + 1, (210, 210, 210))
            else:
                # a bag, leaning on the next thing
                box(d, x, y_bot - h, x + w, y_bot, c)
                box(d, x, y_bot - h, x + 2, y_bot - h + 2, (80, 56, 44))
                box(d, x + w - 2, y_bot - h, x + w, y_bot - h + 2, (80, 56, 44))
            x += w + 1 + hsh(shelf, n, 5) % 2
            n += 1
        box(d, 0, y_bot, 128, y_bot + 2, (150, 112, 74))  # the shelf board
    box(d, 0, 0, 128, 1, (40, 30, 24))
    return im


def mags():
    """64 x 48: eight magazine covers (16 x 24), four across."""
    im = Image.new("RGB", (64, 48), (60, 60, 70))
    d = ImageDraw.Draw(im)
    heads = [(220, 60, 90), (60, 120, 200), (240, 190, 50), (80, 170, 110),
             (200, 90, 200), (240, 130, 60), (70, 180, 200), (150, 80, 60)]
    skin = (240, 205, 175)
    for i in range(8):
        cx, cy = (i % 4) * 16, (i // 4) * 24
        base = heads[i]
        box(d, cx, cy, cx + 16, cy + 24, tuple(min(255, int(c * 0.35 + 170)) for c in base))
        box(d, cx, cy, cx + 16, cy + 4, base)                       # the masthead
        box(d, cx + 2, cy + 1, cx + 9 + hsh(i) % 4, cy + 3, WHITE)
        k = hsh(i, 9) % 3
        if k == 0:                                                   # a face
            box(d, cx + 5, cy + 6, cx + 11, cy + 14, skin)
            box(d, cx + 4, cy + 5, cx + 12, cy + 8, (50, 40, 40))
            box(d, cx + 3, cy + 14, cx + 13, cy + 24, base)
        elif k == 1:                                                 # a big round thing
            for y in range(24):
                for x in range(16):
                    if (x - 8) ** 2 + (y - 12) ** 2 < 25:
                        d.point((cx + x, cy + y), fill=base)
            box(d, cx + 6, cy + 10, cx + 10, cy + 14, WHITE)
        else:                                                        # a car, going
            box(d, cx + 2, cy + 11, cx + 14, cy + 16, base)
            box(d, cx + 5, cy + 8, cx + 11, cy + 11, base)
            box(d, cx + 3, cy + 16, cx + 6, cy + 18, INK)
            box(d, cx + 10, cy + 16, cx + 13, cy + 18, INK)
        for j in range(3):                                           # cover lines
            box(d, cx + 2, cy + 19 + j * 2, cx + 14 - hsh(i, j) % 6, cy + 20 + j * 2, (40, 40, 40))
        box(d, cx + 14, cy, cx + 15, cy + 24, (255, 255, 255)) if False else None
    return im


def hang():
    """128 x 20 with clear gaps: magazines pegged to a string, a cut-out."""
    im = Image.new("RGBA", (128, 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    box(d, 0, 0, 128, 1, (60, 50, 40, 255))
    heads = [(220, 60, 90), (60, 120, 200), (240, 190, 50), (80, 170, 110), (200, 90, 200),
             (240, 130, 60), (70, 180, 200), (150, 80, 60), (90, 90, 200), (220, 100, 60)]
    x = 2
    n = 0
    while x < 118:
        w = 9 + hsh(n, 2) % 3
        h = 14 + hsh(n, 3) % 5
        c = heads[hsh(n, 4) % len(heads)]
        box(d, x, 1, x + w, 1 + h, c + (255,))
        box(d, x + 1, 2, x + w - 1, 4, (240, 236, 224, 255))
        box(d, x + 2, 7, x + w - 2, 11, (240, 205, 175, 255) if hsh(n, 5) % 2 else (255, 255, 255, 255))
        box(d, x + 2, 13, x + w - 1, 14, (40, 40, 40, 255))
        box(d, x + w // 2, 0, x + w // 2 + 1, 2, (230, 210, 120, 255))  # the clip
        x += w + 2
        n += 1
    return im


def valance():
    """96 x 12: striped scalloped valance with a clear scalloped edge, a cut-out."""
    im = Image.new("RGBA", (96, 12), (0, 0, 0, 0))
    for x in range(96):
        col = BLUE if (x // 6) % 2 == 0 else WHITE
        r = 3 - abs(x % 6 - 2.5) * 0.0
        depth = 12 - [0, 1, 2, 2, 1, 0][x % 6]
        for y in range(depth):
            im.putpixel((x, y), col + (255,))
    return im


def board():
    """32 x 48: the extra-edition sandwich board, "go-gai"."""
    im = Image.new("RGB", (32, 48), (236, 226, 190))
    d = ImageDraw.Draw(im)
    box(d, 0, 0, 32, 3, DBLUE)
    box(d, 0, 45, 32, 48, DBLUE)
    box(d, 0, 0, 2, 48, DBLUE)
    box(d, 30, 0, 32, 48, DBLUE)
    box(d, 3, 4, 29, 26, RED)
    text(d, (3, 8), "号外", 13, WHITE)
    for j in range(5):
        box(d, 4, 29 + j * 3, 28 - hsh(j) % 8, 30 + j * 3, (50, 44, 40))
    return im


def poster(i):
    """24 x 32: a festival poster."""
    cols = [((236, 214, 120), RED, DBLUE), ((150, 210, 220), (240, 120, 60), (40, 70, 110))][i]
    im = Image.new("RGB", (24, 32), cols[0])
    d = ImageDraw.Draw(im)
    box(d, 0, 0, 24, 2, cols[2])
    box(d, 0, 30, 24, 32, cols[2])
    for y in range(32):
        for x in range(24):
            if (x - 12) ** 2 + (y - 13) ** 2 < 50:
                d.point((x, y), fill=cols[1])
    text(d, (4, 20), "祭" if i == 0 else "夏", 14, cols[2])
    for j in range(2):
        box(d, 3, 2 + j * 0, 3 + 4 + j * 6, 3, cols[2])
    return im


def plate(s, bg, fg, size=13):
    im = Image.new("RGB", (40, 16), bg)
    d = ImageDraw.Draw(im)
    box(d, 0, 0, 40, 1, fg)
    box(d, 0, 15, 40, 16, fg)
    text(d, (2, 1), s, size, fg)
    return im


def fridge():
    """32 x 56: a drinks fridge with a glass door, three shelves of bottles and cans, lit from within."""
    im = Image.new("RGB", (32, 56), (200, 214, 226))
    d = ImageDraw.Draw(im)
    box(d, 0, 0, 32, 56, (44, 52, 64))
    box(d, 2, 6, 30, 52, (176, 210, 230))
    box(d, 3, 1, 29, 5, (240, 240, 235))
    box(d, 5, 2, 13, 4, RED)
    pal = [(216, 64, 47), (240, 196, 60), (60, 140, 90), (60, 110, 190), (230, 130, 50),
           (110, 80, 160), (240, 240, 240), (150, 100, 60)]
    for r in range(3):
        yb = 20 + r * 15
        x = 3
        n = 0
        while x < 28:
            w = 3 + hsh(r, n, 11) % 2
            h = 8 + hsh(r, n, 12) % 5
            c = pal[hsh(r, n, 13) % len(pal)]
            box(d, x, yb - h, x + w, yb, c)
            box(d, x, yb - h, x + w, yb - h + 2, (230, 230, 225))
            x += w + 1
            n += 1
        box(d, 2, yb, 30, yb + 1, (110, 130, 150))
    box(d, 27, 22, 28, 34, (200, 200, 205))  # the handle
    return im


def clock():
    """24 x 24 round, clear corners: a station clock at ten to eight."""
    im = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    for y in range(24):
        for x in range(24):
            r2 = (x - 11.5) ** 2 + (y - 11.5) ** 2
            if r2 < 11.6 ** 2:
                im.putpixel((x, y), INK + (255,))
            if r2 < 9.6 ** 2:
                im.putpixel((x, y), (244, 240, 228, 255))
    d = ImageDraw.Draw(im)
    for k in range(12):
        import math
        a = k * math.pi / 6
        px, py = 11.5 + 8.2 * math.sin(a), 11.5 - 8.2 * math.cos(a)
        d.point((int(round(px)), int(round(py))), fill=INK + (255,))
    for (x, y) in [(11, 11), (11, 10), (11, 9), (11, 8), (11, 7), (11, 6), (11, 5), (12, 11),
                   (12, 12), (13, 12), (14, 13), (15, 13)]:
        d.point((x, y), fill=INK + (255,))
    d.point((10, 12), fill=RED + (255,))
    return im


def emblem():
    """24 x 24 round, clear corners: the station mark, a red ring round the character for station."""
    im = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    for y in range(24):
        for x in range(24):
            r2 = (x - 11.5) ** 2 + (y - 11.5) ** 2
            if r2 < 11.6 ** 2:
                im.putpixel((x, y), RED + (255,))
            if r2 < 9.0 ** 2:
                im.putpixel((x, y), WHITE + (255,))
    d = ImageDraw.Draw(im)
    text(d, (5, 4), "駅", 14, RED)
    return im


def door():
    """24 x 48: the staff door at the back, a window in the top and a plain brass handle."""
    im = Image.new("RGB", (24, 48), (84, 72, 64))
    d = ImageDraw.Draw(im)
    box(d, 0, 0, 24, 48, (44, 56, 70))
    box(d, 2, 2, 22, 48, (140, 108, 78))
    for x in range(3, 22, 4):
        box(d, x, 20, x + 1, 48, (120, 90, 64))
    box(d, 4, 5, 20, 17, (170, 205, 226))
    box(d, 11, 5, 13, 17, (140, 108, 78))
    box(d, 4, 10, 20, 12, (140, 108, 78))
    box(d, 5, 6, 8, 9, (225, 240, 245))
    box(d, 18, 28, 20, 33, (230, 196, 90))
    return im


def cat_face():
    """32 x 16, wraps once round the head: white cat, closed eyes, red cheeks and a small nose."""
    im = Image.new("RGB", (32, 16), (244, 240, 230))
    px = im.putpixel
    c = 8
    for ex in (c - 3, c + 3):
        px((ex - 1, 9), INK)
        px((ex, 9), INK)
        px((ex + 1, 9), INK)
    px((c, 11), (230, 110, 120))
    px((c - 1, 12), INK)
    px((c + 1, 12), INK)
    px((c, 12), INK)
    for bx in (c - 5, c + 5):
        px((bx, 11), (240, 170, 160))
        px((bx + 1, 11), (240, 170, 160))
    # three whisker ticks each side, kept short
    for sx in (c - 6, c + 6):
        px((sx, 10), (150, 150, 150))
        px((sx, 12), (150, 150, 150))
    for y in range(0, 5):  # a tuft of orange on top of the head
        for x in range(32):
            if (x - c) ** 2 < 12 and y < 3:
                px((x, y), (230, 160, 70))
    return im


def make_art():
    cells = [("sign", sign()), ("goods", goods()), ("mags", mags()), ("hang", hang()),
             ("valance", valance()), ("board", board()), ("poster_a", poster(0)),
             ("poster_b", poster(1)), ("door", door()), ("fridge", fridge()), ("clock", clock()),
             ("emblem", emblem()), ("tobacco", plate("たばこ", RED, WHITE)),
             ("card", plate("テレカ", (240, 196, 60), INK))]
    sheet = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    rects = {}
    x = y = row_h = 0
    for name, im in cells:
        im = im.convert("RGBA")
        if x + im.width > 256:
            x, y, row_h = 0, y + row_h, 0
        sheet.paste(im, (x, y))
        rects[name] = [x, y, im.width, im.height]
        x += im.width
        row_h = max(row_h, im.height)
    sheet = sheet.crop((0, 0, 256, y + row_h))
    sheet.save(os.path.join(ART, "newsstand_sheet.png"))
    with open(os.path.join(ART, "newsstand_sheet.sheet.json"), "w") as f:
        json.dump({"format": "mei-sheet", "version": 1, "cells": rects}, f, indent=1)
        f.write("\n")
    cat_face().save(os.path.join(ART, "cat_face.png"))


# ------------------------------------------------------------------ recipe

def tex_fit(cell, bits=4, emissive=False, color="#ffffff", double=False, tag=None):
    m = {"color": color, "texture": {"sheet": "art", "cell": cell, "bits": bits, "projection": "fit"}}
    if emissive:
        m["class"] = "emissive"
    if double:
        m["double_sided"] = True
    if tag:
        m["tag"] = tag
    return m


def card(id_, size, pos, mat, facing="back", rot=None):
    """A box with one face left: a flat card showing its texture on the `facing` side."""
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


CANDY = ["".join("0" if (x % 4 == 3) else str(1 + hsh(x // 4, y // 3, 7) % 4) for x in range(8)) for y in range(8)]


def recipe():
    mats = {
        "enamel": {"color": "#2a6cb4", "tag": "wall",
                   "texture": {"pattern": "tile", "size": 16, "colors": ["#2f72bc", "#1f5590"],
                               "params": {"count": 2, "grout": 1}, "projection": "box",
                               "scale": [0.8, 0.8]}},
        "concrete": {"color": "#8a8a84", "tag": "floor",
                     "texture": {"pattern": "speckle", "size": 16,
                                 "colors": ["#8c8c86", "#7a7a76", "#9c9c94", "#6c7468"],
                                 "params": {"density": 0.3, "seed": 3}, "projection": "box",
                                 "scale": [0.6, 0.6]}},
        "roof": {"color": "#7a8088", "tag": "roof",
                 "texture": {"pattern": "stripes", "size": 16, "colors": ["#8a9098", "#6a7078"],
                             "params": {"count": 8, "axis": "u"}, "projection": "box",
                             "scale": [0.6, 0.6]}},
        "laminate": {"color": "#b8895a", "tag": "counter",
                     "texture": {"pattern": "grain", "size": 16, "colors": ["#c49a68", "#a87a4c", "#b78856"],
                                 "params": {"rings": 3, "waves": 1}, "projection": "box",
                                 "scale": [0.8, 0.8]}},
        "news": {"color": "#dcd8cc",
                 "texture": {"pattern": "stripes", "size": 16, "colors": ["#e6e2d6", "#b9b5aa", "#d4d0c4"],
                             "params": {"count": 8, "axis": "v"}, "projection": "box",
                             "scale": [0.3, 0.3]}},
        "candy": {"color": "#d06060",
                  "texture": {"texels": CANDY,
                              "colors": ["#2a2a30", "#d84a3a", "#f0c040", "#4aa060", "#3a78c8"],
                              "projection": "box", "scale": [0.16, 0.1]}},
        "trim": {"color": "#e8e4d8"},
        "dark": {"color": "#33363c"},
        "shutter": {"color": "#8a9aa8"},
        "wood": {"color": "#8a6a48"},
        "paper": {"color": "#d8c8a0"},
        "metal": {"color": "#a0a4a8"},
        "sign": tex_fit("sign", bits=4, emissive=True, tag="sign"),
        "goods": tex_fit("goods", bits=8),
        "mags": tex_fit("mags", bits=8),
        "hang": tex_fit("hang", bits=8, double=True),
        "valance": tex_fit("valance", bits=4, double=True),
        "board": tex_fit("board", bits=4),
        "poster_a": tex_fit("poster_a", bits=4),
        "poster_b": tex_fit("poster_b", bits=4),
        "tobacco": tex_fit("tobacco", bits=4),
        "card": tex_fit("card", bits=4),
        "fridge": tex_fit("fridge", bits=8),
        "clock": {"color": "#f4f0e4", "texture": {"sheet": "art", "cell": "clock", "bits": 4,
                                                  "projection": "disc", "axis": "y"}},
        "emblem": {"color": "#d8402f", "texture": {"sheet": "art", "cell": "emblem", "bits": 4,
                                                   "projection": "disc", "axis": "y"}},
        "door": tex_fit("door", bits=4, tag="door"),
        "cream": {"color": "#e8e2d0", "tag": "wall"},
        "stool": {"color": "#b8433a"},
        "cat": {"color": "#f4f0e6", "smooth": True},
        "cat_head": {"color": "#f4f0e6", "smooth": True,
                     "texture": {"image": "art/cat_face.png", "projection": "cylindrical",
                                 "scale": [0.5341, 0.2], "offset": [0.25, 0.5]}},
        "cat_red": {"color": "#c8352c"},
        "cat_gold": {"color": "#e8bc3c"},
        "ash": {"color": "#c0392b"},
    }
    N = []
    # ---- the shell
    N += [
        slab("plinth", [3.1, 0.1, 1.9], [0, 0.05, -0.1], "concrete"),
        slab("back", [2.76, 2.34, 0.08], [0, 1.27, 0.7], "enamel"),
        {"id": "sides", "op": "group", "children": [
            slab("side", [0.08, 2.35, 1.5], [1.36, 1.275, 0.0], "enamel")],
         "modifiers": [{"op": "mirror", "axis": "x"}]},
        slab("counter_front", [2.7, 0.9, 0.1], [0, 0.55, -0.72], "enamel", ("bottom", "top")),
        slab("counter_top", [2.9, 0.06, 0.9], [0, 1.02, -0.78], "laminate", ()),
        slab("fascia", [2.9, 0.5, 0.16], [0, 2.22, -0.73], "enamel"),
        card("sign", [2.66, 0.38, 0.01], [0, 2.22, -0.825], "sign"),
        {"id": "shutter_box", "op": "cylinder", "radius": 0.07, "height": 2.6, "segments": 8,
         "material": "shutter", "transform": {"rotate": [0, 0, 90], "translate": [0, 1.9, -0.62]}},
        slab("roof", [3.3, 0.1, 2.1], [0, 2.48, -0.1], "roof", ()),
        card("valance", [3.3, 0.2, 0.01], [0, 2.3, -1.16], "valance"),
    ]
    # ---- the shelves behind the counter
    N += [
        card("goods", [2.56, 1.12, 0.01], [0, 1.58, 0.64], "goods"),
        slab("shelf_a", [2.56, 0.04, 0.26], [0, 1.78, 0.52], "wood", ()),
        slab("shelf_b", [2.56, 0.04, 0.26], [0, 1.42, 0.52], "wood", ()),
        card("hang", [2.4, 0.4, 0.01], [0, 1.75, -0.6], "hang"),
    ]
    # ---- on the counter
    N += [
        slab("news_stack_a", [0.5, 0.12, 0.36], [-0.9, 1.11, -0.8], "news"),
        slab("news_stack_b", [0.42, 0.08, 0.3], [-0.88, 1.205, -0.8], "news", ("bottom",),
             rot=[0, 8, 0]),
        slab("candy_box", [0.5, 0.14, 0.3], [0.85, 1.12, -0.85], "candy"),
        {"id": "radio", "op": "group", "children": [
            slab("radio_body", [0.28, 0.16, 0.1], [-0.3, 1.13, -0.55], "dark"),
            {"id": "radio_ant", "op": "cylinder", "radius": 0.006, "height": 0.34, "segments": 3,
             "caps": False, "material": "metal",
             "transform": {"rotate": [0, 0, -20], "translate": [-0.2, 1.36, -0.55]}},
        ]},
    ]
    # ---- trim, vent, clock, emblem
    N += [
        {"id": "corner_trims", "op": "group", "children": [
            slab("corner_trim", [0.08, 2.36, 0.08], [1.43, 1.28, -0.785], "cream")],
         "modifiers": [{"op": "mirror", "axis": "x"}]},
        slab("gutter", [3.34, 0.07, 0.07], [0, 2.43, -1.17], "cream", ()),
        {"id": "vent_pipe", "op": "cylinder", "radius": 0.1, "height": 0.16, "segments": 6,
         "caps": False, "material": "shutter", "transform": {"translate": [0.9, 2.61, 0.3]}},
        {"id": "vent_cap", "op": "cone", "radius": 0.17, "height": 0.1, "segments": 6,
         "material": "shutter", "transform": {"translate": [0.9, 2.74, 0.3]}},
        {"id": "clock", "op": "cylinder", "radius": 0.17, "height": 0.04, "segments": 12,
         "material": "clock", "transform": {"rotate": [0, 0, -90], "translate": [1.43, 1.9, -0.3]}},
        {"id": "emblem", "op": "cylinder", "radius": 0.17, "height": 0.04, "segments": 12,
         "material": "emblem", "transform": {"rotate": [0, 0, 90], "translate": [-1.43, 1.9, -0.3]}},
    ]
    # ---- inside: a drinks fridge against the back wall
    N += [
        slab("fridge_body", [0.62, 1.85, 0.5], [-0.95, 1.025, 0.38], "dark", ("bottom",)),
        card("fridge_door", [0.5, 0.88, 0.01], [-0.95, 1.5, 0.125], "fridge"),
    ]
    # ---- the stool and crates beside the board
    N += [
        slab("crate_a", [0.42, 0.28, 0.3], [-1.05, 0.14, -1.0], "candy", ("bottom",)),
        slab("crate_b", [0.42, 0.28, 0.3], [-1.04, 0.425, -1.0], "candy", ("bottom",), rot=[0, 6, 0]),
        {"id": "stool_seat", "op": "cylinder", "radius": 0.15, "height": 0.05, "segments": 8,
         "material": "stool", "transform": {"translate": [0.35, 0.40, -1.3]}},
        {"id": "stool_legs", "op": "group", "children": [
            {"id": "stool_leg", "op": "cylinder", "radius": 0.015, "height": 0.38, "segments": 3,
             "caps": False, "material": "metal", "transform": {"translate": [0.1, 0.19, 0.0]}}],
         "modifiers": [{"op": "radial", "count": 3}], "transform": {"translate": [0.35, 0, -1.3]}},
    ]
    # ---- the back: staff door, step, downpipe, a meter box
    N += [
        card("back_door", [0.5, 1.0, 0.01], [0.5, 0.62, 0.745], "door", facing="front"),
        slab("back_step", [0.7, 0.06, 0.4], [0.5, 0.03, 1.0], "concrete"),
        {"id": "downpipe", "op": "cylinder", "radius": 0.03, "height": 2.3, "segments": 4,
         "caps": False, "material": "metal", "transform": {"translate": [-1.3, 1.25, 0.775]}},
        slab("meter_box", [0.26, 0.34, 0.1], [-0.6, 1.5, 0.79], "metal", ("back",)),
    ]
    # ---- the lucky cat
    N += [
        {"id": "cat_body", "op": "sphere", "radius": 0.1, "rings": 3, "segments": 8, "material": "cat",
         "transform": {"translate": [0.25, 1.14, -0.82], "scale": [1, 1.1, 0.9]}},
        {"id": "cat_head", "op": "sphere", "radius": 0.085, "rings": 3, "segments": 8,
         "material": "cat_head", "transform": {"translate": [0.25, 1.32, -0.84]}},
        {"id": "cat_ears", "op": "group", "children": [
            {"id": "cat_ear", "op": "cone", "radius": 0.028, "height": 0.05, "segments": 3,
             "material": "cat", "transform": {"translate": [0.055, 1.4, -0.84]}}],
         "modifiers": [{"op": "mirror", "axis": "x", "offset": 0.25}]},
        {"id": "cat_collar", "op": "cylinder", "radius": 0.082, "height": 0.025, "segments": 6,
         "caps": False, "material": "cat_red", "transform": {"translate": [0.25, 1.23, -0.83]}},
        {"id": "cat_paw", "op": "box", "size": [0.04, 0.09, 0.04], "material": "cat",
         "transform": {"rotate": [0, 0, -15], "translate": [0.36, 1.27, -0.88]}},
        {"id": "cat_coin", "op": "box", "size": [0.05, 0.065, 0.012], "material": "cat_gold",
         "transform": {"translate": [0.25, 1.14, -0.9]}},
    ]
    # ---- the front: magazine racks, plates, the sandwich board, the ashtray
    N += [
        {"id": "racks", "op": "group", "children": [
            card("rack", [1.0, 0.64, 0.02], [0.72, 0.5, -0.83], "mags", rot=[-12, 0, 0]),
            slab("rack_ledge", [1.0, 0.03, 0.1], [0.72, 0.17, -0.87], "dark", ("bottom",)),
        ], "modifiers": [{"op": "mirror", "axis": "x"}]},
        card("plate_tobacco", [0.4, 0.16, 0.01], [-1.05, 0.9, -0.79], "tobacco"),
        card("plate_card", [0.4, 0.16, 0.01], [1.05, 0.9, -0.79], "card"),
        card("board_front", [0.46, 0.74, 0.02], [-1.0, 0.39, -1.42], "board", rot=[10, 0, 0]),
        slab("board_back", [0.46, 0.74, 0.02], [-1.0, 0.39, -1.18], "wood", ("bottom",), rot=[-10, 0, 0]),
        {"id": "ash_pole", "op": "cylinder", "radius": 0.018, "height": 0.8, "segments": 5,
         "caps": False, "material": "ash", "transform": {"translate": [1.25, 0.4, -1.4]}},
        {"id": "ash_bowl", "op": "cylinder", "radius": 0.1, "height": 0.1, "segments": 8,
         "material": "ash", "transform": {"translate": [1.25, 0.85, -1.4]}},
        card("poster_l", [0.01, 0.64, 0.48], [-1.405, 1.2, 0.25], "poster_a", facing="left"),
        card("poster_r", [0.01, 0.64, 0.48], [1.405, 1.2, 0.25], "poster_b", facing="right"),
    ]
    return {
        "format": "mei-asset", "version": 1, "name": "newsstand",
        "budget": {"vertices": 1024, "triangles": 1000},
        "sheets": {"art": {"image": "art/newsstand_sheet.png"}},
        "materials": mats,
        "lighting": {"mode": "vertical", "ambient": 0.55},
        "verification": {"required": True, "depth": True, "perspective": True},
        "nodes": N,
    }


if __name__ == "__main__":
    make_art()
    with open(os.path.join(HERE, "newsstand.asset.json"), "w") as f:
        json.dump(recipe(), f, indent=1)
        f.write("\n")
