#!/usr/bin/env python3
"""Writes art/face.png, art/back.png and hanafuda_moon.asset.json. Run from anywhere (Pillow).

The level goal: the August hanafuda card, the full moon over susuki grass, about 1 m tall. A thick
gilt-edged card. The moon is printed on the face and framed by a thin gilt bead, a ring of
diamond section through the card that stands 1.7 cm proud of each face: a low relief that reads
from both sides as the card turns. The back, shared by every goal card, is seigaiha waves in dark
gold with a kikko crest inside the bead. The bead's faces slope at about 60 degrees, so none of them
lies within 3 cm of a parallel face (the Asset Kit's close-face rule).
"""
import json
import math
import os

from PIL import Image, ImageColor, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "art")
os.makedirs(ART, exist_ok=True)

# ---------------------------------------------------------------- card geometry (metres)
W, H, T = 0.62, 1.0, 0.05          # card width, height, thickness
CR, CSEG = 0.05, 3                 # rounded corners: radius, segments a corner
BASE = 0.0                         # card bottom (the cart floats and spins it about Y)
MOON_Y = BASE + 0.69               # moon centre
MOON_R = 0.18                      # the printed moon (the bead's inner edge meets the face here)
BEAD_IN, BEAD_OUT, BEAD_TOP = 0.16, 0.21, 0.042   # the bead's diamond section: radii, half height
BEAD_SEG = 16

# ---------------------------------------------------------------- texture (texels)
TW, TH = 64, 104                   # 0.62 x 1.0 m: about 1 cm a texel
GOLD, GOLD_DK = "#e8b83a", "#9a6a1c"
INK = "#17121a"
SKY, SKY_DK = "#d8282c", "#a81a22"
MOON, MOON_SH = "#fbf4dc", "#e6d6a8"
GRASS, GRASS_HI = "#8c8478", "#d8d0bc"


def tex_xy(x, y):
    """A card point (metres, x centred, y from BASE) to texel coordinates."""
    return (x / W + 0.5) * TW, (1 - (y - BASE) / H) * TH


def border(d, inner):
    d.rectangle((0, 0, TW - 1, TH - 1), fill=GOLD)
    d.rectangle((1, 1, TW - 2, TH - 2), outline=GOLD_DK)
    d.rectangle((3, 3, TW - 4, TH - 4), fill=INK)
    d.rectangle((4, 4, TW - 5, TH - 5), fill=inner)


