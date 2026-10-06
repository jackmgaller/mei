"""Writes station_concourse.asset.json and station_concourse_col.asset.json beside this script.
Run after changing it: python3 carts/garden/shrinetown/assets/station_concourse/make_concourse.py

Yuyakedai station's hall under the viaduct and its two stairs up from the plaza. The origin is
the middle of the station at the ground, under the viaduct's centre line (world (160, 0, 8));
the front (the plaza) faces -Z, so the world places it at yaw 180. It spans the three
viaduct_station_span pieces (x -24..24) and stands on their deck where it has to:

- the hall: a box under the deck (x -24..24, z -7.0..6.5, up into the deck's underside at 8.6),
  its front the ground floor's tile wall to 4.6 with the entrance (x -4..4, 3.0 high) and the
  cream cladding above it with the station's name; an eave over the entrance at 3.45-3.6;
- inside the entrance, a room (x -10..10, z -6.7..3.5, floor 0.06, ceiling 3.4): ticket
  machines and the fare chart on the -x wall, the office window on the +x wall, the timetable
  and the sign to the platform (のりば) on the back wall. The ticket gates (ticket_gates) stand
  in it at (0, 0.06, 0.6), facing -Z. The middle bent's north column (station span, z -4.1) is
  clad in tile;
- the platform stair, from the paid side of the gates up to the island platform
  (station_platform's floor, 10.0). The numbers are in the town's frame (u = world x - 160 = -x
  here, w = world z - 8 = -z; make_station_viaduct.py's STAIR_*), all three flights at 27.1
  degrees (0.5125): the first flight rises along the back wall (w -3.5..-1.35) from u 8.0
  through an opening in the room's -x wall into a stair hall behind it (u 10..17.3, up to the
  deck's underside), to a landing (u 14.8..17.2, 3.56) under the east span's bent; it turns,
  and the second flight climbs back west between walls (|w| < 1.2) to a half landing (u 9.4..
  11.0, 5.52) over the room's ceiling, the third on up to the top step at u 0.65, coming up
  through the opening in the middle span's deck (viaduct_station_span_stair, u 0.65..7.9) into
  the platform's stairwell;
- two stairs at x = -10 and +10, 3 m wide between their walls, from the plaza (foot at
  z -26.6) up 9.0 m over 18 m (26.6 degrees) to a landing at the deck's edge (z -7.6..-8.6,
  top 9.0) under a roof that follows them (2.6 m over the steps, walkable at 26.6 degrees). They
  are the town's way up onto the viaduct's walkway and its parapet (spec's way up B), not to the
  trains: nothing crosses track 2 from them;
- on the deck: the north parapet over the station (the station span leaves it off), z -7.35..
  -7.6, top 10.2, the same section and textures as the viaduct's, with a gap at each stair
  (x +-8.35..+-11.65).
"""
import importlib.util
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location(
    'make_station_viaduct', os.path.join(ROOT, 'viaduct_station_span', 'make_station_viaduct.py'))
sv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sv)
mv = sv.mv

DECK, TOP = 9.0, 10.2
HALF = 24.0                    # the hall's half length: three 16 m spans
FRONT = -7.0                   # the facade's outer face
BACK = 6.5                     # the hall's back wall
GROUND_TOP = 4.6               # the tile wall's top; cladding to 8.6
CLAD_TOP = 8.6
DOOR_HALF, DOOR_H = 4.0, 3.0
ROOM_HALF, ROOM_BACK, ROOM_H, FLOOR_Y = 10.0, 3.5, 3.4, 0.06
ROOM_BACK_WAS = 3.0            # where the back wall stood: the decals keep their places
EDGE = -7.6                    # the deck's north edge (station span)
PAR_IN = -7.35                 # the parapet's inner face
STAIR_X = 10.0
STAIR_HALF = 1.5               # the flight's half width; walls outside it
WALL_IN, WALL_OUT = 1.48, 1.63 # the stair walls' faces, from the stair's centre line
LAND = -8.6                    # the landing's outer edge / the flight's top
FOOT = -26.6                   # the flight's foot
RISE = DECK
SLOPE = RISE / (LAND - FOOT)   # 0.5
SLAB = 0.45                    # the flight's thickness, measured vertically
RAIL_H = 1.1                   # the walls' top over the steps
ROOF_UP = 2.6                  # the roof's top over the steps
ROOF_T = 0.12
ROOF_END = -7.75               # the roof's upper end
GAP_IN, GAP_OUT = STAIR_X - WALL_OUT, STAIR_X + WALL_OUT

