"""The World Checker: in-level verification of a world pack (docs/WORLDCHECKER.md).

    from worldkit.verify import verify
    report = verify(pack_bytes, settings={'mode': 'report'}, out_dir='build/city-check')
    report['ok']            # False only for hard failures, or threshold failures in strict mode

Or from the command line (JSON on stdout, exit 0 or 1):

    python3 tools/worldkit/verify.py city.world.bin [-o DIR] [--settings FILE] [--strict]

Three groups of checks, all from the pack alone (plus optional names for reports):

1. Static: collision cracks and mismatched floor edges (inside cells and across seams),
   entities inside solid collision, references (face indices, stand-ins, layers), and per-cell
   and per-region counts against budgets.
2. Sampled views on the real runtime (stdlib/worldpack.akr on the headless core): cameras on
   walkable floors at eye height and behind a follow camera, on each cell's highest floors, in
   the air between rooftops, aimed at each entity that has a mesh, at authored vantage points and
   on cell seams, for each layer combination; CPU and GPU cycles, triangles submitted and
   dropped, packet arena use.
3. Ordering: each view's triangle-ID picture against an independent reference that resolves
   true depth (verify_render.py), with the reader's passes (far stand-ins, ground, near) kept
   apart as the reader draws them; in depth mode (runtime depth: the game draws with the depth
   buffer) one pass, a regression check of the depth test, on a sample of the views
   (ordering.depth_views, ordering_sample()) while the budgets are measured on every view.

Hard failures in every mode: dropped triangles, a full packet arena, static collision errors
and broken references. Thresholds (budgets, wrong-order pixels, stand-ins) fail the check only
in strict mode; in report mode (the default) they are reported.
"""
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = 'worldkit'

from .pack import decode, PackError, ONE, KIND_FLOOR, KIND_CEILING  # noqa: E402
from . import verify_static as ST  # noqa: E402
from . import verify_render as RD  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SCREEN = RD.W * RD.H

DEFAULTS = {
    'mode': 'report',                   # 'report' (never fails on thresholds) or 'strict'
    'probe': {'radius': 0.3, 'height': 1.6, 'step': 0.32, 'bridge': 0.0},   # the game schema's probe
    'eye_height': 1.5,
    'thresholds': {
        'near_band': 16.0,              # units: wrong-order pixels nearer than this, or on entities...
        'near_wrong_pixels': 0,         # ...allowed per view
        'far_wrong_fraction': 0.005,    # of the screen, per view, elsewhere
        'coverage_pixels': 0,           # pixels the runtime drew differently from the reference
        'ground_inversion_pixels': 0,   # per view: pixels where ground truly hides what is drawn over it
        'gpu_cycles': 1600000,          # per view (80% of 2,000,000)
        'draw_cpu_cycles': 600000,      # wp_draw() plus entity meshes per view (60% of 1,000,000)
        'view_triangles': 4000,         # triangles submitted per view (WORLDKIT.md, "A frame budget")
        'cell_triangles': 1600,
        'cell_placements': 100,
        'standin_triangles': 32,
        'occlusion_leaks': 0,           # rays from an occlusion zone that reach what it hides (pack 1.5)
    },
    'sampling': {
        'floor_spacing': 16.0,          # grid over each cell's walkable floors (units)
        'yaws': 8,                      # directions per position
        'yaw_offset_degrees': 22.5,
        'eye_pitches_degrees': [0.0],
        'follow': {'distance': 6.0, 'height': 2.5},     # None: no follow cameras
        'rooftops_per_cell': 2,
        'roof_pitches_degrees': [-20.0],
        'air': {'height': 4.0, 'reach': 48.0},           # None: no cameras between rooftops
        'seams': {'spacing': 32.0},                      # None: no seam cameras
        'entities': {'yaws': 6, 'distances': [1.5, 4.0, 8.0], 'pitches_degrees': [-55.0, -30.0, -10.0],
                     'floor_distances': [2.5, 6.0]},     # None: no cameras aimed at entities
        'layer_combinations': True,
        'max_views': 600,
    },
    'vantage_points': [],               # {"position": [x, y, z], "yaw": deg, "pitch": deg, "yaws": n, "name": s}
    'runtime': {'far_ring': 3, 'clip_near': 0.1, 'near_far': None, 'draw_entities': True, 'ground_first': True,
                'entity_drawing': 'object', 'object_bias': 1.5, 'object_squash': 2, 'lod': True, 'lod_fine': True,
                'depth': False, 'perspective': False,      # render_depth(), render_perspective()
                'occlusion': True},                        # wp_occlusion: the pack's occlusion zones (1.5)
    'ordering': {'enabled': True, 'edge_margin': 1.0, 'depth_epsilon': 0.001, 'witnesses': 8,
                 'depth_views': 60},        # depth mode: views given the pixel comparison (None: all)
    'collision': {'crack_samples_per_unit': 4.0, 'solid_ray_length': 32.0, 'findings': 50,
                  'crack_baseline': None,       # the cracks of NAME.cracks.json: known, not failures
                  # bodies dropped onto steep ground (verify_static.drop_check); None: no drops
                  'drop': {'spacing': 1.0, 'start': 1.0, 'speed': 0.375, 'ticks': 240, 'min_normal_y': 0.2,
                           'merge': 4.0}},
    'occlusion': {'enabled': True, 'rays_per_target': 48, 'findings': 20},   # pack 1.5's zones
    'images': 6,
}


class SettingsError(ValueError):
    def __init__(self, path, message):
        super().__init__(f'{path}: {message}')
        self.path = path


def merge_settings(settings):
    """DEFAULTS overridden by `settings`, with unknown keys refused."""
    out = copy.deepcopy(DEFAULTS)

    def walk(dst, src, path):
        if not isinstance(src, dict):
            raise SettingsError(path or '/', 'expected an object')
        for k, v in src.items():
            if k not in dst:
                raise SettingsError(f'{path}/{k}', 'unknown setting')
            if isinstance(dst[k], dict) and v is not None:
                walk(dst[k], v, f'{path}/{k}')
            else:
                dst[k] = copy.deepcopy(v)
    walk(out, settings or {}, '')
    if out['mode'] not in ('report', 'strict'):
        raise SettingsError('/mode', "must be 'report' or 'strict'")
    if out['runtime']['entity_drawing'] not in ('object', 'mesh_at'):
        raise SettingsError('/runtime/entity_drawing', "must be 'object' or 'mesh_at'")
    for k in ('depth', 'perspective'):
        if not isinstance(out['runtime'][k], bool):
            raise SettingsError(f'/runtime/{k}', 'must be true or false')
    n = out['ordering']['depth_views']
    if n is not None and (isinstance(n, bool) or not isinstance(n, int) or n < 1):
        raise SettingsError('/ordering/depth_views', 'must be a positive whole number or null')
    # Depth mode: the cameras aimed at entities look for what the ordering table gets wrong
    # around small objects, which the depth test does not; they are off unless asked for.
    if out['runtime']['depth'] and 'entities' not in ((settings or {}).get('sampling') or {}):
        out['sampling']['entities'] = None
    return out


def shown_settings(cfg):
    """The settings as the report lists them: runtime depth and perspective only when either is
    on, and ordering depth_views only in depth mode, so that a report without them is the one the
    checker made before they existed."""
    out = copy.deepcopy(cfg)
    if not cfg['probe'].get('bridge'):
        del out['probe']['bridge']
    if cfg['collision']['crack_baseline'] is None:
        del out['collision']['crack_baseline']
    else:
        out['collision']['crack_baseline'] = len(cfg['collision']['crack_baseline'])
    if not (cfg['runtime']['depth'] or cfg['runtime']['perspective']):
        del out['runtime']['depth'], out['runtime']['perspective']
    if cfg['runtime']['occlusion'] is True:
        del out['runtime']['occlusion']
    if not cfg['runtime']['depth']:
        del out['ordering']['depth_views']
    return out


