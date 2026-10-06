"""The shrine zone's placement (PLACE_SPLIT): z >= 128 and x >= 64, and the great torii (c2_1).
The zones' hook (place/__init__.py) calls world(ns) from make_world.py, after the three generators
have written their cells: it takes the zone's grey boxes out of those cells and puts the real
assets in, and changes the world with the paths, terrain operations, entity moves, scatters,
levels of detail and asset directories that come with them; the cells it changed are written
back. Idempotent: what it places has ids starting `sh_` and is replaced on every run; what it
removes is found by id.

The real assets are the built shrine's (carts/garden/shrine/assets: the halls, gate, temple,
pagoda, walls, torii, lanterns, trees and forest pieces) and shrine town's own
(assets/NAME/: the gates in the white wall, the chozuya, the office, the komainu, the bell
pavilion, the cemetery, the hollow cedar and its rope and root curtain, the rope ladder, the
dead cedar, the falls cave, the stage bell, the koi, the zelkova, jizo and hokora) and the zone's
few pieces of its own (assets/shrine_extras/). What changed from the grey box, and why, is in
DESIGN.md 12.5.
"""
import math
import sys
from pathlib import Path

ST = Path(__file__).resolve().parent.parent
if str(ST) not in sys.path:
    sys.path.insert(0, str(ST))
import layout as L                                            # noqa: E402

PFX = 'sh_'
R = lambda v: round(v, 3)


def in_zone(x, z):
    return x >= 64 and z >= 128


# ---------------------------------------------------------------------------- the precinct's plan
# The white wall is the shrine's 8 m and 4 m modules with corner posts, so its runs are multiples
# of 4 m between gates (the grey box's wall had chamfered corners and any length). The rectangle:
WX0, WX1 = 117.6, 210.4               # west and east walls (grey 115 / 213)
WZ0, WZ1 = 168.6, 237.4               # south and north walls (grey 167 / 233)
TORII_Z = 124.0                       # the great torii (as the grey box's)
GATE = (160.0, 172.0)                 # the two-storey gate (arch_gate, 20 x 8): its front at 168 meets the wall
GATE_W_Z, GATE_E_Z = 201.0, 193.0     # the west and east gates (arch_wall_gate) on their walls (grey 200 / 192)
GATE_N_X = 162.0                      # the north gate (shortcut B) on the north wall (grey 160)
TERR_Z1 = 238.0                       # the terrace runs on to 238 (grey 234) behind the north wall
# The temple (arch_temple: podium 52 x 24, ridge 27.5 in its collision, z +-0.55) stands with its
# ridge on the line G5 takes off from (scenario 414 at z 222.3): its centre at 221.75, the podium
# 209.75-233.75, 3.15 m clear of the north wall.
TEMPLE = (160.0, 221.75)
SIDE_HALLS = ((128.0, 144.0, 270), (192.0, 144.0, 90))           # arch_side_hall (36 x 12), roofs 11.6
CORRIDORS = ((128.0, 188.0, 270), (192.0, 188.0, 90))            # arch_corridor_hall (32 x 12) on the terrace

# ---------------------------------------------------------------------------- the treetop walkway
DECKS = list(L.DECKS)                 # (x, z, deck height): 9, 12, 15, 18, 21, 22 and the rope deck 24
CROWN = L.CROWN                       # (70, 220, 28)
LANDING = (CROWN[0], CROWN[1], 15.0)  # the crown's landing: a second platform on the crown deck's cedar
PLAT_HALF, PLAT_GAP = 3.5, 1.2        # forest_platform: 7 x 7, its railing open 2.4 m in the middle of each side

# ---------------------------------------------------------------------------- the mountain
CEDAR = (L.CEDAR[0], L.BASIN[3], L.CEDAR[1])                     # the sacred cedar's foot (154, 13, 296)
ROPE_DECK = DECKS[6]
CEDAR_YAW = math.degrees(math.atan2(CEDAR[0] - ROPE_DECK[0], CEDAR[2] - ROPE_DECK[1]))   # its knot hole (-Z) to the rope deck
# forest_stage_hall: deck 32 x 20 (z 340-360, its front where the grey box's was), the hall on it (x 144-164,
# z 348-362 with its eaves), railings with side gaps at z 345. The open deck beside the hall (x 164-170) is
# where G8 takes off (scenario 417); G6's take-off moved there too (415: x 162 is under the hall's eaves).
STAGE = (154.0, L.STAGE_Z, 350.0)
FALLS = (214.0, 12.0, 330.0)          # water_falls, forest_falls_cave and shrine_falls_cliff: the falls' foot on the pool
DEAD_CEDAR = (256.0, 306.0)
DEAD_CEDAR_YAW = math.degrees(math.atan2(DEAD_CEDAR[0] - 226.0, DEAD_CEDAR[1] - 318.0))   # -Z across the gorge to the shelf

# ---------------------------------------------------------------------------- the cemetery
CEM_X0, CEM_X1, CEM_Z0 = 256.0, 316.0, 130.0
WALL_XS = (262.0, 274.0, 298.0, 310.0)        # cemetery_terrace_wall_12 centres: the middle stair runs between, x 280-292
GRAVE_XS = (264.0, 274.0, 298.0, 308.0)
CEM_GATE = (286.0, 1.8, 131.4)                # at the head of the first flight, on terrace 1 (the shrine's region)