def face():
    im = Image.new("RGB", (TW, TH), SKY)
    d = ImageDraw.Draw(im)
    border(d, SKY)
    # a darker band of sky at the top, the old cards' printed gradient done in two steps
    d.rectangle((4, 4, TW - 5, 13), fill=SKY_DK)
    d.rectangle((4, 14, TW - 5, 15), fill=SKY)
    for x in range(4, TW - 4, 2):
        d.point((x, 14), fill=SKY_DK)
    # the moon (its edge under the bead)
    mx, my = tex_xy(0, MOON_Y)
    r = MOON_R / W * TW
    d.ellipse((mx - r, my - r, mx + r, my + r), fill=MOON)
    # the hill: a black dome over the lower half
    d.ellipse((-22, 58, TW + 22, 58 + 2 * 70), fill=INK)
    d.rectangle((4, 90, TW - 5, TH - 5), fill=INK)
    # susuki along the crest: tall blades against the red sky, leaning right as in the wind
    rng = 0x5eed
    for i, x0 in enumerate(range(5, TW - 4, 3)):
        rng = (rng * 1103515245 + 12345) & 0x7fffffff
        crest = 58 + 70 - math.sqrt(max(0.0, 70 ** 2 - ((x0 - TW / 2) * 70 / (TW / 2 + 22)) ** 2))
        hgt = 5 + (rng >> 8) % 6 + (4 if i % 4 == 1 else 0)
        lean = 2 + (rng >> 12) % 3
        top = (x0 + lean, crest - hgt)
        d.polygon([(x0 - 1, crest + 2), (x0 + 1, crest + 2), top], fill=INK)
    # three plumes over the crest: seed heads on bending stalks, pale against the red
    for px, py, ln in ((12, 60, 9), (43, 56, 11), (53, 62, 8)):
        stalk = [(px - k // 3, py + ln - k) for k in range(ln)]
        d.line(stalk, fill=INK, width=1)
        tip = stalk[-1]
        head = [(tip[0] + k, tip[1] - 1 + (k * k) // 6) for k in range(6)]
        d.line(head, fill=GRASS_HI, width=2)
    # grass on the hill: long pale fronds sweeping up to the right and curling over, in rows,
    # drawn on a layer and kept inside the dome
    grass = Image.new("RGB", (TW, TH), INK)
    g = ImageDraw.Draw(grass)
    for row, y0 in enumerate(range(64, TH, 7)):
        for x0 in range(-4 + (row % 2) * 3, TW, 6):
            pts = [(x0 + (k * k) // 14, y0 + 9 - k) for k in range(10)]
            g.line(pts, fill=GRASS_HI if (x0 // 6 + row) % 3 == 0 else GRASS, width=1)
    dome = Image.new("L", (TW, TH), 0)
    ImageDraw.Draw(dome).ellipse((-22, 62, TW + 22, 62 + 2 * 70), fill=255)
    im.paste(grass, (0, 0), dome)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, TW - 1, TH - 1), outline=GOLD)
    d.rectangle((1, 1, TW - 2, TH - 2), outline=GOLD_DK)
    d.rectangle((2, 2, TW - 3, TH - 3), outline=GOLD)
    d.rectangle((3, 3, TW - 4, TH - 4), outline=INK)
    im.save(os.path.join(ART, "face.png"))


def back():
    """The back every goal card shares: seigaiha (overlapping waves) in dark gold on the ink, inside
    the gilt border; the bead frames a crest, a gold kikko (tortoiseshell hexagon) on deep red."""
    im = Image.new("RGB", (TW, TH), INK)
    px = im.load()
    R = 10.0                                  # a wave scale's radius, texels
    rows = int(TH / (R / 2)) + 3
    for y in range(TH):
        for x in range(TW):
            # the scale drawn last over (x, y): the lowest row whose circle covers it
            best = None
            for row in range(rows):
                cy = row * R / 2 - R
                cx0 = (row % 2) * R
                k = round((x + 0.5 - cx0) / (2 * R))
                for cx in (cx0 + 2 * R * k, cx0 + 2 * R * (k - 1), cx0 + 2 * R * (k + 1)):
                    dd = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
                    if dd < R:
                        best = dd
            if best is None:
                continue
            ring = int(R - best)              # 0 at the rim: gold rings a texel wide, two of ink between
            c = SKY_DK if best < 1.0 else (GOLD_DK if ring % 3 == 0 else INK)
            px[x, y] = ImageColor.getrgb(c)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, TW - 1, TH - 1), outline=GOLD)
    d.rectangle((1, 1, TW - 2, TH - 2), outline=GOLD_DK)
    d.rectangle((2, 2, TW - 3, TH - 3), outline=GOLD)
    d.rectangle((3, 3, TW - 4, TH - 4), outline=INK)
    # the crest inside the bead: deep red, a gold hexagon and a gold dot
    mx, my = tex_xy(0, MOON_Y)
    r = MOON_R / W * TW
    d.ellipse((mx - r, my - r, mx + r, my + r), fill=SKY_DK)
    hexr = r * 0.62
    pts = [(mx + hexr * math.cos(math.radians(90 + 60 * i)),
            my + hexr * math.sin(math.radians(90 + 60 * i))) for i in range(6)]
    d.polygon(pts, outline=GOLD)
    d.line(pts + [pts[0]], fill=GOLD, width=2)
    d.ellipse((mx - 1.5, my - 1.5, mx + 1.5, my + 1.5), fill=GOLD)
    im.save(os.path.join(ART, "back.png"))


face()
back()

# ---------------------------------------------------------------- the card as one closed mesh
def outline():
    """Rounded rectangle, clockwise as the front camera sees it (from top-left)."""
    pts = []
    corners = [(-W / 2 + CR, H - CR, 180, 90), (W / 2 - CR, H - CR, 90, 0),
               (W / 2 - CR, CR, 0, -90), (-W / 2 + CR, CR, -90, -180)]
    for cx, cy, a0, a1 in corners:
        for k in range(CSEG + 1):
            a = math.radians(a0 + (a1 - a0) * k / CSEG)
            pts.append((round(cx + CR * math.cos(a), 5), round(BASE + cy + CR * math.sin(a), 5)))
    return pts


pts = outline()
n = len(pts)
verts = [[x, y, -T / 2] for x, y in pts] + [[x, y, T / 2] for x, y in pts]
faces = [list(range(n)), list(range(2 * n - 1, n - 1, -1))]
mats = ["face", "back"]
for i in range(n):
    j = (i + 1) % n
    faces.append([i + n, j + n, j, i])
    mats.append("edge")

def bead():
    """The gilt bead round the moon: a ring of diamond section about the card's Z axis, through the
    card, its outer corners BEAD_TOP in front of and behind the card's centre plane."""
    mid = 0.5 * (BEAD_IN + BEAD_OUT)
    sec = [(BEAD_IN, 0.0), (mid, -BEAD_TOP), (BEAD_OUT, 0.0), (mid, BEAD_TOP)]
    vs = []
    for k in range(BEAD_SEG):
        a = 2 * math.pi * k / BEAD_SEG
        for r, z in sec:
            vs.append([round(r * math.cos(a), 5), round(MOON_Y + r * math.sin(a), 5), z])
    fs = []
    for k in range(BEAD_SEG):
        k2 = (k + 1) % BEAD_SEG
        for j in range(4):
            j2 = (j + 1) % 4
            q = [k * 4 + j, k * 4 + j2, k2 * 4 + j2, k2 * 4 + j]
            # outward and right-handed: reversed where the normal points into the tube
            p0, p1, p2 = (vs[i] for i in q[:3])
            u = [p1[i] - p0[i] for i in range(3)]
            v = [p2[i] - p0[i] for i in range(3)]
            n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
            c = [sum(vs[i][t] for i in q) / 4 for t in range(3)]
            rr = math.hypot(c[0], c[1] - MOON_Y)
            axis = [c[0] / rr * mid, MOON_Y + (c[1] - MOON_Y) / rr * mid, 0.0]
            if sum(n[t] * (c[t] - axis[t]) for t in range(3)) < 0:
                q.reverse()
            fs += [q[:3], [q[0], q[2], q[3]]]    # two triangles: the rounded corners are not planar
    return vs, fs


bead_v, bead_f = bead()

materials = {
    "face": {"color": SKY, "class": "emissive",
             "texture": {"image": "art/face.png", "projection": "fit"}},
    "back": {"color": INK, "class": "emissive",
             "texture": {"image": "art/back.png", "projection": "fit"}},
    "edge": {"color": GOLD},
    "bead": {"color": "#ffd34e"},
}

nodes = [
    {"id": "card", "op": "mesh", "material": "edge", "vertices": verts, "faces": faces,
     "face_materials": mats},
    {"id": "bead", "op": "mesh", "material": "bead", "vertices": bead_v, "faces": bead_f},
]

recipe = {
    "format": "mei-asset",
    "version": 1,
    "name": "hanafuda_moon",
    "budget": {"vertices": 256, "triangles": 300},
    "materials": materials,
    "lighting": {"mode": "vertical", "ambient": 0.55},
    "verification": {"required": True, "depth": True, "perspective": True},
    "nodes": nodes,
}
with open(os.path.join(HERE, "hanafuda_moon.asset.json"), "w") as f:
    json.dump(recipe, f, indent=1)
    f.write("\n")
