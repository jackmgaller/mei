#!/usr/bin/env python3
"""Pocket Cube: writes art/pocket_sheet.png (+ .sheet.json), console.asset.json and
controller.asset.json beside this script.

Real size, metres. The console faces -Z, Y up, its base at y = 0. Every part is a `mesh`
node built here from stacked outlines (prism_stack) or rings with a well (ring_well), each
placed on a face of the body by a frame (origin, U, V, W): u right and v up as the face is
seen from outside, w out of it. Winding is set from an outward hint per polygon.

    python3 make_pocket_cube.py
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- 2D helpers

def area2(pts):
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
               for i in range(len(pts)))


def ccw(pts):
    return pts if area2(pts) > 0 else pts[::-1]


def offset(pts, d):
    """Move a CCW outline inward by d (miter)."""
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % n]
        e1 = (p1[0] - p0[0], p1[1] - p0[1])
        e2 = (p2[0] - p1[0], p2[1] - p1[1])
        l1 = math.hypot(*e1); l2 = math.hypot(*e2)
        n1 = (-e1[1] / l1, e1[0] / l1)
        n2 = (-e2[1] / l2, e2[0] / l2)
        m = (n1[0] + n2[0], n1[1] + n2[1])
        lm = math.hypot(*m)
        m = (m[0] / lm, m[1] / lm)
        k = d / max(0.3, m[0] * n1[0] + m[1] * n1[1])
        out.append((p1[0] + m[0] * k, p1[1] + m[1] * k))
    return out


def rrect(w, h, r, seg=3, cx=0.0, cy=0.0):
    """Rounded rectangle, CCW, `seg` steps per corner."""
    hx, hy = w / 2, h / 2
    r = min(r, hx, hy)
    pts = []
    for (sx, sy, a0) in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
        ccx, ccy = sx * (hx - r), sy * (hy - r)
        for k in range(seg + 1):
            a = math.radians(a0 + 90 * k / seg)
            pts.append((cx + ccx + r * math.cos(a), cy + ccy + r * math.sin(a)))
    return pts


def rect(w, h):
    return [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]


def circle(r, n, cx=0.0, cy=0.0, phase=0.0):
    return [(cx + r * math.cos(2 * math.pi * (k + phase) / n),
             cy + r * math.sin(2 * math.pi * (k + phase) / n)) for k in range(n)]


def ear_clip(pts):
    """Triangles (index triples) of a simple CCW polygon."""
    idx = list(range(len(pts)))
    tris = []

    def inside(p, a, b, c):
        def s(p1, p2, p3):
            return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
        d1, d2, d3 = s(p, a, b), s(p, b, c), s(p, c, a)
        return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))

    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = pts[i0], pts[i1], pts[i2]
            cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cross <= 1e-12:
                continue
            if any(inside(pts[j], a, b, c) for j in idx if j not in (i0, i1, i2)):
                continue
            tris.append((i0, i1, i2))
            idx.pop(k)
            break
    tris.append(tuple(idx))
    return tris

# ---------------------------------------------------------------- 3D mesh

def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def newell(pts):
    n = [0.0, 0.0, 0.0]
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


class Frame:
    def __init__(self, origin, U, V, W):
        self.o, self.U, self.V, self.W = origin, U, V, W

    def p(self, u, v, w):
        o, U, V, W = self.o, self.U, self.V, self.W
        return tuple(round(o[i] + u * U[i] + v * V[i] + w * W[i], 6) for i in range(3))

    def d(self, u, v, w):
        U, V, W = self.U, self.V, self.W
        return tuple(u * U[i] + v * V[i] + w * W[i] for i in range(3))


def F_front(x, y, z=-0.100):  return Frame((x, y, z), (1, 0, 0), (0, 1, 0), (0, 0, -1))
def F_back(x, y, z=0.100):    return Frame((x, y, z), (-1, 0, 0), (0, 1, 0), (0, 0, 1))
def F_top(x, z, y):           return Frame((x, y, z), (1, 0, 0), (0, 0, 1), (0, 1, 0))
def F_right(z, y, x=0.100):   return Frame((x, y, z), (0, 0, 1), (0, 1, 0), (1, 0, 0))
def F_left(z, y, x=-0.100):   return Frame((x, y, z), (0, 0, -1), (0, 1, 0), (-1, 0, 0))


class Mesh:
    def __init__(self):
        self.v, self.key, self.f, self.fm = [], {}, [], []

    def vid(self, p):
        k = tuple(round(c, 6) for c in p)
        if k not in self.key:
            self.key[k] = len(self.v)
            self.v.append(list(k))
        return self.key[k]

    def poly(self, pts, mat, hint):
        ids = [self.vid(p) for p in pts]
        # drop repeated consecutive vertices
        clean = []
        for i in ids:
            if not clean or clean[-1] != i:
                clean.append(i)
        if len(clean) > 1 and clean[0] == clean[-1]:
            clean.pop()
        if len(clean) < 3:
            return
        P = [self.v[i] for i in clean]
        if dot(newell(P), hint) < 0:
            clean.reverse()
        flat = any(len({round(self.v[i][a], 6) for i in clean}) == 1 for a in range(3))
        if len(clean) > 3 and not flat:
            for k in range(1, len(clean) - 1):
                self.f.append([clean[0], clean[k], clean[k + 1]])
                self.fm.append(mat)
            return
        self.f.append(clean)
        self.fm.append(mat)

    def node(self, nid):
        return {"id": nid, "op": "mesh", "vertices": self.v, "faces": self.f,
                "face_materials": self.fm}


def prism_stack(m, fr, outline, rings, band_mats, top_mat, bottom_mat=None):
    """Stack of an outline: rings [(inset, w)], w a number or f(u, v); walls between them,
    a top cap on the last ring and optionally a bottom cap on the first."""
    outline = ccw(outline)
    n = len(outline)
    R = []
    for inset, w in rings:
        o2 = offset(outline, inset) if inset else outline
        R.append([fr.p(u, v, w(u, v) if callable(w) else w) for (u, v) in o2])
    for k in range(len(R) - 1):
        mat = band_mats[k] if isinstance(band_mats, list) else band_mats
        if mat is None:
            continue
        for i in range(n):
            j = (i + 1) % n
            e = (outline[j][0] - outline[i][0], outline[j][1] - outline[i][1])
            hint = fr.d(e[1], -e[0], 0)  # outward for a CCW outline
            m.poly([R[k][i], R[k][j], R[k + 1][j], R[k + 1][i]], mat, hint)
    if top_mat:
        m.poly(R[-1], top_mat, fr.d(0, 0, 1))
    if bottom_mat:
        base = rings[0]
        if callable(base[1]):
            o2 = offset(outline, base[0]) if base[0] else outline
            for (a, b, c) in ear_clip(o2):
                m.poly([R[0][a], R[0][b], R[0][c]], bottom_mat, fr.d(0, 0, -1))
        else:
            m.poly(R[0], bottom_mat, fr.d(0, 0, -1))


def ring_well(m, fr, outer, inner, w_base, w_top, w_floor, mat_out, mat_top, mat_in, mat_floor,
              bevel=None):
    """A raised rim around a shallow well: outer walls, a top ring, inner walls, a floor.
    `outer` and `inner` must have the same point count. bevel=(inset, dw) chamfers the rim."""
    outer, inner = ccw(outer), ccw(inner)
    n = len(outer)
    assert len(inner) == n
    top_outer = outer
    w_rim = w_top
    if bevel:
        top_outer = offset(outer, bevel[0])
        w_rim = w_top
    for i in range(n):
        j = (i + 1) % n
        e = (outer[j][0] - outer[i][0], outer[j][1] - outer[i][1])
        hint = fr.d(e[1], -e[0], 0)
        wt = w_top - bevel[1] if bevel else w_top
        m.poly([fr.p(*outer[i], w_base), fr.p(*outer[j], w_base),
                fr.p(*outer[j], wt), fr.p(*outer[i], wt)], mat_out, hint)
        if bevel:
            m.poly([fr.p(*outer[i], wt), fr.p(*outer[j], wt),
                    fr.p(*top_outer[j], w_rim), fr.p(*top_outer[i], w_rim)], mat_out,
                   fr.d(e[1], -e[0], 1))
        m.poly([fr.p(*top_outer[i], w_rim), fr.p(*top_outer[j], w_rim),
                fr.p(*inner[j], w_rim), fr.p(*inner[i], w_rim)], mat_top, fr.d(0, 0, 1))
        ei = (inner[j][0] - inner[i][0], inner[j][1] - inner[i][1])
        m.poly([fr.p(*inner[i], w_rim), fr.p(*inner[j], w_rim),
                fr.p(*inner[j], w_floor), fr.p(*inner[i], w_floor)], mat_in,
               fr.d(-ei[1], ei[0], 0))
    m.poly([fr.p(u, v, w_floor) for (u, v) in inner], mat_floor, fr.d(0, 0, 1))


def single(nid, build):
    m = Mesh()
    build(m)
    return m.node(nid)

# ---------------------------------------------------------------- art

SUN = (242, 140, 40)
MOON = (156, 192, 236)


def draw_sheet():
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    S = 8  # supersample
    cells = {}
    sheet = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    hira = "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc"
    if not os.path.exists(hira):
        hira = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
    avenir = "/System/Library/Fonts/Avenir Next.ttc"

    def mei_glyph(img, x, y, size, split=0.47, shadow=True):
        """明 with 日 in sun orange and 月 in moon blue, top-left at x, y."""
        f = ImageFont.truetype(hira, size)
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).text((x, y), "明", font=f, fill=255)
        bb = mask.getbbox()
        cut = bb[0] + int((bb[2] - bb[0]) * split)
        sun = Image.new("RGBA", img.size, SUN + (255,))
        moon = Image.new("RGBA", img.size, MOON + (255,))
        left = mask.copy(); right = mask.copy()
        ImageDraw.Draw(left).rectangle([cut, 0, img.size[0], img.size[1]], fill=0)
        ImageDraw.Draw(right).rectangle([0, 0, cut - 1, img.size[1]], fill=0)
        if shadow:
            sh = mask.filter(ImageFilter.GaussianBlur(size * 0.02))
            dark = Image.new("RGBA", img.size, (8, 10, 14, 255))
            img.paste(dark, (int(size * 0.03), int(size * 0.04)), sh)
        img.paste(sun, (0, 0), left)
        img.paste(moon, (0, 0), right)
        return bb

    # logo badge: 96 x 32, charcoal, 明 + MEI
    w, h = 96, 32
    im = Image.new("RGBA", (w * S, h * S), (30, 33, 38, 255))
    d = ImageDraw.Draw(im)
    bb = mei_glyph(im, 6 * S, -1 * S, 30 * S)
    fa = ImageFont.truetype(avenir, 19 * S, index=1)  # Avenir Next Bold
    d.text((37 * S, 2 * S), "MEI", font=fa, fill=(250, 250, 248, 255))
    fs = ImageFont.truetype(avenir, 6 * S, index=5)
    d.text((38 * S, 23 * S), "SUN & MOON", font=fs, fill=(178, 186, 196, 255))
    im = im.resize((w, h), Image.LANCZOS)
    sheet.paste(im, (0, 0)); cells["logo"] = [0, 0, w, h]

    # cart label: 64 x 48
    w, h = 64, 48
    im = Image.new("RGBA", (w * S, h * S), (255, 255, 255, 255))
    d = ImageDraw.Draw(im)
    for yy in range(h * S):  # sky
        t = yy / (h * S)
        c = (int(120 + 120 * t), int(186 + 50 * t), int(236 - 40 * t), 255)
        d.line([(0, yy), (w * S, yy)], fill=c)
    d.ellipse([34 * S, 13 * S, 56 * S, 35 * S], fill=SUN + (255,))
    d.ellipse([10 * S, 15 * S, 18 * S, 23 * S], fill=(250, 250, 240, 255))
    d.ellipse([12 * S, 14 * S, 20 * S, 22 * S], fill=(120 + 60, 200, 225, 255))
    d.polygon([(0, 48 * S), (0, 34 * S), (14 * S, 25 * S), (26 * S, 33 * S), (40 * S, 27 * S),
               (64 * S, 37 * S), (64 * S, 48 * S)], fill=(46, 138, 143, 255))
    d.polygon([(0, 48 * S), (0, 41 * S), (20 * S, 36 * S), (44 * S, 42 * S), (64 * S, 40 * S),
               (64 * S, 48 * S)], fill=(30, 92, 98, 255))
    d.rectangle([0, 0, w * S, 9 * S], fill=(30, 33, 38, 255))
    d.rectangle([0, 9 * S, w * S, 10 * S], fill=SUN + (255,))
    mei_glyph(im, 2 * S, -1 * S, 10 * S, shadow=False)
    fb = ImageFont.truetype(avenir, 6 * S, index=1)
    d.text((14 * S, 1 * S), "MEI  64M", font=fb, fill=(240, 240, 236, 255))
    ft = ImageFont.truetype(avenir, 13 * S, index=1)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 1)):
        d.text((5 * S + dx * S // 2 * 2, 31 * S + dy * S // 2 * 2), "HARE!", font=ft,
               fill=(24, 40, 60, 255))
    d.text((5 * S, 31 * S), "HARE!", font=ft, fill=(255, 255, 255, 255))
    im = im.resize((w, h), Image.LANCZOS)
    sheet.paste(im, (0, 32)); cells["label"] = [0, 32, w, h]

    # button letters: 16 x 16 each, the button colour behind a letter
    letters = [("A", SUN, (255, 250, 240)), ("B", MOON, (34, 52, 86)),
               ("X", (236, 230, 214), (60, 64, 70)), ("Y", (86, 92, 102), (236, 230, 214))]
    fl = ImageFont.truetype(avenir, 12 * S, index=1)
    for k, (ch, bg, fg) in enumerate(letters):
        im = Image.new("RGBA", (16 * S, 16 * S), bg + (255,))
        d = ImageDraw.Draw(im)
        tb = d.textbbox((0, 0), ch, font=fl)
        d.text(((16 * S - (tb[2] - tb[0])) / 2 - tb[0], (16 * S - (tb[3] - tb[1])) / 2 - tb[1]),
               ch, font=fl, fill=fg + (255,))
        im = im.resize((16, 16), Image.LANCZOS)
        x = 96 + (k % 2) * 16
        y = (k // 2) * 16
        sheet.paste(im, (x, y)); cells["btn_" + ch.lower()] = [x, y, 16, 16]

    # small print under the top buttons: 32 x 8 each
    fp = ImageFont.truetype(avenir, 6 * S, index=1)
    for k, word in enumerate(("POWER", "RESET", "START", "SELECT")):
        im = Image.new("RGBA", (32 * S, 8 * S), (236, 230, 214, 255))
        d = ImageDraw.Draw(im)
        tb = d.textbbox((0, 0), word, font=fp)
        d.text(((32 * S - (tb[2] - tb[0])) / 2 - tb[0], (8 * S - (tb[3] - tb[1])) / 2 - tb[1]),
               word, font=fp, fill=(70, 74, 82, 255))
        im = im.resize((32, 8), Image.LANCZOS)
        x, y = 64, 32 + k * 8
        sheet.paste(im, (x, y)); cells["print_" + word.lower()] = [x, y, 32, 8]

    # back panel print: 64 x 16
    im = Image.new("RGBA", (64 * S, 16 * S), (30, 33, 38, 255))
    d = ImageDraw.Draw(im)
    fq = ImageFont.truetype(avenir, 5 * S, index=1)
    for x, word in ((3, "DC IN"), (24, "AV OUT"), (47, "MEINET")):
        d.text((x * S, 9 * S), word, font=fq, fill=(200, 204, 210, 255))
    d.text((3 * S, 1 * S), "MEI-0001  MADE IN JAPAN", font=fq, fill=(140, 146, 154, 255))
    im = im.resize((64, 16), Image.LANCZOS)
    sheet.paste(im, (64, 64)); cells["back_print"] = [64, 64, 64, 16]

    os.makedirs(os.path.join(HERE, "art"), exist_ok=True)
    sheet.save(os.path.join(HERE, "art", "pocket_sheet.png"))
    with open(os.path.join(HERE, "art", "pocket_sheet.sheet.json"), "w") as fh:
        json.dump({"format": "mei-sheet", "version": 1, "cells": cells}, fh, indent=1)
        fh.write("\n")

# ---------------------------------------------------------------- materials

COL = {
    "shell": "#2f878c",    # ramune teal
    "top": "#ece6d6",      # cream
    "base": "#363a41",     # charcoal
    "seam": "#141619",
    "trim": "#3d4148",
    "well": "#0b0c0e",
    "metal": "#b9bec6",
    "cart": "#61656d",
    "cart_dark": "#4a4e55",
    "sun": "#f28c28",
    "moon": "#9cc0ec",
    "dish": "#d6cfbd",
    "bezel": "#6e737c",
    "slate": "#565c66",
}


def mats(extra):
    out = {k: {"color": v} for k, v in COL.items()}
    out["metal"]["smooth"] = False
    out.update(extra)
    return out


def sheet_mat(color, cell, emissive=False):
    m = {"color": color, "texture": {"sheet": "pocket", "cell": cell, "bits": 8,
                                      "projection": "fit"}}
    if emissive:
        m["class"] = "emissive"
    return m

# ---------------------------------------------------------------- console

W = 0.200      # width and depth
HB = 0.176     # body height
TOPY = HB


def console():
    nodes = []

    # Body: a rounded cube, charcoal base band, a dark seam, teal walls, cream top.
    def body(m):
        fr = Frame((0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0))
        out = rrect(W, W, 0.024, seg=3)
        rings = [(0.005, 0.000), (0.0, 0.005), (0.0, 0.050), (0.003, 0.0535),
                 (0.0, 0.057), (0.0, 0.167), (0.007, TOPY)]
        bands = ["base", "base", "seam", "seam", "shell", "shell"]
        prism_stack(m, fr, out, rings, bands, "top", "base")
    nodes.append(single("body", body))

    # Cart slot collar on top, the cart standing in it.
    CZ = 0.028
    def collar(m):
        fr = F_top(0.0, CZ, TOPY)
        outer = rrect(0.128, 0.040, 0.008, seg=1)
        inner = rrect(0.110, 0.026, 0.002, seg=1)
        ring_well(m, fr, outer, inner, -0.003, 0.0075, 0.0035, "base", "base", "seam", "well",
                  bevel=(0.0025, 0.002))
    nodes.append(single("cart_slot", collar))

    def cart(m):
        # outline seen from the front: 0.104 wide, from inside the body up to y 0.256
        x0, x1, yb, yt = -0.052, 0.052, 0.150, 0.256
        ch = 0.007
        zf, zb = CZ - 0.010, CZ + 0.010
        out = [(x0, yb), (x1, yb), (x1, yt - ch), (x1 - ch, yt), (x0 + ch, yt), (x0, yt - ch)]
        lab = [(-0.043, 0.190), (0.043, 0.190), (0.043, 0.247), (-0.043, 0.247)]
        P = lambda q, z: (q[0], q[1], z)
        # front: label and the frame around it
        m.poly([P(q, zf) for q in lab], "label", (0, 0, -1))
        frame_polys = [
            [out[0], out[1], lab[1], lab[0]],
            [out[1], out[2], lab[2], lab[1]],
            [out[2], out[3], out[4], out[5], lab[3], lab[2]],
            [out[5], out[0], lab[0], lab[3]],
        ]
        for fp in frame_polys:
            m.poly([P(q, zf) for q in fp], "cart", (0, 0, -1))
        # back: grip ridges as bands
        m.poly([P(q, zb) for q in out], "cart", (0, 0, 1))
        # sides
        for i in range(len(out)):
            j = (i + 1) % len(out)
            if i == 0:
                continue  # bottom edge, inside the body
            a, b = out[i], out[j]
            hint = (b[1] - a[1], -(b[0] - a[0]), 0)
            hint = (-hint[0], -hint[1], 0) if area2(out) < 0 else hint
            m.poly([P(a, zf), P(b, zf), P(b, zb), P(a, zb)], "cart", hint)
        # grip ridges across the top of the back face
        for k in range(3):
            y = yt - 0.016 - k * 0.0065
            fr = Frame((0.0, y, zb), (-1, 0, 0), (0, 1, 0), (0, 0, 1))
            prism_stack(m, fr, rect(0.080, 0.0025), [(0, -0.001), (0, 0.0015)],
                        "cart_dark", "cart_dark")
    nodes.append(single("cart", cart))

    # Power (sun) and reset (moon) on the top, front corners, with their print.
    def button(m, x, z, r_dish, r_btn, h, mat, nseg):
        fr = F_top(x, z, TOPY)
        prism_stack(m, fr, circle(r_dish, nseg), [(0, -0.002), (0, 0.002)], "trim", "trim")
        prism_stack(m, fr, circle(r_btn, nseg), [(0, 0.001), (0, h), (0.0015, h + 0.0015)],
                    mat, mat)
    nodes.append(single("power", lambda m: button(m, -0.060, -0.050, 0.0175, 0.0135, 0.0055,
                                                    "sun", 12)))
    nodes.append(single("reset", lambda m: button(m, 0.060, -0.050, 0.0125, 0.0085, 0.0045,
                                                    "moon", 10)))

    def top_print(m):
        for x, mat in ((-0.060, "print_power"), (0.060, "print_reset")):
            fr = F_top(x, -0.078, TOPY)
            prism_stack(m, fr, rect(0.028, 0.007), [(0, -0.001), (0, 0.0006)], "top", mat)
    nodes.append(single("top_print", top_print))

    # Cart eject: a slider to the right of the slot.
    def eject(m):
        fr = F_top(0.078, CZ, TOPY)
        prism_stack(m, fr, rrect(0.007, 0.026, 0.002, seg=1), [(0, -0.002), (0, 0.0009)],
                    "seam", "well")
        prism_stack(m, Frame((0.078, TOPY, CZ + 0.004), (1, 0, 0), (0, 0, 1), (0, 1, 0)),
                    rrect(0.0085, 0.006, 0.0015, seg=1),
                    [(0, 0.0008), (0, 0.006), (0.001, 0.007)], "base", "base")
    nodes.append(single("eject", eject))

    # Front: badge, two memory card slots, two controller ports, player dots, LED.
    nodes.append(single("badge", badge_build))

    def card_slots(m):
        for sx in (-1, 1):
            fr = F_front(sx * 0.042, 0.080)
            ring_well(m, fr, rrect(0.038, 0.012, 0.004, seg=1), rrect(0.029, 0.004, 0.0015, seg=1),
                      -0.002, 0.004, 0.0015, "trim", "trim", "seam", "well")
    nodes.append(single("card_slots", card_slots))

    def ports(m):
        for sx in (-1, 1):
            fr = F_front(sx * 0.042, 0.0275)
            outer = port_outline(0.032, 0.022, 2)
            inner = port_outline(0.022, 0.012, 2)
            ring_well(m, fr, outer, inner, -0.002, 0.005, 0.0015, "bezel", "bezel", "seam", "well")
            # contact pins
            prism_stack(m, fr, [(-0.0065, 0.0005), (0.0065, 0.0005), (0.0065, 0.0025),
                                (-0.0065, 0.0025)], [(0, 0.001), (0, 0.0026)], "metal", "metal")
    nodes.append(single("ports", ports))

    def dots(m):
        for sx, mat in ((-1, "sun"), (1, "moon")):
            fr = F_front(sx * 0.042 + sx * -0.000, 0.098)
            prism_stack(m, fr, circle(0.0032, 8), [(0, -0.001), (0, 0.001)], mat, mat)
        fr = F_front(-0.070, 0.152)
        prism_stack(m, fr, circle(0.0022, 6), [(0, -0.001), (0, 0.0012)], "led", "led")
    nodes.append(single("player_dots", dots))

    # Sides: vent grilles.
    def vents(m):
        for fr in (F_right(0.0, 0.112), F_left(0.0, 0.112)):
            prism_stack(m, fr, rrect(0.120, 0.060, 0.006, seg=1), [(0, -0.002), (0, 0.0015),
                        (0.0012, 0.0025)], "shell", "vent")
    nodes.append(single("vents", vents))

    # Back: print strip, DC in, AV out, MeiNet antenna socket, rear vents.
    def back(m):
        fr = F_back(0.0, 0.040)
        prism_stack(m, fr, rect(0.150, 0.028), [(0, -0.002), (0, 0.0008)], "base", "back_print")
        fr = F_back(-0.054, 0.024)
        ring_well(m, fr, circle(0.0065, 6), circle(0.0035, 6), -0.002, 0.004, 0.0015,
                  "trim", "trim", "seam", "well")
        fr = F_back(-0.012, 0.024)
        ring_well(m, fr, rrect(0.026, 0.011, 0.003, seg=1), rrect(0.019, 0.006, 0.0015, seg=1),
                  -0.002, 0.004, 0.0015, "trim", "trim", "seam", "well")
        fr = F_back(0.046, 0.024)
        prism_stack(m, fr, circle(0.0068, 6), [(0, -0.002), (0, 0.004)], "metal", "metal")
        prism_stack(m, fr, circle(0.0040, 8), [(0, 0.003), (0, 0.013), (0.001, 0.014)],
                    "metal", "metal")
        fr = F_back(0.0, 0.118)
        prism_stack(m, fr, rect(0.140, 0.070), [(0, -0.002), (0, 0.0015)], "shell", "vent")
    nodes.append(single("back", back))

    materials = mats({
        "label": sheet_mat("#7ab8e0", "label"),
        "logo": sheet_mat("#1e2126", "logo"),
        "print_power": sheet_mat(COL["top"], "print_power"),
        "print_reset": sheet_mat(COL["top"], "print_reset"),
        "back_print": sheet_mat(COL["base"], "back_print"),
        "led": {"color": "#ff9a3a", "class": "emissive"},
        "vent": {"color": COL["shell"], "texture": {
            "pattern": "stripes", "colors": [COL["shell"], "#123638"], "size": 16,
            "params": {"count": 4, "axis": "v"}, "projection": "box", "scale": [0.016, 0.016]}},
    })
    return {
        "format": "mei-asset", "version": 1, "name": "pocket_cube_console",
        "budget": {"vertices": 2048, "triangles": 1200},
        "sheets": {"pocket": {"image": "art/pocket_sheet.png"}},
        "materials": materials,
        "lighting": {"direction": [-0.4, 0.85, -0.35], "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "nodes": nodes,
    }


def badge_build(m):
    fr = F_front(0.0, 0.132)
    plate = rrect(0.080, 0.030, 0.003, seg=1)
    prism_stack(m, fr, plate, [(0, -0.002), (0, 0.0012), (0.001, 0.002)], "base", None)
    top = offset(ccw(plate), 0.001)
    lab = [(0.0375, 0.0125), (-0.0375, 0.0125), (-0.0375, -0.0125), (0.0375, -0.0125)]
    c = [top[k * 2:(k + 1) * 2] for k in range(4)]
    up = fr.d(0, 0, 1)
    for k in range(4):
        n = (k + 1) % 4
        m.poly([fr.p(u, v, 0.002) for (u, v) in [lab[k]] + c[k]], "base", up)
        m.poly([fr.p(u, v, 0.002) for (u, v) in [c[k][-1], c[n][0], lab[n], lab[k]]], "base", up)
    m.poly([fr.p(u, v, 0.002) for (u, v) in lab], "logo", up)


def port_outline(w, h, n=4):
    """Controller port mouth: flat top, rounded bottom corners, a slight trapezoid."""
    r = h * 0.45
    pts = [(w / 2, h / 2), (-w / 2, h / 2)]
    bw = w / 2 * 0.86
    cx = -bw + r
    for k in range(n + 1):
        a = math.pi + (math.pi / 2) * k / n
        pts.append((cx + r * math.cos(a), -h / 2 + r + r * math.sin(a)))
    cx = bw - r
    for k in range(n + 1):
        a = 1.5 * math.pi + (math.pi / 2) * k / n
        pts.append((cx + r * math.cos(a), -h / 2 + r + r * math.sin(a)))
    return pts

# ---------------------------------------------------------------- controller

def ctrl_outline():
    half = [(0.034, 0.040), (0.056, 0.036), (0.070, 0.025),
            (0.077, 0.008), (0.077, -0.014), (0.073, -0.033), (0.064, -0.046), (0.051, -0.053),
            (0.038, -0.052), (0.027, -0.042), (0.016, -0.028), (0.0, -0.022)]
    right = half
    left = [(-x, z) for (x, z) in half[:-1]][::-1]
    return right + left  # clockwise from top centre around the right; ccw() fixes it


def grip(u, v):
    t = max(0.0, min(1.0, (-0.006 - v) / 0.040))
    t = t * t * (3 - 2 * t)
    g = max(0.0, min(1.0, (abs(u) - 0.012) / 0.030))
    return t * g


def controller():
    nodes = []
    TY = 0.030

    def shell(m):
        fr = Frame((0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0))
        rings = [(0.007, lambda u, v: 0.001 - 0.016 * grip(u, v)),
                 (0.0, lambda u, v: 0.009 - 0.012 * grip(u, v)),
                 (0.0, 0.019), (0.0, 0.0255), (0.0065, TY)]
        prism_stack(m, fr, ctrl_outline(), rings, ["base", "shell", "shell", "shell"], "top", "base")
    nodes.append(single("shell", shell))

    def dpad(m):
        fr = F_top(-0.046, 0.006, TY)
        prism_stack(m, fr, circle(0.0165, 12), [(0, -0.002), (0, 0.0015)], "dish", "dish")
        a, b = 0.0045, 0.0138
        cross = [(b, -a), (b, a), (a, a), (a, b), (-a, b), (-a, a), (-b, a), (-b, -a),
                 (-a, -a), (-a, -b), (a, -b), (a, -a)]
        prism_stack(m, fr, cross, [(0, 0.001), (0, 0.0055), (0.0008, 0.0065)], "base", "base")
    nodes.append(single("dpad", dpad))

    def face_buttons(m):
        cx, cz, s = 0.046, 0.006, 0.0118
        for (dx, dz, ch, mat) in ((s, 0, "a", "sun"), (0, -s, "b", "moon"),
                                  (0, s, "x", "top"), (-s, 0, "y", "slate")):
            fr = F_top(cx + dx, cz + dz, TY)
            prism_stack(m, fr, circle(0.0053, 8, phase=0.5),
                        [(0, 0.0005), (0, 0.0045), (0.0011, 0.0058)], mat, "btn_" + ch)
    nodes.append(single("face_buttons", face_buttons))

    def stick(m):
        fr = F_top(0.0, -0.002, TY)
        prism_stack(m, fr, circle(0.0105, 10), [(0, -0.002), (0.0035, 0.004)], "base", "seam")
        prism_stack(m, fr, circle(0.0032, 6), [(0, 0.003), (0, 0.009)], "base", None)
        prism_stack(m, fr, circle(0.0085, 10), [(0.0015, 0.0085), (0, 0.0115), (0.0012, 0.0128)],
                    "top", "dish")
    nodes.append(single("stick", stick))

    def start_select(m):
        for sx, cell in ((-1, "print_select"), (1, "print_start")):
            fr = F_top(sx * 0.0105, 0.015, TY)
            prism_stack(m, fr, rrect(0.010, 0.0042, 0.0016, seg=1),
                        [(0, -0.001), (0, 0.0026)], "base", "base")
            fr2 = F_top(sx * 0.0105, 0.0092, TY)
            prism_stack(m, fr2, rrect(0.016, 0.004, 0.0005, seg=1), [(0, -0.001), (0, 0.0004)],
                        "top", cell)
    nodes.append(single("start_select", start_select))

    def logo(m):
        fr = F_top(0.0, 0.0255, TY)
        prism_stack(m, fr, rrect(0.030, 0.0105, 0.0015, seg=1), [(0, -0.001), (0, 0.0008)],
                    "base", "logo")
    nodes.append(single("logo", logo))

    def shoulders(m):
        for sx in (-1, 1):
            fr = Frame((sx * 0.046, 0.0205, 0.0), (-1, 0, 0), (0, 1, 0), (0, 0, 1))
            out = rrect(0.030, 0.0105, 0.004, seg=1)
            prism_stack(m, fr, out, [(0, 0.030), (0, 0.0405), (0.002, 0.043)], "slate", "slate")
    nodes.append(single("shoulders", shoulders))

    def cable(m):
        fr = Frame((0.0, 0.014, 0.0), (-1, 0, 0), (0, 1, 0), (0, 0, 1))
        prism_stack(m, fr, circle(0.0048, 8), [(0, 0.036), (0, 0.047), (0.0015, 0.049)],
                    "seam", "seam")
    nodes.append(single("cable_nub", cable))

    # Rest it on its grips: the lowest point at y = 0.
    for n in nodes:
        for v in n["vertices"]:
            v[1] = round(v[1] + 0.015, 6)

    materials = mats({
        "logo": sheet_mat("#1e2126", "logo"),
        "btn_a": sheet_mat(COL["sun"], "btn_a"),
        "btn_b": sheet_mat(COL["moon"], "btn_b"),
        "btn_x": sheet_mat(COL["top"], "btn_x"),
        "btn_y": sheet_mat("#565c66", "btn_y"),
        "print_start": sheet_mat(COL["top"], "print_start"),
        "print_select": sheet_mat(COL["top"], "print_select"),
    })
    return {
        "format": "mei-asset", "version": 1, "name": "pocket_cube_controller",
        "budget": {"vertices": 2048, "triangles": 800},
        "sheets": {"pocket": {"image": "art/pocket_sheet.png"}},
        "materials": materials,
        "lighting": {"direction": [-0.4, 0.85, -0.35], "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "nodes": nodes,
    }


def used(recipe):
    """Keep only the materials the nodes use."""
    names = set()

    def walk(n):
        for fm in n.get("face_materials", []):
            names.add(fm)
        for c in n.get("children", []):
            walk(c)
    for n in recipe["nodes"]:
        walk(n)
    recipe["materials"] = {k: v for k, v in recipe["materials"].items() if k in names}
    return recipe


def write(name, recipe):
    text = json.dumps(used(recipe), indent=1)
    with open(os.path.join(HERE, name), "w") as fh:
        fh.write(text + "\n")


if __name__ == "__main__":
    draw_sheet()
    write("console.asset.json", console())
    write("controller.asset.json", controller())