# The platform stair, in the town's frame (u east = -x, w north = -z; see the docstring).
PLATFORM = DECK + 1.0          # station_platform's floor
S = sv.STAIR_SLOPE
TOP_U = sv.STAIR_TOP_U
SW = sv.STAIR_HALF             # the second and third flights' half width
SWT = sv.STAIR_WALL
HOLE_END = sv.HOLE_U[1]        # the deck's opening ends here: the walls' tops step down
SOFFIT, GIRDER = 8.3, 7.8      # the deck's underside between the girders, and the girders'
F1_W = (-ROOM_BACK, -(SW + SWT))  # the first flight's band, along the back wall
FOOT_U = 8.0                   # the first flight's foot
MID_U = (9.4, 11.0)            # the half landing
MID_Y = PLATFORM - S * (MID_U[0] - TOP_U)
LAND_U0 = (MID_Y - FLOOR_Y + S * (MID_U[1] + FOOT_U)) / (2 * S)   # the landing's west edge
LAND_Y = FLOOR_Y + S * (LAND_U0 - FOOT_U)
LAND_U1 = LAND_U0 + 2.4        # its east edge, the stair hall's end wall
HALL_U = ROOM_HALF             # the room's -x wall: the stair hall starts here
IN = 0.02                      # what the walls' tops go into the deck


def r(v):
    return round(v + 0.0, 4) + 0.0


def stair_y(z):
    """The steps' line (the nosings) at z."""
    return SLOPE * (z - FOOT)


SHEET = 'art/concourse.png'
CONCRETE = '../viaduct_span_16/art/concrete.png'


def tex(cell, projection='fit', **kw):
    t = {"sheet": "concourse", "cell": cell, "projection": projection}
    t.update(kw)
    return t


MATERIALS = {
    "tile": {"color": "#b09070", "tag": "wall", "texture": tex("tile", "box", scale=[0.5, 0.5])},
    "tile_flat": {"color": "#a88a6a", "palette": True, "tag": "wall"},
    "stone": {"color": "#b4b0a6", "palette": True, "double_sided": True},
    "panel": {"color": "#e2dccb", "tag": "wall",
              "texture": tex("panel", "box", scale=[2.0, 4.0], offset=[0.0, 0.5])},
    "floor": {"color": "#a9a8a2", "tag": "floor", "texture": tex("floor", "box", scale=[1.0, 1.0])},
    "tread": {"color": "#bcb8ae", "tag": "stairs", "texture": tex("tread", "box")},
    "concrete": {"color": "#b4b0a6", "tag": "wall",
                 "texture": {"sheet": "concrete", "cell": "wall", "projection": "box",
                             "scale": [4.0, 2.0]}},
    "fascia": {"color": "#b4b0a6",
               "texture": {"sheet": "concrete", "cell": "fascia", "projection": "box",
                           "scale": [4.0, 1.65]}},
    "coping": {"color": "#c8c4b8", "palette": True},
    "steel": {"color": "#9ba3ac", "palette": True},
    "green": {"color": "#4f7f6a", "palette": True},
    "roof": {"color": "#a9c4b4", "palette": True, "tag": "roof"},
    "interior": {"color": "#e2d8c0", "palette": True, "tag": "wall"},
    "orange": {"color": "#e8782a", "palette": True},
    "dark": {"color": "#2c2a28", "palette": True},
    "lamp": {"color": "#f4fbff", "class": "emissive", "tag": "lamp"},
    "name_sign": {"color": "#f6f6f0", "tag": "sign", "texture": tex("name_sign")},
    "entrance_sign": {"color": "#1e2838", "tag": "sign", "texture": tex("entrance_sign")},
    "clock": {"color": "#f6f6f0", "texture": tex("clock")},
    "lockers": {"color": "#d2d6d4", "texture": tex("lockers")},
    "machines": {"color": "#c9ced0", "texture": tex("machines")},
    "fare_chart": {"color": "#f6f6f0", "tag": "sign", "texture": tex("fare_chart")},
    "noriba": {"color": "#1e2838", "tag": "sign", "texture": tex("noriba")},
    "timetable": {"color": "#f6f6f0", "texture": tex("timetable")},
    "poster_a": {"color": "#e8a050", "texture": tex("poster_a")},
    "poster_b": {"color": "#3a6ab0", "texture": tex("poster_b")},
    "office": {"color": "#c8d4d8", "texture": tex("office")},
}


def box(id_, size, at, material, open_=None, faces=None, decals=None):
    n = {"id": id_, "op": "box", "size": [r(v) for v in size], "material": material,
         "transform": {"translate": [r(v) for v in at]}}
    if open_:
        n["open"] = list(open_)
    if faces:
        n["faces"] = faces
    if decals:
        n["decals"] = decals
    return n


def decal(id_, face, material, size, at):
    return {"id": id_, "face": face, "material": material, "size": [r(v) for v in size],
            "at": [r(v) for v in at]}


# ---------------------------------------------------------------------------- the hall
FACADE_PTS = [[-HALF, 0], [-DOOR_HALF, 0], [-DOOR_HALF, DOOR_H], [DOOR_HALF, DOOR_H],
              [DOOR_HALF, 0], [HALF, 0], [HALF, GROUND_TOP], [-HALF, GROUND_TOP]]