def default_tools():
    return {'compiler': Path(os.environ.get('MEIC', ROOT / 'build/meic')),
            'probe': Path(os.environ.get('SCENE_PROBE', ROOT / 'build/mei-scene-probe'))}


# ---- sampling cameras

def _floor_at(floors, x, z):
    """Heights of the floors over (x, z) (float point-in-triangle on the stored rows)."""
    out = []
    for t in floors:
        if t.verts is None:
            continue
        vs = t.verts
        if not (min(v[0] for v in vs) - 1e-6 <= x <= max(v[0] for v in vs) + 1e-6 and
                min(v[2] for v in vs) - 1e-6 <= z <= max(v[2] for v in vs) + 1e-6):
            continue
        if all(e[0] * x + e[1] * z + e[2] >= -1e-9 for e in ((r[0] / ONE, r[1] / ONE, r[2] / ONE) for r in t.rows[1])):
            out.append((ST._height(t, x, z), t))
    return out


def _standing(floors, ceilings, x, z, room, grid=None, radius=0.0):
    """Distinct floor heights at (x, z) with `room` units clear above them and, given a grid
    of collision, no wall within `radius` (where a body cannot stand)."""
    hs = sorted(_floor_at(floors, x, z), key=lambda h: h[0])
    cs = sorted(h for h, _ in _floor_at(ceilings, x, z))
    out = []
    for k, (h, t) in enumerate(hs):
        if out and abs(out[-1][0] - h) < 0.25:
            continue
        above = [g for g, _ in hs[k + 1:] if g > h + 0.05] + [g for g in cs if g > h + 0.05]
        if above and min(above) < h + room:
            continue
        if grid is not None and radius > 0 and not _clear(grid, x, h, z, room, radius):
            continue
        out.append((h, t))
    return out


def _clear(grid, x, h, z, room, radius):
    for y in (h + 0.1, h + room / 2, h + room * 0.95):
        for k in range(8):
            a = 2 * math.pi * (k + 0.5) / 8
            if ST.first_hit(grid, (x, y, z), (math.sin(a) * radius, 0.0, math.cos(a) * radius)) is not None:
                return False
    return True


def sample_views(pack, tris, settings, only=None):
    """Cameras: dicts with kind, eye, yaw, pitch (radians), cell. only: a set of cells (i, j):
    the cameras sampled from those cells and whose eye is in one of them (the quick check's
    focus; vantage points are always kept), or None for every cell."""
    smp = settings['sampling']
    S = 1 << pack.cell_shift
    floors = [t for t in tris if t.kind == KIND_FLOOR]
    ceilings = [t for t in tris if t.kind == KIND_CEILING]
    grid = ST.TriGrid(tris)
    probe = settings['probe']
    room = (grid, probe['radius'])
    eye_h = settings['eye_height']
    yaws = [math.radians(smp['yaw_offset_degrees']) + 2 * math.pi * k / max(1, smp['yaws'])
            for k in range(max(1, smp['yaws']))]
    views = []

    def add(kind, eye, yaw, pitch, extra=None):
        v = {'kind': kind, 'eye': [round(c, 4) for c in eye], 'yaw': round(yaw, 6), 'pitch': round(pitch, 6)}
        if extra:
            v.update(extra)
        views.append(v)

    every = cells = sorted(pack.cells, key=lambda ij: (ij[1], ij[0]))
    if only is not None:
        cells = [c for c in cells if c in only]
    sp = smp['floor_spacing']
    n = max(1, int(round(S / sp))) if sp else 0
    follow = smp.get('follow')
    for (i, j) in cells if n else ():
        for gz in range(n):
            for gx in range(n):
                x, z = i * S + (gx + 0.5) * S / n, j * S + (gz + 0.5) * S / n
                for h, t in _standing(floors, ceilings, x, z, probe['height'], *room):
                    head = (x, h + eye_h, z)
                    for yaw in yaws:
                        for pd in smp['eye_pitches_degrees']:
                            add('eye', head, yaw, math.radians(pd))
                        if follow:
                            add('follow', _follow(grid, head, yaw, follow), yaw,
                                -math.atan2(follow['height'], follow['distance']))
    # rooftops: each cell's highest floors with room to stand
    roofs = []
    for (i, j) in cells if smp['rooftops_per_cell'] > 0 else ():
        mine = [t for t in floors if t.verts is not None and
                (math.floor(sum(v[0] for v in t.verts) / 3 / S),
                 math.floor(sum(v[2] for v in t.verts) / 3 / S)) == (i, j)]
        mine.sort(key=lambda t: (-sum(v[1] for v in t.verts) / 3, t.tag, t.rows))
        picked = []
        for t in mine:
            cx, cz = sum(v[0] for v in t.verts) / 3, sum(v[2] for v in t.verts) / 3
            if any(t.tag == p[3] or math.hypot(cx - p[0], cz - p[2]) < 4 for p in picked):
                continue
            stand = _standing(floors, ceilings, cx, cz, probe['height'], *room)
            if not any(abs(h - ST._height(t, cx, cz)) < 1e-6 for h, _ in stand):
                continue
            picked.append((cx, ST._height(t, cx, cz), cz, t.tag))
            if len(picked) >= smp['rooftops_per_cell']:
                break
        for cx, h, cz, _ in picked:
            roofs.append((cx, h, cz))
            for yaw in yaws:
                for pd in smp['roof_pitches_degrees']:
                    add('rooftop', (cx, h + eye_h, cz), yaw, math.radians(pd))
    air = smp.get('air')
    if air:
        for a in range(len(roofs)):
            for b in range(a + 1, len(roofs)):
                p, q = roofs[a], roofs[b]
                d = math.hypot(p[0] - q[0], p[2] - q[2])
                if d < 4 or d > air['reach']:
                    continue
                mid = ((p[0] + q[0]) / 2, max(p[1], q[1]) + air['height'], (p[2] + q[2]) / 2)
                toward = math.atan2(q[0] - p[0], q[2] - p[2])
                for yaw in (toward, toward + math.pi / 2, toward + math.pi, toward - math.pi / 2):
                    add('air', mid, yaw, math.radians(-20))
    seams = smp.get('seams')
    if seams:
        n = max(1, int(round(S / seams['spacing'])))
        for (i, j) in every:
            for di, dj in ((1, 0), (0, 1)):
                if (i + di, j + dj) not in pack.cells:
                    continue
                if only is not None and (i, j) not in only and (i + di, j + dj) not in only:
                    continue
                for k in range(n):
                    f = (k + 0.5) / n
                    for side in (-1, 1):
                        if di:
                            x, z, yaw = (i + 1) * S + side * 0.01, j * S + f * S, math.pi / 2 * -side
                        else:
                            x, z, yaw = i * S + f * S, (j + 1) * S + side * 0.01, (0 if side < 0 else math.pi)
                        for h, t in _standing(floors, ceilings, x, z, probe['height'], *room)[:1]:
                            for y2 in (yaw, yaw + math.pi / 2):
                                add('seam', (x, h + eye_h, z), y2, 0.0)
    ents = smp.get('entities')
    if ents:
        _entity_cameras(pack, grid, floors, ceilings, probe, eye_h, ents, add, only)
    for k, vp in enumerate(settings['vantage_points']):
        # yaws: n directions from yaw, evenly round; else the one direction
        n = int(vp.get('yaws', 1))
        extra = {'vantage': k, **({'name': vp['name']} if vp.get('name') else {})}
        for q in range(max(1, n)):
            add('vantage', vp['position'], math.radians(vp.get('yaw', 0.0) + 360.0 * q / max(1, n)),
                math.radians(vp.get('pitch', 0.0)), extra)
    for v in views:
        v['cell'] = [math.floor(v['eye'][0]) >> pack.cell_shift, math.floor(v['eye'][2]) >> pack.cell_shift]
    if only is not None:
        views = [v for v in views if v['kind'] == 'vantage' or tuple(v['cell']) in only]
    return views


