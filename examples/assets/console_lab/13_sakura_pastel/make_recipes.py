#!/usr/bin/env python3
"""Writes console.asset.json and controller.asset.json for look 13, Sakura Pastel.

Run: python3 examples/assets/console_lab/13_sakura_pastel/make_recipes.py
(after make_art.py, which draws art/sakura_sheet.png).

Both models face -Z, Y up, in metres at real size: the console 0.272 m wide, the controller
0.148 m. Shells are lofts of rounded outlines; small parts are explicit meshes whose corners are
computed here, so their printed faces can carry a texture while their sides stay plain.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def r5(v):
    return [round(x, 5) for x in v]


# ---------------------------------------------------------------- outlines

def rrect(w, d, r, n=5, cx=0.0, cz=0.0):
    """A rounded rectangle in XZ, n points a corner, counterclockwise seen from above."""
    pts = []
    corners = ((w / 2 - r, d / 2 - r, 0), (-w / 2 + r, d / 2 - r, 90),
               (-w / 2 + r, -d / 2 + r, 180), (w / 2 - r, -d / 2 + r, 270))
    for ox, oz, a0 in corners:
        for k in range(n):
            a = math.radians(a0 + 90 * k / (n - 1))
            pts.append([round(cx + ox + r * math.cos(a), 5), round(cz + oz + r * math.sin(a), 5)])
    return pts


def chaikin(pts, rounds=1):
    for _ in range(rounds):
        out = []
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            out.append([0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]])
            out.append([0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1]])
        pts = out
    return pts


def resample(pts, n):
    """n points evenly spaced along a closed outline, the first at pts[0]."""
    segs = [math.dist(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
    total = sum(segs)
    out, i, acc = [], 0, 0.0
    for k in range(n):
        t = total * k / n
        while acc + segs[i] < t:
            acc += segs[i]
            i += 1
        f = (t - acc) / segs[i]
        a, b = pts[i], pts[(i + 1) % len(pts)]
        out.append([a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f])
    return out


def area(pts):
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
               for i in range(len(pts))) / 2


def offset(pts, inset):
    """Move each point of a closed outline inward by `inset` along its averaged normal."""
    ccw = area(pts) > 0
    out = []
    n = len(pts)
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        normals = []
        for a, b in ((p0, p1), (p1, p2)):
            ex, ez = b[0] - a[0], b[1] - a[1]
            l = math.hypot(ex, ez)
            # inward normal of a counterclockwise outline is the left normal (-ez, ex)
            nx, nz = (-ez / l, ex / l) if ccw else (ez / l, -ex / l)
            normals.append((nx, nz))
        mx, mz = normals[0][0] + normals[1][0], normals[0][1] + normals[1][1]
        ml = math.hypot(mx, mz)
        mx, mz = mx / ml, mz / ml
        cosh = mx * normals[0][0] + mz * normals[0][1]
        s = inset / max(cosh, 0.5)
        out.append([round(p1[0] + mx * s, 5), round(p1[1] + mz * s, 5)])
    return out


def flower(r_out, r_in):
    """A five-petal sakura outline in XY: rounded petals, deep valleys between them and the
    sakura's small notch at each petal's tip. Six points a petal."""
    shape = [r_in / r_out, 0.80, 0.97, 0.84, 0.97, 0.80]   # valley, flank, shoulder, notch, ...
    pts = []
    for k in range(30):
        t = k / 30 * 2 * math.pi + math.pi / 2 - math.pi / 5
        r = r_out * shape[k % 6]
        pts.append([round(r * math.cos(t), 5), round(r * math.sin(t), 5)])
    return pts


def bumper(id, edge, out_d, in_d, y0, y1, material):
    """A strip along an open run of outline points: out_d outside the shell, in_d into it, from
    y0 to y1, with rounded-off ends. A loft of the strip's outline."""
    def normal(i):
        a = edge[max(i - 1, 0)]
        b = edge[min(i + 1, len(edge) - 1)]
        ex, ez = b[0] - a[0], b[1] - a[1]
        l = math.hypot(ex, ez)
        return ez / l, -ex / l
    outer, inner = [], []
    for i, (x, z) in enumerate(edge):
        nx, nz = normal(i)
        # outward normal: away from the controller's middle
        if nx * x + nz * z < 0:
            nx, nz = -nx, -nz
        outer.append([x + nx * out_d, z + nz * out_d])
        inner.append([x - nx * in_d, z - nz * in_d])
    ring = outer + list(reversed(inner))
    if area(ring) < 0:
        ring = list(reversed(ring))
    return loft(id, [(y0, ring), (y1, ring)], material)


