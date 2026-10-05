"""Writes the station's viaduct recipes: viaduct_station_span (the wide span the island platform
stands on) and viaduct_station_taper (the span that widens the standard section to it), each
with its _col companion, into their folders beside this one.
Run once and commit the outputs:
python3 carts/garden/shrinetown/assets/viaduct_station_span/make_station_viaduct.py

Both use make_viaduct.py's conventions and the common concrete set (viaduct_span_16/art/
concrete.png): the deck is a cross-section swept along the track, deck 9.0, parapet tops 10.2,
fascia foot 8.55, hand UVs that run on across the joints (the same repeats a metre as the
standard span), and a two-column bent at each piece's middle.

The wide section (z across, half widths): tracks at z = +-4.1, each on a 4 m ballast bed
(|z| 2.1..6.1), the deck between the beds (|z| < 2.1) under the island platform, the cable-trough
walkway (6.1..7.35), the parapet (7.35..7.6). 15.2 m over the fascias, against the standard
span's 12. Two girders under the tracks (|z| 3.2..5.0) to 7.8, the columns at +-4.1.

viaduct_station_span: 16 m of the wide section. Its -Z side (the plaza's, as the asset's front)
has no parapet: the walkway runs to the fascia (z -7.6) and station_concourse stands the north
parapet on it, with gaps where its two stairs arrive. Placed at yaw 180, -Z is north.

viaduct_station_taper: 16 m from the standard section at x = -8 to the wide one at x = +8. The
tracks swing out on an S (smoothstep: z = +-(2 + 2.1 s), s = smoothstep((x + 8) / 16)), the
fascias and parapets flare in straight lines (6.0 to 7.6), the girders follow the tracks. Both
parapets are kept. Placed at yaw 0 on the west of the station and 180 on the east.
"""
import importlib.util
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location(
    'make_viaduct', os.path.join(ROOT, 'viaduct_span_16', 'make_viaduct.py'))
mv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mv)

DECK, TOP, EDGE_Y = mv.DECK, mv.TOP, mv.EDGE_Y
SHEET = '../viaduct_span_16/art/concrete.png'
FASCIA_H = TOP - EDGE_Y
LENGTH = 16.0

TRACK_STD, TRACK_WIDE = 2.0, 4.1
OUT_STD, OUT_WIDE = 6.0, 7.6
PARAPET_T = 0.25
COL_Z = 4.1                                      # the wide bent's columns, under the tracks


def smooth(t):
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------------------- the sections
# A section is a ring of (z, y, material, v) points, each edge (to the next point) drawn in the
# point's material with v running from the point's v to the edge's end v (given as v_end).
# Points are given as (z, y, material, v_start, v_end).