def _entity_cameras(pack, grid, floors, ceilings, probe, eye_h, ents, add, only=None):
    """Cameras aimed at each entity that has a mesh, at the middle of its mesh's height: around
    it at each distance and pitch (from above, like a follow camera; pulled in front of anything
    between them, as a follow camera is), and from eye height on the floors around it (from below
    a ledge it stands on, too)."""
    S = 1 << pack.cell_shift
    nyaw = max(1, ents['yaws'])
    for (i, j) in sorted(pack.cells, key=lambda ij: (ij[1], ij[0])):
        if only is not None and (i, j) not in only:
            continue
        c = pack.cells[(i, j)]
        for e in c.entities:
            if not e['mesh']:
                continue
            ys = [v[1] / ONE for v in RD.read_mesh(pack.data, e['mesh']).raw]
            radius = RD.mesh_bounds(pack.data, e["mesh"])[0]
            t = (i * S + S / 2 + e['pos'][0] / ONE, e['pos'][1] / ONE + (min(ys) + max(ys)) / 2,
                 j * S + S / 2 + e['pos'][2] / ONE)
            layer = c.layers[e['mask'].bit_length() - 1] if e['mask'] else None
            extra = {'entity': e['number'], 'entity_layer': layer}
            yaws = [2 * math.pi * (k + 0.25) / nyaw for k in range(nyaw)]
            for d in ents['distances']:
                for pd in ents['pitches_degrees']:
                    p = math.radians(pd)
                    for yaw in yaws:
                        fwd = (math.sin(yaw) * math.cos(p), math.sin(p), math.cos(yaw) * math.cos(p))
                        seg = [-fwd[k] * d for k in range(3)]
                        hit = ST.first_hit(grid, t, seg)
                        s = 1.0 if hit is None else max(0.0, hit[0] - 0.3 / d)
                        if s * d < radius + 0.3:
                            continue            # no room for the camera outside the object
                        add('entity', tuple(t[k] + seg[k] * s for k in range(3)), yaw, p, extra)
            for r in ents['floor_distances']:
                for a in yaws:
                    x, z = t[0] + math.sin(a) * r, t[2] + math.cos(a) * r
                    for h, _ in _standing(floors, ceilings, x, z, probe['height'], grid, probe['radius']):
                        eye = (x, h + eye_h, z)
                        if abs(eye[1] - t[1]) > 2 * r:
                            continue
                        add('entity', eye, math.atan2(t[0] - x, t[2] - z),
                            math.atan2(t[1] - eye[1], math.hypot(t[0] - x, t[2] - z)), extra)