def loft(id, sections, material, caps=True):
    return {"id": id, "op": "loft", "material": material, "caps": caps,
            "sections": [{"y": round(y, 5), "points": [r5(p) for p in pts]} for y, pts in sections]}


def loft_mesh(id, sections, band_mats, bottom_mat, top_mat):
    """A loft as one explicit mesh, so each band between two sections can have its own material
    and no cap is buried between two shells. Outlines counterclockwise seen from above."""
    n = len(sections[0][1])
    vs = []
    for y, pts in sections:
        for x, z in pts:
            vs.append(r5([x, y, z]))
    faces, fm = [], []
    faces.append(list(range(n)))                          # bottom, looking down
    fm.append(bottom_mat)
    for k in range(len(sections) - 1):
        for i in range(n):
            j = (i + 1) % n
            a, b = k * n + i, k * n + j
            faces += [[a, a + n, b + n], [a, b + n, b]]
            fm += [band_mats[k]] * 2
    last = (len(sections) - 1) * n
    faces.append([last + i for i in reversed(range(n))])  # top, looking up
    fm.append(top_mat)
    node = {"id": id, "op": "mesh", "vertices": vs, "faces": faces, "material": band_mats[0]}
    if len(set(fm)) > 1:
        node["face_materials"] = fm
    return node


# ---------------------------------------------------------------- small solids

def slab(id, c, size, material, faces=None, rot_y=0.0, omit=()):
    """A box as an explicit mesh with a material per side. faces: {'top': mat, 'front': mat, ...}
    using the model's words: front is -Z (toward the viewer), back +Z, top +Y."""
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    vs = []
    idx = {}

    def v(sx, sy, sz):
        k = (sx, sy, sz)
        if k not in idx:
            idx[k] = len(vs)
            vs.append(r5([sx * hx, sy * hy, sz * hz]))
        return idx[k]
    # quads listed clockwise as seen from outside (top-left, top-right, bottom-right, bottom-left)
    quads = {
        "front": [v(-1, 1, -1), v(1, 1, -1), v(1, -1, -1), v(-1, -1, -1)],
        "back": [v(1, 1, 1), v(-1, 1, 1), v(-1, -1, 1), v(1, -1, 1)],
        "top": [v(-1, 1, 1), v(1, 1, 1), v(1, 1, -1), v(-1, 1, -1)],
        "bottom": [v(-1, -1, -1), v(1, -1, -1), v(1, -1, 1), v(-1, -1, 1)],
        "left": [v(-1, 1, 1), v(-1, 1, -1), v(-1, -1, -1), v(-1, -1, 1)],
        "right": [v(1, 1, -1), v(1, 1, 1), v(1, -1, 1), v(1, -1, -1)],
    }
    faces = faces or {}
    fl, fm = [], []
    for name, q in quads.items():
        if name in omit:
            continue
        fl.append(q)
        fm.append(faces.get(name, material))
    node = {"id": id, "op": "mesh", "vertices": vs, "faces": fl, "material": material,
            "transform": {"translate": r5(c)}}
    if any(m != material for m in fm):
        node["face_materials"] = fm
    if rot_y:
        node["transform"]["rotate"] = [0, rot_y, 0]
    return node


def decal_top(id, c, w, d, material, rot_y=0.0):
    """One quad looking up, centred at c: a print on a horizontal surface."""
    hw, hd = w / 2, d / 2
    vs = [[-hw, 0, hd], [hw, 0, hd], [hw, 0, -hd], [-hw, 0, -hd]]
    node = {"id": id, "op": "mesh", "vertices": [r5(p) for p in vs], "faces": [[0, 1, 2, 3]],
            "material": material, "transform": {"translate": r5(c)}}
    if rot_y:
        node["transform"]["rotate"] = [0, rot_y, 0]
    return node


def cyl(id, r, h, c, material, seg=12, rot=None, caps=True):
    node = {"id": id, "op": "cylinder", "radius": r, "height": h, "segments": seg,
            "material": material, "transform": {"translate": r5(c)}}
    if not caps:
        node["caps"] = False
    if rot:
        node["transform"]["rotate"] = rot
    return node