def section(o, w, g, level=0, north=True):
    """The deck at track offset o, outer half width w, girder centre g. level 0 full, 1 no
    girders, 2 a box. north=False leaves the -Z parapet off (the station span)."""
    pi = w - PARAPET_T                           # parapet's inner face
    mid = o - 2.0                                # the beds' inner edges
    trough = 1.75
    pts = []
    # +Z parapet, walkway, bed, middle, bed, walkway (start at the +Z coping's outer corner)
    if level == 2:
        if north:
            return [(w, TOP, 'soffit', 0.0, w), (-w, TOP, 'fascia', 0.0, 1.0),
                    (-w, EDGE_Y, 'soffit', 0.0, w), (w, EDGE_Y, 'fascia', 1.0, 0.0)]
        return [(w, TOP, 'soffit', 0.0, w), (-pi, DECK, 'trough', 0.0, 1.0),
                (-w, DECK, 'fascia', (TOP - DECK) / FASCIA_H, 1.0),
                (-w, EDGE_Y, 'soffit', 0.0, w), (w, EDGE_Y, 'fascia', 1.0, 0.0)]
    pts.append((w, TOP, 'coping', 0.0, 1.0))
    pts.append((pi, TOP, 'concrete', 0.0, (TOP - DECK) / 2.0))
    pts.append((pi, DECK, 'trough', (pi - (o + 2.0)) / trough, 0.0))
    pts.append((o + 2.0, DECK, 'track', 2.0, 1.0))
    pts.append((mid, DECK, 'trough', 0.0, 2 * mid / trough))
    pts.append((-mid, DECK, 'track', 1.0, 0.0))
    if north:
        pts.append((-(o + 2.0), DECK, 'trough', 0.0, (pi - (o + 2.0)) / trough))
        pts.append((-pi, DECK, 'concrete', 0.0, (TOP - DECK) / 2.0))
        pts.append((-pi, TOP, 'coping', 0.0, 1.0))
        pts.append((-w, TOP, 'fascia', 0.0, 1.0))
    else:
        pts.append((-(o + 2.0), DECK, 'trough', 0.0, (w - (o + 2.0)) / trough))
        pts.append((-w, DECK, 'fascia', (TOP - DECK) / FASCIA_H, 1.0))
    # underside, from the -Z fascia's foot round to the +Z one
    if level == 0:
        cant = g + 1.1                           # the cantilever's root, at the haunch
        pts += [(-w, EDGE_Y, 'soffit', 0.0, (w - cant) / 2.0),
                (-cant, 8.3, 'concrete', 0.0, 0.27), (-(g + 0.9), 7.8, 'soffit', 0.0, 0.9),
                (-(g - 0.9), 7.8, 'concrete', 0.0, 0.27), (-(g - 1.1), 8.3, 'soffit', 0.0, g - 1.1),
                ((g - 1.1), 8.3, 'concrete', 0.0, 0.27), ((g - 0.9), 7.8, 'soffit', 0.0, 0.9),
                ((g + 0.9), 7.8, 'concrete', 0.0, 0.27), (cant, 8.3, 'soffit', 0.0, (w - cant) / 2.0),
                (w, EDGE_Y, 'fascia', 1.0, 0.0)]
    else:
        pts += [(-w, EDGE_Y, 'soffit', 0.0, w), (w, EDGE_Y, 'fascia', 1.0, 0.0)]
    return pts


def wide(level=0, north=True):
    return section(TRACK_WIDE, OUT_WIDE, COL_Z, level, north)


def taper_at(t, level=0):
    s = smooth(t)
    return section(TRACK_STD + (TRACK_WIDE - TRACK_STD) * s, OUT_STD + (OUT_WIDE - OUT_STD) * t,
                   3.0 + (COL_Z - 3.0) * s, level)