# The shrine's levels of detail for the assets it shares with the level (shrine.world.json), a little
# nearer where the shrine town's forest views were over the draw budget (the giant cedars, the
# platforms, the fox torii).
SHRINE_LOD = {'tree_cedar_giant': {'distances': [22, 80]}, 'forest_stage_hall': {'distances': [18, 60]},
              'forest_fox_torii': {'distances': [16], 'cull': 48}, 'forest_platform': {'distances': [24]}, 'arch_temple': {'distances': [30, 90]},
              'arch_side_hall': {'distances': [28]}, 'arch_corridor_hall': {'distances': [28]},
              'arch_gate': {'distances': [30, 80]}, 'arch_pagoda': {'distances': [32, 90]},
              'arch_torii_great': {'distances': [30]}, 'arch_wall_8': {'distances': [24]},
              'arch_wall_4': {'distances': [24]}, 'tree_maple': {'distances': [18, 48]},
              'tree_maple_small': {'distances': [16, 44]}, 'tree_ginkgo': {'distances': [18, 48]},
              'tree_cedar': {'distances': [20, 52]}}

# The assets' directories: the shrine's, and each shrine town asset the zone places.
ASSET_DIRS = ['../shrine/assets'] + [f'assets/{d}' for d in (
    'arch_chozuya', 'arch_ema_board', 'arch_komainu', 'arch_omikuji_rack', 'arch_shrine_office', 'arch_wall_gate',
    'arch_wall_gate_bar', 'bell_pavilion', 'cemetery_gate', 'cemetery_grave_row', 'cemetery_jizo_hall',
    'cemetery_sotoba_rack', 'cemetery_terrace_wall_12', 'forest_dead_cedar', 'forest_falls_cave',
    'forest_root_curtain', 'forest_rope_ladder', 'forest_shide_rope', 'forest_stage_bell', 'life_koi',
    'tree_cedar_sacred_hollow', 'tree_zelkova', 'jizo', 'hokora', 'shishi_odoshi', 'shrine_extras')]

# The grey boxes this zone replaces, by asset (in the zone, and the great torii in c2_1).
GREY = ('gbc_side_hall_', 'gbc_stone_lantern', 'gbc_chozuya', 'gbc_shrine_office', 'gbc_corridor_', 'gbc_temple',
        'gbc_gate', 'gbc_bell_pavilion', 'gbc_wall_', 'gbc_boulder_', 'gbc_deck_tree_', 'gbc_crown_landing',
        'gbc_pagoda_lantern', 'gbc_pond_stone', 'gbc_grave_row', 'gbc_jizo_hall', 'gbc_cem_gate_',
        'gbm_pagoda', 'gbm_cedar_kick_', 'gbm_deck_', 'gbm_cedar_hollow', 'gbm_root_curtain', 'gbm_ladder_a',
        'gbm_hollow_log', 'gbm_fox_', 'gbm_stage', 'gbm_falls_cave', 'gbm_path_out', 'gbm_dead_cedar_')
KEEP = ('gbm_kick_chimney',)          # the chimney's two rock faces stay (no asset is a rock face)
# Assets with repeating textures (a texture window table) cannot be merged (the World Kit refuses),
# and merged lily pads would lose their levels: they are placed alone even where merging was meant
# (the cemetery's rows and walls, the lanterns).
NO_MERGE = {'arch_komainu_a', 'arch_komainu_un', 'forest_stone_lantern', 'shishi_odoshi', 'forest_fox_statue', 'hokora',
            'jizo', 'water_lily_pad', 'water_lily_pad_flower', 'life_koi', 'cemetery_terrace_wall_12',
            'cemetery_grave_row'}


def rot(x, z, yaw):
    """A local (x, z) turned by yaw (degrees; +Z toward +X, as the kit's yaw)."""
    a = math.radians(yaw)
    return x * math.cos(a) + z * math.sin(a), -x * math.sin(a) + z * math.cos(a)


def bearing(dx, dz):
    return math.degrees(math.atan2(dx, dz)) % 360


class Zone:
    def __init__(self, cells, world):
        self.cells, self.world = cells, world
        self.paths = world['paths']

    # ---- cells
    def cell_of(self, x, z):
        return f'c{int(x // 64)}_{int(z // 64)}'

    def place(self, pid, asset, pos, collision='self', yaw=None, layer=None, merge=False, lift=None):
        """pos: (x, y, z), or (x, z) on the ground."""
        x, z = pos[0], pos[-1]
        c = self.cells[self.cell_of(x, z)]
        p = {'id': PFX + pid, 'asset': asset, 'position': [R(v) for v in pos], 'collision': collision}
        if yaw is not None and round(yaw % 360, 2):
            p['yaw'] = R(yaw % 360 if yaw % 360 <= 180 else yaw % 360 - 360)
        if layer:
            p['layer'] = layer
        if merge and asset not in NO_MERGE:
            p['merge'] = True
        if lift is not None:
            p['lift'] = lift
        assert not any(q['id'] == p['id'] for q in c['placements']), p['id']
        c['placements'].append(p)
        return p

    def entity(self, eid):
        for c in self.cells.values():
            for e in c.get('entities', []):
                if e['id'] == eid:
                    return c, e
        raise KeyError(eid)

    def move_entity(self, eid, pos, **params):
        """Moves an entity (to another cell if it crosses one), keeping its id."""
        c, e = self.entity(eid)
        e['position'] = [R(v) for v in pos]
        if params:
            e.setdefault('params', {}).update(params)
        to = self.cells[self.cell_of(pos[0], pos[-1])]
        if to is not c:
            c['entities'].remove(e)
            to.setdefault('entities', []).append(e)

    def clear(self):
        """Takes out what an earlier run placed and the zone's grey boxes."""
        n = 0
        for c in self.cells.values():
            keep = []
            for p in c['placements']:
                x, z = p['position'][0], p['position'][-1]
                grey = p['asset'].startswith(GREY) and not p['asset'].startswith(KEEP) and in_zone(x, z)
                if p['id'].startswith(PFX) or grey or (c['id'] == 'c2_1' and p['id'] == 'torii'):
                    n += 1
                    continue
                keep.append(p)
            c['placements'] = keep
        return n

    # ---- world parts
    def path(self, name, spec):
        self.paths[name] = spec

    def ops(self):
        return self.world['terrain']['fields']['ground']['operations']