def sheet_mat(color, cell, bits=8, emissive=False):
    m = {"color": color, "texture": {"sheet": "art", "cell": cell, "bits": bits, "projection": "fit"}}
    if emissive:
        m["class"] = "emissive"
    return m


def write(name, recipe):
    path = os.path.join(HERE, name)
    with open(path, "w") as f:
        json.dump(recipe, f, indent=1)
        f.write("\n")


# The lid's print: a small blossom and two drifting petals, tone on tone, 16 x 16 texels.
LID_TILE = [
    "0000000000000000",
    "0000000000000000",
    "0000010000000000",
    "0001111000000000",
    "0011121100000000",
    "0001121000000000",
    "0011010000000000",
    "0000000000000000",
    "0000000000003000",
    "0000000000031000",
    "0000000000001000",
    "0000000000000000",
    "0000000000000000",
    "0000300000000000",
    "0000110000000000",
    "0000000000000000",
]

LID_PRINT = {"color": "#fbd9e2", "texture": {"texels": LID_TILE,
                                             "colors": ["#fbd9e2", "#f6c6d3", "#f9e6b0", "#f8cfda"],
                                             "projection": "planar", "axis": "y", "scale": [0.056, 0.056]}}

VERIFY = {"required": True, "depth": True, "perspective": True}
SHEETS = {"art": {"image": "art/sakura_sheet.png"}}

COLORS = {
    "pink": "#f2b6c6",      # lower shell: sakura
    "blush": "#fbd9e2",     # upper shell: the paler petal
    "mint": "#a3dbc4",
    "mint_deep": "#79c2a6",
    "cream": "#fff7ef",
    "rose": "#d9708f",
    "socket": "#3a2b35",
}


# ---------------------------------------------------------------- the console

