"""Shrine town (A + C): the plan in numbers, shared by draw.py and the checks.

Metres. x east 0..320, z north 0..384 (5 x 6 cells of 64 m), heights above the street (0).
Direction A's shrine is placed whole: A's (x, y) maps to (x + 64, 280 - y).
"""
import math

W, D = 320, 384
CELL = 64

def clamp(v, a, b): return max(a, min(b, v))
def smooth(t): t = clamp(t, 0.0, 1.0); return t * t * (3 - 2 * t)
def seg_dist(px, pz, a, b):
    ax, az = a; bx, bz = b
    dx, dz = bx - ax, bz - az
    L = dx * dx + dz * dz
    t = 0.0 if L == 0 else clamp(((px - ax) * dx + (pz - az) * dz) / L, 0, 1)
    return math.hypot(px - ax - t * dx, pz - az - t * dz)
def poly_dist(px, pz, pts): return min(seg_dist(px, pz, a, b) for a, b in zip(pts, pts[1:]))
def poly_len(pts): return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
def in_rect(x, z, r): return r[0] <= x <= r[2] and r[1] <= z <= r[3]

# ------------------------------------------------------------------ zones (x1, z1, x2, z2)
VIADUCT = [(0, 8), (276, 8), (290, 12), (299, 22), (302, 36), (302, 118), (306, 134), (320, 146)]
VIADUCT_W, VIADUCT_DECK = 12, 9.0
ROAD = (0, 104, 320, 118)            # the front road, 14 m with sidewalks
PLAZA = (108, 16, 214, 44)
SANDO = (154, 44, 166, 104)          # the shopping street itself
COURT = (110, 118, 210, 167)         # outer courtyard, 0.6
TERR = (114, 167, 214, 234)          # inner precinct terrace, 5.0
TEMPLE = (134, 208, 186, 228)        # temple podium, 8.6
CANAL = (44, 0, 52, 292)             # canal, water -0.4, bed -1.2
PARK = (0, 118, 44, 206)             # park and festival ground, 0.6
POOL = (214, 22, 240, 40)            # school pool, -1.2
CEMETERY = (256, 130, 316, 250)      # 1.8 m terraces up to 16.2
STAGE = (138, 340, 170, 354)         # Kiyomizu stage deck, 60
STAGE_Z = 60.0
PAGODA = (178, 262)
# The pagoda's terrace is cut 5 m into the ridge's crest (the plan had it on the crest at 20): with
# the real temple's ridge (27.5) and the real pagoda's first roof (25.0 above a base of 20, its
# eave 5.4 m out) the glide G5 came down 3.6 m short, under the eave. At 15 it lands on roof 1;
# G7 from roof 5 still reaches the cemetery's top terrace (DESIGN.md, "Changes from the plan").
PAG_BASE = 15.0
# The pagoda is the shrine's real one (owner, 2026-10-05): eave tops 3.6 m apart (5.0 to 19.4 above
# the base), eave half widths 5.4 to 2.6, the dew basin's top at 21.19, the finial pole 8.8 to 30.0.
PAG_EAVES = [5.4, 4.7, 4.0, 3.3, 2.6]
PAG_ROOFS = [PAG_BASE + h for h in (5.0, 8.6, 12.2, 15.8, 19.4)]; PAG_TOP = PAG_BASE + 30.0
BASIN = (154, 296, 15, 13.0)         # sacred cedar basin: centre, radius, floor
CEDAR = (154, 296)                   # sacred cedar (tree_cedar_sacred, 45.8 m)
KNOT = (150.5, 295.0, 21.5)          # the knot hole, west face
FOX = (90, 294, 10, 15.0)            # fox grove
FALLS_POOL = (214, 322, 9, 12.0)
FALLS = (210, 338, 218, 342)         # falls 48 -> 12
CHIMNEY = (195, 330, 198, 338)       # kick chimney, two rock faces 3 m apart, 18 -> 48
POND = [(234, 140, 15), (236, 166, 16)]
STREAM = [(214, 322), (224, 298), (236, 268), (244, 232), (240, 198), (237, 182)]
SENBON = [(94, 300), (92, 314), (106, 318), (96, 328), (112, 334), (106, 342), (122, 346)]   # torii tunnel, 15 -> 54.5, switchbacks
CLEARINGS = [BASIN, FOX, FALLS_POOL, (PAGODA[0], PAGODA[1], 13, PAG_BASE, 16)]    # (x, z, r, floor[, bank])