def loft(id_, sections, xs, textured=True):
    """A mesh node: the sections (one per x in xs, the same edges in each) joined into bands.
    An edge that has no width in one section makes a triangle there, none where it has none in
    both."""
    verts, uvs, faces, mats = [], [], [], []
    vid = {}

    def vert(x, z, y, u, v):
        key = (round(x, 6), round(z, 6), round(y, 6), round(u, 6), round(v, 6))
        if key not in vid:
            vid[key] = len(verts)
            verts.append([mv.r7(x), mv.r7(y), mv.r7(z)])
            uvs.append([mv.r4(u), mv.r4(v)])
        return vid[key]

    n = len(sections[0])
    length = xs[-1] - xs[0]
    for i in range(n):
        mat = sections[0][i][2]
        if textured and mat is None:
            continue                             # an edge left open (a parapet's foot)
        reps = max(1, round(length / mv.REP.get(mat, 4.0)))
        for k in range(len(xs) - 1):
            ring = []
            for kk in (k, k + 1):
                a = sections[kk][i]
                b = sections[kk][(i + 1) % n]
                ring.append((xs[kk], a, b))
            f0 = (xs[k] - xs[0]) / length
            f1 = (xs[k + 1] - xs[0]) / length
            (x0, a0, b0), (x1, a1, b1) = ring
            corners = [(x0, a0[0], a0[1], f0, a0[3]), (x0, b0[0], b0[1], f0, a0[4]),
                       (x1, b1[0], b1[1], f1, a1[4]), (x1, a1[0], a1[1], f1, a1[3])]
            # drop a corner that repeats its predecessor (an edge of no width at one end)
            poly, seen = [], []
            for c in corners:
                p = (round(c[0], 6), round(c[1], 6), round(c[2], 6))
                if p in seen:
                    continue
                seen.append(p)
                poly.append(c)
            if len(poly) < 3:
                continue
            q = [vert(c[0], c[1], c[2], reps * c[3], c[4]) for c in poly]
            # orient outward: the section rings run so that the solid is on one side; check
            # against the edge's outward normal in the section plane
            za, ya = a0[0], a0[1]
            zb, yb = b0[0], b0[1]
            if abs(zb - za) + abs(yb - ya) < 1e-9:
                za, ya, zb, yb = a1[0], a1[1], b1[0], b1[1]
            out = (0.0, -(zb - za), yb - ya)     # (x, y, z): the rings run counterclockwise (z right)
            p0, p1, p2 = verts[q[0]], verts[q[1]], verts[q[2]]
            e1 = [p1[j] - p0[j] for j in range(3)]
            e2 = [p2[j] - p0[j] for j in range(3)]
            nrm = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2],
                   e1[0] * e2[1] - e1[1] * e2[0]]
            if sum(nrm[j] * out[j] for j in range(3)) < 0:
                q.reverse()
            polys = [q]
            if len(q) == 4 and not planar([verts[i] for i in q]):
                polys = [[q[0], q[1], q[2]], [q[0], q[2], q[3]]]
            for pq in polys:
                faces.append(pq)
                mats.append(mat if textured else 'solid')
    node = {"id": id_, "op": "mesh", "vertices": verts, "faces": faces, "face_materials": mats}
    if textured:
        node["uvs"] = uvs
    return node


def planar(pts):
    """Whether four corners lie in one plane (to the kit's tolerance, with room to spare)."""
    a, b, c, d = pts
    e1 = [b[j] - a[j] for j in range(3)]
    e2 = [c[j] - a[j] for j in range(3)]
    e3 = [d[j] - a[j] for j in range(3)]
    n = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2],
         e1[0] * e2[1] - e1[1] * e2[0]]
    ln = math.sqrt(sum(v * v for v in n)) or 1.0
    return abs(sum(n[j] * e3[j] for j in range(3))) / ln < 1e-7


def ring_sign(sec):
    pts = [(p[0], p[1]) for p in sec]
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
               for i in range(len(pts)))


# ---------------------------------------------------------------------------- the bent
def bent(id_, x=0.0, col_z=COL_Z, detail=True, plates=True):
    """The standard bent (make_viaduct.bent) with its columns at +-col_z and the beam widened."""
    kids = []
    top = 7.5 if detail else 8.65
    half = col_z + 0.65
    for side, sz in (('n', 1), ('s', -1)):
        col = {"id": f"column_{side}", "op": "box", "size": [mv.COL_X, top, mv.COL_W],
               "material": "concrete", "open": ["top", "bottom"],
               "transform": {"translate": [x, top / 2, mv.r4(sz * col_z)]}}
        if detail and plates:
            col["decals"] = [{"id": "plate", "face": "front" if sz > 0 else "back",
                              "material": "pier_plate", "size": [0.32, 0.16],
                              "at": [0, 2.1 - top / 2]}]
        kids.append(col)
    if detail:
        h, c = mv.r4(half), mv.r4(col_z - 0.1)
        inner = mv.r4(col_z - 1.35)
        kids.append({"id": "beam", "op": "extrude", "material": "concrete", "depth": mv.BEAM_X,
                     "points": [[-h, 8.35], [h, 8.35], [h, 7.0], [c, 7.0], [c, 6.4],
                                [inner, 7.0], [-inner, 7.0], [-c, 6.4], [-c, 7.0], [-h, 7.0]],
                     "transform": {"rotate": [0, 90, 0], "translate": [x, 0, 0]}})
    return {"id": id_, "op": "group", "children": kids}