def console():
    W, D = 0.272, 0.214
    mats = {k: {"color": v} for k, v in COLORS.items()}
    mats.update({
        "logo": sheet_mat("#b9506f", "logo"),
        "label": sheet_mat("#f6bfcd", "label"),
        "port1": sheet_mat("#a6dcc6", "port1"),
        "port2": sheet_mat("#a6dcc6", "port2"),
        "card1": sheet_mat("#a6dcc6", "card1"),
        "card2": sheet_mat("#a6dcc6", "card2"),
        "edition": sheet_mat("#fff6ec", "edition"),
        "seam": {"color": "#8fd0b6"},
        "cart": {"color": "#fdfbf8"},
        "lid_print": LID_PRINT,
        "power_print": sheet_mat("#fbdbe3", "power", bits=4),
        "reset_print": sheet_mat("#fbdbe3", "reset", bits=4),
        "rear_print": sheet_mat("#f6bfcd", "rear", bits=4),
        "blossom": {"color": "#f7a8bd", "texture": {"sheet": "art", "cell": "sakura", "bits": 4,
                                                    "projection": "fit"}},
        "vent": {"color": "#e9a9bb", "texture": {"pattern": "stripes", "colors": ["#f3c4d1", "#c97890"],
                                                  "size": 16, "params": {"count": 4, "axis": "v"},
                                                  "projection": "planar", "axis": "y",
                                                  "scale": [0.016, 0.016]}},
        "lamp_power": {"color": "#ff7aa0", "class": "emissive"},
        "lamp_net": {"color": "#9fd0ff", "class": "emissive"},
        "metal": {"color": "#c9c3c6"},
        "slot_dark": {"color": "#4a3640"},
    })
    nodes = []

    # --- the body, one closed shell: a cream foot, the sakura lower shell, a mint seam set in a
    # groove, the blush lid with a soft chamfer and a tone-on-tone petal print on its top
    full = rrect(W, D, 0.036)
    groove = rrect(W - 0.005, D - 0.005, 0.0335)
    nodes.append(loft_mesh("body", [
        (0.000, rrect(W - 0.030, D - 0.028, 0.024)),
        (0.0075, rrect(W - 0.024, D - 0.022, 0.026)),
        (0.0075, rrect(W - 0.012, D - 0.012, 0.030)),
        (0.013, full),
        (0.0345, full),
        (0.0345, groove),
        (0.0405, groove),
        (0.0405, full),
        (0.055, full),
        (0.0625, rrect(W - 0.006, D - 0.006, 0.033)),
        (0.0675, rrect(W - 0.015, D - 0.015, 0.0285)),
        (0.070, rrect(W - 0.026, D - 0.026, 0.023))],
        ["cream", "pink", "pink", "pink", "pink", "seam", "blush", "blush", "blush", "blush", "blush"],
        "cream", "lid_print"))
    TOP = 0.070
    FRONT = -D / 2

    # --- the cartridge slot, with a cart standing in it
    SZ = 0.036                                  # slot centre, toward the back
    nodes.append(loft("slot_housing", [(0.066, rrect(0.152, 0.042, 0.012, 4, cz=SZ)),
                                       (0.0775, rrect(0.152, 0.042, 0.012, 4, cz=SZ)),
                                       (0.0805, rrect(0.143, 0.033, 0.008, 4, cz=SZ))], "mint"))
    nodes.append(slab("slot_mouth", [0, 0.0795, SZ], [0.126, 0.004, 0.024], "slot_dark"))
    cart_pts = [[-0.056, 0.060], [0.056, 0.060], [0.056, 0.121], [0.052, 0.127], [0.040, 0.131],
                [-0.040, 0.131], [-0.052, 0.127], [-0.056, 0.121]]
    nodes.append({"id": "cart", "op": "extrude", "points": cart_pts, "depth": 0.017,
                  "material": "cart", "transform": {"translate": [0, 0, SZ]}})
    # grip ridges across the cart's top
    nodes.append(slab("cart_grip", [0, 0.1295, SZ], [0.070, 0.006, 0.019], "mint"))
    nodes.append(slab("cart_label", [0, 0.1025, SZ - 0.0085], [0.056, 0.0465, 0.003], "cream",
                      faces={"front": "label"}))

    # --- top, front left: the 明 MEI badge; top, front right: power and reset
    nodes.append(slab("logo_badge", [-0.074, TOP - 0.0005, -0.064], [0.064, 0.0045, 0.024], "rose",
                      faces={"top": "logo"}, omit=("bottom",)))
    PZ = -0.062
    nodes.append(cyl("power_collar", 0.0135, 0.004, [0.086, TOP + 0.0005, PZ], "mint_deep", seg=14))
    nodes.append({"id": "power_button", "op": "extrude", "points": flower(0.0122, 0.0062), "depth": 0.007,
                  "material": "mint", "transform": {"rotate": [90, 0, 0], "translate": [0.086, TOP + 0.0045, PZ]}})
    nodes.append(cyl("power_heart", 0.0030, 0.002, [0.086, TOP + 0.0080, PZ], "rose", seg=8))
    nodes.append(cyl("reset_collar", 0.0095, 0.004, [0.052, TOP + 0.0005, PZ], "mint_deep", seg=12))
    nodes.append(cyl("reset_button", 0.0072, 0.0065, [0.052, TOP + 0.0025, PZ], "rose", seg=12))
    nodes.append(decal_top("power_print", [0.086, TOP + 0.0012, PZ - 0.022], 0.026, 0.0065, "power_print"))
    nodes.append(decal_top("reset_print", [0.052, TOP + 0.0012, PZ - 0.022], 0.026, 0.0065, "reset_print"))

    # --- printed blossoms drifting across the lid (cutouts)
    nodes.append(decal_top("blossom_big", [0.060, TOP + 0.0012, -0.012], 0.046, 0.046, "blossom", rot_y=14))
    nodes.append(decal_top("blossom_mid", [-0.010, TOP + 0.0012, -0.040], 0.026, 0.026, "blossom", rot_y=-22))
    nodes.append(decal_top("blossom_small", [-0.040, TOP + 0.0012, -0.006], 0.017, 0.017, "blossom", rot_y=40))
    nodes.append(decal_top("blossom_far", [-0.103, TOP + 0.0012, 0.058], 0.014, 0.014, "blossom", rot_y=-8))

    # --- vents either side of the slot
    for s, name in ((1, "vent_r"), (-1, "vent_l")):
        nodes.append(slab(name, [s * 0.098, TOP - 0.0005, 0.036], [0.030, 0.0035, 0.026], "vent",
                          omit=("bottom",)))

    # --- front: two controller ports, two memory card slots, lamps, the edition plate
    FY = 0.0225
    for n, x in ((1, -0.037), (2, 0.037)):
        nodes.append(slab("port%d" % n, [x, FY, FRONT + 0.0005], [0.029, 0.019, 0.006], "mint",
                          faces={"front": "port%d" % n}, omit=("back",)))
    for n, x in ((1, -0.080), (2, 0.080)):
        nodes.append(slab("card%d" % n, [x, FY, FRONT + 0.0010], [0.034, 0.0128, 0.006], "mint",
                          faces={"front": "card%d" % n}, omit=("back",)))
    nodes.append(cyl("lamp_power", 0.0022, 0.004, [-0.007, FY, FRONT - 0.0005], "lamp_power", seg=8,
                     rot=[90, 0, 0]))
    nodes.append(cyl("lamp_net", 0.0022, 0.004, [0.007, FY, FRONT - 0.0005], "lamp_net", seg=8,
                     rot=[90, 0, 0]))
    nodes.append(slab("edition_plate", [0, 0.0475, FRONT + 0.0010], [0.040, 0.010, 0.0045], "cream",
                      faces={"front": "edition"}, omit=("back",)))

    # --- back: DC in, AV out, the MeiNet antenna socket
    BACK = D / 2
    nodes.append(slab("rear_plate", [0, 0.0225, BACK - 0.0010], [0.072, 0.018, 0.0045], "pink",
                      faces={"back": "rear_print"}, omit=("front",)))
    ry = 0.027
    nodes.append(cyl("dc_in", 0.0034, 0.006, [0.0295, ry, BACK + 0.0025], "socket", seg=10, rot=[90, 0, 0]))
    nodes.append(slab("av_out", [0.010, ry, BACK + 0.0020], [0.010, 0.006, 0.005], "socket"))
    nodes.append(cyl("ant_in", 0.0030, 0.009, [-0.0155, ry, BACK + 0.0040], "metal", seg=10, rot=[90, 0, 0]))

    return {
        "format": "mei-asset", "version": 1, "name": "sakura_console",
        "budget": {"vertices": 1400, "triangles": 1200},
        "sheets": SHEETS,
        "materials": mats,
        "lighting": {"direction": [-0.45, 0.75, -0.55], "ambient": 0.62},
        "verification": VERIFY,
        "nodes": nodes,
    }