def pond_d(x, z): return min(math.hypot(x - cx, (z - cz) * .95) / r for cx, cz, r in POND)
def stream_d(x, z): return poly_dist(x, z, STREAM)

def mountain(x, z):
    """The wooded land north of the road: west woods, ridge, basin, back mountain, east shoulder."""
    h = 1.6 + 1.2 * math.sin(x / 13.0) * math.cos(z / 17.0) + 0.8 * math.sin((x + z) / 9.0)
    h += 10.0 * smooth((z - 240) / 34)                                   # land steps up behind the precinct
    h += 11.0 * math.exp(-((z - 262) / 13) ** 2) * smooth((x - 84) / 30) * smooth((252 - x) / 30)  # the ridge
    h += 44.0 * clamp((z - 308) / 48, 0, 1) ** 0.85                      # the back mountain
    if z > 316: h += 6.0 * smooth((z - 316) / 6)                         # its cliff band
    # west woods ease down to the canal lane
    h = 1.0 + (h - 1.0) * smooth((x - 54) / 14) if x < 68 else h
    # east shoulder: the cemetery's top (16.2 at z 250) up to the falls' top (48 at z 346)
    if x > 244 and z > 236:
        sh = 16.2 + 31.8 * smooth((z - 250) / 96) + 4 * smooth((x - 300) / 20)
        h = max(h, sh * smooth((x - 244) / 14) + h * (1 - smooth((x - 244) / 14)))
    for cx, cz, r, fl, *bank in CLEARINGS:
        w = bank[0] if bank else 7                  # the pagoda's hollow eases out over 16 m (under 30 degrees)
        d = math.hypot(x - cx, z - cz)
        if d < r + w: h = fl + (h - fl) * smooth((d - r) / w)
    # ease to the courtyard (0.6) and to 3 m along the terrace's retaining wall
    if COURT[0] - 12 < x < COURT[2] + 12 and z < COURT[3] + 4:
        e = min(abs(x - COURT[0]), abs(x - COURT[2]))
        h = 0.6 + (h - 0.6) * smooth(e / 12)
    if TERR[0] - 10 < x < TERR[2] + 10 and TERR[1] < z < TERR[3] + 8:
        e = min(abs(x - TERR[0]), abs(x - TERR[2]), abs(z - TERR[3]) if z > TERR[3] else 99)
        h = 3.0 + (h - 3.0) * smooth(e / 10)
    h = min(h, 0.6 + (z - 118) * 0.35) if z < 140 else h                # meets the road's kerb gently
    sd = stream_d(x, z)
    if sd < 5 and z < 318: h -= 2.2 * (1 - sd / 5) + .3
    pd = pond_d(x, z)
    if pd < 1.15: h = min(h, -1.4 + 2.0 * smooth((pd - .6) / .55))
    return h