# ---------------------------------------------------------------------------- helpers
def plank_bridge(a, b, sag=0.35, n=5):
    pts = []
    for i in range(n):
        f = i / (n - 1)
        pts.append([R(a[0] + (b[0] - a[0]) * f), R(a[1] + (b[1] - a[1]) * f - sag * math.sin(math.pi * f)),
                    R(a[2] + (b[2] - a[2]) * f)])
    return pts


def platform_yaw(bearings):
    """The yaw (0-89) that puts a railing gap nearest every bearing (the worst one counts)."""
    def off(b, y):
        d = (b - y) % 90
        return min(d, 90 - d)
    return min(range(90), key=lambda y: (max(off(b, y) for b in bearings), sum(off(b, y) for b in bearings)))


def gap_point(centre, yaw, toward, inset=0.5):
    """The middle of the platform's railing gap nearest the bearing `toward`, `inset` onto the deck."""
    k = round(((toward - yaw) % 360) / 90) % 4
    g = math.radians(yaw + 90 * k)
    r = PLAT_HALF - inset
    return centre[0] + r * math.sin(g), centre[1] + r * math.cos(g)


# ---------------------------------------------------------------------------- apply
def world(ns):
    """The hook's last stage (make_world.py): the cells as the generators wrote them, and the world."""
    import json
    files = {f: json.loads(f.read_text()) for f in sorted((ST / 'cells').glob('*.cell.json'))}
    before = {f: json.dumps(c) for f, c in files.items()}
    apply({c['id']: c for c in files.values()}, ns['world'])
    for f, c in files.items():
        if json.dumps(c) != before[f]:
            f.write_text(json.dumps(c, indent=1) + '\n')


def apply(cells, world):
    Z = Zone(cells, world)
    Z.clear()
    dirs = world.setdefault('asset_dirs', [])
    for d in ASSET_DIRS:
        if d not in dirs:
            dirs.append(d)
    lod = world.setdefault('lod', {}).setdefault('assets', {})
    for k, v in SHRINE_LOD.items():
        lod.setdefault(k, v)
    courtyard(Z)
    precinct(Z)
    walkway(Z)
    ridge_and_basin(Z)
    fox_grove(Z)
    back_mountain(Z)
    valley_and_pond(Z)
    cemetery(Z)
    forest(Z)


# ---------------------------------------------------------------------------- 3.6 the outer courtyard
def courtyard(Z):
    # the great torii (c2_1), its posts poles as the shrine's (x +-5, 9.9 m). (The race line G8, scenario
    # 417, now comes down on its top beam: DESIGN.md 12.5.)
    ty, tz = 0.6, TORII_Z
    Z.place('torii_great', 'arch_torii_great', (160.0, ty, tz), 'arch_torii_great_col')
    Z.move_entity('pole_torii_w', (155.0, ty, tz), height=9.9)
    Z.move_entity('pole_torii_e', (165.0, ty, tz), height=9.9)
    for (x, z, yaw), side in zip(SIDE_HALLS, 'we'):
        Z.place(f'side_hall_{side}', 'arch_side_hall', (x, 0.6, z), 'arch_side_hall_col', yaw)
    Z.place('chozuya', 'arch_chozuya', (143.0, 0.6, 138.0), 'arch_chozuya_col', 270)
    Z.place('shrine_office', 'arch_shrine_office', (180.0, 0.6, 155.0), 'arch_shrine_office_col', 90)
    Z.place('omikuji', 'arch_omikuji_rack', (175.2, 0.6, 148.6), 'arch_omikuji_rack_col', 90, merge=True)
    Z.place('ema', 'arch_ema_board', (175.2, 0.6, 161.4), 'arch_ema_board_col', 90, merge=True)
    # the komainu: the open-mouthed lion left of the approach as a visitor sees it, the closed one right
    Z.place('komainu_a', 'arch_komainu_a', (152.8, 0.6, 150.0), 'arch_komainu_a_col', merge=True)
    Z.place('komainu_un', 'arch_komainu_un', (167.2, 0.6, 150.0), 'arch_komainu_un_col', merge=True)
    for k, z in enumerate((132, 140, 148)):
        for side, x in (('w', 154.0), ('e', 166.0)):
            Z.place(f'lantern_court_{side}{k}', 'forest_stone_lantern', (x, 0.6, z), 'forest_stone_lantern_col', merge=True)
    # the mossy boulder below the terrace's south-west corner (spec 3.7: where the wall is easy)
    Z.place('boulder_court', 'forest_boulder', (128.0, 164.5), 'self', 30)
    # zelkovas behind the side halls and a shishi-odoshi by the office
    for k, (x, z) in enumerate(((114.0, 131.0), (115.0, 157.0), (205.0, 131.0), (205.5, 158.0))):
        Z.place(f'zelkova_{k}', 'tree_zelkova', (x, z), 'tree_zelkova_col', 40 + 77 * k)
    Z.place('shishi_odoshi', 'shishi_odoshi', (184.6, 0.6, 162.4), 'shishi_odoshi_col', 90, merge=True)
    # coins on the halls' ridges (1 m over the real ridges: side halls 10.9, see 12.5)
    for side, (x, z, _) in zip('we', SIDE_HALLS):
        Z.move_entity(f'core_coin_side_hall_{side}', (x, 0.6 + 10.3 + 1.0, z))
    # the lantern strings: from the kasagi's top (13.1) to the side halls' ridge ends (10.9), and on to the
    # gate's lower roof (its eave 11.9 at the front corners)
    torii = {'w': (155.0, 13.2, TORII_Z), 'e': (165.0, 13.2, TORII_Z)}
    hall = {'w': (128.0, 11.0, 158.6), 'e': (192.0, 11.0, 158.6)}
    gate = {'w': (GATE[0] - 9.0, 12.0, GATE[1] - 3.9), 'e': (GATE[0] + 9.0, 12.0, GATE[1] - 3.9)}
    for side in 'we':
        for kind, a, b in (('torii', torii[side], hall[side]), ('gate', hall[side], gate[side])):
            name = f'core_string_{kind}_{side}'
            Z.paths[name]['points'] = [[R(v) for v in a], [R(v) for v in b]]
            c = a if a[2] >= 128 else b
            Z.move_entity(f'core_rail_string_{kind}_{side}', c)
            for k, f in enumerate((1 / 3, 2 / 3)):
                Z.move_entity(f'core_coin_string_{kind}_{side}_{k}',
                              tuple(a[i] + (b[i] - a[i]) * f + (0.9 if i == 1 else 0) for i in range(3)))


