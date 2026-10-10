#!/usr/bin/env python3
"""Console lab, look 03 Eclipse Black: writes art/eclipse_black.png (+ .sheet.json),
console.asset.json and controller.asset.json beside this script.

Metres at real size, Y up, the console's front (ports) and the controller's player side
facing -Z. Needs Pillow and the macOS Hiragino and Futura fonts to redraw the sheet.
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ART = HERE / "art"

# Colours shared by both models.
CHARCOAL = "#4a4a52"
PLINTH = "#18181b"
MOON = "#121216"
GOLD = "#d9b057"
GRAPHITE = "#26262b"
NEAR_BLACK = "#0d0d0f"
SUN = "#f29a3a"
MOONBLUE = "#a6c8f2"

R2 = lambda v: round(v, 5)


# ---------------------------------------------------------------- the sheet

def font(path, size, index=0):
    return ImageFont.truetype(path, size, index=index)


def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def draw_emblem(size=32):
    """明 on black, the 日 in sun orange and the 月 in moon blue (disc texture)."""
    ss = 8
    big = size * ss
    mask = Image.new("L", (big, big), 0)
    d = ImageDraw.Draw(mask)
    f = font("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", int(big * 0.70))
    box = d.textbbox((0, 0), "明", font=f)
    w, h = box[2] - box[0], box[3] - box[1]
    d.text(((big - w) / 2 - box[0], (big - h) / 2 - box[1]), "明", font=f, fill=255)
    # Colour by connected stroke: 日 is the component whose centre lies left of the glyph's
    # middle, everything else (月, with the sweep of its leg under the 日) is the moon.
    gx0, _, gx1, _ = mask.getbbox()
    mid = (gx0 + gx1) / 2
    label = [[-1] * big for _ in range(big)]
    is_sun = {}
    for y0 in range(big):
        for x0 in range(big):
            if mask.getpixel((x0, y0)) < 40 or label[y0][x0] >= 0:
                continue
            comp = len(is_sun)
            stack, sx, cnt = [(x0, y0)], 0, 0
            label[y0][x0] = comp
            while stack:
                x, y = stack.pop()
                sx += x
                cnt += 1
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < big and 0 <= ny < big and label[ny][nx] < 0 \
                            and mask.getpixel((nx, ny)) >= 40:
                        label[ny][nx] = comp
                        stack.append((nx, ny))
            is_sun[comp] = sx / cnt < mid - (gx1 - gx0) * 0.12
    sun, moon, bg = hexrgb(SUN), hexrgb(MOONBLUE), hexrgb(MOON)
    img = Image.new("RGB", (big, big), bg)
    px = img.load()
    for y in range(big):
        for x in range(big):
            a = mask.getpixel((x, y))
            if a:
                # faint edge pixels take their nearest labelled neighbour's colour
                comp = label[y][x]
                if comp < 0:
                    for r in range(1, 4):
                        near = [label[yy][xx] for yy in range(max(0, y - r), min(big, y + r + 1))
                                for xx in range(max(0, x - r), min(big, x + r + 1))
                                if label[yy][xx] >= 0]
                        if near:
                            comp = near[0]
                            break
                c = sun if comp >= 0 and is_sun[comp] else moon
                px[x, y] = tuple(round(bg[i] + (c[i] - bg[i]) * a / 255) for i in range(3))
    return img.resize((size, size), Image.LANCZOS)


def draw_wordmark(w=64, h=16):
    """MEI in gold, spaced, on the body's charcoal (fit texture on the front plaque)."""
    ss = 8
    img = Image.new("RGB", (w * ss, h * ss), hexrgb(CHARCOAL))
    d = ImageDraw.Draw(img)
    f = font("/System/Library/Fonts/Supplemental/Futura.ttc", int(h * ss * 0.92), index=0)
    text = "M E I"
    box = d.textbbox((0, 0), text, font=f)
    tw, th = box[2] - box[0], box[3] - box[1]
    d.text(((w * ss - tw) / 2 - box[0], (h * ss - th) / 2 - box[1]), text, font=f,
           fill=hexrgb("#d8b360"))
    return img.resize((w, h), Image.LANCZOS)