def height(x, z):
    if in_rect(x, z, CANAL) and z < 292: return -1.2
    if z < ROAD[3]:                                     # the town south of the front road
        if in_rect(x, z, POOL): return -1.2
        return 0.0
    if in_rect(x, z, TEMPLE): return 8.6
    if in_rect(x, z, TERR): return 5.0
    if in_rect(x, z, COURT) and pond_d(x, z) > 1.05: return 0.6
    if in_rect(x, z, PARK): return 0.6
    if x < 44 and z > 206:                              # bamboo grove rising to the north-west seam
        return 0.6 + 22 * smooth((z - 206) / 178) * (0.6 + 0.4 * smooth((44 - x) / 44))
    if in_rect(x, z, CEMETERY):
        return 1.8 * min(9, math.floor((z - 130) / 12) + 1)
    if 252 <= x <= 320 and 118 <= z < 130: return 0.0   # cemetery lane along the road
    if seg_dist(x, z, (160, 234), (172, 254)) < 3.5:    # stone stair, north gate to the pagoda terrace
        t = clamp((z - 234) / 20, 0, 1); return 5.0 + t * (PAG_BASE - 5.0)
    if in_rect(x, z, STAGE): return STAGE_Z
    return mountain(x, z)

def is_water(x, z):
    if in_rect(x, z, CANAL) and z < 292: return True
    if in_rect(x, z, POOL): return True
    if z < ROAD[3]: return False
    return pond_d(x, z) < .92 or (stream_d(x, z) < 1.8 and z < 318) or \
        math.hypot(x - FALLS_POOL[0], z - FALLS_POOL[1]) < 6

# ------------------------------------------------------------------ texture regions (TEXTURES.md)
# Two World Kit regions, each with its own texture set: the town (rows 0-1, z < 128: station,
# plaza, shotengai, alleys, school, the front road, the canal's machiya and sento) and the shrine
# (rows 2-5: courtyard, precinct, woods, ridge, mountain, pond, cemetery, park, bamboo). The
# boundary is the cell line z = 128, 10 m north of the front road's kerb.
REGIONS = ('town', 'shrine')
TOWN_ROWS = 2                        # rows 0 .. TOWN_ROWS - 1 are the town's
def region_of(i, j): return 'town' if j < TOWN_ROWS else 'shrine'

# ------------------------------------------------------------------ things that stand
# boxes: (x1, z1, x2, z2, base, top, colour, label)
RED, ROOF, WOOD, STONE, WHITE, TILE, CONC = '#c43026', '#3a3c44', '#96683f', '#97928a', '#eee8d6', '#5a6068', '#c8c4b8'
boxes = []
def box(x1, z1, x2, z2, h, col, base=None, lab=None):
    b = height((x1 + x2) / 2, (z1 + z2) / 2) if base is None else base
    boxes.append((x1, z1, x2, z2, b, b + h, col, lab)); return b + h
def hall(x1, z1, x2, z2, h, roof, col=RED, over=1.5, base=None, lab=None):
    b = height((x1 + x2) / 2, (z1 + z2) / 2) if base is None else base
    box(x1, z1, x2, z2, h, col, b)
    box(x1 - over, z1 - over, x2 + over, z2 + over, roof * .45, ROOF, b + h)
    box(x1 + (x2 - x1) * .2, z1 + (z2 - z1) * .2, x2 - (x2 - x1) * .2, z2 - (z2 - z1) * .2, roof * .55, ROOF,
        b + h + roof * .45, lab)
    return b + h + roof

# -- station, plaza
box(136, 2, 184, 14, 12.8, '#7a8a70', 0, 'Station: platform 9, canopy 12.8')
box(178, 18, 214, 32, 5.6, '#dfe3e8', 0, 'Konbini 5.6')
box(116, 18, 128, 28, 5.9, '#3a6ab0', 0, 'Koban')
box(136, 34, 144, 37, 2.6, '#b4ae9e', 0)                 # bus stop
box(70, 18, 86, 34, 18.8, CONC, 0, 'Danchi 18.8')
box(92, 18, 108, 34, 9.1, '#d88aa0', 0, 'Pachinko 9.1')
# -- sando: six shops a side, 10 m frontage; two 3-storey (9.5) a side
SHOPS = []
for i, z in enumerate(range(44, 104, 10)):
    hw = 9.5 if i in (1, 5) else 6.5
    he = 9.5 if i in (2, 5) else 6.5
    SHOPS.append(box(140, z + .5, 154, z + 9.5, hw, TILE, 0)); SHOPS.append(box(166, z + .5, 180, z + 9.5, he, TILE, 0))
