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
   the air between rooftops, at authored vantage points and on cell seams, for each layer
   combination; CPU and GPU cycles, triangles submitted and dropped, packet arena use.
3. Ordering: each view's triangle-ID picture against an independent reference that resolves
   true depth (verify_render.py), with the reader's passes (far stand-ins, ground, near) kept
   apart as the reader draws them.

Hard failures in every mode: dropped triangles, a full packet arena, static collision errors
and broken references. Thresholds (budgets, wrong-order pixels, stand-ins) fail the check only
in strict mode; in report mode (the default) they are reported.
"""
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
    'probe': {'radius': 0.3, 'height': 1.6, 'step': 0.32},   # the game schema's probe
    'eye_height': 1.5,
    'thresholds': {
        'near_band': 16.0,              # units: wrong-order pixels nearer than this, or on entities...
        'near_wrong_pixels': 0,         # ...allowed per view
        'far_wrong_fraction': 0.005,    # of the screen, per view, elsewhere
        'coverage_pixels': 0,           # pixels the runtime drew differently from the reference
        'ground_inversion_pixels': 0,   # per view: pixels where ground truly hides what is drawn over it
        'gpu_cycles': 800000,           # per view (80% of 1,000,000)
        'draw_cpu_cycles': 300000,      # wp_draw() plus entity meshes per view (60% of 500,000)
        'cell_triangles': 1600,
        'cell_placements': 100,
        'standin_triangles': 32,
    },
    'sampling': {
        'floor_spacing': 16.0,          # grid over each cell's walkable floors (units)
        'yaws': 4,                      # directions per position
        'yaw_offset_degrees': 22.5,
        'eye_pitches_degrees': [0.0],
        'follow': {'distance': 6.0, 'height': 2.5},     # None: no follow cameras
        'rooftops_per_cell': 2,
        'roof_pitches_degrees': [-20.0],
        'air': {'height': 4.0, 'reach': 48.0},           # None: no cameras between rooftops
        'seams': {'spacing': 32.0},                      # None: no seam cameras
        'layer_combinations': True,
        'max_views': 600,
    },
    'vantage_points': [],               # {"position": [x, y, z], "yaw": deg, "pitch": deg}
    'runtime': {'far_ring': 3, 'clip_near': 0.1, 'near_far': None, 'draw_entities': True, 'ground_first': True},
    'ordering': {'enabled': True, 'edge_margin': 1.0, 'depth_epsilon': 0.001, 'witnesses': 8},
    'collision': {'crack_samples_per_unit': 4.0, 'solid_ray_length': 32.0, 'findings': 50},
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


def sample_views(pack, tris, settings):
    """Cameras: dicts with kind, eye, yaw, pitch (radians), cell."""
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

    cells = sorted(pack.cells, key=lambda ij: (ij[1], ij[0]))
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
        for (i, j) in cells:
            for di, dj in ((1, 0), (0, 1)):
                if (i + di, j + dj) not in pack.cells:
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
    for k, vp in enumerate(settings['vantage_points']):
        add('vantage', vp['position'], math.radians(vp.get('yaw', 0.0)), math.radians(vp.get('pitch', 0.0)),
            {'vantage': k})
    for v in views:
        v['cell'] = [math.floor(v['eye'][0]) >> pack.cell_shift, math.floor(v['eye'][2]) >> pack.cell_shift]
    return views


def thin(views, cap):
    """At most `cap` views (vantage points always kept), each kind thinned evenly in its own
    order: deterministic, and every kind keeps a share proportional to its size."""
    if not cap or len(views) <= cap:
        return views
    kinds = {}
    for v in views:
        kinds.setdefault(v['kind'], []).append(v)
    fixed = len(kinds.get('vantage', []))
    rest = len(views) - fixed
    room = max(0, cap - fixed)
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


def verify(pack_bytes, settings=None, names=None, out_dir=None, tools=None):
    """Checks a world pack. Returns the report (a JSON-ready dict); see docs/WORLDCHECKER.md.
    Raises SettingsError for bad settings and RD.RenderError when the native tools fail."""
    t_start = time.perf_counter()
    cfg = merge_settings(settings)
    th = cfg['thresholds']
    tools = {**default_tools(), **(tools or {})}
    report = {'format': 'mei-world-check', 'version': 1, 'ok': False, 'mode': cfg['mode'], 'settings': cfg,
              'hard_failures': [], 'threshold_failures': []}
    timing = {}
    try:
        pack = decode(pack_bytes)
    except PackError as error:
        report['hard_failures'].append({'code': 'bad_pack', 'message': str(error)})
        report['timing'] = {'total_seconds': time.perf_counter() - t_start}
        return report
    S = 1 << pack.cell_shift
    rt = dict(cfg['runtime'])
    if rt['near_far'] is None:
        rt['near_far'] = 1.5 * S
    report['pack'] = {'sha256': hashlib.sha256(bytes(pack_bytes)).hexdigest(), 'bytes': len(pack_bytes),
                      'cells': len(pack.cells), 'cell_size': S, 'layers': [l[0] for l in pack.layers]}

    # 1. static checks
    t0 = time.perf_counter()
    tris = ST.world_triangles(pack)
    static = {'errors': [], 'warnings': []}
    lim = cfg['collision']['findings']
    cracks, ncrack, nedges = [], 0, 0
    for name, on in [('none', frozenset())] + [(l[0], frozenset([k])) for k, l in enumerate(pack.layers)]:
        found, n, ne, _ = ST.crack_check(pack, tris, on, cfg['probe'], cfg['collision'], lim)
        nedges = max(nedges, ne)
        for f in found:
            f['layers'] = sorted(pack.layers[k][0] for k in on)
            key = (f['code'], tuple(f['cell']), f['floor_tag'], f['beyond_tag'])
            if all((g['code'], tuple(g['cell']), g['floor_tag'], g['beyond_tag']) != key for g in cracks):
                cracks.append(f)
        ncrack += n
    ents, nent = ST.entity_check(pack, tris, cfg['collision'], lim)
    ref_err, ref_warn = ST.reference_check(pack, rt['far_ring'])
    if rt['ground_first']:
        ref_warn += ST.ground_check(pack, rt['near_far'], lim)
    cells, regions = ST.counts(pack)
    static['collision'] = {'triangles': len(tris), 'boundary_edges': nedges, 'findings': cracks[:lim],
                           'entities_in_solid': ents}
    static['cells'] = cells
    static['regions'] = regions
    static['warnings'] = ref_warn
    report['static'] = static
    for f in cracks:
        report['hard_failures'].append({'check': 'collision', **f})
    for f in ents:
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
    cams = sample_views(pack, tris, cfg)
    combos = layer_combinations(pack, cfg)
    ring = int(rt['far_ring'])
    layered_cells = {}
    for (i, j), c in pack.cells.items():
        for lid in c.layers:
            layered_cells.setdefault(lid, set()).add((i, j))
    views = []
    for cam in cams:
        for name, on in combos:
            if on:
                ci, cj = cam['cell']
                if not any(max(abs(a - ci), abs(b - cj)) <= max(1, ring)
                           for lid in on for a, b in layered_cells.get(lid, ())):
                    continue
            views.append({**cam, 'layer_set': name, 'layers': sorted(on)})
    sampled = len(views)
    views = thin(views, cfg['sampling']['max_views'])
    for k, v in enumerate(views):
        v['index'] = k
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
    by_cell = {}
    for inst in insts:
        by_cell.setdefault(inst.cell, []).append(inst)
    describe = _describe(names)
    order_cfg = {**cfg['ordering'], 'near_band': th['near_band']}
    rows = []
    images = []
    t_native = t_ref = 0.0
    compile_s = run_s = 0.0
    diag = []
    with tempfile.TemporaryDirectory(prefix='mei-world-check-') as tmp:
        for g, (ginsts, gviews) in enumerate(_groups(pack, insts, meshes, views, ring)):
            if not gviews:
                continue
            first, nid = {}, 1
            for inst in ginsts:
                first[inst.key] = nid
                nid += len(meshes[inst.mesh].faces)
            ids_ok = nid - 1 <= RD.MAX_ID
            idp = RD.identity_pack(pack.data, ginsts, first, meshes) if ids_ok else bytes(pack.data)
            work = Path(tmp) / f'group{g}'
            work.mkdir()
            t1 = time.perf_counter()
            recs, tm = RD.run_cart(bytes(pack.data), idp, gviews, rt, tools, work)
            t_native += time.perf_counter() - t1
            compile_s += tm['compile_seconds']
            run_s += tm['run_seconds']
            for k, v in enumerate(gviews):
                st, out, _ = recs[2 * k]
                st2, out2, pic = recs[2 * k + 1]
                row = {'index': v['index'], 'kind': v['kind'],
                       'camera': {'eye': v['eye'], 'yaw_degrees': round(math.degrees(v['yaw']), 3),
                                  'pitch_degrees': round(math.degrees(v['pitch']), 3), 'cell': v['cell']},
                       'layer_set': v['layer_set'],
                       'layers': [pack.layers[l][0] for l in v['layers']]}
                if 'vantage' in v:
                    row['vantage'] = v['vantage']
                row['stats'] = {'draw_cpu_cycles': out['draw_cycles'] + out['entity_cycles'],
                                'wp_draw_cycles': out['draw_cycles'], 'entity_cycles': out['entity_cycles'],
                                'frame_cpu_cycles': st['cpu_cycles'], 'gpu_cycles': st['gpu_cycles'],
                                'triangles': st['tris'],
                                'triangles_dropped': max(st['tris_dropped'], st2['tris_dropped']),
                                'arena_bytes': out['arena_bytes'],
                                'arena_full': min(out['arena_left'], out2['arena_left']) < RD.ARENA_FULL,
                                'placements_drawn': out['drawn'], 'ground_drawn': out['ground'],
                                'standins_drawn': out['standins'], 'entities_drawn': out['entities']}
                t1 = time.perf_counter()
                if cfg['ordering']['enabled'] and ids_ok:
                    near_planes = {'near': rt['clip_near'], 'ground': rt['clip_near'], 'far': S / 2}
                    sel = RD.select(pack, by_cell, v['eye'], out2['vp'], set(v['layers']), rt)
                    faces = RD.view_faces(pack, meshes, sel, out2['vp'], out2['origin'], first, near_planes)
                    cmp = RD.compare_view(faces, pic, order_cfg)
                    issues, near_px, far_px = RD.witnesses(cmp, pic, order_cfg, describe, order_cfg['witnesses'])
                    cov = int(cmp['coverage'].sum())
                    ginv = int(cmp['ground_inversion'].sum())
                    row['ordering'] = {'tested_pixels': int((cmp['tested'] & cmp['covered']).sum()),
                                       'tested_background': int((cmp['tested'] & ~cmp['covered']).sum()),
                                       'undecided_pixels': int(cmp['ambiguous'].sum()),
                                       'wrong_near_pixels': near_px, 'wrong_far_pixels': far_px,
                                       'coverage_errors': cov, 'pass_inversions': int(cmp['inversion'].sum()),
                                       'ground_inversions': ginv, 'faces': len(faces), 'issues': issues}
                    if ginv:
                        row['ordering']['ground_issues'] = RD.ground_witnesses(cmp, describe,
                                                                               order_cfg['witnesses'])
                    if cov:
                        p = int(RD.numpy().flatnonzero(cmp['coverage'])[0])
                        row['ordering']['coverage_sample'] = {'pixel': [p % RD.W, p // RD.W], 'drawn_id': int(pic[p]),
                                                              'expected_id': int(cmp['expected'][p])}
                    if out_dir and (near_px or far_px or cov or ginv):
                        diag.append(((near_px + ginv, far_px + cov), v['index'], cmp, pic))
                        diag.sort(key=lambda d: (-d[0][0], -d[0][1], d[1]))
                        del diag[cfg['images']:]
                else:
                    row['ordering'] = {'skipped': 'disabled' if ids_ok else
                                       f'more than {RD.MAX_ID} faces within reach of this camera cell'}
                t_ref += time.perf_counter() - t1
                rows.append(row)
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
        for code, value, limit in (('gpu_cycles', s['gpu_cycles'], th['gpu_cycles']),
                                   ('draw_cpu_cycles', s['draw_cpu_cycles'], th['draw_cpu_cycles'])):
            if limit is not None and value > limit:
                report['threshold_failures'].append({'check': 'budget', 'code': code, **where, 'value': value,
                                                     'limit': limit})
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
        'hard_failures': len(report['hard_failures']),
        'threshold_failures': len(report['threshold_failures']),
    }
    report['ok'] = not report['hard_failures'] and (cfg['mode'] == 'report' or not report['threshold_failures'])
    report['scope'] = ('Static collision checks use the reader\'s exact floor query at sampled points. '
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


def _first(issues, cls):
    return next((i for i in issues if i['class'] == cls), None)


def check_world(context):
    """The World Kit build's entry point (worldkit.build.run_gate): a thin adapter over
    verify(). context carries the staged pack's path ('pack'), the recipe's verification 'mode'
    ('report' or 'enforce', which is this checker's 'strict') and 'thresholds', the game's
    'probe', the staging directory ('stage', where the report and images go, under
    verification/) and optionally the 'compiler' to use (mei-scene-probe is looked for beside
    it). Returns the report, or {'ok': False, 'errors': [...]} when the check could not run."""
    mode = context.get('mode') or 'report'
    settings = {'mode': 'strict' if mode == 'enforce' else mode,
                'thresholds': dict(context.get('thresholds') or {})}
    probe = {k: v for k, v in (context.get('probe') or {}).items() if k in DEFAULTS['probe']}
    if probe:
        settings['probe'] = {**DEFAULTS['probe'], **probe}
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