def draw_port(w=24, h=12):
    """A controller socket: graphite frame, black mouth, a row of gold contacts."""
    img = Image.new("RGB", (w, h), hexrgb("#222226"))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2, 2, w - 3, h - 3], radius=3, fill=hexrgb("#050506"))
    for i in range(7):
        x = 5 + i * 2
        d.point((x, h // 2), fill=hexrgb("#a08040"))
    return img


def draw_cart_label(w=48, h=32):
    """The cart in the slot: a night-sky label with a gold eclipse ring."""
    ss = 8
    W, H = w * ss, h * ss
    img = Image.new("RGB", (W, H), (0, 0, 0))
    px = img.load()
    top, bot = hexrgb("#0e1430"), hexrgb("#33416e")
    for y in range(H):
        t = y / (H - 1)
        c = tuple(round(top[i] + (bot[i] - top[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = c
    d = ImageDraw.Draw(img)
    # hills
    d.polygon([(0, H), (0, H * 0.78), (W * 0.25, H * 0.66), (W * 0.5, H * 0.8),
               (W * 0.72, H * 0.62), (W, H * 0.74), (W, H)], fill=hexrgb("#0a0c18"))
    # eclipse: gold corona ring, black moon, diamond bead
    cx, cy, r = W * 0.5, H * 0.42, H * 0.24
    d.ellipse([cx - r * 1.12, cy - r * 1.12, cx + r * 1.12, cy + r * 1.12], fill=hexrgb("#e8c06a"))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=hexrgb("#06070c"))
    bx, by = cx + r * 0.78, cy - r * 0.78
    d.ellipse([bx - ss * 1.8, by - ss * 1.8, bx + ss * 1.8, by + ss * 1.8], fill=hexrgb("#fff6dc"))
    # top band of the label
    d.rectangle([0, 0, W, H * 0.12], fill=hexrgb("#08080a"))
    d.rectangle([0, H * 0.12, W, H * 0.12 + ss * 0.6], fill=hexrgb("#c9a24c"))
    return img.resize((w, h), Image.LANCZOS)


def draw_vent(w=16, h=16):
    img = Image.new("RGB", (w, h), hexrgb(CHARCOAL))
    d = ImageDraw.Draw(img)
    for y in range(1, h, 4):
        d.rectangle([0, y, w - 1, y + 1], fill=hexrgb("#0b0b0d"))
    return img


def write_sheet():
    ART.mkdir(exist_ok=True)
    cells = {
        "emblem": draw_emblem(),
        "wordmark": draw_wordmark(),
        "port": draw_port(),
        "cart_label": draw_cart_label(),
        "vent": draw_vent(),
    }
    W = max(c.width for c in cells.values())
    H = sum(c.height for c in cells.values())
    sheet = Image.new("RGB", (W, H), (0, 0, 0))
    rects, y = {}, 0
    for name, c in cells.items():
        sheet.paste(c, (0, y))
        rects[name] = [0, y, c.width, c.height]
        y += c.height
    sheet.save(ART / "eclipse_black.png")
    (ART / "eclipse_black.sheet.json").write_text(json.dumps(
        {"format": "mei-sheet", "version": 1, "cells": rects}, indent=2) + "\n")


# ---------------------------------------------------------------- helpers

def node(id, op, mat=None, t=None, r=None, s=None, **kw):
    n = {"id": id, "op": op}
    n.update(kw)
    if mat:
        n["material"] = mat
    tr = {}
    if s:
        tr["scale"] = s
    if r:
        tr["rotate"] = r
    if t:
        tr["translate"] = [R2(v) for v in t]
    if tr:
        n["transform"] = tr
    return n


def box(id, mat, size, t, **kw):
    return node(id, "box", mat, t, size=[R2(v) for v in size], **kw)


def lathe(id, mat, profile, segs, t, caps=True):
    return node(id, "lathe", mat, t, profile=[[R2(a), R2(b)] for a, b in profile],
                segments=segs, caps=caps)


def rounded_rect(w, d, r, n=4, cz=0.0):
    """Clockwise-from-above-agnostic rounded rectangle, n points per corner."""
    pts = []
    corners = [(w / 2 - r, d / 2 - r, 0), (-w / 2 + r, d / 2 - r, 90),
               (-w / 2 + r, -d / 2 + r, 180), (w / 2 - r, -d / 2 + r, 270)]
    for cx, cz0, a0 in corners:
        for i in range(n):
            a = math.radians(a0 + 90 * i / (n - 1))
            pts.append([R2(cx + r * math.cos(a)), R2(cz0 + r * math.sin(a) + cz)])
    return pts


def offset_outline(pts, d):
    """Move each point of a closed counter-clockwise outline inward by d."""
    out = []
    n = len(pts)
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        def nrm(a, b):
            ex, ez = b[0] - a[0], b[1] - a[1]
            L = math.hypot(ex, ez)
            return (-ez / L, ex / L)   # left normal: inward for a CCW outline
        n1, n2 = nrm(p0, p1), nrm(p1, p2)
        bx, bz = n1[0] + n2[0], n1[1] + n2[1]
        L = math.hypot(bx, bz)
        bx, bz = bx / L, bz / L
        cosh = bx * n1[0] + bz * n1[1]
        k = d / max(cosh, 0.5)
        out.append([R2(p1[0] + bx * k), R2(p1[1] + bz * k)])
    return out


VERIFY = {"required": True, "depth": True, "perspective": True}


# ---------------------------------------------------------------- console

def console():
    W, D = 0.300, 0.235            # footprint
    TOP = 0.068                    # flat top
    FZ = -D / 2                    # front face plane
    DISC_Z = -0.026                # the eclipse's centre
    RING = 0.076                   # gold ring's outer radius

    mats = {
        "body": {"color": CHARCOAL},
        "plinth": {"color": PLINTH},
        "moon": {"color": MOON, "smooth": True},
        "gold": {"color": GOLD, "smooth": True},
        "diamond": {"color": "#fff3cf", "class": "emissive"},
        "led_sun": {"color": SUN, "class": "emissive"},
        "led_moon": {"color": MOONBLUE, "class": "emissive"},
        "button": {"color": GRAPHITE, "smooth": True},
        "collar": {"color": NEAR_BLACK},
        "slot": {"color": NEAR_BLACK},
        "cart": {"color": "#5a5a62"},
        "emblem": {"color": MOON, "texture": {"sheet": "eclipse", "cell": "emblem",
                                              "projection": "disc", "axis": "y"}},
        "wordmark": {"color": CHARCOAL, "texture": {"sheet": "eclipse", "cell": "wordmark",
                                                    "projection": "fit"}},
        "port": {"color": "#222226", "texture": {"sheet": "eclipse", "cell": "port",
                                                 "projection": "fit"}},
        "cart_label": {"color": "#1b2340", "texture": {"sheet": "eclipse", "cell": "cart_label",
                                                       "bits": 8, "projection": "fit"}},
        "vent": {"color": CHARCOAL, "texture": {"sheet": "eclipse", "cell": "vent",
                                                "projection": "fit"}},
    }

    # A lower body and a lid with a dark shadow line between them, on a recessed plinth.
    n = 4
    SPLIT = 0.0535
    lower = [
        {"y": 0.008, "points": rounded_rect(W - 0.010, D - 0.010, 0.015, n)},
        {"y": 0.015, "points": rounded_rect(W, D, 0.020, n)},
        {"y": SPLIT - 0.001, "points": rounded_rect(W, D, 0.020, n)},
    ]
    seam = [
        {"y": SPLIT - 0.0025, "points": rounded_rect(W - 0.003, D - 0.003, 0.0185, n)},
        {"y": SPLIT + 0.0025, "points": rounded_rect(W - 0.003, D - 0.003, 0.0185, n)},
    ]
    lid = [
        {"y": SPLIT + 0.001, "points": rounded_rect(W, D, 0.020, n)},
        {"y": 0.059, "points": rounded_rect(W, D, 0.020, n)},
        {"y": TOP, "points": rounded_rect(W - 0.016, D - 0.016, 0.012, n)},
    ]
    nodes = [
        node("body", "loft", "body", sections=lower),
        node("seam", "loft", "plinth", sections=seam, caps=False),
        node("lid", "loft", "body", sections=lid),
        box("plinth", "plinth", [W - 0.040, 0.011, D - 0.040], [0, 0.0045, 0], open=["bottom"]),
    ]

    # The eclipse: a thin gold corona around a black moon, 明 at its heart.
    seg = 40
    eclipse = [
        lathe("corona", "gold", [(RING, TOP - 0.004), (RING, TOP + 0.0025),
                                 (RING - 0.0045, TOP + 0.0036)], seg, [0, 0, DISC_Z], caps=False),
        lathe("moon_disc", "moon", [(RING - 0.0040, TOP - 0.003), (RING - 0.0040, TOP + 0.0031),
                                    (RING - 0.010, TOP + 0.0052), (0.0, TOP + 0.0066)],
              seg, [0, 0, DISC_Z], caps=False),
        lathe("emblem", "emblem", [(0.021, TOP + 0.004), (0.021, TOP + 0.0072),
                                   (0.0, TOP + 0.00721)], 24, [0, 0, DISC_Z], caps=False),
    ]
    # the diamond-ring bead: the power light, on the ring toward the rear right
    a = math.radians(42)
    bead = node("diamond_ring", "sphere", "diamond",
                [math.cos(a) * (RING - 0.0009), TOP + 0.0034, DISC_Z + math.sin(a) * (RING - 0.0009)],
                radius=0.0032, rings=4, segments=8)
    nodes.append(node("eclipse", "group", children=eclipse + [bead]))

    # Power (left, the sun's light) and reset (right, the moon's) on the top's front corners.
    def push_button(id, x, led_mat, led_dx):
        z = -0.072
        return node(id, "group", children=[
            lathe("collar", "collar", [(0.0125, TOP - 0.003), (0.0125, TOP + 0.0009),
                                       (0.0, TOP + 0.00091)], 16, [x, 0, z], caps=False),
            lathe("cap", "button", [(0.0098, TOP - 0.002), (0.0098, TOP + 0.0032),
                                    (0.0088, TOP + 0.0042), (0.0, TOP + 0.0046)], 16, [x, 0, z],
                  caps=False),
            node("led", "cylinder", led_mat, [x + led_dx, TOP + 0.0002, z], radius=0.0016,
                 height=0.002, segments=6),
        ])
    nodes.append(push_button("power", -0.112, "led_sun", 0.020))
    nodes.append(push_button("reset", 0.112, "led_moon", -0.020))

    # The cart slot at the rear, with a cart standing in it, label to the front.
    CZ, CT = 0.0745, 0.019
    cart_outline = [[-0.058, -0.036], [0.058, -0.036], [0.058, 0.026], [0.054, 0.033],
                    [0.046, 0.036], [-0.046, 0.036], [-0.054, 0.033], [-0.058, 0.026]]
    nodes += [
        box("slot_lip", "slot", [0.130, 0.006, 0.031], [0, TOP + 0.0005, CZ]),
        node("cart", "extrude", "cart", [0, 0.076, CZ], points=cart_outline, depth=CT),
        box("cart_label", "cart_label", [0.088, 0.032, 0.002], [0, 0.0905, CZ - CT / 2 + 0.0003]),
        box("cart_grip", "slot", [0.070, 0.003, 0.0204], [0, 0.1085, CZ]),
    ]

    # Front: two controller ports, two memory card slots above them, the gold wordmark.
    for i, x in ((1, -0.088), (2, 0.088)):
        nodes.append(box(f"port_{i}", "port", [0.034, 0.017, 0.012], [x, 0.031, FZ + 0.0049]))
        nodes.append(box(f"card_{i}", "slot", [0.044, 0.0045, 0.012], [x, 0.0475, FZ + 0.0049]))
    nodes.append(box("wordmark", "wordmark", [0.072, 0.018, 0.004], [0, 0.034, FZ + 0.0011]))

    # Side vents and the rear connectors.
    for side, sx in (("left", -1), ("right", 1)):
        nodes.append(box(f"vent_{side}", "vent", [0.004, 0.026, 0.060],
                         [sx * (W / 2 - 0.0011), 0.036, 0.050]))
    nodes += [
        box("av_out", "slot", [0.024, 0.010, 0.006], [-0.070, 0.034, D / 2 + 0.0009]),
        box("dc_in", "slot", [0.014, 0.010, 0.006], [0.085, 0.034, D / 2 + 0.0009]),
    ]

    return {
        "format": "mei-asset", "version": 1, "name": "mei_console_eclipse_black",
        "budget": {"vertices": 1400, "triangles": 1200},
        "sheets": {"eclipse": {"image": "art/eclipse_black.png"}},
        "materials": mats,
        "lighting": {"direction": [-0.45, 0.8, -0.4], "ambient": 0.42},
        "verification": VERIFY,
        "nodes": nodes,
    }


# ---------------------------------------------------------------- controller

def controller_outline():
    """Top-view outline (x right, z away from the player), counter-clockwise."""
    right = [(0.000, 0.0475), (0.054, 0.046), (0.067, 0.041), (0.075, 0.031),
             (0.079, 0.012), (0.077, -0.018), (0.074, -0.038), (0.069, -0.056),
             (0.061, -0.068), (0.051, -0.073), (0.041, -0.070), (0.034, -0.060), (0.027, -0.048),
             (0.018, -0.041), (0.008, -0.039)]
    left = [(-x, z) for x, z in reversed(right[1:])]
    pts = right + left
    # make it counter-clockwise seen from above (x right, z up on the page)
    area = sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts)))
    if area < 0:
        pts.reverse()
    return [list(p) for p in pts]


def controller():
    T = 0.028                       # flat top
    mats = {
        "body": {"color": CHARCOAL},
        "well": {"color": NEAR_BLACK},
        "pad": {"color": "#3a3a41"},
        "gold": {"color": GOLD, "smooth": True},
        "stick": {"color": "#2a2a30", "smooth": True},
        "stick_cap": {"color": "#55555e", "smooth": True},
        "grip": {"color": "#424249", "smooth": True},
        "btn_a": {"color": "#c27a3c", "smooth": True},
        "btn_b": {"color": "#7f9cc0", "smooth": True},
        "btn_xy": {"color": "#46464e", "smooth": True},
        "emblem": {"color": MOON, "texture": {"sheet": "eclipse", "cell": "emblem",
                                              "projection": "disc", "axis": "y"}},
    }
    out = controller_outline()
    sections = [
        {"y": 0.000, "points": offset_outline(out, 0.007)},
        {"y": 0.007, "points": offset_outline(out, 0.0015)},
        {"y": 0.021, "points": out},
        {"y": T, "points": offset_outline(out, 0.0055)},
    ]
    nodes = [node("body", "loft", "body", sections=sections)]

    # Rounded handles under the grips, so the pad is not a slab.
    for side, sx in (("l", -1), ("r", 1)):
        nodes.append(node(f"handle_{side}", "sphere", "grip", [sx * 0.054, 0.0105, -0.046],
                          [0, sx * 12, 0], s=[0.0195, 0.0155, 0.030], radius=1.0, rings=4,
                          segments=8))

    # D-pad in a black well, left wing.
    DX, DZ = -0.050, 0.012
    nodes.append(node("dpad", "group", children=[
        lathe("well", "well", [(0.0165, T - 0.003), (0.0165, T + 0.0008), (0.0, T + 0.00081)], 10,
              [DX, 0, DZ], caps=False),
        box("bar_x", "pad", [0.0265, 0.0058, 0.0085], [DX, T + 0.0005, DZ]),
        box("bar_z", "pad", [0.0085, 0.0058, 0.0265], [DX, T + 0.0008, DZ]),
    ]))

    # A B X Y, right wing: A (the sun's orange) right, B (the moon's blue) bottom.
    AX, AZ, S = 0.050, 0.012, 0.0105
    face_buttons = [lathe("well", "well", [(0.0195, T - 0.003), (0.0195, T + 0.0008),
                                           (0.0, T + 0.00081)], 10, [AX, 0, AZ], caps=False)]
    for id, mat, dx, dz in (("a", "btn_a", S, 0), ("b", "btn_b", 0, -S),
                            ("x", "btn_xy", 0, S), ("y", "btn_xy", -S, 0)):
        face_buttons.append(lathe(id, mat, [(0.0047, T - 0.002), (0.0047, T + 0.0034),
                                            (0.0, T + 0.0044)], 8,
                                  [AX + dx, 0, AZ + dz], caps=False))
    nodes.append(node("face_buttons", "group", children=face_buttons))

    # The stick, centre bottom, ringed in gold like the console's eclipse.
    SX, SZ = 0.0, -0.017
    nodes.append(node("stick", "group", children=[
        lathe("corona", "gold", [(0.0136, T - 0.003), (0.0136, T + 0.0012),
                                 (0.0124, T + 0.0019)], 16, [SX, 0, SZ], caps=False),
        lathe("well", "well", [(0.0127, T - 0.003), (0.0127, T + 0.0006), (0.0, T + 0.00061)], 16,
              [SX, 0, SZ], caps=False),
        node("post", "cylinder", "stick", [SX, T + 0.004, SZ], radius=0.0035, height=0.008,
             segments=6, caps=False),
        lathe("cap", "stick_cap", [(0.0086, T + 0.0065), (0.0093, T + 0.0088),
                               (0.0084, T + 0.0105), (0.0, T + 0.0112)], 12, [SX, 0, SZ],
              caps=False),
    ]))

    # Select and Start, the 明 emblem above them.
    nodes.append(node("select", "box", "pad", [-0.011, T + 0.0003, 0.012], [0, 25, 0],
                      size=[0.0095, 0.0036, 0.0036]))
    nodes.append(node("start", "box", "pad", [0.011, T + 0.0003, 0.012], [0, -25, 0],
                      size=[0.0095, 0.0036, 0.0036]))
    nodes.append(lathe("emblem", "emblem", [(0.0068, T - 0.002), (0.0068, T + 0.0007),
                                            (0.0, T + 0.00071)], 10, [0, 0, 0.031], caps=False))

    # L and R on the far edge, and the cord's strain relief between them.
    for id, x in (("l", -0.050), ("r", 0.050)):
        nodes.append(node(f"shoulder_{id}", "extrude", "pad", [x, 0.0155, 0.0445], [0, -90, 0],
                          points=[[-0.006, -0.0055], [0.0055, -0.0055], [0.0075, -0.001],
                                  [0.0065, 0.0045], [0.003, 0.0060], [-0.006, 0.0060]],
                          depth=0.030))
    nodes.append(node("cord", "cylinder", "well", [0, 0.012, 0.050], [90, 0, 0], radius=0.0042,
                      height=0.016, segments=5))

    return {
        "format": "mei-asset", "version": 1, "name": "mei_controller_eclipse_black",
        "budget": {"vertices": 900, "triangles": 800},
        "sheets": {"eclipse": {"image": "art/eclipse_black.png"}},
        "materials": mats,
        "lighting": {"direction": [-0.45, 0.8, -0.4], "ambient": 0.42},
        "verification": VERIFY,
        "nodes": nodes,
    }


def main():
    write_sheet()
    for name, recipe in (("console", console()), ("controller", controller())):
        (HERE / f"{name}.asset.json").write_text(json.dumps(recipe, indent=1) + "\n")


if __name__ == "__main__":
    main()