box(152, 62, 168, 94, 1.5, '#a8c0cc', 7.0, 'Arcade roof 7-8.5')
for zz in (60, 96): box(152, zz, 168, zz + 2, 8.3, '#c8402a', 0)   # arcade gates
# -- the building with the fire escape (street_building, turned)
box(186, 44, 200, 102, 18.3, '#b8b0a0', 0, 'Building 18.3')
# -- back alleys
import random
_r = random.Random(7)
for x in range(66, 136, 12):
    for z in range(44, 102, 11):
        if 96 <= x <= 108 and 66 <= z <= 80: continue          # fire tower yard
        if (x, z) in ((78, 77), (114, 88), (66, 55)): continue    # three yards: no alley runs straight
        if x >= 126 and z < 54: continue                         # dagashi corner
        box(x, z, x + 9.5, z + 8.5, _r.choice([6, 6.5, 7, 8]), ROOF, 0)
box(99, 71, 105, 77, 15.2, '#a8321e', 0, 'Fire tower 15.2')
box(126, 44, 131, 49, 4.4, '#b08a5e', 0)                   # dagashi shop
# -- west of the canal: machiya and the sento
for z in range(18, 104, 12):
    if 56 <= z <= 78: continue
    box(4, z, 18, z + 10, 7.5, ROOF, 0); box(24, z, 40, z + 10, 7.0, ROOF, 0)
box(8, 60, 30, 73, 8.0, '#7a5a48', 0, 'Sento')
box(22, 67, 25, 70, 18.2, '#8a8478', 0)                    # its chimney
box(6, 212, 24, 224, 16.2, '#e8e2d2', None, 'Sake brewery 16.2')
box(18, 156, 26, 164, 8.0, WOOD, 0.6, 'Yagura 8')
# -- school
box(258, 56, 288, 86, 18.9, '#d8d4c8', 0, 'School 18.9')
box(214, 64, 238, 94, 9.0, '#8a9a80', 0, 'Gym 9')
box(256, 106, 268, 116, 7.0, '#5a8a60', 0)                 # overpass deck (over the road)
# -- shrine (direction A, moved)
box(155, 123.5, 165, 124.5, 13.2, RED, 0.6, 'Great torii 13.2')
SIDE_ROOF = hall(122, 126, 134, 162, 6, 5, base=0.6); hall(186, 126, 198, 162, 6, 5, base=0.6)
CORR_ROOF = hall(122, 174, 134, 202, 5, 5, base=5.0); hall(186, 174, 198, 202, 5, 5, base=5.0)
TEMPLE_ROOF = hall(136, 210, 184, 226, 9, 11.9, col=WOOD, over=3, base=8.6)
box(151, 162, 169, 172, 6, RED, 5.0); box(149, 160, 171, 174, 1.2, ROOF, 11.0)
box(152, 163, 168, 171, 4, RED, 12.2); GATE_ROOF = box(150, 161, 170, 173, 2.4, ROOF, 16.2)
box(202, 224, 206, 228, 4.7, WOOD, 5.0)                     # bell pavilion
WALL = [(150, 167), (116, 167), (114, 172), (114, 228), (118, 234), (128, 236), (192, 236), (210, 232), (214, 222),
        (214, 176), (210, 167), (170, 167)]