def facade(level=0):
    n = {"id": "facade", "op": "extrude", "material": "tile" if level == 0 else "tile_flat",
         "depth": 0.3, "points": FACADE_PTS,
         "faces": {"front": "interior", "side": "tile_flat"},
         "transform": {"translate": [0, 0, FRONT + 0.15]}}
    if level == 0:
        n["decals"] = [
            decal("entrance_sign", "back", "entrance_sign", [4.0, 0.75], [0, 4.075]),
            decal("office_w1", "back", "office", [2.4, 1.2], [-13.5, 1.9]),
            decal("office_w2", "back", "office", [2.4, 1.2], [-18.5, 1.9]),
            decal("office_e1", "back", "office", [2.4, 1.2], [13.5, 1.9]),
            decal("office_e2", "back", "office", [2.4, 1.2], [18.5, 1.9]),
            decal("poster_1", "back", "poster_a", [0.6, 0.9], [5.4, 1.65]),
            decal("poster_2", "back", "poster_b", [0.6, 0.9], [6.2, 1.65]),
            decal("poster_3", "back", "poster_a", [0.6, 0.9], [-9.4, 1.65]),
        ]
    return n


def cladding(level=0):
    decals = [decal("name_sign", "back", "name_sign", [9.6, 2.4], [0, 0.2])]
    if level == 0:
        decals.append(decal("clock", "back", "clock", [1.0, 1.0], [7.2, 0.4]))
    return box("cladding", [2 * HALF, CLAD_TOP - GROUND_TOP, 0.3],
               [0, (GROUND_TOP + CLAD_TOP) / 2, FRONT + 0.15],
               "panel" if level == 0 else "interior",
               open_=["bottom", "top", "front"], decals=decals)


def hall_box(level=0):
    depth = BACK - (FRONT + 0.3)
    return box("hall", [2 * HALF, CLAD_TOP, depth], [0, CLAD_TOP / 2, (BACK + FRONT + 0.3) / 2],
               "concrete" if level == 0 else "stone", open_=["top", "bottom", "back"])


def eave(level=0):
    n = box("eave", [12.0, 0.15, 2.05], [0, 3.525, FRONT + 0.05 - 1.025], "roof",
            faces={"back": "orange", "bottom": "interior"})
    if level == 0:
        n["decals"] = [decal("light_a", "bottom", "lamp", [4.0, 0.2], [-3.0, 0]),
                       decal("light_b", "bottom", "lamp", [4.0, 0.2], [3.0, 0])]
    return n


def lockers():
    return box("lockers", [2.4, 1.8, 0.5], [-7.0, 0.9, FRONT - 0.23], "steel",
               open_=["bottom", "front"], faces={"back": "lockers"})


# ---------------------------------------------------------------------------- the room
def room():
    zc = (FRONT + 0.3 + ROOM_BACK) / 2
    depth = ROOM_BACK - (FRONT + 0.3)
    zc_was = (FRONT + 0.3 + ROOM_BACK_WAS) / 2
    # The -x wall stops at the stair's opening (z 1.35..3.5, the first flight's band).
    w_z1 = -F1_W[1]
    wc, wd = (FRONT + 0.3 + w_z1) / 2, w_z1 - (FRONT + 0.3)
    keep_only = lambda keep: [s for s in ("top", "bottom", "left", "right", "back", "front")
                              if s != keep]
    return [
        box("room_floor", [2 * ROOM_HALF, 0.1, depth], [0, FLOOR_Y - 0.05, zc], "floor",
            open_=keep_only("top")),
        box("room_ceiling", [2 * ROOM_HALF, 0.1, depth], [0, ROOM_H + 0.05, zc], "interior",
            open_=keep_only("bottom"),
            decals=[decal(f"light_{k}", "bottom", "lamp", [6.0, 0.25], [0, z])
                    for k, z in enumerate((-2.6, 0.0, 2.6))]),
        box("room_west", [0.1, ROOM_H, wd], [-ROOM_HALF - 0.05, ROOM_H / 2, wc], "interior",
            open_=keep_only("right"),
            decals=[decal("fare_chart", "right", "fare_chart", [3.2, 1.2],
                          [-0.85 + zc_was - wc, 0.65])]),
        box("room_east", [0.1, ROOM_H, depth], [ROOM_HALF + 0.05, ROOM_H / 2, zc], "interior",
            open_=keep_only("left"),
            decals=[decal("office", "left", "office", [2.4, 1.2], [0.0 - zc_was + zc, 0.0]),
                    decal("poster", "left", "poster_b", [0.6, 0.9], [-3.0 - zc_was + zc, 0.0])]),
        box("room_back", [2 * ROOM_HALF, ROOM_H, 0.1], [0, ROOM_H / 2, ROOM_BACK + 0.05],
            "interior", open_=keep_only("back"),
            decals=[decal("noriba", "back", "noriba", [1.6, 0.4], [-6.4, 1.25]),
                    decal("timetable", "back", "timetable", [1.2, 1.6], [-4.5, 0.15]),
                    decal("poster_a", "back", "poster_a", [0.6, 0.9], [4.4, 0.1]),
                    decal("poster_b", "back", "poster_b", [0.6, 0.9], [5.2, 0.1])]),
        box("machines", [0.6, 1.7, 2.4], [-ROOM_HALF + 0.29, FLOOR_Y + 0.85, -1.0], "steel",
            open_=["left", "bottom"], faces={"right": "machines"}),
        box("column_clad", [1.4, ROOM_H - FLOOR_Y, 1.5],
            [0, (ROOM_H + FLOOR_Y) / 2, -4.1], "tile", open_=["top", "bottom"],
            decals=[decal("poster", "back", "poster_a", [0.6, 0.9], [0, 0.1])]),
    ]