# ---------------------------------------------------------------------------- 3.7 the inner precinct
def precinct(Z):
    gx, gz = GATE
    Z.place('gate', 'arch_gate', (gx, 5.0, gz), 'arch_gate_col')
    Z.move_entity('core_coin_gate', (gx, 5.0 + 12.79 + 1.0, gz))
    for (x, z, yaw), side in zip(CORRIDORS, 'we'):
        Z.place(f'corridor_{side}', 'arch_corridor_hall', (x, 5.0, z), 'arch_corridor_hall_col', yaw)
        Z.move_entity(f'core_coin_corridor_{side}', (x, 5.0 + 9.3 + 1.0, z))
    tx, tz = TEMPLE
    Z.place('temple', 'arch_temple', (tx, 5.0, tz), 'arch_temple_col')
    Z.move_entity('core_coin_temple', (tx, 5.0 + 22.54 + 1.0, tz))
    Z.place('bell_pavilion', 'bell_pavilion', (204.0, 5.0, 226.0), 'bell_pavilion_col', 90)
    for k, (x, z) in enumerate([(152, 184), (168, 184), (152, 196), (168, 196)]):
        Z.place(f'lantern_terr{k}', 'forest_stone_lantern', (x, 5.0, z), 'forest_stone_lantern_col', merge=True)
    Z.place('omikuji_terr', 'arch_omikuji_rack', (180.0, 5.0, 202.5), 'arch_omikuji_rack_col', 0, merge=True)

    # the temple stands on its own podium: the grey box's terrain podium goes (its ground set to the
    # terrace), and so do its stair (the temple's own) and the podium's paint
    ops = Z.ops()
    temple = [134, 208, 186, 228]
    terr = [114, 166, 214, 234]
    keep = []
    for o in ops:
        rect = o.get('area', {}).get('rect')
        if rect == temple and o['op'] in ('cliff', 'paint'):
            continue
        if rect == temple and o['op'] == 'set':
            o = dict(o, height=5.0)
        if rect == terr:
            o = dict(o, area={'rect': [114, 166, 214, TERR_Z1]})
        keep.append(o)
    ops[:] = keep
    Z.paths.pop('core_temple_stair', None)

    # the white wall: 8 m and 4 m modules from corner to gate, corner posts; the north run on a 1 m
    # plinth (top 3.6 m over the terrace: decision #5); the west, east and north gates in it
    def run(a, b, fixed, axis, raised=False):
        """Modules along x (axis 'x', at z = fixed) or z from a to b (a < b), 8 m then a 4 m."""
        pos, out = a, []
        while b - pos >= 8 - 1e-6:
            out.append((pos + 4, 8)); pos += 8
        if b - pos >= 4 - 1e-6:
            out.append((pos + 2, 4)); pos += 4
        assert abs(b - pos) < 1e-6, (a, b, fixed, axis)
        for c, size in out:
            x, z = (c, fixed) if axis == 'x' else (fixed, c)
            yaw = None if axis == 'x' else 90
            y = 6.0 if raised else 5.0
            nm = f'wall_{axis}{int(fixed)}_{int(c * 10)}'
            Z.place(nm, f'arch_wall_{size}', (x, y, z), f'arch_wall_{size}_col', yaw)
            if raised:
                Z.place(nm + '_plinth', f'shrine_wall_plinth_{size}', (x, 5.0, z), f'shrine_wall_plinth_{size}_col', yaw,
                        merge=True)
        return out
    e = 0.4                                          # a module's end sits 0.4 m past its corner post's centre
    run(WX0 + e, gx - 10, WZ0, 'x'); run(gx + 10, WX1 - e, WZ0, 'x')
    run(WX0 + e, GATE_N_X - 4, WZ1, 'x', True); run(GATE_N_X + 4, WX1 - e, WZ1, 'x', True)
    run(WZ0 + e, GATE_W_Z - 4, WX0, 'z'); run(GATE_W_Z + 4, WZ1 - e, WX0, 'z')
    run(WZ0 + e, GATE_E_Z - 4, WX1, 'z'); run(GATE_E_Z + 4, WZ1 - e, WX1, 'z')
    for k, (x, z) in enumerate(((WX0, WZ0), (WX1, WZ0), (WX0, WZ1), (WX1, WZ1))):
        north = z == WZ1
        Z.place(f'wall_corner_{k}', 'arch_wall_corner', (x, 6.0 if north else 5.0, z), 'arch_wall_corner_col', merge=True)
        if north:
            Z.place(f'wall_corner_{k}_plinth', 'shrine_wall_plinth_corner', (x, 5.0, z), 'shrine_wall_plinth_corner_col',
                    merge=True)
    Z.place('gate_w', 'arch_wall_gate', (WX0, 5.0, GATE_W_Z), 'arch_wall_gate_col', 90)
    Z.place('gate_e', 'arch_wall_gate', (WX1, 5.0, GATE_E_Z), 'arch_wall_gate_col', 270)
    # the north gate, shortcut B: shut and barred on the ridge side (layer gate_b_barred, on), open with the
    # bar set down (gate_b_open). The gate's -Z (outside) faces north; the bar's +Z is the ridge side.
    gn = (GATE_N_X, 5.0, WZ1)
    Z.place('gate_n_shut', 'arch_wall_gate_shut', gn, 'arch_wall_gate_shut_col', 180, layer='gate_b_barred')
    Z.place('gate_n_open', 'arch_wall_gate', gn, 'arch_wall_gate_col', 180, layer='gate_b_open')
    bar = (GATE_N_X, 5.0, WZ1 + 0.15)
    Z.place('gate_n_bar', 'arch_wall_gate_bar', bar, 'arch_wall_gate_bar_col', layer='gate_b_barred')
    Z.place('gate_n_bar_down', 'arch_wall_gate_bar_lifted', bar, 'none', layer='gate_b_open')
    # the stairs to the west and east gates end at the terrace's edge, as before; the north stair starts
    # outside the north gate and climbs to the pagoda's terrace (15)
    Z.paths['core_north_stair']['points'] = [[GATE_N_X, 5.0, TERR_Z1 - 0.1], [174.0, L.PAG_BASE, 256.5]]
    # the mossy boulders below the terrace's west edge (where the wall is easy, spec 3.7)
    Z.place('boulder_w0', 'forest_boulder_big', (110.5, 184.0), 'self', 20)
    Z.place('boulder_w1', 'forest_boulder_big', (110.5, 214.0), 'self', 200)