# ---------------------------------------------------------------- the controller

def controller_outline():
    # right half, from the back centre clockwise in the top view (+Z is the shoulder edge)
    half = [(0.000, 0.039), (0.030, 0.041), (0.052, 0.037), (0.066, 0.026), (0.073, 0.008),
            (0.074, -0.014), (0.070, -0.036), (0.062, -0.054), (0.049, -0.064), (0.036, -0.061),
            (0.028, -0.047), (0.020, -0.030), (0.010, -0.022)]
    left = [(-x, z) for x, z in reversed(half[1:])]
    ring = [list(p) for p in half] + [[0.0, -0.020]] + [list(p) for p in left]
    # that runs clockwise seen from above; reverse to counterclockwise like rrect
    ring = list(reversed(ring))
    smooth = chaikin(ring, 3)
    # start at the back centre, on the axis, so the even resampling stays symmetric
    for i in range(len(smooth)):
        a, b = smooth[i], smooth[(i + 1) % len(smooth)]
        if a[0] > 0 >= b[0] and a[1] > 0:
            f = a[0] / (a[0] - b[0])
            start = [0.0, a[1] + (b[1] - a[1]) * f]
            smooth = [start] + smooth[i + 1:] + smooth[:i + 1]
            break
    return [r5(p) for p in resample(smooth, 34)]