# ---------------------------------------------------------------------------- the platform stair
# Built in the town's frame (u, y, w) and turned into the asset's (x, y, z) = (-u, y, -w): a
# rotation, so the faces keep their winding.
def here(p):
    return [r(-p[0]), r(p[1]), r(-p[2])]


def uyw_mesh(id_, polys, material, uvs=False):
    """A mesh node from polygons (corners in (u, y, w), the normal they face, a material; with
    uvs, a list of corner UVs too)."""
    m = sv.Mesh(id_, textured=uvs)
    for poly in polys:
        corners, normal, mat = poly[:3]
        m.poly([here(c) for c in corners], [-normal[0], normal[1], -normal[2]], mat,
               poly[3] if uvs else None)
    n = m.node()
    if not uvs:
        n["face_materials"] = [p[2] for p in polys]
    n["material"] = material
    return n


def at_u(pts, w):
    """(u, y) outline points on the plane w."""
    return [[u, y, w] for u, y in pts]


def at_w(pts, u):
    """(w, y) outline points on the plane u."""
    return [[u, y, w] for w, y in pts]


def flight(u0, y0, u1, y1, w0, w1):
    """A flight's steps as one textured slope, a repeat a 0.3 m of rise as on the outside
    stairs (v from the foot up)."""
    n = round(abs(y1 - y0) / 0.3)
    width = (w1 - w0) / 2.0
    return ([[u0, y0, w0], [u0, y0, w1], [u1, y1, w1], [u1, y1, w0]], [0, 1, 0], "tread",
            [[0, 0], [width, 0], [width, n], [0, n]])


def flights():
    return [flight(FOOT_U, FLOOR_Y, LAND_U0, LAND_Y, F1_W[0], F1_W[1]),
            flight(LAND_U0, LAND_Y, MID_U[1], MID_Y, -SW, SW),
            flight(MID_U[0], MID_Y, TOP_U, PLATFORM, -SW, SW)]


def tunnel_wall(top_end, hall_u=HALL_U, over=ROOM_H + 0.1):
    """A wall's outline (u, y) along the second and third flights, from the room's ceiling (and
    below it the ground, in the stair hall) up into the deck: to the platform's base (DECK) over
    the deck's opening, to the deck's underside beyond it; ending at top_end."""
    return [(TOP_U, over), (hall_u, over), (hall_u, 0.0), (top_end, 0.0),
            (top_end, SOFFIT + IN), (HOLE_END, SOFFIT + IN), (HOLE_END, DECK), (TOP_U, DECK)]


def soffit_line(w0, w1):
    """The deck's underside across w0..w1 (w0 < w1), into it by IN: (w, y) points from w1 back
    to w0, with the north girder's foot (south of w -3.0) where the band reaches it."""
    pts = [(w1, SOFFIT + IN)]
    if w0 < -3.0:
        pts += [(-3.0 + 0.01, SOFFIT + IN), (-3.2 - 0.01, GIRDER + IN), (w0, GIRDER + IN)]
    else:
        pts += [(w0, SOFFIT + IN)]
    return pts


def platform_stair(level=0):
    """The stair to the platform: the flights, the landings and the walls round them."""
    fw0, fw1 = F1_W
    steps = uyw_mesh("platform_steps", flights(), "tread", uvs=True)
    floors = [
        (at_w([(fw0, LAND_Y), (SW, LAND_Y)], LAND_U0) + at_w([(SW, LAND_Y), (fw0, LAND_Y)],
                                                              LAND_U1), [0, 1, 0], "floor"),
        ([[MID_U[0], MID_Y, -SW], [MID_U[1], MID_Y, -SW], [MID_U[1], MID_Y, SW],
          [MID_U[0], MID_Y, SW]], [0, 1, 0], "floor"),
    ]
    walls = [
        # along the second and third flights: the north wall (to the end wall) and the
        # divider's south face (to the landing)
        (at_u(tunnel_wall(LAND_U1), SW), [0, 0, -1], "interior"),
        (at_u(tunnel_wall(LAND_U0), -SW), [0, 0, 1], "interior"),
    ]
    if level == 0:
        walls += [
            # the divider's face to the first flight, and its end at the landing
            (at_u([(HALL_U, 0.0), (LAND_U0, 0.0), (LAND_U0, SOFFIT + IN), (HALL_U, SOFFIT + IN)],
                  fw1), [0, 0, -1], "interior"),
            (at_w([(fw1, LAND_Y - 0.1), (-SW, LAND_Y - 0.1), (-SW, SOFFIT + IN),
                   (fw1, SOFFIT + IN)], LAND_U0), [1, 0, 0], "interior"),
            # the first flight's side in the room, below the divider
            ([[FOOT_U, FLOOR_Y, fw1], [HALL_U, FLOOR_Y, fw1],
              [HALL_U, FLOOR_Y + S * (HALL_U - FOOT_U), fw1]], [0, 0, 1], "dark"),
            # the stair hall's back wall, its end wall, and over the room's ceiling the end of
            # the first flight's band
            (at_u([(HALL_U, 0.0), (LAND_U1, 0.0), (LAND_U1, GIRDER + IN), (HALL_U, GIRDER + IN)],
                  fw0), [0, 0, 1], "interior"),
            (at_w([(fw0, 0.0), (SW, 0.0)] + soffit_line(fw0, SW), LAND_U1), [-1, 0, 0],
             "interior"),
            (at_w([(fw0, ROOM_H), (fw1, ROOM_H)] + soffit_line(fw0, fw1), HALL_U), [1, 0, 0],
             "interior"),
        ]
    return [steps, uyw_mesh("platform_stair", floors + walls, "interior")]