# ---------------------------------------------------------------------------- 3.9 the treetop walkway
def walkway(Z):
    decks = [(x, z, h) for x, z, h in DECKS]
    # each deck's neighbours (bridges): index pairs, and the foot and crown bridges' far ends
    links = {i: [] for i in range(len(decks))}
    for i in range(len(decks) - 1):
        links[i].append(decks[i + 1][:2]); links[i + 1].append(decks[i][:2])
    links[0].append((97.5, 137.0))                          # the foot bridge, down to the walkway's stair
    links[2].append(LANDING[:2])                            # the crown's landing
    yaws = {}
    for i, (x, z, h) in enumerate(decks):
        yaws[i] = platform_yaw([bearing(px - x, pz - z) for px, pz in links[i]]
                               + ([bearing(L.KNOT[0] - x, L.KNOT[1] - z)] if i == 6 else []))
    for i, (x, z, h) in enumerate(decks):
        tag = 'rope' if i == 6 else str(i)
        Z.place(f'deck_tree_{tag}', 'tree_cedar_giant', (x, z), 'tree_cedar_giant_col', 37 * i)
        Z.place(f'deck_{tag}', 'forest_platform', (x, h, z), 'forest_platform_col', yaws[i])
    # the crown deck and its landing, on one cedar; the landing's railing gap faces deck 3
    cx, cz, ch = CROWN
    Z.place('deck_tree_crown', 'tree_cedar_giant', (cx, cz), 'tree_cedar_giant_col', 250)
    Z.place('deck_crown', 'forest_platform', (cx, ch, cz), 'forest_platform_col', 0)
    Z.move_entity('core_coin_crown', (cx + 1.5, ch + 1.0, cz + 1.5))
    land_yaw = platform_yaw([bearing(decks[2][0] - cx, decks[2][1] - cz)])
    Z.place('deck_crown_landing', 'forest_platform', (cx, LANDING[2], cz), 'forest_platform_col', land_yaw)

    def ends(i, j):
        (ax, az, ah), (bx, bz, bh) = decks[i], decks[j]
        pa = gap_point((ax, az), yaws[i], bearing(bx - ax, bz - az))
        pb = gap_point((bx, bz), yaws[j], bearing(ax - bx, az - bz))
        return (pa[0], ah - 0.04, pa[1]), (pb[0], bh - 0.04, pb[1])
    for i in range(5):                                       # core_walkway_12 .. 56
        a, b = ends(i, i + 1)
        Z.paths[f'core_walkway_{i + 1}{i + 2}']['points'] = plank_bridge(a, b)
    # deck 6 to the rope deck (the mountain's, with hand ropes)
    a, b = ends(5, 6)
    pts = plank_bridge(a, b, sag=0.5)
    Z.paths['bridge_deck6_rope']['points'] = pts
    dx, dz = b[0] - a[0], b[2] - a[2]
    d = math.hypot(dx, dz); nx, nz = dz / d, -dx / d
    for side, s in (('l', -1), ('r', 1)):
        Z.paths[f'bridge_deck6_rope_{side}']['points'] = [
            [R(p[0] + s * 0.85 * nx), R(p[1] + 1.0 + 0.4 * abs(k / 4 - 0.5) * 2), R(p[2] + s * 0.85 * nz)]
            for k, p in enumerate(pts)]
    # deck 1 down to the walkway's stair (its other points as before)
    x, z, h = decks[0]
    p = gap_point((x, z), yaws[0], bearing(97.5 - x, 137.0 - z))
    Z.paths['core_walkway_foot']['points'][0] = [R(p[0]), h - 0.04, R(p[1])]
    # deck 3 to the crown's landing
    x, z, h = decks[2]
    pa = gap_point((x, z), yaws[2], bearing(cx - x, cz - z))
    pb = gap_point((cx, cz), land_yaw, bearing(x - cx, z - cz))
    Z.paths['core_walkway_crown']['points'] = [[R(pa[0]), h - 0.04, R(pa[1])], [R(pb[0]), LANDING[2] - 0.04, R(pb[1])]]