def thin(views, cap):
    """At most `cap` sampled views, each kind thinned evenly in its own order: deterministic, and
    every kind keeps a share proportional to its size. Vantage points are always kept, on top of
    the cap."""
    fixed = sum(1 for v in views if v['kind'] == 'vantage')
    if not cap or len(views) - fixed <= cap:
        return views
    kinds = {}
    for v in views:
        kinds.setdefault(v['kind'], []).append(v)
    rest = len(views) - fixed
    room = cap
    # quotas by largest remainder, so they add up to exactly `room`
    share = {k: room * len(vs) / rest for k, vs in kinds.items() if k != 'vantage'}
    quota = {k: int(q) for k, q in share.items()}
    for k in sorted(share, key=lambda k: (-(share[k] - quota[k]), k))[:room - sum(quota.values())]:
        quota[k] += 1
    quota['vantage'] = fixed
    keep = set()
    for kind, vs in kinds.items():
        q = min(quota[kind], len(vs))
        for k in range(q):
            keep.add(id(vs[(k * len(vs)) // q]))
    return [v for v in views if id(v) in keep]


def _follow(grid, head, yaw, follow):
    d, h = follow['distance'], follow['height']
    cam = (head[0] - math.sin(yaw) * d, head[1] + h, head[2] - math.cos(yaw) * d)
    seg = [cam[k] - head[k] for k in range(3)]
    hit = ST.first_hit(grid, head, seg)
    if hit is None:
        return cam
    ln = math.sqrt(sum(c * c for c in seg))
    s = max(0.0, hit[0] - 0.3 / ln)
    return tuple(head[k] + seg[k] * s for k in range(3))


def layer_combinations(pack, settings):
    """(name, set of layer ids): all off, each layer alone, the largest set the exclusive groups
    allow (in each group, the layer with the most triangles)."""
    combos = [('none', frozenset())]
    if not pack.layers or not settings['sampling']['layer_combinations']:
        return combos
    weight = {}
    data = pack.data
    for c in pack.cells.values():
        for p in c.placements:
            if p['mask']:
                lid = c.layers[p['mask'].bit_length() - 1]
                weight[lid] = weight.get(lid, 0) + ST.mesh_triangles_count(data, p['mesh'])[2]
    for lid, (name, group, on) in enumerate(pack.layers):
        combos.append((name, frozenset([lid])))
    groups = {}
    largest = set()
    for lid, (name, group, on) in enumerate(pack.layers):
        if group == 0xFF:
            largest.add(lid)
        else:
            groups.setdefault(group, []).append(lid)
    for g, members in sorted(groups.items()):
        largest.add(max(members, key=lambda l: (weight.get(l, 0), -l)))
    if len(largest) > 1:
        combos.append(('largest', frozenset(largest)))
    return combos


def layer_views(pack, cams, combos, near_far):
    """Each camera with each layer combination that can change what it draws. A layer changes a
    view only through its placements in the cells the near pass draws (stand-ins leave layers
    out), so a combination is taken at a camera only where a cell with one of its layers'
    placements (its square grown by the overhang) is within near_far (units) of the eye;
    elsewhere the view is the one with every layer off. A camera aimed at an entity in a layer
    takes only the combinations with that layer."""
    S = 1 << pack.cell_shift
    layered = {}
    for (i, j), c in pack.cells.items():
        for p in c.placements:
            if p['mask']:
                layered.setdefault(c.layers[p['mask'].bit_length() - 1], set()).add((i, j))
    reach = near_far + pack.overhang / ONE

    def near(eye, cells):
        for a, b in cells:
            dx = max(a * S - eye[0], 0.0, eye[0] - (a + 1) * S)
            dz = max(b * S - eye[2], 0.0, eye[2] - (b + 1) * S)
            if dx * dx + dz * dz <= reach * reach:
                return True
        return False
    views = []
    for cam in cams:
        for name, on in combos:
            if cam.get('entity_layer') is not None and cam['entity_layer'] not in on:
                continue                    # the entity aimed at is not there
            if on and cam.get('entity_layer') is None and \
                    not near(cam['eye'], set().union(*(layered.get(lid, set()) for lid in on))):
                continue
            views.append({**cam, 'layer_set': name, 'layers': sorted(on)})
    return views


# ---- the check

def _describe(names):
    pl = (names or {}).get('placements', {})
    en = (names or {}).get('entities', {})

    def describe(f):
        key = f.inst.key
        out = {'kind': key[0], 'cell': list(f.inst.cell), 'face': f.index}
        if key[0] == 'placement':
            out['placement'] = key[3]
            out['tag'] = f.inst.tag
            if str(f.inst.tag) in pl:
                out['name'] = pl[str(f.inst.tag)]
        elif key[0] == 'entity':
            out['entity'] = key[1]
            out['type'] = f.inst.tag
            if str(key[1]) in en:
                out['name'] = en[str(key[1])]
        return out
    return describe


def _groups(pack, insts, meshes, views, ring):
    """Views sharing one triangle-ID assignment. One group if every face fits in 15-bit IDs;
    otherwise one per camera cell, with the instances within the far ring of it."""
    total = sum(len(meshes[i.mesh].faces) for i in insts)
    if total <= RD.MAX_ID:
        return [(insts, views)]
    by_cell = {}
    for v in views:
        by_cell.setdefault(tuple(v['cell']), []).append(v)
    out = []
    reach = max(1, ring)
    for (ci, cj), vs in sorted(by_cell.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        mine = [i for i in insts
                if max(abs(i.cell[0] - ci), abs(i.cell[1] - cj)) <= (1 if i.key[0] != 'standin' else reach)]
        out.append((mine, vs))
    return out


def _view_context(pack, names, cfg, rt, groups, heaviest=False):
    """What the ordering check of each view needs, rebuilt from the pack in a worker process.
    heaviest: list each view's heaviest placements (always in a world with levels of detail)."""
    insts = RD.instances(pack)
    meshes = {}
    for inst in insts:
        if inst.mesh not in meshes:
            meshes[inst.mesh] = RD.read_mesh(pack.data, inst.mesh)
    by_cell = {}
    for inst in insts:
        by_cell.setdefault(inst.cell, []).append(inst)
    return {'pack': pack, 'names': names, 'cfg': cfg, 'rt': rt, 'groups': groups, 'insts': insts,
            'meshes': meshes, 'by_cell': by_cell, 'describe': _describe(names),
            'texels': RD.pack_texels(pack) if rt.get('textured') else None,
            'lod_pack': any(p.get('lod') for c in pack.cells.values() for p in c.placements),
            'heaviest': heaviest,
            'order_cfg': {**cfg['ordering'], 'near_band': cfg['thresholds']['near_band'], 'depth': rt['depth']}}


def _view_row(ctx, g, v, rec, rec2, out_dir, sample=None):
    """One view's row of the report from its two recorded frames, and its diagnostic entry
    (score, index, comparison, picture) when it has ordering findings and out_dir is set. In
    depth mode, rec2 is None for a view outside the ordering sample, and `sample` says why a
    view in it was chosen."""
    pack, names, cfg, rt = ctx['pack'], ctx['names'], ctx['cfg'], ctx['rt']
    meshes, by_cell, describe = ctx['meshes'], ctx['by_cell'], ctx['describe']
    lod_pack, order_cfg = ctx['lod_pack'], ctx['order_cfg']
    first, ids_ok = ctx['groups'][g]
    S = 1 << pack.cell_shift
    st, out, _ = rec
    # rec2 None: depth mode, a view outside the ordering sample, measured only
    st2, out2, pic = rec2 if rec2 is not None else rec
    diag = None
    row = {'index': v['index'], 'kind': v['kind'],
           'camera': {'eye': v['eye'], 'yaw_degrees': round(math.degrees(v['yaw']), 3),
                      'pitch_degrees': round(math.degrees(v['pitch']), 3), 'cell': v['cell']},
           'layer_set': v['layer_set'],
           'layers': [pack.layers[l][0] for l in v['layers']]}
    for k2 in ('vantage', 'name', 'entity'):
        if k2 in v:
            row[k2] = v[k2]
    row['stats'] = {'draw_cpu_cycles': out['draw_cycles'] + out['entity_cycles'],
                    'wp_draw_cycles': out['draw_cycles'], 'entity_cycles': out['entity_cycles'],
                    'frame_cpu_cycles': st['cpu_cycles'], 'gpu_cycles': st['gpu_cycles'],
                    'triangles': st['tris'],
                    'triangles_dropped': max(st['tris_dropped'], st2['tris_dropped']),
                    'arena_bytes': out['arena_bytes'],
                    'arena_full': min(out['arena_left'], out2['arena_left']) < (
                        RD.ARENA_FULL_DEPTH if rt['depth'] or rt['perspective'] else RD.ARENA_FULL),
                    'placements_drawn': out['drawn'], 'ground_drawn': out['ground'],
                    'standins_drawn': out['standins'], 'entities_drawn': out['entities'],
                    'coarse_drawn': out['coarse'], 'lod_culled': out['lod_culled']}
    if pack.minor >= 5:
        row['stats'].update(occluded=out['occluded'], standins_occluded=out['standins_occluded'], zone=out['zone'])
    if rt['depth'] or rt['perspective']:
        row['stats']['depth'] = {k: st[k] for k in RD.DEPTH_STATS}
    if rt['depth']:
        # pixels the measured frame drew without the depth test (every face is depth-tested in
        # depth mode), and the identity frame's when there is one
        row['stats']['depth']['untested_pixels'] = max(_untested(st), _untested(st2))
    sel = None
    if lod_pack or ctx.get('heaviest'):
        sel = RD.select(pack, by_cell, v['eye'], out2['vp'], set(v['layers']), rt, v.get('region'))
        row['heaviest'] = _heaviest(pack, sel, meshes, v['eye'], names)
    if rec2 is None:
        row['ordering'] = {'skipped': 'not in the ordering sample (depth mode)'}
    elif cfg['ordering']['enabled'] and ids_ok:
        # in depth mode wp_draw() draws the stand-ins over the near pass's clip range too
        near_planes = {'near': rt['clip_near'], 'ground': rt['clip_near'],
                       'far': rt['clip_near'] if rt['depth'] else S / 2}
        if sel is None or pack.minor >= 5:
            # the reference: what is in sight, occlusion zones or not (a zone that hides something
            # in sight shows as pixels drawn wrongly)
            sel = RD.select(pack, by_cell, v['eye'], out2['vp'], set(v['layers']), rt, v.get('region'), occlusion=False)
        faces = RD.view_faces(pack, meshes, sel, out2['vp'], out2['origin'], first, near_planes,
                              ctx['texels'], v.get('region'))
        cmp = RD.compare_view(faces, pic, order_cfg)
        issues, near_px, far_px = RD.witnesses(cmp, pic, order_cfg, describe, order_cfg['witnesses'])
        cov = int(cmp['coverage'].sum())
        ginv = int(cmp['ground_inversion'].sum())
        ent = RD.entity_pixels(faces, cmp, pic)
        row['ordering'] = {'tested_pixels': int((cmp['tested'] & cmp['covered']).sum()),
                           'tested_background': int((cmp['tested'] & ~cmp['covered']).sum()),
                           'undecided_pixels': int(cmp['ambiguous'].sum()),
                           'wrong_near_pixels': near_px, 'wrong_far_pixels': far_px,
                           'coverage_errors': cov, 'pass_inversions': int(cmp['inversion'].sum()),
                           'ground_inversions': ginv, 'faces': len(faces), **ent, 'issues': issues}
        if sample:
            row['ordering']['sample'] = sample
        if ginv:
            row['ordering']['ground_issues'] = RD.ground_witnesses(cmp, describe,
                                                                   order_cfg['witnesses'])
        if cov:
            p = int(RD.numpy().flatnonzero(cmp['coverage'])[0])
            row['ordering']['coverage_sample'] = {'pixel': [p % RD.W, p // RD.W], 'drawn_id': int(pic[p]),
                                                  'expected_id': int(cmp['expected'][p])}
        if out_dir and (near_px or far_px or cov or ginv):
            diag = ((near_px + ginv, far_px + cov), v['index'], cmp, pic)
    else:
        row['ordering'] = {'skipped': 'disabled' if ids_ok else
                           f'more than {RD.MAX_ID} faces within reach of this camera cell'}
    return row, diag


def _untested(st):
    """Pixels a frame drew without the depth test: every kind's pixels less the depth-tested."""
    return sum(st[f'px{k}'] for k in range(8)) - st['px_ztest']


_WORKER = {}


def _view_worker_init(pack_bytes, names, cfg, rt, groups, heaviest=False):
    _WORKER['ctx'] = _view_context(decode(pack_bytes), names, cfg, rt, groups, heaviest)


def _view_worker(task):
    return _view_row(_WORKER['ctx'], *task)


def _view_rows(pool, ctx, tasks, chunksize=4):
    """_view_row() of each task, in order: in the pool's workers, or here when there is no
    pool or it cannot run (a script that starts the check without `if __name__ == '__main__'`)."""
    if pool:
        try:
            return list(pool.map(_view_worker, tasks, chunksize=chunksize))
        except (BrokenProcessPool, OSError, RuntimeError):
            pass
    return [_view_row(ctx, *t) for t in tasks]


def _jobs():
    """Worker processes for the ordering checks: $MEI_KIT_JOBS, else the number of cores."""
    try:
        return max(1, int(os.environ['MEI_KIT_JOBS']))
    except (KeyError, ValueError):
        return os.cpu_count() or 1


def _depth_mode_views(pool, ctx, groups, meshes, tools, out_dir):
    """Depth mode's views (docs/WORLDCHECKER.md, "Depth mode"): every view's measured frame, for
    the budgets; then the identity frames and the pixel comparison of the ordering sample alone.
    Returns (rows, diagnostic entries, {index: why sampled}, (native, compile, emulator,
    reference seconds))."""
    pack, cfg, rt = ctx['pack'], ctx['cfg'], ctx['rt']
    swatch = RD.swatch_rows(meshes.values())
    jobs = _jobs()
    t_native = t_ref = compile_s = run_s = 0.0
    group_of, measured, rows = {}, {}, {}
    with tempfile.TemporaryDirectory(prefix='mei-world-check-') as tmp:
        idps = {}
        for g, (ginsts, gviews, first, ids_ok) in enumerate(groups):
            if not gviews:
                continue
            idps[g] = (RD.identity_pack(pack.data, ginsts, first, meshes, pack, ctx['texels']) if ids_ok
                       else bytes(pack.data))
            t1 = time.perf_counter()
            recs, tm = RD.run_frames(bytes(pack.data), idps[g], [(v, False) for v in gviews], rt, tools,
                                     Path(tmp) / f'group{g}', swatch, jobs)
            t_native += time.perf_counter() - t1
            compile_s += tm['compile_seconds']
            run_s += tm['run_seconds']
            for v, rec in zip(gviews, recs):
                group_of[v['index']], measured[v['index']] = (g, v), rec
                rows[v['index']] = _view_row(ctx, g, v, rec, None, False)[0]
        ordered = [rows[k] for k in sorted(rows)]
        chosen = ordering_sample(ordered, cfg['ordering']['depth_views']) if cfg['ordering']['enabled'] else {}
        diag = []
        for g, (ginsts, gviews, first, ids_ok) in enumerate(groups):
            mine = [v for v in gviews if v['index'] in chosen]
            if not mine:
                continue
            t1 = time.perf_counter()
            recs, tm = RD.run_frames(bytes(pack.data), idps[g], [(v, True) for v in mine], rt, tools,
                                     Path(tmp) / f'group{g}-ids', swatch, jobs)
            t_native += time.perf_counter() - t1
            compile_s += tm['compile_seconds']
            run_s += tm['run_seconds']
            tasks = [(g, v, measured[v['index']], rec, bool(out_dir), chosen[v['index']])
                     for v, rec in zip(mine, recs)]
            t1 = time.perf_counter()
            for row, d in _view_rows(pool, ctx, tasks, 1):
                rows[row['index']] = row
                if d:
                    diag.append(d)
            t_ref += time.perf_counter() - t1
    return [rows[k] for k in sorted(rows)], diag, chosen, (t_native, compile_s, run_s, t_ref)


def _spread_key(k):
    """k's place in the binary van der Corput sequence: walking 0, 1, 2, ... in this order
    visits the halves, then the quarters, then the eighths of the range, and so on."""
    out, f = 0.0, 0.5
    while k:
        out += f * (k & 1)
        k >>= 1
        f /= 2
    return out


def _strata(r):
    k, ls, c = r['kind'], r['layer_set'], tuple(r['camera']['cell'])
    return {('kind', k), ('layer_set', ls), ('cell', c), ('kind+layer_set', k, ls), ('kind+cell', k, c),
            ('cell+layer_set', c, ls)}


def ordering_sample(rows, n):
    """Depth mode's ordering sample: the views (rows with their measured stats, in view order)
    that get the pixel comparison, as {view index: why}, in the order chosen. Deterministic:

    1. 'vantage': every authored vantage point;
    2. 'most gpu_cycles', 'most draw_cpu_cycles', 'most triangles', 'most arena_bytes': the
       worst view by each budget (the most faces, depth tests and overlap);
    3. 'stratum': then, greedily, the view that adds the most strata not yet in the sample
       (its kind, layer set, camera cell, and each pair of them), until every stratum is in;
    4. 'heaviest' and 'spread', taking turns: the views with the most triangles, and the views
       in van der Corput order of their index (evenly over the sampled order: kinds, cells).

    Ties go to the earlier view in the van der Corput order. n None: every view ('every view')."""
    if n is None or n >= len(rows):
        return {r['index']: 'every view' for r in rows}
    chosen = {}

    def take(r, why):
        if r['index'] not in chosen and len(chosen) < n:
            chosen[r['index']] = why
    for r in rows:
        if r['kind'] == 'vantage':
            take(r, 'vantage')
    for key in ('gpu_cycles', 'draw_cpu_cycles', 'triangles', 'arena_bytes'):
        take(max(rows, key=lambda r: (r['stats'][key], -r['index'])), f'most {key}')
    spread = sorted(rows, key=lambda r: (_spread_key(r['index']), r['index']))
    by_index = {r['index']: r for r in rows}
    covered = set()
    for k in chosen:
        covered |= _strata(by_index[k])
    while len(chosen) < n:
        best, gain = None, 0
        for r in spread:
            if r['index'] not in chosen:
                g = len(_strata(r) - covered)
                if g > gain:
                    best, gain = r, g
        if best is None:
            break
        take(best, 'stratum')
        covered |= _strata(best)
    heavy = iter(sorted(rows, key=lambda r: (-r['stats']['triangles'], r['index'])))
    even = iter(spread)
    turn = 0
    while len(chosen) < n:
        source, why = (heavy, 'heaviest') if turn % 2 == 0 else (even, 'spread')
        turn += 1
        for r in source:
            if r['index'] not in chosen:
                take(r, why)
                break
    return chosen


def _sample_summary(chosen, views):
    why = {}
    for w in chosen.values():
        why[w] = why.get(w, 0) + 1
    return {'views': len(chosen), 'of': views, 'chosen': dict(sorted(why.items()))}


def verify(pack_bytes, settings=None, names=None, out_dir=None, tools=None, focus=None):
    """Checks a world pack. Returns the report (a JSON-ready dict); see docs/WORLDCHECKER.md.
    Raises SettingsError for bad settings and RD.RenderError when the native tools fail.

    focus (the quick check, `mei_world.py check`): {'cells': [(i, j), ...]} narrows the check to
    those cells: the static collision checks find what lies in them, the sampled views are the
    ones sampled from them, the cell budgets are theirs, and every view lists its heaviest
    placements. The vantage points are checked as always. None: the whole world."""
    t_start = time.perf_counter()
    cfg = merge_settings(settings)
    th = cfg['thresholds']
    tools = {**default_tools(), **(tools or {})}
    report = {'format': 'mei-world-check', 'version': 1, 'ok': False, 'mode': cfg['mode'],
              'settings': shown_settings(cfg),
              'hard_failures': [], 'threshold_failures': []}
    timing = {}
    try:
        pack = decode(pack_bytes)
    except PackError as error:
        report['hard_failures'].append({'code': 'bad_pack', 'message': str(error)})
        report['timing'] = {'total_seconds': time.perf_counter() - t_start}
        return report
    S = 1 << pack.cell_shift
    if pack.minor < 5:                  # no occlusion zones: the report is the one made before them
        report['settings'].pop('occlusion', None)
        report['settings']['thresholds'].pop('occlusion_leaks', None)
    rt = dict(cfg['runtime'])
    if any(r.textures for r in pack.regions):
        rt['textured'] = True       # each view enters its camera cell's region (verify_render.py)
    if rt['near_far'] is None:          # the pack's own (1.3), else the reader's default
        rt['near_far'] = pack.near_far / ONE if pack.near_far else 1.5 * S
    report['pack'] = {'sha256': hashlib.sha256(bytes(pack_bytes)).hexdigest(), 'bytes': len(pack_bytes),
                      'cells': len(pack.cells), 'cell_size': S, 'layers': [l[0] for l in pack.layers]}
    if focus is not None:
        report['focus'] = {'cells': sorted([list(c) for c in focus.get('cells', ())], key=lambda c: (c[1], c[0])),
                           'vantage_points': len(cfg['vantage_points'])}

    # 1. static checks
    t0 = time.perf_counter()
    tris = ST.world_triangles(pack)
    static = {'errors': [], 'warnings': []}
    lim = cfg['collision']['findings']
    only = None if focus is None else {tuple(c) for c in focus.get('cells', ())}
    static_tris = tris if only is None else ST.near_cells(tris, only, S)

    def focused(found):
        """Findings whose point lies in the focus's cells."""
        if only is None:
            return found
        return [f for f in found if ((math.floor(f['at'][0]) >> pack.cell_shift),
                                     (math.floor(f['at'][2]) >> pack.cell_shift)) in only]
    cracks, ncrack, nedges = [], 0, 0
    sets = [('none', frozenset())] + [(l[0], frozenset([k])) for k, l in enumerate(pack.layers)]
    if only is not None:
        # a layer with no collision near the cells finds what every layer off finds
        near = {t.layer for t in ST.near_cells(tris, only, S, 2.0)}
        sets = [(name, on) for name, on in sets if not on or on & near]
    baseline = cfg['collision']['crack_baseline']
    for name, on in sets:
        found, n, ne, _ = ST.crack_check(pack, static_tris, on, cfg['probe'], cfg['collision'],
                                         lim if only is None and baseline is None else 10 ** 9)
        if only is not None:
            found = focused(found)
            n = len(found)
        if baseline is None:
            found = found[:lim]
        nedges = max(nedges, ne)
        for f in found:
            f['layers'] = sorted(pack.layers[k][0] for k in on)
            key = (f['code'], tuple(f['cell']), f['floor_tag'], f['beyond_tag'])
            if all((g['code'], tuple(g['cell']), g['floor_tag'], g['beyond_tag']) != key for g in cracks):
                cracks.append(f)
        ncrack += n
    known = []
    if baseline is not None:
        # NAME.cracks.json: the cracks known when it was written are listed, not failures
        cracks, known, fixed = ST.against_baseline(cracks, baseline)
        if only is not None:
            fixed = focused(fixed)
        static['crack_baseline'] = {'known': len(known), 'new': len(cracks), 'fixed': len(fixed),
                                    'known_findings': known[:lim], 'fixed_findings': fixed[:lim]}
    drops, made = [], 0
    drop = cfg['collision']['drop']
    if drop:
        # every layer off over every cell, then each layer alone over the cells with its collision
        dsets = [(frozenset(), None)]
        for k, l in enumerate(pack.layers):
            mine = {ij for ij, c in pack.cells.items() if k in c.layers} if any(t.layer == k for t in tris) else None
            if mine:
                dsets.append((frozenset([k]), mine))
        for on, mine in dsets:
            cells_of = mine if only is None else (only if mine is None else mine & only)
            found, n, m = ST.drop_check(pack, on, cfg['probe'], drop, 10 ** 9, cells_of)
            made += m
            for f in found:
                f['layers'] = sorted(pack.layers[k][0] for k in on)
                if not any(g['cell'] == f['cell'] and abs(g['at'][0] - f['at'][0]) <= drop['merge'] and
                           abs(g['at'][2] - f['at'][2]) <= drop['merge'] for g in drops):
                    drops.append(f)
    ents, nent = ST.entity_check(pack, tris, cfg['collision'], lim)
    ref_err, ref_warn = ST.reference_check(pack, rt['far_ring'])
    if only is not None:
        ents = focused(ents)
        ref_err = [e for e in ref_err if 'cell' not in e or tuple(e['cell']) in only]
        ref_warn = [e for e in ref_warn if 'cell' not in e or tuple(e['cell']) in only]
    if rt['ground_first'] and not rt['depth']:     # the depth test draws ground in its place
        ref_warn += ST.ground_check(pack, rt['near_far'], lim, only)
    cells, regions = ST.counts(pack)
    if only is not None:
        cells = [c for c in cells if tuple(c['cell']) in only]
    static['collision'] = {'triangles': len(tris), 'boundary_edges': nedges, 'findings': cracks[:lim],
                           'entities_in_solid': ents}
    if drop:
        static['collision']['drops'] = {'made': made, 'through': len(drops), 'findings': drops[:lim]}
    static['cells'] = cells
    static['regions'] = regions
    static['warnings'] = ref_warn
    if pack.minor >= 5 and cfg['occlusion']['enabled']:
        from . import verify_occlusion as OC
        t1 = time.perf_counter()
        occ = OC.check(pack, cfg['occlusion'], only, names)
        timing['occlusion_seconds'] = time.perf_counter() - t1
        static['occlusion'] = occ
        if th['occlusion_leaks'] is not None and occ['leaks'] > th['occlusion_leaks']:
            report['threshold_failures'].append({'check': 'occlusion', 'code': 'occlusion_leak', 'value': occ['leaks'],
                                                 'limit': th['occlusion_leaks'], 'witness': occ['findings'][:1]})
    report['static'] = static
    for f in cracks:
        report['hard_failures'].append({'check': 'collision', **f})
    for f in ents:
        report['hard_failures'].append({'check': 'collision', **f})
    for f in drops[:lim]:
        report['hard_failures'].append({'check': 'collision', **f})
    for e in ref_err:
        dest = report['threshold_failures'] if e.get('policy') else report['hard_failures']
        dest.append({'check': 'references', **e})
    for c in cells:
        for key, limit in (('triangles', th['cell_triangles']), ('placements', th['cell_placements']),
                           ('standin_triangles', th['standin_triangles'])):
            if c[key] is not None and limit is not None and c[key] > limit:
                report['threshold_failures'].append({'check': 'budget', 'code': f'cell_{key}', 'cell': c['cell'],
                                                     'value': c[key], 'limit': limit})
    timing['static_seconds'] = time.perf_counter() - t0

    # 2 and 3. sampled views
    t0 = time.perf_counter()
    cams = sample_views(pack, tris, cfg, only)
    combos = layer_combinations(pack, cfg)
    ring = int(rt['far_ring'])
    views = layer_views(pack, cams, combos, rt['near_far'])
    sampled = len(views)
    views = thin(views, cfg['sampling']['max_views'])
    for k, v in enumerate(views):
        v['index'] = k
        if rt.get('textured'):
            v['region'] = RD.cell_region(pack, v['eye'])
    timing['sampling_seconds'] = time.perf_counter() - t0
    report['sampling'] = {'cameras': len(cams), 'sampled_views': sampled, 'thinned': sampled - len(views),
                          'layer_sets': [c[0] for c in combos],
                          'views': len(views),
                          'kinds': {k: sum(1 for v in cams if v['kind'] == k)
                                    for k in sorted({v['kind'] for v in cams})}}
    insts = RD.instances(pack)
    meshes = {}
    for inst in insts:
        if inst.mesh not in meshes:
            meshes[inst.mesh] = RD.read_mesh(pack.data, inst.mesh)
    groups = []
    for ginsts, gviews in _groups(pack, insts, meshes, views, ring):
        first, nid = {}, 1
        for inst in ginsts:
            first[inst.key] = nid
            nid += len(meshes[inst.mesh].faces)
        groups.append((ginsts, gviews, first, nid - 1 <= RD.MAX_ID))
    firsts = [(first, ids_ok) for _, _, first, ids_ok in groups]
    ctx = _view_context(pack, names, cfg, rt, firsts, focus is not None)
    rows = []
    images = []
    t_native = t_ref = 0.0
    compile_s = run_s = 0.0
    diag = []
    # The views' ordering checks are independent: with more than one job they run in worker
    # processes, and their rows are put back in view order, as one process would make them.
    jobs = min(_jobs(), len(views) // 8)
    pool = None
    if jobs > 1:
        pool = ProcessPoolExecutor(jobs, initializer=_view_worker_init,
                                   initargs=(bytes(pack_bytes), names, cfg, rt, firsts, focus is not None))
    try:
        if rt['depth']:
            rows, diag, chosen, tm = _depth_mode_views(pool, ctx, groups, meshes, tools, out_dir)
            t_native, compile_s, run_s, t_ref = tm
            report['sampling']['ordering_sample'] = _sample_summary(chosen, len(rows))
        else:
            with tempfile.TemporaryDirectory(prefix='mei-world-check-') as tmp:
                for g, (ginsts, gviews, first, ids_ok) in enumerate(groups):
                    if not gviews:
                        continue
                    idp = (RD.identity_pack(pack.data, ginsts, first, meshes, pack, ctx['texels']) if ids_ok
                           else bytes(pack.data))
                    work = Path(tmp) / f'group{g}'
                    work.mkdir()
                    t1 = time.perf_counter()
                    recs, tm = RD.run_cart(bytes(pack.data), idp, gviews, rt, tools, work,
                                           RD.swatch_rows(meshes.values()))
                    t_native += time.perf_counter() - t1
                    compile_s += tm['compile_seconds']
                    run_s += tm['run_seconds']
                    tasks = [(g, v, recs[2 * k], recs[2 * k + 1], bool(out_dir)) for k, v in enumerate(gviews)]
                    t1 = time.perf_counter()
                    for row, d in _view_rows(pool, ctx, tasks):
                        rows.append(row)
                        if d:
                            diag.append(d)
                            diag.sort(key=lambda d: (-d[0][0], -d[0][1], d[1]))
                            del diag[cfg['images']:]
                    t_ref += time.perf_counter() - t1
    finally:
        if pool:
            pool.shutdown(cancel_futures=True)
    rows.sort(key=lambda r: r['index'])
    if out_dir and cfg['images']:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        diag.sort(key=lambda d: (-d[0][0], -d[0][1], d[1]))
        for score, idx, cmp, pic in diag[:cfg['images']]:
            fn = f'view_{idx:04}.png'
            (out / fn).write_bytes(RD.diagnostic_image(cmp, pic))
            images.append(fn)
            rows[idx]['image'] = fn
    report['views'] = rows
    report['images'] = images

    # 4. outcome
    for r in rows:
        s, o = r['stats'], r['ordering']
        where = {'view': r['index'], 'kind': r['kind'], 'camera': r['camera'], 'layer_set': r['layer_set']}
        if s['triangles_dropped']:
            report['hard_failures'].append({'check': 'views', 'code': 'triangles_dropped', **where,
                                            'value': s['triangles_dropped']})
        if s['arena_full']:
            report['hard_failures'].append({'check': 'views', 'code': 'arena_full', **where, 'value': s['arena_bytes']})
        if rt['depth'] and (s['depth']['untested_pixels'] or s['depth']['zclears'] < 1):
            # depth mode on every view: the frame drew without the depth test, or never cleared it
            report['hard_failures'].append({'check': 'views', 'code': 'depth_untested', **where,
                                            'value': s['depth']['untested_pixels'],
                                            'zclears': s['depth']['zclears']})
        for code, value, limit in (('gpu_cycles', s['gpu_cycles'], th['gpu_cycles']),
                                   ('draw_cpu_cycles', s['draw_cpu_cycles'], th['draw_cpu_cycles']),
                                   ('view_triangles', s['triangles'], th['view_triangles'])):
            if limit is not None and value > limit:
                f = {'check': 'budget', 'code': code, **where, 'value': value, 'limit': limit}
                if 'heaviest' in r:         # what to give levels of detail, or farther switch distances
                    f['heaviest'] = r['heaviest'][:3]
                report['threshold_failures'].append(f)
        if 'skipped' in o:
            continue
        if o['wrong_near_pixels'] > th['near_wrong_pixels']:
            report['threshold_failures'].append({'check': 'ordering', 'code': 'wrong_order_near', **where,
                                                 'value': o['wrong_near_pixels'], 'limit': th['near_wrong_pixels'],
                                                 'witness': _first(o['issues'], 'near')})
        if o['wrong_far_pixels'] > th['far_wrong_fraction'] * SCREEN:
            report['threshold_failures'].append({'check': 'ordering', 'code': 'wrong_order_far', **where,
                                                 'value': o['wrong_far_pixels'],
                                                 'limit': math.floor(th['far_wrong_fraction'] * SCREEN),
                                                 'witness': _first(o['issues'], 'far')})
        if o['coverage_errors'] > th['coverage_pixels']:
            report['threshold_failures'].append({'check': 'ordering', 'code': 'coverage', **where,
                                                 'value': o['coverage_errors'], 'limit': th['coverage_pixels'],
                                                 'sample': o.get('coverage_sample')})
        if o['ground_inversions'] > th['ground_inversion_pixels']:
            report['threshold_failures'].append({'check': 'ordering', 'code': 'ground_inversion', **where,
                                                 'value': o['ground_inversions'],
                                                 'limit': th['ground_inversion_pixels'],
                                                 'witness': o['ground_issues'][0]})

    def worst(key, f):
        cand = [r for r in rows if f(r) is not None]
        if not cand:
            return None
        r = max(cand, key=lambda r: (f(r), -r['index']))
        return {'view': r['index'], 'value': f(r)}
    report['summary'] = {
        'views': len(rows),
        'max_gpu_cycles': worst('gpu', lambda r: r['stats']['gpu_cycles']),
        'max_draw_cpu_cycles': worst('cpu', lambda r: r['stats']['draw_cpu_cycles']),
        'max_triangles': worst('tris', lambda r: r['stats']['triangles']),
        'max_arena_bytes': worst('arena', lambda r: r['stats']['arena_bytes']),
        'max_wrong_near_pixels': worst('wn', lambda r: r['ordering'].get('wrong_near_pixels')),
        'max_wrong_far_pixels': worst('wf', lambda r: r['ordering'].get('wrong_far_pixels')),
        'coverage_errors': sum(r['ordering'].get('coverage_errors', 0) for r in rows),
        'max_ground_inversions': worst('gi', lambda r: r['ordering'].get('ground_inversions')),
        'tested_pixels': sum(r['ordering'].get('tested_pixels', 0) for r in rows),
        'entity_views': _entity_summary(rows),
        'lod': _lod_summary(rows) if ctx['lod_pack'] else None,
        'hard_failures': len(report['hard_failures']),
        'threshold_failures': len(report['threshold_failures']),
    }
    if baseline is not None:
        report['summary']['known_cracks'] = len(known)
    report['ok'] = not report['hard_failures'] and (cfg['mode'] == 'report' or not report['threshold_failures'])
    report['scope'] = (DEPTH_SCOPE if rt['depth'] else 'Static collision checks use the reader\'s exact floor query at sampled points. '
                       'Views are sampled, not exhaustive. Ordering compares pixels at least edge_margin '
                       'pixels inside the nearest face and clear of every other face that could be nearer; '
                       'other pixels are counted as undecided. Ground placements are expected behind '
                       'everything near drawn after them, as the reader draws them; where ground truly hides '
                       'such a face it is counted as a ground inversion. Semi-transparent and non-swatch '
                       'textured faces are never the expected face. See docs/WORLDCHECKER.md.')
    timing['native_seconds'] = t_native
    timing['compile_seconds'] = compile_s
    timing['emulator_seconds'] = run_s
    timing['reference_seconds'] = t_ref
    timing['total_seconds'] = time.perf_counter() - t_start
    timing['per_view_seconds'] = (t_native + t_ref) / len(rows) if rows else 0.0
    report['timing'] = timing
    if out_dir:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / 'world-check.json').write_text(json.dumps(report, indent=1) + '\n')
    return report


DEPTH_SCOPE = ('Static collision checks use the reader\'s exact floor query at sampled points. Views are '
               'sampled, not exhaustive. Depth mode: every pass is judged as one, by depth, as the depth test '
               'draws it; ordering compares pixels at least edge_margin pixels inside the nearest face where it '
               'is nearer than every other face by more than two steps of the depth key and half a pixel of '
               'each face\'s depth slope; other pixels, coplanar faces among them, are counted as undecided. '
               'Semi-transparent and non-swatch textured faces are never the expected face. '
               'See docs/WORLDCHECKER.md.')


def _heaviest(pack, sel, meshes, eye, names, n=5):
    """The placements drawn in a view with the most faces, what a budget failure points at: each
    with its distance from the eye, the level of detail drawn and how many levels it has."""
    S = 1 << pack.cell_shift
    pl = (names or {}).get('placements', {})
    out = []
    for inst, pas, _ in sel:
        if inst.key[0] != 'placement':
            continue
        c = inst.sphere
        w = (c[0] / ONE + inst.cell[0] * S + S / 2, c[1] / ONE, c[2] / ONE + inst.cell[1] * S + S / 2)
        out.append((len(meshes[inst.mesh].faces), inst, math.dist(w, eye)))
    out.sort(key=lambda t: (-t[0], t[1].key))
    rows = []
    for faces, inst, dist in out[:n]:
        row = {'cell': list(inst.cell), 'placement': inst.key[3], 'tag': inst.tag, 'faces': faces,
               'distance': round(dist, 2), 'level': inst.level, 'levels': 1 + len(inst.lod['rows']) if inst.lod else 1}
        if str(inst.tag) in pl:
            row['name'] = pl[str(inst.tag)]
        rows.append(row)
    return rows


def _lod_summary(rows):
    """Levels of detail over the views: how many placements were drawn coarser or culled."""
    return {'views_with_coarse': sum(1 for r in rows if r['stats']['coarse_drawn']),
            'coarse_drawn': sum(r['stats']['coarse_drawn'] for r in rows),
            'lod_culled': sum(r['stats']['lod_culled'] for r in rows),
            'max_triangles': max((r['stats']['triangles'] for r in rows), default=0)}


def _entity_summary(rows):
    """The views aimed at entities (kind 'entity'), in sum: how much of the entities' drawn
    pixels the ordering check could judge, and what it found."""
    out = {'views': 0, 'views_with_wrong_near': 0, 'wrong_near_pixels': 0, 'undecided_pixels': 0,
           'entity_pixels': 0, 'entity_pixels_tested': 0, 'entity_over_nearer_pixels': 0, 'over_entity_pixels': 0}
    for r in rows:
        o = r['ordering']
        if r['kind'] != 'entity' or 'skipped' in o:
            continue
        out['views'] += 1
        out['views_with_wrong_near'] += o['wrong_near_pixels'] > 0
        out['wrong_near_pixels'] += o['wrong_near_pixels']
        out['undecided_pixels'] += o['undecided_pixels']
        for k in ('entity_pixels', 'entity_pixels_tested', 'entity_over_nearer_pixels', 'over_entity_pixels'):
            out[k] += o[k]
    return out


def _first(issues, cls):
    return next((i for i in issues if i['class'] == cls), None)


def check_world(context):
    """The World Kit build's entry point (worldkit.build.run_gate): a thin adapter over
    verify(). context carries the staged pack's path ('pack'), the recipe's verification 'mode'
    ('report' or 'enforce', which is this checker's 'strict') and 'thresholds', the game's
    'probe', the staging directory ('stage', where the report and images go, under
    verification/) and optionally the 'compiler' to use (mei-scene-probe is looked for beside
    it), 'checker' (a number: sample at most that many views; build --world-checker N),
    'runtime' (the recipe's runtime: depth and perspective, how the game draws the world) and
    'crack_baseline' (the entries of NAME.cracks.json: those cracks are known, not failures) and
    'vantage_points' (the recipe's verification.vantage_points: cameras always checked).
    Returns the report, or {'ok': False, 'errors': [...]} when the check could not run."""
    mode = context.get('mode') or 'report'
    settings = {'mode': 'strict' if mode == 'enforce' else mode,
                'thresholds': dict(context.get('thresholds') or {})}
    if isinstance(context.get('checker'), int):     # build --world-checker N: a reduced sample
        settings['sampling'] = {'max_views': context['checker']}
    if context.get('vantage_points'):               # the recipe's verification.vantage_points
        settings['vantage_points'] = [dict(vp) for vp in context['vantage_points']]
    runtime = {k: bool(v) for k, v in (context.get('runtime') or {}).items() if k in ('depth', 'perspective')}
    if runtime:                                     # the recipe's runtime.depth, runtime.perspective
        settings['runtime'] = runtime
    probe = {k: v for k, v in (context.get('probe') or {}).items() if k in DEFAULTS['probe']}
    if probe:
        settings['probe'] = {**DEFAULTS['probe'], **probe}
    if context.get('crack_baseline') is not None:   # NAME.cracks.json's entries
        settings['collision'] = {'crack_baseline': list(context['crack_baseline'])}
    tools = {}
    if context.get('compiler'):
        tools['compiler'] = Path(context['compiler'])
        beside = Path(context['compiler']).parent / 'mei-scene-probe'
        if beside.exists():
            tools['probe'] = beside
    out_dir = Path(context['stage']) / 'verification' if context.get('stage') else None
    try:
        return verify(Path(context['pack']).read_bytes(), settings, None, out_dir, tools)
    except (OSError, ValueError, RD.RenderError) as error:
        return {'ok': False, 'ran': False,
                'errors': [{'path': getattr(error, 'path', '/verification'), 'message': str(error)}]}


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description='The World Checker: verify a world pack (docs/WORLDCHECKER.md).')
    p.add_argument('pack', help='a .world.bin pack')
    p.add_argument('-o', '--output', help='write world-check.json and diagnostic images here')
    p.add_argument('--settings', help='a JSON file of settings (see DEFAULTS in this file)')
    p.add_argument('--names', help='a JSON file naming placements by tag and entities by number')
    p.add_argument('--strict', action='store_true', help='fail on thresholds as well')
    p.add_argument('--compiler', help='meic to use')
    p.add_argument('--probe', help='mei-scene-probe to use')
    args = p.parse_args(argv)
    try:
        settings = json.loads(Path(args.settings).read_text()) if args.settings else {}
        if args.strict:
            settings['mode'] = 'strict'
        names = json.loads(Path(args.names).read_text()) if args.names else None
        tools = {}
        if args.compiler:
            tools['compiler'] = Path(args.compiler)
        if args.probe:
            tools['probe'] = Path(args.probe)
        report = verify(Path(args.pack).read_bytes(), settings, names, args.output, tools)
    except (OSError, ValueError, RD.RenderError) as error:
        print(json.dumps({'ok': False, 'errors': [{'path': getattr(error, 'path', '/input'), 'message': str(error)}]},
                         indent=1))
        return 1
    print(json.dumps(report, indent=1))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
