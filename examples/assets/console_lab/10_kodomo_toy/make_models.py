#!/usr/bin/env python3
"""Write console.asset.json and controller.asset.json for the Kodomo Toy look.

Real size in metres, Y up, the front facing -Z. The bodies are lofts of rounded outlines
(a red bumper shell under a cream pillow); the labels come from art/kodomo.png
(gen_art.py draws it).
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent

CREAM = "#f2e6c8"
CREAM_D = "#ddcca4"
TOMATO = "#e0402c"
TOMATO_D = "#b02c1e"
DARK = "#3a2c28"
CART = "#f2c230"


def r6(v):
    return round(v, 6)


def tex(cell, projection, **kw):
    t = {"sheet": "kodomo", "cell": cell, "projection": projection}
    t.update(kw)
    return t


def common_materials():
    return {
        "cream": {"color": CREAM},
        "cream_dark": {"color": CREAM_D},
        "tomato": {"color": TOMATO},
        "tomato_dark": {"color": TOMATO_D},
        "dark": {"color": DARK},
    }


# ---------------------------------------------------------------- outlines

def rrect(hw, hd, r, n=5):
    """A rounded rectangle in XZ, counterclockwise seen from above, n points a corner."""
    r = max(min(r, hw - 1e-4, hd - 1e-4), 0.0015)
    pts = []
    for cx, cz, a0 in ((hw - r, hd - r, 0), (-(hw - r), hd - r, 90),
                       (-(hw - r), -(hd - r), 180), (hw - r, -(hd - r), 270)):
        for k in range(n):
            a = math.radians(a0 + 90 * k / (n - 1))
            pts.append([r6(cx + r * math.cos(a)), r6(cz + r * math.sin(a))])
    return pts


def rrect_loft(hw, hd, r, levels, n=5, ox=0.0, oz=0.0):
    """levels: [(y, inset)]. Each section is the rounded rectangle shrunk by inset."""
    return [{"y": r6(y), "points": [[r6(x + ox), r6(z + oz)] for x, z in rrect(hw - d, hd - d, r - d, n)]}
            for y, d in levels]


def offset(poly, d):
    """Move each vertex of a closed counterclockwise polygon inward by d along its normal."""
    out, n = [], len(poly)
    for i in range(n):
        px, pz = poly[i - 1]
        x, z = poly[i]
        nx_, nz_ = poly[(i + 1) % n]
        ex, ez = nx_ - px, nz_ - pz
        L = math.hypot(ex, ez)
        # inward normal of a counterclockwise outline (seen from above, x right, z up)
        ix, iz = -ez / L, ex / L
        out.append([r6(x + ix * d), r6(z + iz * d)])
    return out


def poly_loft(poly, levels):
    return [{"y": r6(y), "points": offset(poly, d) if d else [[r6(x), r6(z)] for x, z in poly]}
            for y, d in levels]


def align_y_to(d):
    """Euler rotation [rx, ry, 0] (degrees) taking +Y to the direction d."""
    dx, dy, dz = d
    L = math.sqrt(dx * dx + dy * dy + dz * dz)
    a = math.degrees(math.acos(max(-1.0, min(1.0, dy / L))))
    b = math.degrees(math.atan2(dx, dz))
    return [r6(a), r6(b), 0]


def rod(id_, p, q, radius, material, segments=8):
    mid = [r6((a + b) / 2) for a, b in zip(p, q)]
    d = [b - a for a, b in zip(p, q)]
    length = math.sqrt(sum(c * c for c in d))
    return {"id": id_, "op": "cylinder", "radius": radius, "height": r6(length),
            "segments": segments, "material": material,
            "transform": {"rotate": align_y_to(d), "translate": mid}}


def write(name, recipe):
    path = HERE / f"{name}.asset.json"
    path.write_text(json.dumps(recipe, indent=1, ensure_ascii=False) + "\n")
    print("wrote", path.name)


# ---------------------------------------------------------------- console

def console():
    W2, D2 = 0.160, 0.120          # half width and depth of the red bumper shell
    SHELL_TOP = 0.040
    BODY_INSET = 0.010             # the cream pillow sits this far inside the bumper
    BW, BD = W2 - BODY_INSET, D2 - BODY_INSET
    TOP = 0.112                    # the flat top of the pillow
    U = TOP - 0.096                # what sits on the top is placed relative to it
    FRONT = -BD                    # the cream body's front face, z

    mats = common_materials()
    mats.update({
        "cart": {"color": CART},
        "logo": {"color": TOMATO, "texture": tex("logo", "planar", axis="y",
                                                  scale=[0.104, 0.044], offset=[0.5, 0.5])},
        "power": {"color": TOMATO, "texture": tex("power", "disc", scale=[0.054, 0.054])},
        "reset": {"color": CREAM, "texture": tex("reset", "disc", scale=[0.042, 0.042])},
        "port1": {"color": TOMATO, "texture": tex("port1", "planar", axis="z",
                                                   scale=[0.050, 0.026], offset=[0.5, 0.5])},
        "port2": {"color": TOMATO, "texture": tex("port2", "planar", axis="z",
                                                   scale=[0.050, 0.026], offset=[0.5, 0.5])},
        "label": {"color": "#78bee8", "texture": tex("cart_label", "planar", axis="z",
                                                      scale=[0.094, 0.044], offset=[0.5, 0.5])},
    })

    nodes = []
    # The red bumper shell: a fat rounded tub the cream body sits in, lifted on its own curve.
    nodes.append({"id": "bumper", "op": "loft", "material": "tomato",
                  "sections": rrect_loft(W2, D2, 0.052, [(0.0, 0.011), (0.011, 0.0),
                                                         (0.033, 0.0), (SHELL_TOP, 0.005)], n=6)})
    # The cream pillow.
    nodes.append({"id": "body", "op": "loft", "material": "cream",
                  "sections": rrect_loft(BW, BD, 0.046, [(0.034, 0.0), (0.078, 0.0), (0.094, 0.006),
                                                         (0.106, 0.017), (TOP, 0.032)], n=6)})

    # The cart slot: a raised red mouth on the back half of the top, a cart standing in it.
    slot_z = 0.030
    nodes.append({"id": "slot_mouth", "op": "loft", "material": "tomato",
                  "sections": rrect_loft(0.072, 0.024, 0.014,
                                         [(0.090 + U, 0.0), (0.106 + U, 0.0), (0.110 + U, 0.004)],
                                         n=4, oz=slot_z)})
    nodes.append({"id": "slot_hole", "op": "box", "size": [0.126, 0.004, 0.028], "material": "dark",
                  "transform": {"translate": [0, r6(0.1095 + U), slot_z]}})
    cart_pts = [[-0.058, r6(0.070 + U)]]
    for cx, a0 in ((-0.046, 180), (0.046, 90)):
        for k in range(4):
            a = math.radians(a0 - 90 * k / 3)
            cart_pts.append([r6(cx + 0.012 * math.cos(a)), r6(0.150 + U + 0.012 * math.sin(a))])
    cart_pts.append([0.058, r6(0.070 + U)])
    nodes.append({"id": "cart", "op": "extrude", "points": cart_pts, "depth": 0.020,
                  "material": "cart", "transform": {"translate": [0, 0, slot_z]}})
    nodes.append({"id": "cart_grip", "op": "box", "size": [0.070, 0.006, 0.022], "material": "cart",
                  "transform": {"translate": [0, r6(0.155 + U), slot_z]}})
    nodes.append({"id": "cart_label", "op": "box", "size": [0.090, 0.040, 0.002], "material": "label",
                  "transform": {"translate": [0, r6(0.134 + U), r6(slot_z - 0.0105)]}})

    # The badge: 明 MEI on a red sticker at the front of the top.
    nodes.append({"id": "badge", "op": "loft", "material": "logo",
                  "sections": rrect_loft(0.050, 0.020, 0.008,
                                         [(0.092 + U, 0.0), (0.0985 + U, 0.0), (0.100 + U, 0.0015)],
                                         n=3, oz=-0.044)})

    # Power (a red sun) and reset (a cream moon): big domed toy buttons in beige collars.
    def button(id_, x, r, mat):
        return [
            {"id": id_ + "_collar", "op": "cylinder", "radius": r6(r + 0.005), "height": 0.010,
             "segments": 12, "material": "cream_dark",
             "transform": {"translate": [x, r6(0.093 + U), -0.044]}},
            {"id": id_, "op": "lathe", "segments": 16, "material": mat,
             "profile": [[r, r6(0.094 + U)], [r, r6(0.105 + U)], [r6(r * 0.85), r6(0.110 + U)],
                         [0.0, r6(0.112 + U)]],
             "transform": {"translate": [x, 0, -0.044]}},
        ]
    nodes += button("power", 0.086, 0.024, "power")
    nodes += button("reset", -0.088, 0.018, "reset")

    # Front: two controller ports, two memory card slots.
    for i, x in ((1, -0.090), (2, 0.090)):
        nodes.append({"id": f"port{i}", "op": "box", "size": [0.050, 0.026, 0.012],
                      "material": f"port{i}", "transform": {"translate": [x, 0.060, r6(FRONT - 0.003)]}})
    for i, x in ((1, -0.034), (2, 0.034)):
        nodes.append({"id": f"card{i}", "op": "group", "children": [
            {"id": "frame", "op": "box", "size": [0.044, 0.016, 0.008], "material": "cream_dark"},
            {"id": "slit", "op": "box", "size": [0.036, 0.005, 0.004], "material": "dark",
             "transform": {"translate": [0, 0.001, -0.003]}},
        ], "transform": {"translate": [x, 0.060, r6(FRONT - 0.002)]}})

    # The carry handle: a fat red loop out of the back, for little hands.
    hy, hx, hz, hr = 0.060, 0.072, r6(BD + 0.054), 0.0135
    nodes.append({"id": "handle", "op": "group", "children": [
        rod("arm_l", [-hx, hy, r6(BD - 0.012)], [-hx, hy, hz], hr, "tomato"),
        rod("arm_r", [hx, hy, r6(BD - 0.012)], [hx, hy, hz], hr, "tomato"),
        rod("bar", [-hx, hy, hz], [hx, hy, hz], hr, "tomato"),
        {"id": "corner_l", "op": "sphere", "radius": hr, "rings": 4, "segments": 8, "material": "tomato",
         "transform": {"translate": [-hx, hy, hz]}},
        {"id": "corner_r", "op": "sphere", "radius": hr, "rings": 4, "segments": 8, "material": "tomato",
         "transform": {"translate": [hx, hy, hz]}},
    ]})

    return {
        "format": "mei-asset", "version": 1, "name": "kodomo_console",
        "budget": {"vertices": 1200, "triangles": 1200},
        "sheets": {"kodomo": {"image": "art/kodomo.png"}},
        "materials": mats,
        "lighting": {"direction": [-0.45, 0.85, -0.4], "ambient": 0.5},
        "nodes": nodes,
        "verification": {"required": True, "depth": True, "perspective": True},
    }


# ---------------------------------------------------------------- controller

def dogbone(n=32):
    """The controller's outline in XZ: a rounded middle and two round grips toward the player."""
    def inside(x, z):
        hx, z0, z1, r = 0.056, -0.030, 0.036, 0.020
        qx, qz = abs(x) - (hx - r), max(z0 + r - z, z - (z1 - r), 0)
        in_rect = (abs(x) <= hx and z0 <= z <= z1 and
                   (qx <= 0 or (z0 + r <= z <= z1 - r) or qx * qx + qz * qz <= r * r))
        in_grip = (abs(x) - 0.047) ** 2 + (z + 0.020) ** 2 <= 0.035 ** 2
        return in_rect or in_grip
    cz = 0.0
    dense = []
    for k in range(720):
        a = 2 * math.pi * k / 720
        lo, hi = 0.0, 0.12
        # outermost boundary along the ray
        t = hi
        while t > 0 and not inside(t * math.cos(a), cz + t * math.sin(a)):
            t -= 0.0005
        lo, hi = t, t + 0.0005
        for _ in range(20):
            m = (lo + hi) / 2
            if inside(m * math.cos(a), cz + m * math.sin(a)):
                lo = m
            else:
                hi = m
        dense.append((lo * math.cos(a), cz + lo * math.sin(a)))
    # Resample by arc length, starting at the far edge's middle.
    seg = [math.dist(dense[i], dense[(i + 1) % len(dense)]) for i in range(len(dense))]
    total = sum(seg)
    pts, acc, i = [], 0.0, 0
    start = 180  # the ray at 90 degrees: the far edge's middle
    dense = dense[start:] + dense[:start]
    seg = seg[start:] + seg[:start]
    for k in range(n):
        target = total * k / n
        while acc + seg[i] < target:
            acc += seg[i]
            i += 1
        f = (target - acc) / seg[i]
        a, b = dense[i], dense[(i + 1) % len(dense)]
        pts.append([r6(a[0] + (b[0] - a[0]) * f), r6(a[1] + (b[1] - a[1]) * f)])
    # Straight runs keep only their ends (the loft refuses collinear points).
    keep = []
    for i, p in enumerate(pts):
        a, b = pts[i - 1], pts[(i + 1) % len(pts)]
        cross = (p[0] - a[0]) * (b[1] - p[1]) - (p[1] - a[1]) * (b[0] - p[0])
        if abs(cross) > 2e-6:
            keep.append(p)
    return keep