GATES = [(114, 200, 4), (160, 236, 5), (214, 192, 4)]
wall_segs = []
for (ax, az), (bx, bz) in zip(WALL, WALL[1:]):
    n = max(1, int(math.hypot(bx - ax, bz - az) // 2))
    for k in range(n):
        x0, z0 = ax + (bx - ax) * k / n, az + (bz - az) * k / n
        x1, z1 = ax + (bx - ax) * (k + 1) / n, az + (bz - az) * (k + 1) / n
        if any(math.hypot((x0 + x1) / 2 - gx, (z0 + z1) / 2 - gz) < gr for gx, gz, gr in GATES): continue
        wall_segs.append(((x0, z0), (x1, z1)))
        boxes.append((min(x0, x1) - .4, min(z0, z1) - .4, max(x0, x1) + .4, max(z0, z1) + .4, 5.0, 7.6, WHITE, None))
_b = PAG_BASE
for i, z in enumerate(PAG_ROOFS):
    sz = PAG_EAVES[i] - 1.0
    box(PAGODA[0] - sz, PAGODA[1] - sz, PAGODA[0] + sz, PAGODA[1] + sz, z - 0.6 - _b, '#a03c2e', _b)
    box(PAGODA[0] - PAG_EAVES[i], PAGODA[1] - PAG_EAVES[i], PAGODA[0] + PAG_EAVES[i], PAGODA[1] + PAG_EAVES[i], 0.6, ROOF, z - 0.6)
    _b = z
box(PAGODA[0] - .3, PAGODA[1] - .3, PAGODA[0] + .3, PAGODA[1] + .3, PAG_TOP - PAG_ROOFS[4], '#c8aa3c', PAG_ROOFS[4])
# The kick pair: two cedars west of the pagoda, trunk faces 3.2 m apart (north and south), 1.05 m
# from roof 2's west eave line (the plan's single KICK_CEDAR south of the pagoda is dropped: roof 1's
# eave closed its shaft).
KICK_PAIR = [(171.35, 259.5), (171.35, 264.5)]
for _kx, _kz in KICK_PAIR:
    box(_kx - .9, _kz - .9, _kx + .9, _kz + .9, 21.5, '#3a4a30', PAG_BASE)
for px in range(140, 170, 6):
    for pz in (342, 348, 353):
        g = mountain(px, pz); box(px - .6, pz - .6, px + .6, pz + .6, STAGE_Z - g, WOOD, g)
box(STAGE[0], STAGE[1], STAGE[2], STAGE[3], 1.0, '#aa7c50', STAGE_Z - 1)
hall(140, 355, 168, 374, 8, 10, col=WOOD, base=STAGE_Z, lab='Stage hall')
box(FALLS[0], FALLS[1], FALLS[2], FALLS[3], 36, '#5a96dc', 12)
box(CEDAR[0] - 3, CEDAR[1] - 3, CEDAR[0] + 3, CEDAR[1] + 3, 45.8, '#2e4a30', BASIN[3])
box(86, 304, 94, 310, 4.4, RED)                             # fox shrine
for (ax, az), (bx, bz) in zip(SENBON, SENBON[1:]):
    n = int(math.hypot(bx - ax, bz - az) // 4)
    for k in range(n):
        tx, tz = ax + (bx - ax) * k / n, az + (bz - az) * k / n
        zz = height(tx, tz); box(tx - 1.6, tz - .3, tx + 1.6, tz + .3, 3.6, '#e0502a', zz)

# treetop walkway (deck centres and absolute deck heights)
DECKS = [(94, 152, 9), (82, 180, 12), (80, 208, 15), (88, 234, 18), (102, 252, 21), (114, 264, 22), (130, 282, 24)]
CROWN = (70, 220, 28)
for x, z, h in DECKS + [CROWN]: box(x - 3, z - 3, x + 3, z + 3, .6, '#aa7c50', h - .6)
BRIDGE = [(214, 192), (220, 186), (216, 180), (222, 174), (218, 168), (224, 162), (220, 156)]

# ------------------------------------------------------------------ routes (by layer)
SPAWN = (160, 26)
# ground layer
R_AXIS = [SPAWN, (160, 44), (160, 104), (160, 124), (160, 160), (160, 200), (150, 206), (150, 232), (160, 236), (148, 246), (166, 254), (178, 262)]
R_WEST = [SPAWN, (132, 40), (118, 44), (118, 60), (112, 66), (112, 104), (104, 112), (100, 130), (96, 150), (84, 176), (78, 206), (84, 232), (96, 256), (94, 284), (90, 294)]
R_TUNNEL = SENBON + [(138, 347)]
R_EAST = [SPAWN, (196, 40), (206, 44), (206, 100), (226, 104), (262, 104), (262, 118), (262, 124), (286, 132), (286, 250), (290, 262), (302, 282), (262, 300), (296, 322), (250, 338), (226, 346)]
R_ROPEBRIDGE = [(222, 346), (196, 346), (170, 347)]
R_WATER = [(214, 120), (226, 128), (232, 150), (236, 180), (240, 198), (244, 232), (236, 268), (224, 298), (214, 318)]
R_CANAL = [SPAWN, (120, 40), (90, 40), (60, 40), (56, 60), (56, 104), (56, 140), (48, 176), (30, 176), (22, 200), (24, 250), (20, 300), (8, 350)]
# town roof layer (dashed): bus stop, konbini, wire, sando roofs, arcade, wire, torii; alleys; fire tower; danchi
R_ROOF = [(168, 32), (172, 44), (173, 52), (173, 62), (160, 70), (160, 92), (147, 96), (147, 102), (152, 111), (160, 124)]
R_ROOF3 = [(186, 33), (196, 28), (210, 40), (207, 104), (190, 104)]
R_ROOF2 = [(147, 66), (135, 66), (120, 66), (104, 74), (90, 60), (80, 46), (78, 30)]
R_SHRINE_ROOF = [(128, 158), (155, 124), (165, 124), (192, 158), (192, 140), (170, 165), (160, 167), (128, 176), (128, 200), (150, 210), (160, 218), (178, 256)]
# tree layer
R_TREE = [(102, 118), (94, 152), (82, 180), (80, 208), (88, 234), (102, 252), (114, 264), (130, 282)]
R_CROWN = [(80, 208), CROWN[:2]]
R_ROPE = [(130, 282), KNOT[:2]]
# rails: utility wires (8 m) and the courtyard's lantern strings
WIRES = [[(x, 104) for x in range(10, 300, 30)], [(150, 104), (150, 44)], [(210, 40), (207, 104)], [(118, 104), (118, 44)]]
STRINGS = [((155, 124), (134, 158)), ((165, 124), (186, 158)), ((134, 160), (151, 166)), ((186, 160), (169, 166))]
# glides (start x, z, start height incl. the 3.4 m double-jump apex, end x, z)
GLIDES = [
    ('G1 building roof -> east side hall', (193, 102, 18.3), (192, 126)),
    ('G2 danchi roof -> canal lane', (78, 34, 18.8), (56, 80)),
    ('G3 sento chimney -> park', (23.5, 70, 18.2), (22, 138)),
    ('G4 fire tower -> courtyard west', (102, 77, 15.2), (112, 140)),
    ('G5 temple ridge -> pagoda roof 1', (172.5, 222.3, 27.5), (178, 256.6)),   # the real temple's ridge; roof 1 at 20.0
    ('G6 stage -> pagoda roof 4', (162, 340, 60.0), (179, 266)),
    ('G7 pagoda roof 5 -> cemetery top', (180.6, 262, PAG_ROOFS[4]), (263, 247)),   # lands on the top terrace's west end (scenario 416)
    ('G8 race line: stage -> arcade', (170, 340, 60.0), (160, 98)),
]
SHORTCUTS = [
    ('A', (154, 336), (154, 318), 'Rope ladder: kicked down from the stage ledge (44 m) to the basin rim'),
    ('B', (160, 244), (160, 238), 'North gate bar: lifted from the ridge side'),
    ('C', (256, 306), (226, 318), 'Dead cedar: pounded down across the gorge (shoulder 34 m <-> falls-pool shelf 20 m)'),
    ('D', (151, 284), (151, 290), 'Root door: pounded open from inside the cedar'),
    ('E', (200, 104), (200, 98), 'Fire-escape ladder: dropped from the building roof'),
]

# ------------------------------------------------------------------ goals and places
STARS = [
    (1, PAGODA[0], PAGODA[1], PAG_TOP, 'Pagoda finial (50 m)'),
    (2, 160, 124, 13.2, 'Eight red coins over the shotengai; star on the torii (13.2 m)'),
    (3, 154, 358, 61.0, 'The stage bell (60 m)'),
    (4, CEDAR[0], CEDAR[1], 13.0, 'Inside the sacred cedar (one way in)'),
    (5, 160, 8, 9.0, 'The last train (timed, from the stage to the platform)'),
]
RED_COINS = [(160, 78, 8.5), (102, 74, 15.2), (172, 8, 12.8), (78, 26, 20.8), (196, 30, 7.0),
             (130, 104, 8.0), (23.5, 68.5, 18.2), (48, 8, 10.2)]
RACE_SWITCH = (168, 342)
POIS = [
    ('S', SPAWN[0], SPAWN[1], 'Spawn: station plaza'), (1, 160, 8, 'Station, platform 9 m'),
    (2, 196, 25, 'Konbini (door to the garden)'), (3, 122, 24, 'Koban'), (4, 78, 26, 'Danchi 18.8 m, outside stair'),
    (5, 160, 74, 'Shotengai under the arcade'), (6, 100, 58, 'Back alleys'), (7, 102, 74, 'Fire tower 15.2 m'),
    (8, 48, 60, 'Canal (wading 0.8 m)'), (9, 19, 66, 'Sento, chimney 18.2 m'), (10, 193, 73, 'Building 18.3 m, fire escape'),
    (11, 273, 71, 'School 18.9 m'), (12, 226, 79, 'Gym 9 m'), (13, 262, 111, 'Overpass 7 m'),
    (14, 300, 111, 'Viaduct underpass: seamless edge'), (15, 160, 124, 'Great torii'), (16, 160, 142, 'Outer courtyard'),
    (17, 160, 167, 'Gate 18.6 m'), (18, 160, 192, 'Inner precinct (5 m)'), (19, 160, 218, 'Temple (ridge 29.5 m)'),
    (20, 114, 200, 'West gate'), (21, 214, 192, 'East water gate'), (22, 160, 236, 'North gate (B)'),
    (23, 178, 262, 'Pagoda terrace (20 m)'), (24, 234, 150, 'Pond'), (25, 22, 160, 'Park, festival yagura'),
    (26, 48, 196, 'Watermill, arched bridge'), (27, 15, 218, 'Sake brewery 16.2 m'), (28, 22, 320, 'Bamboo grove: soft edge'),
    (29, 84, 200, 'West woods, treetop decks'), (30, 70, 220, 'Crown deck 28 m'), (31, 130, 282, 'Rope deck 24 m'),
    (32, 154, 296, 'Sacred cedar basin (13 m)'), (33, 90, 294, 'Fox grove (15 m)'), (34, 104, 330, 'Senbon torii tunnel'),
    (35, 154, 365, 'Stage (60 m) and hall'), (36, 214, 334, 'Falls 48->12 m, cave behind'), (37, 196, 326, 'Kick chimney'),
    (38, 192, 350, 'Rope bridge'), (39, 286, 190, 'Cemetery terraces 1.8-16.2 m'), (40, 292, 300, 'East shoulder trail'),
    (41, 236, 111, 'Culvert under the road'), (42, 252, 370, 'Mountain path out (next hill)'),
]

def glide_end_height(start, end):
    (x0, z0, h0), (x1, z1) = start, end
    d = math.hypot(x1 - x0, z1 - z0)
    return h0 + 3.4 - d / 4.0, d