# ---------------------------------------------------------------------------- the stairs
def flight_top():
    """The steps as one textured slope, a step a repeat (v from the foot up)."""
    steps = round(RISE / 0.3)
    xa, xb = -STAIR_HALF, STAIR_HALF
    v = [[xa, 0.0, FOOT], [xb, 0.0, FOOT], [xb, RISE, LAND], [xa, RISE, LAND]]
    return {"id": "steps", "op": "mesh", "material": "tread", "vertices": v,
            "faces": [[3, 2, 1, 0]], "uvs": [[0, 0], [1.5, 0], [1.5, steps], [0, steps]]}


def flight_under():
    xa, xb = -STAIR_HALF, STAIR_HALF
    z_ground = LAND - (RISE - SLAB) / SLOPE
    v = [[xa, RISE - SLAB, LAND], [xb, RISE - SLAB, LAND], [xb, 0.0, r(z_ground)],
         [xa, 0.0, r(z_ground)]]
    return {"id": "underside", "op": "mesh", "material": "concrete", "vertices": v,
            "faces": [[3, 2, 1, 0]]}


def landing():
    return box("landing", [2 * STAIR_HALF, SLAB, abs(LAND - EDGE)],
               [0, RISE - SLAB / 2, (LAND + EDGE) / 2], "concrete", open_=["front"],
               faces={"top": "floor"})


def wall_outline(drop=0.05):
    """The stair wall's side outline in (-z, y): 1.1 m over the steps, its foot `drop` below
    the flight's underside (so the two faces are not one plane)."""
    low = RISE - SLAB - drop
    z_ground = LAND - low / SLOPE
    return [[-EDGE, RISE + RAIL_H], [-LAND, RISE + RAIL_H], [-FOOT, RAIL_H], [-FOOT, 0],
            [r(-z_ground), 0], [-LAND, r(low)], [-EDGE, r(low)]]


def walls(double=False):
    kids = [{"id": "wall", "op": "extrude", "material": "green", "depth": WALL_OUT - WALL_IN,
             "points": wall_outline(), "faces": {"front": "concrete", "back": "concrete"},
             "transform": {"rotate": [0, 90, 0], "translate": [r((WALL_IN + WALL_OUT) / 2), 0, 0]}}]
    return {"id": "walls", "op": "group", "children": kids,
            "modifiers": [{"op": "mirror", "axis": "x"}]}


def orient(verts, faces):
    """Turn each face of a closed convex mesh to face away from its centre."""
    c = [sum(p[j] for p in verts) / len(verts) for j in range(3)]
    out = []
    for f in faces:
        a, b, d = verts[f[0]], verts[f[1]], verts[f[2]]
        e1 = [b[j] - a[j] for j in range(3)]
        e2 = [d[j] - a[j] for j in range(3)]
        n = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2],
             e1[0] * e2[1] - e1[1] * e2[0]]
        fc = [sum(verts[i][j] for i in f) / len(f) for j in range(3)]
        out.append(f if sum(n[j] * (fc[j] - c[j]) for j in range(3)) > 0 else f[::-1])
    return out


def roof_line(z):
    return stair_y(z) + ROOF_UP


def roof():
    xa, xb = -(WALL_OUT + 0.17), WALL_OUT + 0.17
    za, zb = ROOF_END, FOOT
    ya, yb = roof_line(za), roof_line(zb)
    v = [[xa, ya, za], [xb, ya, za], [xb, yb, zb], [xa, yb, zb],
         [xa, ya - ROOF_T, za], [xb, ya - ROOF_T, za], [xb, yb - ROOF_T, zb], [xa, yb - ROOF_T, zb]]
    v = [[r(c) for c in p] for p in v]
    faces = orient(v, [[0, 1, 2, 3], [4, 5, 6, 7], [0, 3, 7, 4], [1, 5, 6, 2],
                       [3, 2, 6, 7], [0, 4, 5, 1]])
    return {"id": "roof", "op": "mesh", "material": "green", "vertices": v, "faces": faces,
            "face_materials": ["roof", "interior", "green", "green", "green", "green"]}