# ---------------------------------------------------------------------------- 3.8 the ridge, 3.10 the basin
def ridge_and_basin(Z):
    px, pz = L.PAGODA
    Z.place('pagoda', 'arch_pagoda', (px, L.PAG_BASE, pz), 'arch_pagoda_town_col')
    # the stone lantern in front of its south face: the step to roof 1, its top at 16.4 as before
    # (forest_stone_lantern is 1.85 to its cap in collision: sunk 0.45)
    Z.place('pagoda_lantern', 'forest_stone_lantern', (178.0, L.PAG_BASE - 0.45, 255.5), 'forest_stone_lantern_col')
    # the kick pair: the shrine's giant cedars drawn where the grey box's trunks stand, which stay their
    # collision (two flat faces 3.2 m apart, scenario 420)
    kx = px - L.PAG_EAVES[1] - 1.05 - 0.9
    for k, kz in enumerate((259.5, 264.5)):
        Z.place(f'kick_cedar_{k}', 'tree_cedar_giant', (kx, kz), f'gbm_cedar_kick_{k}_col', 90 + 90 * k)   # square turns: the faces stay on x and z

    # the hollow sacred cedar, its knot hole (-Z) turned to the rope deck; the root curtain in its door;
    # the rope (rail cedar_rope) from the rope deck ends 0.5 m into the hole's mouth, 1.75 over its sill
    cx, cy, cz = CEDAR
    yaw = CEDAR_YAW
    Z.place('sacred_cedar', 'tree_cedar_sacred_hollow', (cx, cy, cz), 'tree_cedar_sacred_hollow_col', yaw)
    dx, dz = rot(0.0, -2.75, yaw)
    Z.place('root_curtain', 'forest_root_curtain', (cx + dx, cy, cz + dz), 'forest_root_curtain_col', yaw,
            layer='root_d_shut')
    hx, hz = rot(0.0, -2.8, yaw)
    rope = Z.paths['cedar_rope']['points']
    rope[1] = [R(cx + hx), R(cy + 8.5 + 1.75), R(cz + hz)]
    a, b = rope
    ry = bearing(b[0] - a[0], b[2] - a[2])
    ox, oz = rot(0.0, -12.0, ry)
    Z.place('shide_rope', 'forest_shide_rope', (b[0] + ox * 1, b[1] - 1.4, b[2] + oz * 1), 'none', ry)

    # the hollow log beside the trail from the basin to the falls pool
    Z.place('hollow_log', 'forest_hollow_log', (191.0, 305.0), 'forest_hollow_log_col', 352)
    # rope ladder A: down (ladder_a) and rolled up on the ledge's lip (ladder_a_up, on at the start)
    la = (154.0, 24.0, 317.85)
    Z.place('ladder_a', 'forest_rope_ladder', la, 'forest_rope_ladder_col', layer='ladder_a')
    Z.place('ladder_a_up', 'forest_rope_ladder_rolled', la, 'forest_rope_ladder_rolled_col', layer='ladder_a_up')
    Z.world['layers']['ladder_a'] = {'group': 'ladder_a'}
    Z.world['layers']['ladder_a_up'] = {'group': 'ladder_a', 'on': True}


# ---------------------------------------------------------------------------- 3.11 the fox grove and tunnel
def fox_grove(Z):
    fx, fz = 84.0, 307.0
    Z.place('fox_shrine', 'forest_fox_shrine', (fx, fz), 'forest_fox_shrine_col',
            bearing(L.FOX[0] - fx, L.FOX[1] - fz) + 180)
    for k, (sx, sz) in enumerate(((91.2, 298.6), (96.8, 298.6))):
        Z.place(f'fox_statue_{k}', 'forest_fox_statue', (sx, sz), 'forest_fox_statue_col', 0, merge=True)
    # the senbon torii: the grey box's frames' places (make_mountain.py), the shrine's torii drawn. Their
    # collision is the grey frames' (gbm_fox_torii: posts 2.9 m apart, the beam's top at 3.6): the
    # shrine's own puts the posts 2.5 m apart, inside the steps' 3 m, and the walking route down the
    # tunnel (scenario 454) caught on them at the switchbacks
    pts = Z.paths['torii_steps']['points']
    n = 0
    for a, b in zip(pts, pts[1:]):
        seg = math.hypot(b[0] - a[0], b[2] - a[2])
        yaw = math.degrees(math.atan2(b[0] - a[0], b[2] - a[2]))
        d = 1.6
        while d < seg - 1.6:
            t = d / seg
            n += 1
            Z.place(f'torii_{n:02d}', 'forest_fox_torii', (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t,
                                                          a[2] + (b[2] - a[2]) * t), 'gbm_fox_torii', yaw)
            d += 1.4
    # a hokora where the trail from the road reaches the grove
    Z.place('hokora_fox', 'hokora', (86.0, 289.5), 'hokora_col', 60, merge=True)