def downpipe(col_z, x=0.0):
    return {"id": "downpipe", "op": "box", "size": [0.16, 7.9, 0.16], "material": "pipe",
            "open": ["top", "bottom"],
            "transform": {"translate": [x - mv.COL_X / 2 - 0.12, 3.95, mv.r4(col_z + 0.25)]}}


# ---------------------------------------------------------------------------- collision
def col_section(o, w, north=True):
    """The collision U: the deck slab (top 9.0, bottom 8.3) and the parapets."""
    pi = w - PARAPET_T
    pts = [(-w, 8.3, None, 0, 0), (w, 8.3, None, 0, 0), (w, TOP, None, 0, 0),
           (pi, TOP, None, 0, 0), (pi, DECK, None, 0, 0)]
    if north:
        pts += [(-pi, DECK, None, 0, 0), (-pi, TOP, None, 0, 0), (-w, TOP, None, 0, 0)]
    else:
        pts += [(-w, DECK, None, 0, 0)]
    return pts


def col_column(id_, z, top=8.4):
    return mv.col_box(id_, [mv.COL_X, top, mv.COL_W], [0, top / 2, mv.r4(z)])


# ---------------------------------------------------------------------------- the pieces
def station_span():
    xs = [-LENGTH / 2, LENGTH / 2]
    nodes = [loft("deck", [wide(0, False)] * 2, xs), bent("bent"), downpipe(COL_Z)]
    lod = {"levels": [
        {"distance": 40, "nodes": [loft("deck", [wide(1, False)] * 2, xs),
                                   bent("bent", detail=False)]},
        {"distance": 100, "nodes": [loft("deck", [wide(2, False)] * 2, xs),
                                    bent("bent", detail=False)]},
    ], "band": 1}
    r = mv.recipe("viaduct_station_span", 140, SHEET, mv.materials(SHEET), nodes, lod)
    cx = [-LENGTH / 2 + LENGTH * i / 8 for i in range(9)]
    col = mv.col_recipe("viaduct_station_span_col", [
        loft("deck", [col_section(TRACK_WIDE, OUT_WIDE, False)] * 9, cx, textured=False),
        col_column("column_n", COL_Z), col_column("column_s", -COL_Z)])
    return r, col


def taper():
    segs = 4
    xs = [-LENGTH / 2 + LENGTH * i / segs for i in range(segs + 1)]
    secs = [taper_at(i / segs) for i in range(segs + 1)]
    g_mid = 3.0 + (COL_Z - 3.0) * smooth(0.5)
    nodes = [loft("deck", secs, xs), bent("bent", col_z=g_mid, plates=False), downpipe(g_mid)]
    lod = {"levels": [
        {"distance": 40, "nodes": [loft("deck", [taper_at(i / 2, 1) for i in range(3)],
                                        [-8.0, 0.0, 8.0]),
                                   bent("bent", col_z=g_mid, detail=False)]},
        {"distance": 100, "nodes": [loft("deck", [taper_at(0, 2), taper_at(1, 2)], [-8.0, 8.0]),
                                    bent("bent", col_z=g_mid, detail=False)]},
    ], "band": 1}
    r = mv.recipe("viaduct_station_taper", 240, SHEET, mv.materials(SHEET), nodes, lod)
    cx = [-LENGTH / 2 + LENGTH * i / 8 for i in range(9)]
    csecs = [col_section(0, OUT_STD + (OUT_WIDE - OUT_STD) * (i / 8)) for i in range(9)]
    col = mv.col_recipe("viaduct_station_taper_col", [
        loft("deck", csecs, cx, textured=False),
        col_column("column_n", g_mid), col_column("column_s", -g_mid)])
    return r, col


def write(folder, rec):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, rec['name'] + '.asset.json')
    with open(path, 'w') as f:
        f.write(mv.dump(rec) + '\n')
    print('wrote', os.path.relpath(path, ROOT))


if __name__ == '__main__':
    for name, (r, col) in (('viaduct_station_span', station_span()),
                           ('viaduct_station_taper', taper())):
        folder = os.path.join(ROOT, name)
        write(folder, r)
        write(folder, col)