def posts():
    kids = []
    length = ROOF_UP - ROOF_T - RAIL_H + 0.05
    for k, z in enumerate((-10.6, -17.6, -24.6)):
        y0 = stair_y(z) + RAIL_H
        kids.append(box(f"post_{k}", [0.06, length, 0.06],
                        [(WALL_IN + WALL_OUT) / 2, y0 + length / 2, z], "green",
                        open_=["top", "bottom"]))
    return {"id": "posts", "op": "group", "children": kids,
            "modifiers": [{"op": "mirror", "axis": "x"}]}


def column():
    z = -17.6
    top = (RISE - SLAB) - SLOPE * (LAND - z) + 0.05
    return box("column", [0.5, top, 0.5], [0, top / 2, z], "stone", open_=["top", "bottom"])


def flat_walls():
    """Level 1's stair walls: each one polygon, drawn from both sides."""
    pts = wall_outline()
    x = r((WALL_IN + WALL_OUT) / 2)
    kids = [{"id": "wall", "op": "mesh", "material": "stone",
             "vertices": [[x, y, -mz] for mz, y in pts], "faces": [list(range(len(pts)))]}]
    return {"id": "walls", "op": "group", "children": kids,
            "modifiers": [{"op": "mirror", "axis": "x"}]}


def stair(level=0):
    kids = [flight_top(), flight_under(), landing(), walls() if level == 0 else flat_walls(),
            roof()]
    if level == 0:
        kids += [posts(), column()]
    elif level == 1:
        kids += [column()]
    return {"id": "stairs", "op": "group",
            "children": [{"id": "stair", "op": "group", "children": kids,
                          "transform": {"translate": [STAIR_X, 0, 0]}}],
            "modifiers": [{"op": "mirror", "axis": "x"}]}


# ---------------------------------------------------------------------------- the parapet
PARAPET = [(PAR_IN, DECK, 'concrete', 0.0, (TOP - DECK) / 2.0),
           (PAR_IN, TOP, 'coping', 0.0, 1.0),
           (EDGE, TOP, 'fascia', 0.0, (TOP - DECK) / sv.FASCIA_H),
           (EDGE, DECK, None, 0.0, 0.0)]
SEGMENTS = [(-HALF, -GAP_OUT), (-GAP_IN, GAP_IN), (GAP_OUT, HALF)]


def parapet():
    kids = []
    caps = {"id": "parapet_ends", "op": "mesh", "material": "concrete", "vertices": [],
            "faces": []}
    for k, (x0, x1) in enumerate(SEGMENTS):
        node = sv.loft(f"parapet_{k}", [PARAPET, PARAPET], [x0, x1])
        kids.append(node)
        for x, sgn in ((x0, -1), (x1, 1)):
            if abs(abs(x) - HALF) < 1e-6:
                continue                         # the hall's ends join the tapers' parapets
            b = len(caps["vertices"])
            caps["vertices"] += [[r(x), DECK, PAR_IN], [r(x), TOP, PAR_IN], [r(x), TOP, EDGE],
                                 [r(x), DECK, EDGE]]
            f = [b, b + 1, b + 2, b + 3]
            caps["faces"].append(f[::-1] if sgn > 0 else f)
    kids.append(caps)
    return {"id": "parapet", "op": "group", "children": kids}


# ---------------------------------------------------------------------------- levels
def level0():
    return [hall_box(), facade(0), cladding(0), eave(0), lockers()] + room() + \
           [stair(0), parapet()] + platform_stair(0)


def level1():
    return [hall_box(1), facade(1), cladding(1), eave(1),
            box("doorway", [2 * DOOR_HALF, DOOR_H, 0.1], [0, DOOR_H / 2, FRONT + 0.3 + 0.05],
                "dark", open_=["top", "bottom", "left", "right", "front"]),
            stair(1), parapet()] + platform_stair(1)


def level2():
    wedge = {"id": "stair", "op": "extrude", "material": "stone", "depth": 2 * WALL_OUT,
             "points": [[-EDGE, RISE + RAIL_H], [-FOOT, RAIL_H], [-FOOT, 0], [-EDGE, 0]],
             "faces": {"side": "roof"},
             "transform": {"rotate": [0, 90, 0], "translate": [STAIR_X, 0, 0]}}
    return [
        box("hall", [2 * HALF, CLAD_TOP, BACK - FRONT], [0, CLAD_TOP / 2, (BACK + FRONT) / 2],
            "stone", open_=["top", "bottom", "front"], faces={"back": "interior"}),
        {"id": "stairs", "op": "group", "children": [wedge],
         "modifiers": [{"op": "mirror", "axis": "x"}]},
    ]


