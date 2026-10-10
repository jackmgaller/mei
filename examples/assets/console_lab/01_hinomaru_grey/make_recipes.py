"""Write console.asset.json and controller.asset.json for 01 Hinomaru Grey.

Run: python3 make_recipes.py (standard library only). Units are metres at real size; the console
faces -Z (its ports toward the front camera), the controller faces -Z too (its grips toward the
player, its shoulder buttons at +Z).
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = {"hino": {"image": "art/hinomaru_sheet.png"}}
VERIFY = {"required": True, "depth": True, "perspective": True}
LIGHT = {"direction": [-0.45, 0.85, -0.4], "ambient": 0.5}


def r(v, n=5):
    return round(v + 0.0, n)


def rrect(w, d, rad, cx=0.0, cz=0.0, steps=2):
    """A rounded rectangle in XZ, counter-clockwise seen from above, steps segments a corner."""
    pts = []
    hw, hd = w / 2 - rad, d / 2 - rad
    for (sx, sz, a0) in ((1, -1, -90), (1, 1, 0), (-1, 1, 90), (-1, -1, 180)):
        for k in range(steps + 1):
            a = math.radians(a0 + 90 * k / steps)
            pts.append([r(cx + sx * hw + rad * math.cos(a)), r(cz + sz * hd + rad * math.sin(a))])
    return pts


def loft(id_, sections, material, caps=True):
    return {"id": id_, "op": "loft", "material": material, "caps": caps,
            "sections": [{"y": r(y), "points": p} for y, p in sections]}


def box(id_, size, at, material, rotate=None, open_=None):
    n = {"id": id_, "op": "box", "size": [r(s) for s in size], "material": material,
         "transform": {"translate": [r(a) for a in at]}}
    if rotate:
        n["transform"]["rotate"] = rotate
    if open_:
        n["open"] = open_
    return n


def cyl(id_, radius, height, at, material, segments=12, rotate=None):
    n = {"id": id_, "op": "cylinder", "radius": r(radius), "height": r(height),
         "segments": segments, "material": material, "transform": {"translate": [r(a) for a in at]}}
    if rotate:
        n["transform"]["rotate"] = rotate
    return n


def newell(pts):
    n = [0.0, 0.0, 0.0]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


def faces_out(verts, faces, centre):
    """Wind every face outward from centre (the kit wants (b-a)x(c-a) pointing out)."""
    out = []
    for f in faces:
        pts = [verts[i] for i in f]
        n = newell(pts)
        c = [sum(p[k] for p in pts) / len(pts) for k in range(3)]
        d = sum(n[k] * (c[k] - centre[k]) for k in range(3))
        # Newell's normal follows (b-a)x(c-a), which the kit wants pointing out
        out.append(list(f) if d > 0 else list(reversed(f)))
    return out


def slab(id_, x0, x1, y0, y1, z0, z1, top, side, bottom=False):
    """A box as a mesh: the top face in one material (a fit texture), the sides in another."""
    v = [[x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1],
         [x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]]
    v = [[r(a) for a in p] for p in v]
    f = [[4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    m = [top, side, side, side, side]
    if bottom:
        f.append([0, 1, 2, 3]); m.append(side)
    c = [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2]
    return {"id": id_, "op": "mesh", "vertices": v, "faces": faces_out(v, f, c), "face_materials": m}


def panel_z(id_, x0, x1, y0, y1, z_in, z_out, face, side):
    """A raised panel on a wall of constant z: its outer face (at z_out) in one material, its four
    edges in another, its inner end (at z_in, buried in the wall) left open."""
    v = [[x0, y0, z_in], [x1, y0, z_in], [x1, y1, z_in], [x0, y1, z_in],
         [x0, y0, z_out], [x1, y0, z_out], [x1, y1, z_out], [x0, y1, z_out]]
    v = [[r(a) for a in p] for p in v]
    f = [[4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    c = [(x0 + x1) / 2, (y0 + y1) / 2, (z_in + z_out) / 2]
    return {"id": id_, "op": "mesh", "vertices": v, "faces": faces_out(v, f, c),
            "face_materials": [face, side, side, side, side]}


def quad_z(id_, x0, x1, y0, y1, z, facing, material):
    """One rectangle in a plane of constant z, seen from -Z (facing -1) or +Z (facing +1)."""
    v = [[r(x0), r(y0), r(z)], [r(x1), r(y0), r(z)], [r(x1), r(y1), r(z)], [r(x0), r(y1), r(z)]]
    f = faces_out(v, [[0, 1, 2, 3]], [(x0 + x1) / 2, (y0 + y1) / 2, z - facing])
    return {"id": id_, "op": "mesh", "vertices": v, "faces": f, "material": material}


def quad_y(id_, x0, x1, z0, z1, y, material):
    """One rectangle facing up."""
    v = [[r(x0), r(y), r(z0)], [r(x1), r(y), r(z0)], [r(x1), r(y), r(z1)], [r(x0), r(y), r(z1)]]
    f = faces_out(v, [[0, 1, 2, 3]], [(x0 + x1) / 2, y - 1, (z0 + z1) / 2])
    return {"id": id_, "op": "mesh", "vertices": v, "faces": f, "material": material}


def sheet_mat(colour, cell, emissive=False, projection="fit"):
    m = {"color": colour, "texture": {"sheet": "hino", "cell": cell, "bits": 8, "projection": projection}}
    if emissive:
        m["class"] = "emissive"
    return m


# --------------------------------------------------------------------------------------------
# Console: 0.290 x 0.078 (0.122 with the cart) x 0.220 m

W, D = 0.290, 0.220
TOP = 0.064            # the deck
SEAM = 0.030           # where the upper shell laps over the lower
FRONT = -D / 2


def console():
    mats = {
        "shell": {"color": "#cbc6bb"},
        "lower": {"color": "#b5b0a5"},
        "plinth": {"color": "#8f8a80"},
        "seam": {"color": "#7c7870"},
        "bay": {"color": "#c2bdb2"},
        "slot_lip": {"color": "#6c6964"},
        "slot_well": {"color": "#1c1c20"},
        "cart": {"color": "#55555c"},
        "cart_label": sheet_mat("#e8862e", "cart"),
        "ring": {"color": "#efece4"},
        "hinomaru": {"color": "#c8281e"},
        "reset": {"color": "#a29e94"},
        "led_sun": {"color": "#ff9a30", "class": "emissive", "palette": True},
        "led_moon": {"color": "#9cc4ff", "class": "emissive", "palette": True},
        "logo": sheet_mat("#2b2d33", "logo"),
        "plate_edge": {"color": "#2b2d33"},
        "fascia": sheet_mat("#b0aca3", "fascia"),
        "collar": {"color": "#6a6862", "double_sided": True},
        "rear": sheet_mat("#b0aca3", "rear"),
        "jack": {"color": "#2a2a2e"},
        "brass": {"color": "#c0a058"},
        "vent": {"color": "#bdb8ad", "texture": {"pattern": "stripes", "colors": ["#c4bfb4", "#77736b"],
                                                 "size": 8, "params": {"count": 2, "axis": "u"},
                                                 "projection": "planar", "axis": "y", "scale": [0.008, 0.008]}},
        "foot": {"color": "#3a3a3e"},
    }
    nodes = []
    # the dark plinth the shell stands on, a step in from the walls
    nodes.append(loft("plinth", [(0.0, rrect(W - 0.030, D - 0.030, 0.010)),
                                 (0.011, rrect(W - 0.018, D - 0.018, 0.012))], "plinth"))
    # the shell: straight walls, then a bevel up to the deck
    # the lower shell, a shade darker, and the upper shell lapping over it by a hair
    nodes.append(loft("lower", [(0.009, rrect(W, D, 0.016)),
                                (SEAM + 0.001, rrect(W, D, 0.016))], "lower"))
    nodes.append(loft("seam", [(SEAM - 0.0016, rrect(W + 0.0008, D + 0.0008, 0.0164)),
                               (SEAM + 0.0002, rrect(W + 0.0008, D + 0.0008, 0.0164))], "seam", caps=False))
    nodes.append(loft("shell", [(SEAM, rrect(W + 0.0014, D + 0.0014, 0.0167)),
                                (0.052, rrect(W + 0.0014, D + 0.0014, 0.0167)),
                                (TOP, rrect(W - 0.016, D - 0.016, 0.010))], "shell"))
    # the cartridge bay: a raised block on the rear half of the deck
    bz = 0.034
    nodes.append(loft("bay", [(TOP - 0.006, rrect(0.172, 0.112, 0.014, cz=bz)),
                              (0.071, rrect(0.172, 0.112, 0.014, cz=bz)),
                              (0.076, rrect(0.160, 0.100, 0.009, cz=bz))], "bay"))
    nodes.append(loft("slot_lip", [(0.0745, rrect(0.126, 0.034, 0.005, cz=bz)),
                                   (0.0772, rrect(0.124, 0.032, 0.004, cz=bz))], "slot_lip"))
    nodes.append(box("slot_well", [0.112, 0.003, 0.022], [0, 0.0765, bz], "slot_well"))
    # a launch cart standing in the slot
    cart_pts = [[-0.051, 0.0], [0.051, 0.0], [0.051, 0.044], [0.046, 0.050], [0.020, 0.050],
                [0.017, 0.047], [-0.017, 0.047], [-0.020, 0.050], [-0.046, 0.050], [-0.051, 0.044]]
    nodes.append({"id": "cart", "op": "extrude", "points": cart_pts, "depth": 0.016,
                  "material": "cart", "transform": {"translate": [0, 0.070, bz]}})
    nodes.append(quad_z("cart_label", -0.025, 0.025, 0.0775, 0.1175, bz - 0.0089, -1, "cart_label"))
    # the deck's front: badge on the left, reset, the two lamps and the hinomaru power button
    lz = -0.062
    nodes.append(slab("logo", -0.115, -0.051, TOP - 0.003, TOP + 0.0012, lz - 0.012, lz + 0.012,
                      "logo", "plate_edge"))
    px = 0.093
    nodes.append(cyl("power_ring", 0.019, 0.006, [px, TOP - 0.0015, lz], "ring", segments=20))
    nodes.append(cyl("power", 0.0130, 0.008, [px, TOP + 0.0, lz], "hinomaru", segments=20))
    nodes.append(loft("reset", [(TOP - 0.003, rrect(0.020, 0.011, 0.004, cx=0.050, cz=lz)),
                                (TOP + 0.0015, rrect(0.020, 0.011, 0.004, cx=0.050, cz=lz)),
                                (TOP + 0.0028, rrect(0.017, 0.008, 0.003, cx=0.050, cz=lz))], "reset"))
    nodes.append(box("led_sun", [0.005, 0.003, 0.0025], [0.062, TOP, -0.091], "led_sun"))
    nodes.append(box("led_moon", [0.005, 0.003, 0.0025], [0.072, TOP, -0.091], "led_moon"))
    # cooling slats on the deck either side of the bay
    for side, sx in (("l", -1), ("r", 1)):
        nodes.append(slab("vent_" + side, sx * 0.104 - 0.019, sx * 0.104 + 0.019,
                          TOP - 0.002, TOP + 0.0008, 0.012, 0.086, "vent", "seam"))
    # the front: printed fascia with raised collars round the two controller ports
    fy0, fy1, fw = 0.0105, 0.0465, 0.144
    nodes.append(panel_z("fascia", -fw / 2, fw / 2, fy0, fy1, FRONT + 0.003, FRONT - 0.0025,
                         "fascia", "lower"))
    texel = fw / 128
    for k, tx in enumerate((34, 94)):
        cx = -fw / 2 + (tx - 0.5) * texel
        cy = fy1 - (20.5 / 32) * (fy1 - fy0)
        nodes.append(box("collar_%d" % (k + 1), [27.5 * texel, 16.5 * texel, 0.006],
                         [cx, cy, FRONT - 0.0040], "collar", open_=["back", "front"]))
    # the back: MeiNet antenna jack, AV out, DC in, over their printed names
    ry0, ry1, rw = 0.018, 0.042, 0.096
    nodes.append(panel_z("rear", -rw / 2, rw / 2, ry0, ry1, D / 2 - 0.003, D / 2 + 0.0025,
                         "rear", "lower"))
    jy = ry1 - 4.5 / 16 * (ry1 - ry0)
    ux = lambda u: rw / 2 - u / 64 * rw   # rear texel column -> x (u runs toward -X there)
    nodes.append(cyl("meinet_jack", 0.0032, 0.010, [ux(11), jy, D / 2 + 0.0065], "brass",
                     segments=8, rotate=[90, 0, 0]))
    nodes.append(cyl("meinet_jack_base", 0.0055, 0.004, [ux(11), jy, D / 2 + 0.0030], "brass",
                     segments=8, rotate=[90, 0, 0]))
    nodes.append(box("av_out", [0.017, 0.0075, 0.006], [ux(33), jy, D / 2 + 0.0035], "jack"))
    nodes.append(cyl("dc_in", 0.0042, 0.006, [ux(54), jy, D / 2 + 0.0035], "jack",
                     segments=8, rotate=[90, 0, 0]))
    return {
        "format": "mei-asset", "version": 1, "name": "hinomaru_console",
        "budget": {"vertices": 1200, "triangles": 1200},
        "sheets": SHEET, "materials": mats, "lighting": LIGHT, "verification": VERIFY,
        "nodes": nodes,
    }


# --------------------------------------------------------------------------------------------
# Controller: about 0.152 x 0.040 x 0.110 m

def pad_outline():
    """The pad seen from above, grips toward -Z: right half, then mirrored."""
    right = [(0.0, 0.036), (0.040, 0.038), (0.058, 0.036), (0.068, 0.030),
             (0.074, 0.018), (0.076, 0.000), (0.0715, -0.038), (0.0645, -0.060),
             (0.0565, -0.0705), (0.0465, -0.0725), (0.0375, -0.067), (0.031, -0.054),
             (0.024, -0.042), (0.013, -0.035)]
    left = [(-x, z) for x, z in reversed(right[1:])]
    pts = right + [(0.0, -0.033)] + left
    # counter-clockwise from above, as rrect makes them
    return pts


def offset(pts, d):
    """Move a closed outline's points along their mitred normals; d < 0 shrinks."""
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    sgn = 1 if area > 0 else -1
    out = []
    for i in range(n):
        p, a, b = pts[i], pts[i - 1], pts[(i + 1) % n]
        def nrm(u, v):
            dx, dz = v[0] - u[0], v[1] - u[1]
            l = math.hypot(dx, dz)
            return (sgn * dz / l, -sgn * dx / l)
        n1, n2 = nrm(a, p), nrm(p, b)
        m = (n1[0] + n2[0], n1[1] + n2[1])
        ml = math.hypot(*m)
        m = (m[0] / ml, m[1] / ml)
        k = d / max(0.35, m[0] * n1[0] + m[1] * n1[1])
        out.append([r(p[0] + m[0] * k), r(p[1] + m[1] * k)])
    return out