# ---------------------------------------------------------------------------- 3.12 the back mountain
def back_mountain(Z):
    sx, sy, sz = STAGE
    Z.place('stage', 'forest_stage_hall', STAGE, 'forest_stage_hall_col')
    # its pad: under the deck's back and the hall, below the deck (the grey box's pad was at the deck's 60)
    for o in Z.ops():
        if o['op'] == 'set' and o.get('area', {}).get('rect') == [138, 354, 170, 377]:
            o['height'] = sy - 0.5
    # the bell under the hall's front eave (underside 4.35): its beam's top there, the pull rope 2.85 m in
    # front of the hall's wall (game.py's BELL: the rope's trigger and star 3 in front of it)
    bell = (sx, sy + 0.8, sz - 1.0)
    Z.place('stage_bell', 'forest_stage_bell', bell, 'forest_stage_bell_col')
    # the stilt ladder from the ledge (44) over the deck's front railing (61): the pole and its look
    front = sz - 10.0
    Z.move_entity('pole_stage_front', (sx, 44.0, front - 0.6), height=18.3)
    Z.place('stilt_ladder', 'shrine_stilt_ladder', (sx, 44.0, front - 0.45), 'none')
    # the stairs from the torii landing and the rope bridge from the falls arrive at the side railings' gaps
    gz = sz - 5.0
    st = Z.paths['landing_stair']['points']
    st[-1] = [R(sx - 16.0 + 0.4), R(sy - 0.1), R(gz)]
    st[-2] = [126.0, 54.5, R(gz - 0.6)]
    br = Z.paths['bridge_falls_stage']['points']
    a, b = (sx + 16.0 - 0.4, sy - 0.08, gz), tuple(br[-1])
    n = len(br)
    for k in range(n):
        f = k / (n - 1)
        br[k] = [R(a[0] + (b[0] - a[0]) * f), R(a[1] + (b[1] - a[1]) * f - 1.0 * 4 * f * (1 - f)), R(a[2] + (b[2] - a[2]) * f)]
    dx, dz = b[0] - a[0], b[2] - a[2]
    d = math.hypot(dx, dz); nx, nz = dz / d, -dx / d
    for side, s in (('l', -1), ('r', 1)):
        Z.paths[f'bridge_falls_stage_{side}']['points'] = [
            [R(p[0] + s * 0.85 * nx), R(p[1] + 1.0 + 0.4 * abs(k / (n - 1) - 0.5) * 2), R(p[2] + s * 0.85 * nz)]
            for k, p in enumerate(br)]

    # the falls: the shrine's water_falls, forest_falls_cave behind it and the rock it falls from; the
    # stream above the lip runs down into the notch the water pours over; the cave's coins move into it
    Z.place('falls', 'water_falls', FALLS, 'none')
    Z.place('falls_cave', 'forest_falls_cave', FALLS, 'forest_falls_cave_col')
    Z.place('falls_cliff', 'shrine_falls_cliff', FALLS, 'shrine_falls_cliff_col')
    Z.paths.pop('falls_sheet', None)
    up = Z.paths['stream_upper']['points']
    up[-1] = [214.0, 48.45, 337.2]
    up.append([214.0, 46.3, 336.5])
    up.append([214.0, 46.3, FALLS[2] + 1.2])
    for k in range(6):
        Z.move_entity(f'coin_cave_{k + 1}', (209.6 + 2.2 * (k % 3) + (k // 3) * 1.1, 15.0, 332.2 + 2.4 * (k // 3)))
    # the way out north-east: a small torii and a jizo by it
    Z.place('path_out_torii', 'forest_fox_torii', (252.0, 378.0), 'forest_fox_torii_col', 20)
    Z.place('path_out_jizo', 'jizo', (255.2, 376.6), 'jizo_col', 200, merge=True)
    # the dead cedar of shortcut C, standing and fallen (one origin, -Z across the gorge)
    Z.place('dead_cedar_up', 'forest_dead_cedar', DEAD_CEDAR, 'forest_dead_cedar_col', DEAD_CEDAR_YAW, layer='cedar_c_up')
    Z.place('dead_cedar_down', 'forest_dead_cedar_fallen', DEAD_CEDAR, 'forest_dead_cedar_fallen_col', DEAD_CEDAR_YAW,
            layer='cedar_c_down')


# ---------------------------------------------------------------------------- 3.13 the pond
def valley_and_pond(Z):
    stones = ('water_stepping_stone_a', 'water_stepping_stone_b', 'water_stepping_stone_c')
    # the grey box's stones (gen_core.py), the shrine's stepping stones: their tops at 0.3 as before
    seen, k = set(), 0
    for (ax, az), (bx, bz) in [((226, 129), (232, 150)), ((232, 150), (236, 179))]:
        n = int(math.hypot(bx - ax, bz - az) // 3.6)
        for i in range(n + 1):
            x, z = round(ax + (bx - ax) * i / n, 1), round(az + (bz - az) * i / n, 1)
            if L.height(x, z) < -0.6 and (x, z) not in seen:
                seen.add((x, z))
                s = stones[k % 3]
                Z.place(f'pond_stone_{k}', s, (x, -1.3, z), s + '_col', 47 * k)
                k += 1
    # lily pads and koi
    for i, (x, z) in enumerate(((228.5, 158.0), (240.5, 171.0), (243.0, 136.0), (229.5, 176.5), (244.5, 160.5))):
        Z.place(f'lily_{i}', 'water_lily_pad_flower' if i % 2 else 'water_lily_pad', (x, 0.0, z), 'none', 70 * i, merge=True)
    for i, (x, z, yaw) in enumerate(((237.0, 146.0, 30), (239.5, 150.0, 200), (233.0, 168.0, 110),
                                     (238.0, 172.5, 300), (241.5, 140.5, 160))):
        Z.place(f'koi_{i}', 'life_koi', (x, -0.5, z), 'none', yaw, merge=True)


# ---------------------------------------------------------------------------- 3.14 the cemetery
def cemetery(Z):
    for t in range(1, 10):                     # terrace t's front edge, from terrace t - 1 (or the lane)
        ze, lo = CEM_Z0 + 12 * (t - 1), 1.8 * (t - 1)
        for x in WALL_XS:
            Z.place(f'cem_wall_{t}_{int(x)}', 'cemetery_terrace_wall_12', (x, lo, ze - 0.5),
                    'cemetery_terrace_wall_12_col', merge=True)
        # the graves: a line of rows 5.5 m behind the edge, facing down the hill, with a sotoba rack
        h = 1.8 * t
        for j, x in enumerate(GRAVE_XS):
            xx = x + (1.0 if (t + j) % 2 else -1.0) * (t % 3 == 0)
            Z.place(f'graves_{t}_{j}', 'cemetery_grave_row', (xx, h, ze + 5.5), 'cemetery_grave_row_col', merge=True)
        sx = GRAVE_XS[t % 4] + (2.0 if t % 2 else -2.0)
        Z.place(f'sotoba_{t}', 'cemetery_sotoba_rack', (sx, h, ze + 6.75), 'cemetery_sotoba_rack_col', merge=True)
    # the middle stair: a flight 12 m wide at each terrace's edge (between the walls), the first from the
    # lane (the grey box had none: FOLLOWUPS)
    wide = [[-6.0, -2.4], [-6.0, 0], [6.0, 0], [6.0, -2.4], [-6.0, -2.4]]
    for t in range(1, 9):
        Z.paths[f'core_cem_stair_{t}']['sweep']['profile'] = wide
    Z.path('core_cem_stair_0', {'points': [[286.0, 0.3, 126.4], [286.0, 1.8, 130.0]],
                                'sweep': {'profile': wide, 'materials': ['steps'] * 4, 'stairs': {'rise': 0.3},
                                          'caps': True}})
    Z.place('cem_gate', 'cemetery_gate', CEM_GATE, 'cemetery_gate_col')
    Z.place('cem_jizo', 'jizo', (293.4, 1.8, 132.2), 'jizo_col', 340, merge=True)
    Z.place('jizo_hall', 'cemetery_jizo_hall', (299.0, 16.2, 241.0), 'cemetery_jizo_hall_col')
    for k, (x, z) in enumerate(((253.0, 133.0), (252.5, 166.0))):
        Z.place(f'cem_zelkova_{k}', 'tree_zelkova', (x, z), 'tree_zelkova_col', 120 + 90 * k)


# ---------------------------------------------------------------------------- the forest
def forest(Z):
    sc = Z.world['scatter']
    low = [{'asset': 'tree_maple', 'weight': 4, 'collision': 'tree_maple_col'},
           {'asset': 'tree_maple_small', 'weight': 2, 'collision': 'tree_maple_small_col'},
           {'asset': 'tree_ginkgo', 'weight': 2, 'collision': 'tree_ginkgo_col'},
           {'asset': 'tree_cedar', 'weight': 3, 'collision': 'tree_cedar_col'}]
    high = [{'asset': 'tree_cedar', 'weight': 5, 'collision': 'tree_cedar_col'},
            {'asset': 'tree_maple', 'weight': 2, 'collision': 'tree_maple_col'},
            {'asset': 'tree_ginkgo', 'weight': 1, 'collision': 'tree_ginkgo_col'}]
    sc['core_woods']['assets'] = low
    sc['core_valley']['assets'] = low
    sc['mountain_forest']['assets'] = high
    # the real trees cost more to draw than the grey ones (textured cards): a little sparser than the grey
    # box's forest (fill 0.8, thinned from 56 m), thinned from 44 m
    for name in ('core_woods', 'core_valley', 'mountain_forest'):
        sc[name]['thin'] = {'distance': 44, 'keep': 0.5, 'scale': 1.2}
        sc[name]['fill'] = 0.68
    # undergrowth and leaf litter (as the shrine's), where the trees are, the zone's part of them
    excl = []
    for name in ('core_woods', 'core_valley', 'mountain_forest'):
        excl += sc[name].get('exclude', [])
    excl = [e for e in excl if e != {'rect': [0, 256, 46, 384]}] + [{'rect': [0, 0, 64, 384]}]
    seen, uniq = set(), []
    for e in excl:
        k = repr(e)
        if k not in seen:
            seen.add(k); uniq.append(e)
    area = {'rect': [64, 128, 318, 380]}
    sc['shrine_undergrowth'] = {
        'assets': [{'asset': 'plant_fern', 'weight': 3}, {'asset': 'plant_sasa', 'weight': 4},
                   {'asset': 'plant_shrub', 'weight': 2}, {'asset': 'plant_susuki', 'weight': 2}],
        'area': area, 'spacing': 5, 'fill': 0.3, 'seed': 59, 'lift': -0.05, 'exclude': uniq[:256],
        'clearance': 1.0, 'max_slope': 30, 'chunk': 16, 'cull': 36, 'lod': 'assets'}
    sc['shrine_litter'] = {
        'assets': [{'asset': 'litter_red', 'weight': 3}, {'asset': 'litter_gold', 'weight': 2}],
        'area': area, 'spacing': 7, 'fill': 0.5, 'seed': 61, 'exclude': uniq[:256],
        'clearance': 0.5, 'max_slope': 8, 'chunk': 16, 'cull': 24, 'lod': 'assets'}
    # reeds round the pond's banks
    sc['shrine_reeds'] = {
        'assets': [{'asset': 'water_reeds'}], 'area': {'rect': [216, 128, 254, 184]}, 'spacing': 3, 'fill': 0.45,
        'seed': 67, 'exclude': [{'circle': [x, z, r * 0.8]} for x, z, r in L.POND] + [{'rect': [212, 150, 228, 196]}],
        'clearance': 0.5, 'max_slope': 30, 'chunk': 16, 'cull': 40, 'lod': 'assets'}