def recipe():
    return {
        "format": "mei-asset", "version": 1, "name": "station_concourse",
        "budget": {"vertices": 1000, "triangles": 800},
        "sheets": {"concourse": {"image": SHEET}, "concrete": {"image": CONCRETE}},
        "materials": MATERIALS,
        "lighting": {"mode": "vertical", "ambient": 0.5},
        "verification": {"required": True, "depth": True, "perspective": True},
        "nodes": level0(),
        "lod": {"levels": [{"distance": 30, "nodes": level1()},
                           {"distance": 70, "nodes": level2()}], "band": 2},
    }


# ---------------------------------------------------------------------------- collision
def cbox(id_, x0, x1, y0, y1, z0, z1, open_=("bottom",)):
    n = {"id": id_, "op": "box", "size": [r(x1 - x0), r(y1 - y0), r(z1 - z0)],
         "material": "solid",
         "transform": {"translate": [r((x0 + x1) / 2), r((y0 + y1) / 2), r((z0 + z1) / 2)]}}
    if open_:
        n["open"] = list(open_)
    return n


def slab(id_, outline_x, x0, x1, material="solid"):
    """An outline in (-z, y) extruded across x0..x1."""
    return {"id": id_, "op": "extrude", "material": material, "depth": r(x1 - x0),
            "points": outline_x,
            "transform": {"rotate": [0, 90, 0], "translate": [r((x0 + x1) / 2), 0, 0]}}


def plan(id_, outline, y0, y1):
    """An outline in (x, -z) extruded up from y0 to y1."""
    return {"id": id_, "op": "extrude", "material": "solid", "depth": r(y1 - y0),
            "points": [[r(a), r(b)] for a, b in outline],
            "transform": {"rotate": [-90, 0, 0], "translate": [0, r((y0 + y1) / 2), 0]}}


def collision():
    """Boxes and slabs. Pieces that meet overlap by a couple of centimetres or leave the
    touching side open, so no two faces share a plane."""
    f0, f1 = FRONT, FRONT + 0.3
    o = 0.02
    zg = LAND - (RISE - SLAB) / SLOPE
    nodes = [
        slab_xy("facade", [[-HALF, 0], [-DOOR_HALF, 0], [-DOOR_HALF, DOOR_H], [DOOR_HALF, DOOR_H],
                           [DOOR_HALF, 0], [HALF, 0], [HALF, CLAD_TOP], [-HALF, CLAD_TOP]],
                f0, f1),
        plan("shell", [[-HALF + 0.05, -(f1 - o)], [-HALF + 0.3, -(f1 - o)],
                       [-HALF + 0.3, -(BACK - 0.3)], [HALF - 0.3, -(BACK - 0.3)],
                       [HALF - 0.3, -(f1 - o)], [HALF - 0.05, -(f1 - o)], [HALF - 0.05, -BACK],
                       [-HALF + 0.05, -BACK]], -0.1, CLAD_TOP - 0.1),
        # the room's +x and back walls, the back wall running on behind the stair hall
        plan("room", [[ROOM_HALF, -(f1 - o)], [ROOM_HALF + 0.2, -(f1 - o)],
                      [ROOM_HALF + 0.2, -(ROOM_BACK + 0.2)], [-(LAND_U1 + 0.1), -(ROOM_BACK + 0.2)],
                      [-(LAND_U1 + 0.1), -ROOM_BACK], [ROOM_HALF, -ROOM_BACK]],
             -0.1, GIRDER + IN),
        # its -x wall, up to the stair's opening
        cbox("room_wall", -ROOM_HALF - 0.2, -ROOM_HALF, -0.1, ROOM_H + 0.1, f1 - o, -F1_W[1] + o),
        cbox("room_ceiling", -ROOM_HALF - 0.1, ROOM_HALF + 0.1, ROOM_H, ROOM_H + 0.2, f1 - 0.06,
             ROOM_BACK + 0.1, None),
        cbox("room_floor", -ROOM_HALF - 0.1, ROOM_HALF + 0.1, FLOOR_Y - 0.2, FLOOR_Y, f1 - 0.06,
             ROOM_BACK + 0.1, None),
        cbox("machines", -ROOM_HALF - o, -ROOM_HALF + 0.6, FLOOR_Y, FLOOR_Y + 1.7, -2.2, 0.2),
        cbox("column_clad", -0.7, 0.7, FLOOR_Y, ROOM_H, -4.85, -3.35, ("bottom", "top")),
        cbox("eave", -6.0, 6.0, 3.45, 3.65, FRONT - 2.05, FRONT + o, None),
        cbox("lockers", -8.2, -5.8, 0, 1.8, FRONT - 0.48, FRONT + o),
    ]
    for side, sx in (("w", -1), ("e", 1)):
        x = sx * STAIR_X
        nodes += [
            slab(f"flight_{side}", [[-EDGE, RISE], [-LAND, RISE], [-FOOT, 0], [r(-zg), 0],
                                    [-LAND, RISE - SLAB], [-EDGE, RISE - SLAB]],
                 x - STAIR_HALF + 0.04, x + STAIR_HALF - 0.04),
            slab(f"wall_{side}_w", wall_outline(0.1), x - WALL_OUT, x - WALL_IN),
            slab(f"wall_{side}_e", wall_outline(0.1), x + WALL_IN, x + WALL_OUT),
            slab(f"roof_{side}", [[-ROOF_END, roof_line(ROOF_END)], [-FOOT, roof_line(FOOT)],
                                  [-FOOT, roof_line(FOOT) - 0.2],
                                  [-ROOF_END, roof_line(ROOF_END) - 0.2]],
                 x - WALL_OUT - 0.17, x + WALL_OUT + 0.17),
            cbox(f"column_{side}", x - 0.25, x + 0.25, 0, 4.1, -17.85, -17.35, ("bottom", "top")),
        ]
    for k, (x0, x1) in enumerate(SEGMENTS):
        nodes.append(cbox(f"parapet_{k}", x0, x1, DECK, TOP, EDGE, PAR_IN))
    nodes += platform_stair_collision()
    for n in nodes:
        if "points" in n:
            n["points"] = [[r(a), r(b)] for a, b in n["points"]]
    return {"format": "mei-asset", "version": 1, "name": "station_concourse_col",
            "materials": {"solid": {"color": "#ffffff", "palette": True}},
            "lighting": {"mode": "vertical", "ambient": 0.5},
            "verification": {"required": True, "depth": True, "perspective": True},
            "nodes": nodes}