def controller():
    mats = {k: {"color": v} for k, v in COLORS.items()}
    mats.update({
        "badge": sheet_mat("#b9506f", "pad_badge"),
        "blossom": {"color": "#9fdcc4", "texture": {"sheet": "art", "cell": "sakura_mint", "bits": 4,
                                                    "projection": "fit"}},
        "top_print": {"color": "#f2b6c6", "texture": {"texels": LID_TILE,
                                                      "colors": ["#f2b6c6", "#eba2b6", "#f6c0a8", "#efaabd"],
                                                      "projection": "planar", "axis": "y", "scale": [0.04, 0.04]}},
        "btn_a": {"color": "#f3889f", "texture": {"sheet": "art", "cell": "btn_a", "bits": 4, "projection": "disc"}},
        "btn_b": {"color": "#f6d77a", "texture": {"sheet": "art", "cell": "btn_b", "bits": 4, "projection": "disc"}},
        "btn_x": {"color": "#9cc8f0", "texture": {"sheet": "art", "cell": "btn_x", "bits": 4, "projection": "disc"}},
        "btn_y": {"color": "#93d8b9", "texture": {"sheet": "art", "cell": "btn_y", "bits": 4, "projection": "disc"}},
    })
    out = controller_outline()
    nodes = []
    nodes.append(loft_mesh("shell", [(0.000, offset(out, 0.008)),
                                     (0.012, out),
                                     (0.021, out),
                                     (0.0275, offset(out, 0.003)),
                                     (0.0305, offset(out, 0.0085))],
                           ["cream", "pink", "pink", "pink"], "cream", "top_print"))
    TOP = 0.0305

    # d-pad on a mint plate, top left
    DX, DZ = -0.046, 0.010
    nodes.append(cyl("dpad_plate", 0.0175, 0.003, [DX, TOP - 0.0005, DZ], "mint", seg=12))
    a, b = 0.0135, 0.0045
    cross = [[b, a], [-b, a], [-b, b], [-a, b], [-a, -b], [-b, -b], [-b, -a], [b, -a], [b, -b], [a, -b],
             [a, b], [b, b]]
    nodes.append({"id": "dpad", "op": "extrude", "points": cross, "depth": 0.005, "material": "cream",
                  "transform": {"rotate": [90, 0, 0], "translate": [DX, TOP + 0.0033, DZ]}})

    # A B X Y on a mint plate, top right: X top, B bottom, Y left, A right
    BX, BZ = 0.046, 0.010
    nodes.append(cyl("face_plate", 0.0205, 0.003, [BX, TOP - 0.0005, BZ], "mint", seg=12))
    for name, dx, dz in (("btn_x", 0, 0.011), ("btn_b", 0, -0.011), ("btn_y", -0.011, 0),
                         ("btn_a", 0.011, 0)):
        nodes.append(cyl(name, 0.0063, 0.005, [BX + dx, TOP + 0.002, BZ + dz], name, seg=8))

    # analog stick on the left grip
    SX, SZ = -0.041, -0.032
    nodes.append(cyl("stick_ring", 0.0125, 0.003, [SX, TOP - 0.0006, SZ], "mint_deep", seg=8))
    nodes.append(cyl("stick_stem", 0.0040, 0.008, [SX, TOP + 0.004, SZ], "cream", seg=8, caps=False))
    nodes.append({"id": "stick_cap", "op": "lathe", "material": "mint", "segments": 10,
                  "profile": [[0.0088, 0.0], [0.0094, 0.0022], [0.0062, 0.0042], [0.0, 0.0048]],
                  "transform": {"translate": [SX, TOP + 0.0068, SZ]}})

    # a blossom printed on the right grip
    nodes.append(decal_top("blossom", [0.044, TOP + 0.0010, -0.035], 0.022, 0.022, "blossom", rot_y=18))

    # start, select and the 明 badge in the middle
    for name, x in (("select", -0.0095), ("start", 0.0095)):
        nodes.append(slab(name, [x, TOP + 0.0005, -0.003], [0.0105, 0.004, 0.0042], "cream",
                          rot_y=-20 if x < 0 else 20))
    nodes.append(slab("badge", [0, TOP - 0.0003, 0.019], [0.018, 0.0035, 0.012], "rose",
                      faces={"top": "badge"}, omit=("bottom",)))

    # L and R: curved bumpers following the shoulder edge
    for s_, name in ((-1, "l_button"), (1, "r_button")):
        edge = [p for p in out if p[1] > 0.012 and 0.024 < s_ * p[0] < 0.068]
        edge.sort(key=lambda p: s_ * p[0])
        nodes.append(bumper(name, edge, 0.0025, 0.007, 0.0150, 0.0255, "mint"))
    # the cable's strain relief at the back centre
    nodes.append(cyl("cord_boot", 0.0042, 0.012, [0, 0.016, 0.0435], "cream", seg=6, rot=[90, 0, 0]))

    return {
        "format": "mei-asset", "version": 1, "name": "sakura_controller",
        "budget": {"vertices": 900, "triangles": 800},
        "sheets": SHEETS,
        "materials": mats,
        "lighting": {"direction": [-0.45, 0.75, -0.55], "ambient": 0.62},
        "verification": VERIFY,
        "nodes": nodes,
    }


if __name__ == "__main__":
    write("console.asset.json", console())
    write("controller.asset.json", controller())