def controller():
    mats = common_materials()
    for k, cell in (("btn_a", "btn_a"), ("btn_b", "btn_b"), ("btn_x", "btn_x"), ("btn_y", "btn_y")):
        mats[k] = {"color": TOMATO if k in ("btn_a", "btn_b") else CREAM,
                   "texture": tex(cell, "disc", scale=[0.0156, 0.0156])}
    mats["logo"] = {"color": TOMATO, "texture": tex("logo_small", "planar", axis="y",
                                                     scale=[0.028, 0.014], offset=[0.5, 0.5])}
    outline = dogbone()
    TOP = 0.034
    nodes = []
    nodes.append({"id": "shell", "op": "loft", "material": "tomato",
                  "sections": poly_loft(outline, [(0.0, 0.0045), (0.021, 0.0)])})
    nodes.append({"id": "body", "op": "loft", "material": "cream",
                  "sections": poly_loft(outline, [(0.018, 0.0025), (TOP, 0.009)])})
    # Chunky red palm bulbs under the grips.
    nodes.append({"id": "bulbs", "op": "group", "children": [
        {"id": "bulb", "op": "sphere", "radius": 0.030, "rings": 3, "segments": 8, "material": "tomato",
         "transform": {"scale": [1, 0.55, 1], "translate": [0.049, 0.006, -0.024]}}],
        "modifiers": [{"op": "mirror", "axis": "x"}]})

    # D-pad in a beige well.
    dx, dz = -0.048, 0.002
    nodes.append({"id": "dpad_well", "op": "cylinder", "radius": 0.020, "height": 0.006, "segments": 10,
                  "material": "cream_dark", "transform": {"translate": [dx, 0.0325, dz]}})
    a, w = 0.0135, 0.0047
    plus = [[w, a], [w, w], [a, w], [a, -w], [w, -w], [w, -a], [-w, -a], [-w, -w], [-a, -w], [-a, w], [-w, w], [-w, a]]
    nodes.append({"id": "dpad", "op": "extrude", "points": plus, "depth": 0.008, "material": "tomato",
                  "transform": {"rotate": [90, 0, 0], "translate": [dx, 0.036, dz]}})

    # A B X Y in a beige well: A and B red, X and Y cream.
    bx, bz, s = 0.048, 0.002, 0.0125
    nodes.append({"id": "face_well", "op": "cylinder", "radius": 0.0225, "height": 0.006, "segments": 10,
                  "material": "cream_dark", "transform": {"translate": [bx, 0.0325, bz]}})
    for id_, ox, oz in (("btn_a", s, 0), ("btn_b", 0, -s), ("btn_x", 0, s), ("btn_y", -s, 0)):
        nodes.append({"id": id_, "op": "cylinder", "radius": 0.0075, "height": 0.009, "segments": 8,
                      "material": id_, "transform": {"translate": [r6(bx + ox), 0.035, r6(bz + oz)]}})

    # The analog stick between the grips.
    sx, sz = 0.0, -0.009
    nodes.append({"id": "stick_base", "op": "lathe", "segments": 10, "material": "cream_dark",
                  "profile": [[0.013, 0.030], [0.0115, 0.037], [0.0, 0.039]],
                  "transform": {"translate": [sx, 0, sz]}})
    nodes.append({"id": "stick_shaft", "op": "cylinder", "radius": 0.0035, "height": 0.010, "segments": 6,
                  "material": "dark", "transform": {"translate": [sx, 0.042, sz]}})
    nodes.append({"id": "stick_cap", "op": "lathe", "segments": 10, "material": "tomato",
                  "profile": [[0.0, 0.045], [0.011, 0.0455], [0.0105, 0.050], [0.0, 0.0515]],
                  "transform": {"translate": [sx, 0, sz]}})

    # Select and Start, and the little badge.
    for id_, x in (("select", -0.016), ("start", 0.016)):
        nodes.append({"id": id_, "op": "box", "size": [0.011, 0.006, 0.0048], "material": "dark",
                      "transform": {"rotate": [0, -20 if x < 0 else 20, 0], "translate": [x, 0.0335, 0.0115]}})
    nodes.append({"id": "badge", "op": "box", "size": [0.028, 0.004, 0.012], "material": "logo",
                  "transform": {"translate": [0, 0.0335, 0.0225]}})

    # L and R: fat red bumpers on the far corners.
    for id_, x in (("l", -0.046), ("r", 0.046)):
        nodes.append({"id": id_, "op": "loft", "material": "tomato",
                      "sections": rrect_loft(0.022, 0.008, 0.006, [(0.014, 0.0), (0.033, 0.0), (0.038, 0.003)],
                                             n=2, ox=x, oz=0.031)})

    # The cord: a strain relief and a short run of cable curling away.
    nodes.append(rod("strain", [0, 0.020, 0.030], [0, 0.020, 0.054], 0.0055, "cream_dark", 8))
    path = [[0, 0.020, 0.052], [0.004, 0.012, 0.078], [0.022, 0.0045, 0.096]]
    for k in range(len(path) - 1):
        nodes.append(rod(f"cord{k}", path[k], path[k + 1], 0.0035, "cream_dark", 6))

    return {
        "format": "mei-asset", "version": 1, "name": "kodomo_controller",
        "budget": {"vertices": 820, "triangles": 820},
        "sheets": {"kodomo": {"image": "art/kodomo.png"}},
        "materials": mats,
        "lighting": {"direction": [-0.45, 0.85, -0.4], "ambient": 0.5},
        # Lifted so the palm bulbs it rests on touch y = 0.
        "nodes": [{"id": "pad", "op": "group", "children": nodes,
                   "transform": {"translate": [0, 0.0105, 0]}}],
        "verification": {"required": True, "depth": True, "perspective": True},
    }


if __name__ == "__main__":
    write("console", console())
    write("controller", controller())