def ubox(id_, u0, u1, y0, y1, w0, w1, open_=("bottom",)):
    """cbox in the town's frame."""
    return cbox(id_, -u1, -u0, y0, y1, -w1, -w0, open_)


def uprism(id_, outline, w0, w1):
    """An outline in (u, y) extruded across w0..w1."""
    return slab_xy(id_, [[-u, y] for u, y in outline], -w1, -w0)


def platform_stair_collision():
    """The flights as slopes (the second and third as slabs over the room), the landings, the
    walls. Touching pieces overlap by a centimetre or two, by different amounts where faces
    would otherwise share a plane."""
    fw0, fw1 = F1_W
    o, d = 0.02, S * 0.02
    over = ROOM_H + 0.15                         # the walls' foot over the room, in its ceiling
    return [
        uprism("flight_1", [(FOOT_U, FLOOR_Y), (LAND_U0 + 0.03, LAND_Y + S * 0.03),
                            (LAND_U0 + 0.03, -0.05), (FOOT_U, -0.05)], fw0 - o, fw1 + o),
        ubox("landing", LAND_U0, LAND_U1 + o, 0.0, LAND_Y, fw0 - 0.03, SW + 0.04),
        uprism("flight_2", [(MID_U[1] - o, MID_Y + d), (LAND_U0 + 0.03, LAND_Y - S * 0.03),
                            (LAND_U0 + 0.03, -0.03), (MID_U[1] - o, -0.03)], -SW - o, SW + o),
        ubox("half_landing", MID_U[0], MID_U[1], MID_Y - 0.4, MID_Y, -SW - 0.03, SW + 0.03,
             ("left", "right")),
        uprism("flight_3", [(MID_U[0] + o, MID_Y - d), (TOP_U, PLATFORM), (TOP_U, PLATFORM - SLAB),
                            (MID_U[0] + o, MID_Y - d - SLAB)], -SW - 0.01, SW + 0.01),
        uprism("wall_n", tunnel_wall(LAND_U1 + 0.05, HALL_U + 0.05, over), SW, SW + SWT),
        uprism("divider", tunnel_wall(LAND_U0 + 0.015, HALL_U + 0.05, over), -SW - SWT, -SW),
        ubox("end_wall", LAND_U1, LAND_U1 + 0.12, 0.0, SOFFIT + 0.04, fw0 - 0.1, SW + SWT + o),
        ubox("over_room", HALL_U + 0.03, HALL_U + 0.18, ROOM_H + 0.05, SOFFIT + 0.05, fw0 - o,
             fw1 + 0.05),
    ]


def slab_xy(id_, outline, z0, z1):
    """An outline in (x, y) extruded across z0..z1."""
    return {"id": id_, "op": "extrude", "material": "solid", "depth": r(z1 - z0),
            "points": [[r(a), r(b)] for a, b in outline],
            "transform": {"translate": [0, 0, r((z0 + z1) / 2)]}}


def write(name, data):
    with open(os.path.join(HERE, name), "w") as f:
        f.write(mv.dump(data) + "\n")
    print("wrote", name)


if __name__ == "__main__":
    # level 2 (from 70 m) is an impostor: cut-out pictures of level 0 on a box round it
    # (tools/assetkit/impostor.py: art/station_concourse_front.png and _side.png; Pillow, NumPy)
    import sys
    sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "..", "..", "tools"))
    from assetkit.impostor import with_impostor
    write("station_concourse.asset.json", with_impostor(recipe(), HERE, "station_concourse", ppu=3.0))
    write("station_concourse_col.asset.json", collision())