def controller():
    mats = {
        "shell": {"color": "#cbc6bb"},
        "under": {"color": "#a8a398"},
        "well": {"color": "#b4afa5"},
        "dpad": {"color": "#3a3a40"},
        "btn_a": sheet_mat("#c8281e", "btn_a", projection="disc"),
        "btn_b": sheet_mat("#46464c", "btn_b", projection="disc"),
        "btn_x": sheet_mat("#96928c", "btn_x", projection="disc"),
        "btn_y": sheet_mat("#96928c", "btn_y", projection="disc"),
        "pill": {"color": "#6c6964"},
        "stick_base": {"color": "#6c6964"},
        "stick": {"color": "#3a3a40", "smooth": True},
        "shoulder": {"color": "#8f8a80"},
        "badge": sheet_mat("#cbc6bb", "badge"),
        "lbl_start": sheet_mat("#cbc6bb", "lbl_start"),
        "lbl_select": sheet_mat("#cbc6bb", "lbl_select"),
        "edge": {"color": "#bdb8ad"},
        "cable": {"color": "#8f8a80", "smooth": True},
    }
    o = pad_outline()
    T = 0.027
    nodes = []
    nodes.append(loft("body", [(0.000, offset(o, -0.0045)),
                               (0.007, o),
                               (0.0225, offset(o, -0.0018)),
                               (T, offset(o, -0.0065))], "shell"))
    # the darker under-shell seam, a hair proud
    nodes.append(loft("seam", [(0.0095, offset(o, 0.0006)), (0.0115, offset(o, 0.0006))],
                      "under", caps=False))
    # d-pad: a dished well and a cross
    dx, dz = -0.0465, 0.006
    nodes.append(cyl("dpad_well", 0.0160, 0.004, [dx, T - 0.0013, dz], "well", segments=10))
    a, b = 0.0128, 0.0041
    cross = [[a, b], [b, b], [b, a], [-b, a], [-b, b], [-a, b], [-a, -b], [-b, -b], [-b, -a],
             [b, -a], [b, -b], [a, -b]]
    nodes.append({"id": "dpad", "op": "extrude", "points": cross, "depth": 0.006, "material": "dpad",
                  "transform": {"rotate": [90, 0, 0], "translate": [dx, T + 0.0012, dz]}})
    # face buttons: A right, B below, X above, Y left
    fx, fz, sp = 0.0465, 0.006, 0.0118
    nodes.append(cyl("face_well", 0.0205, 0.004, [fx, T - 0.0013, fz], "well", segments=10))
    for name, ox, oz in (("a", sp, 0), ("b", 0, -sp), ("x", 0, sp), ("y", -sp, 0)):
        nodes.append(cyl("btn_" + name, 0.0056, 0.0075, [fx + ox, T + 0.0006, fz + oz],
                         "btn_" + name, segments=8))
    # start and select, slanted pills, their names printed under them
    for name, sx in (("select", -1), ("start", 1)):
        cx = sx * 0.0115
        nodes.append(box(name, [0.0095, 0.004, 0.0034], [cx, T + 0.0002, 0.002], "pill",
                         rotate=[0, -sx * 20, 0]))
        nodes.append(quad_y("lbl_" + name, cx - 0.006, cx + 0.006, -0.0060, -0.0020, T + 0.0006,
                            "lbl_" + name))
    # the badge, top centre
    nodes.append(quad_y("badge", -0.012, 0.012, 0.016, 0.025, T + 0.0006, "badge"))
    # the analog stick, lower left on the inner grip
    kx, kz = -0.0265, -0.0255
    nodes.append(cyl("stick_base", 0.0115, 0.005, [kx, T - 0.0012, kz], "stick_base", segments=12))
    nodes.append(cyl("stick_post", 0.0035, 0.010, [kx, T + 0.004, kz], "stick", segments=6))
    nodes.append({"id": "stick_cap", "op": "lathe", "segments": 12, "material": "stick",
                  "profile": [[0.0, 0.0], [0.0094, 0.0010], [0.0090, 0.0036], [0.0, 0.0046]],
                  "transform": {"translate": [kx, T + 0.0075, kz]}})
    # shoulder buttons on the far edge
    for side, sx in (("l", -1), ("r", 1)):
        nodes.append(loft("shoulder_" + side,
                          [(0.0095, rrect(0.034, 0.015, 0.005, cx=sx * 0.053, cz=0.0355, steps=1)),
                           (0.0215, rrect(0.034, 0.015, 0.005, cx=sx * 0.053, cz=0.0355, steps=1)),
                           (0.0245, rrect(0.030, 0.011, 0.003, cx=sx * 0.053, cz=0.0350, steps=1))],
                          "shoulder"))
    # the cable leaving the far edge
    nodes.append({"id": "strain_relief", "op": "lathe", "segments": 8, "material": "cable",
                  "profile": [[0.0048, 0.0], [0.0038, 0.010], [0.0025, 0.021]],
                  "transform": {"rotate": [90, 0, 0], "translate": [0, 0.0135, 0.032]}})
    return {
        "format": "mei-asset", "version": 1, "name": "hinomaru_controller",
        "budget": {"vertices": 800, "triangles": 800},
        "sheets": SHEET, "materials": mats, "lighting": LIGHT, "verification": VERIFY,
        "nodes": nodes,
    }


def write(name, recipe):
    with open(os.path.join(HERE, name), "w") as fh:
        json.dump(recipe, fh, indent=1)
        fh.write("\n")


if __name__ == "__main__":
    write("console.asset.json", console())
    write("controller.asset.json", controller())
