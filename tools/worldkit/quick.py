"""The quick tools over a world recipe (docs/WORLDKIT.md, "Quick tools"): `mei_world.py check`
(the World Checker on a few cells or cameras), `floors` (the pack's floor heights over an area),
`textures` (texture VRAM by region, asset and image) and `cracks` (every crack the game's floor
query does not bridge, against the crack baseline). They only read: nothing a build writes
changes, and only `cracks --write-baseline` writes (NAME.cracks.json).

Each needs the world compiled, which for a large level takes most of a minute. The compiled
world (its pack, and what was placed where) is kept in the cache directory with a manifest of
everything the compile read: the world file, the cell files and their folder's listing, the game
schema, the ID lock file, every asset recipe used and the images and sheets its textures read,
the asset directories' listings, the terrain's heights files and images, and the hash of the
kit's code. While all of that is unchanged the compiled world is reused, and a tool takes
seconds; after a change it is compiled again (and kept for the next run).
"""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

from kitcore.vector import ONE
from .schema import WorldError

VERSION = 1


# ---- the compiled world, kept by its inputs


def _listing(directory, kind):
    """What of a directory's contents a compile depends on: its cell files, asset recipes or
    subfolders, by name."""
    d = Path(directory)
    if not d.is_dir():
        return None
    if kind == 'folders':
        return sorted(p.name for p in d.iterdir() if p.is_dir() and not p.name.startswith('.'))
    suffix = '.cell.json' if kind == 'cells' else '.asset.json'
    return sorted(p.name for p in d.iterdir() if p.is_file() and p.name.endswith(suffix))


def _inputs(source, compiled, assets_dir):
    """The manifest of a compile: {'files': {path: sha256}, 'listings': {path: [kind, names]}}."""
    from assetkit.textures import image_files
    from .assets import asset_directories
    from .build import lock_path
    from .cache import file_hash
    w = source.world
    files = [source.world_path, source.game_path, lock_path(source)]
    files += [Path(cs.file) for cs in source.cells if cs.file]
    for asset in compiled.library.assets.values():
        files.append(Path(asset.file))
        files += [Path(asset.file).parent/name for name in image_files(asset.recipe)]
    files += [Path(f) for f in compiled.terrain_files]
    for mat in w.get('terrain', {}).get('materials', {}).values():
        if 'image' in mat.get('texture', {}):
            files.append(source.base/mat['texture']['image'])
    listings = {}
    if 'cell_dir' in w:
        listings[str((source.base/w['cell_dir']).resolve())] = 'cells'
    for d in asset_directories(w, source.base, assets_dir):
        listings[str(d)] = 'assets'
    for entry in w.get('asset_dirs', []):
        if entry == '*' or entry.endswith('/*'):
            listings[str((source.base/entry[:-1]).resolve())] = 'folders'
    return {'files': {str(Path(f).resolve()): file_hash(f) for f in files},
            'listings': {d: [kind, _listing(d, kind)] for d, kind in sorted(listings.items())}}


def _code():
    from .cache import code_hash, runtime_versions
    from . import build
    return {'version': VERSION, 'code': code_hash(build.__file__, __file__), 'python': runtime_versions()['python']}


def _fresh(manifest):
    """Whether everything a stored compile read is as it was."""
    from .cache import file_hash
    if manifest.get('code') != _code():
        return False
    if any(file_hash(f) != h for f, h in manifest['inputs']['files'].items()):
        return False
    return all(_listing(d, kind) == names for d, (kind, names) in manifest['inputs']['listings'].items())


class World:
    """A compiled world as the quick tools read it: the pack's bytes, and `meta` (snapshot())."""

    def __init__(self, pack, meta, cached, seconds, entry=None):
        self.pack, self.meta, self.cached, self.seconds, self.entry = pack, meta, cached, seconds, entry
        self._decoded = None

    @property
    def decoded(self):
        if self._decoded is None:
            from .pack import decode
            self._decoded = decode(self.pack)
        return self._decoded

    def how(self):
        """How the compiled world was had, for the reports."""
        if self.cached:
            return {'compiled': 'cached', 'seconds': round(self.seconds, 2), 'cache': str(self.entry)}
        return {'compiled': 'now', 'seconds': round(self.seconds, 2),
                **({'cache': str(self.entry)} if self.entry else {})}

    def cell(self, ij):
        return self.meta['cells_by_at'].get(f'{ij[0]},{ij[1]}')


def _f(v):
    return round(float(v), 4)


def snapshot(source, compiled):
    """What the quick tools need of a compiled world, as JSON."""
    from assetkit.textures import describe
    from kitcore.texpack import SLOT_BYTES
    from .textures import allocated
    w, game = source.world, source.game
    cells = []
    for plan in compiled.plans:
        c = plan['source'].recipe
        placements = {}
        for pl in plan['placements']:
            spec = pl['spec']
            placements[str(pl['k'])] = {'id': spec['id'], 'asset': pl['asset'].name, 'collision': spec['collision'],
                                        'position': [_f(x) for x in pl['pos']], 'yaw': _f(pl['yaw']),
                                        **({'layer': spec['layer']} if 'layer' in spec else {})}
        entities = [{'id': e['spec']['id'], 'type': e['spec']['type'], 'position': [_f(x) for x in e['pos']],
                     **({'asset': e['asset'].name} if e['asset'] else {})} for e in plan['entities']]
        drawn = sorted({pl['asset'].name for pl in plan['placements']} | {a.name for _, a in plan['scatter']}
                       | {e['asset'].name for e in plan['entities'] if e['asset']})
        cells.append({'id': c['id'], 'at': list(c['at']), 'region': c['region'], 'placements': placements,
                      'entities': entities, 'scatter': sorted({a.name for _, a in plan['scatter']}), 'drawn': drawn})
    textures = {}
    for r, rt in compiled.region_textures.items():
        tiles = {}
        for a, material, tex in rt.uses():
            t = tex.tile
            row = tiles.setdefault(t.key, {'bits': t.bits, 'size': [t.width, t.height], 'window': t.window,
                                           'stored': t.vram_bytes(), 'allocated': allocated(t), 'users': []})
            row['users'].append([a.name, material])
            if 'source' not in row and getattr(tex, 'source', None) is not None:
                row['source'] = describe(tex)
                if 'image' in tex.source and getattr(a, 'file', None):
                    image = (Path(a.file).parent/tex.source['image']).resolve()
                    row['image'] = os.path.relpath(image, source.base)
            if len(getattr(tex, 'frames', ())) > 1:
                row['frames'] = len(tex.frames)
        textures[r] = {'budget': rt.spec.get('budget', len(rt.slots)*SLOT_BYTES), 'slots': list(rt.slots),
                       'tiles': tiles}
    probe = {k: v for k, v in game.get('probe', {}).items()}
    meta = {'format': 'mei-world-quick', 'version': VERSION, 'name': w['name'],
            'recipe': str(source.world_path) if source.world_path else None,
            'cell_size': w['grid']['cell_size'],
            'settings': {'verification': w.get('verification', {}),
                         'runtime': {k: bool(v) for k, v in w.get('runtime', {}).items() if k in ('depth', 'perspective')},
                         'probe': probe},
            'layers': [[name, bool(spec.get('on'))] for name, spec in w.get('layers', {}).items()],
            'regions': list(w['regions']), 'cells': cells, 'textures': textures}
    return meta


def _index(meta):
    meta['cells_by_at'] = {f'{c["at"][0]},{c["at"][1]}': c for c in meta['cells']}
    return meta


def cache_entry(recipe, assets_dir, cache_dir):
    key = hashlib.sha256(json.dumps([str(Path(recipe).resolve()), str(Path(assets_dir).resolve()) if assets_dir else None]
                                    ).encode()).hexdigest()[:20]
    return Path(cache_dir)/'quick'/f'{Path(recipe).name.split(".")[0]}-{key}'


def load_world(recipe, assets_dir=None, cache_dir=None, refresh=False):
    """The compiled world: from the cache when nothing it read has changed, else compiled now (and
    stored when there is a cache directory). Raises WorldError as validate does."""
    from .build import compile_source
    t0 = time.perf_counter()
    entry = cache_entry(recipe, assets_dir, cache_dir) if cache_dir and recipe != '-' else None
    if entry and not refresh:
        try:
            manifest = json.loads((entry/'manifest.json').read_text())
            if _fresh(manifest):
                meta = json.loads((entry/'world.json').read_text())
                pack = (entry/'world.bin').read_bytes()
                if hashlib.sha256(pack).hexdigest() == manifest['pack_sha256']:
                    return World(pack, _index(meta), True, time.perf_counter() - t0, entry)
        except (OSError, ValueError, KeyError):
            pass
    source, compiled = compile_source(recipe, assets_dir)
    meta = snapshot(source, compiled)
    seconds = time.perf_counter() - t0
    if entry:
        manifest = {'code': _code(), 'inputs': _inputs(source, compiled, assets_dir),
                    'pack_sha256': hashlib.sha256(compiled.pack).hexdigest(), 'compile_seconds': round(seconds, 2)}
        entry.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(dir=entry.parent, prefix='.tmp-'))
        try:
            (tmp/'world.bin').write_bytes(compiled.pack)
            (tmp/'world.json').write_text(json.dumps(meta) + '\n')
            (tmp/'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
            old = entry.with_name(entry.name + '.old')
            shutil.rmtree(old, ignore_errors=True)
            if entry.exists():
                entry.rename(old)
            tmp.rename(entry)
            shutil.rmtree(old, ignore_errors=True)
        except OSError:
            pass                            # another run stored it first: this one is still good
        finally:
            if tmp.exists():
                shutil.rmtree(tmp, ignore_errors=True)
    return World(compiled.pack, _index(meta), False, seconds, entry)


# ---- cells and names


def parse_cells(specs, world):
    """--cells: 'I,J' (a cell's `at`) or a cell ID, separated by ';' or given again."""
    out = []
    ids = {c['id']: tuple(c['at']) for c in world.meta['cells']}
    for spec in specs:
        for part in spec.replace(' ', '').split(';'):
            if not part:
                continue
            if part in ids:
                ij = ids[part]
            else:
                try:
                    i, j = (int(n) for n in part.split(','))
                except ValueError:
                    raise WorldError('/arguments/cells', f'{part!r} is neither a cell ID nor I,J (a cell\'s "at").') from None
                ij = (i, j)
                if world.cell(ij) is None:
                    raise WorldError('/arguments/cells', f'No cell at {list(ij)}. Cells: '
                                     + ', '.join(f'{c["id"]} {c["at"]}' for c in world.meta['cells'][:40]) + '.')
            if ij not in out:
                out.append(ij)
    return out


def tag_name(world, ij, tag, near=None):
    """What a pack tag stands for in cell ij: a placement {'id', 'asset', 'cell'}, or terrain,
    sweep, scatter. A placement's collision copied into a neighbouring cell keeps its own cell's
    tag; given a point `near` (x, z), the nearest placement with that tag in the cell or its
    neighbours is taken."""
    from .terrain import TAG_FIELD, TAG_SWEEP, TAG_SCATTER
    if tag == TAG_FIELD:
        return {'id': 'terrain'}
    if tag == TAG_SWEEP:
        return {'id': 'sweep'}
    if tag == TAG_SCATTER:
        return {'id': 'scatter'}
    found = []
    for di in (0, -1, 1):
        for dj in (0, -1, 1):
            c = world.cell((ij[0] + di, ij[1] + dj))
            p = c and c['placements'].get(str(tag))
            if p:
                d = 0 if near is None else math.hypot(p['position'][0] - near[0], p['position'][-1] - near[1])
                found.append((d, abs(di) + abs(dj), c['id'], p))
                if near is None:
                    break
        if found and near is None:
            break
    if not found:
        return {'id': f'tag {tag}'}
    _, _, cid, p = min(found, key=lambda f: (f[0], f[1]))
    return {'id': p['id'], 'asset': p['asset'], 'cell': cid}


# ---- check


def parse_cameras(texts, files):
    from assetkit.preview import parse_camera, cameras_file
    from assetkit.geometry import AssetError
    from kitcore import jsonio
    cams = []
    try:
        for f in files or []:
            cams += cameras_file(jsonio.load(str(f), AssetError))
        cams += [parse_camera(t, len(cams) + k) for k, t in enumerate(texts or [])]
    except AssetError as error:
        raise WorldError(error.path, str(error)) from None
    names = [c['name'] for c in cams]
    if len(set(names)) != len(names):
        raise WorldError('/arguments/camera', 'Camera names must differ.')
    return cams


def check(world, cells=(), cameras=(), tools=None, max_views=200, out_dir=None):
    """The World Checker on the cells' sampled views and static collision and on the cameras,
    with the world's own settings and thresholds (worldkit.verify.check_world's), at most
    max_views sampled views. Returns its report, with each view's heaviest placements named."""
    from . import verify as V
    s = world.meta['settings']
    mode = s['verification'].get('mode', 'report')
    settings = {'mode': 'strict' if mode == 'enforce' else mode,
                'thresholds': dict(s['verification'].get('thresholds', {})),
                'sampling': {'max_views': max_views},
                'vantage_points': [{'position': c['eye'], 'yaw': math.degrees(c['yaw']),
                                    'pitch': math.degrees(c['pitch'])} for c in cameras]}
    if s['runtime']:
        settings['runtime'] = dict(s['runtime'])
    probe = {k: v for k, v in s['probe'].items() if k in V.DEFAULTS['probe']}
    if probe:
        settings['probe'] = {**V.DEFAULTS['probe'], **probe}
    report = V.verify(world.pack, settings, None, out_dir, tools or {}, focus={'cells': list(cells)})
    for row in report.get('views', []):
        if 'vantage' in row:
            row['name'] = cameras[row['vantage']]['name']
        for h in row.get('heaviest', []):
            h.update({k: v for k, v in tag_name(world, h['cell'], h['tag']).items() if k in ('id', 'asset')})
    for f in (report.get('hard_failures', []) + report.get('threshold_failures', [])
              + report.get('static', {}).get('collision', {}).get('findings', [])):
        if 'floor_tag' in f:
            near = (f['at'][0], f['at'][2])
            f['floor'] = tag_name(world, f['cell'], f['floor_tag'], near)['id']
            f['beyond'] = tag_name(world, f['cell'], f['beyond_tag'], near)['id']
    return report


def _n(v):
    return f'{v:,}' if isinstance(v, int) else str(v)


def check_text(report, world, cells, cameras, rows=12):
    """check's plain-text form."""
    th = report['settings']['thresholds']
    out = [f'{world.meta["name"]}: World Checker on '
           + ', '.join(([f'{len(cells)} cell' + ('s' if len(cells) != 1 else '') + ' ('
                         + ' '.join(world.cell(c)['id'] for c in cells) + ')'] if cells else [])
                       + ([f'{len(cameras)} camera' + ('s' if len(cameras) != 1 else '')] if cameras else []))
           + f' ({report["mode"]} mode; compiled world {world.how()["compiled"]}, {world.seconds:.1f} s; '
             f'check {report["timing"]["total_seconds"]:.1f} s)']
    st = report.get('static', {})
    if cells:
        coll = st.get('collision', {})
        out.append(f'Static: {len(coll.get("findings", []))} collision findings, '
                   f'{len(coll.get("entities_in_solid", []))} entities in solid')
        for f in coll.get('findings', [])[:20]:
            out.append(f'  {f["code"]} at {f["at"]}: {f.get("floor", f["floor_tag"])} | {f.get("beyond", f["beyond_tag"])}'
                       + (f' gap {f["gap"]}' if 'gap' in f else '') + (' (on a seam)' if f.get('on_seam') else ''))
        for c in st.get('cells', []):
            cid = world.cell(c['cell'])['id']
            over = [k for k, lim in (('triangles', th['cell_triangles']), ('placements', th['cell_placements']),
                                     ('standin_triangles', th['standin_triangles']))
                    if c[k] is not None and lim is not None and c[k] > lim]
            out.append(f'  cell {cid} {c["cell"]}: {_n(c["triangles"])} triangles (limit {_n(th["cell_triangles"])}), '
                       f'{c["placements"]} placements ({th["cell_placements"]}), stand-in '
                       f'{_n(c["standin_triangles"])} ({th["standin_triangles"]})' + (' OVER: ' + ', '.join(over) if over else ''))
    views = report.get('views', [])
    smp = report.get('sampling', {})
    named = [r for r in views if 'name' in r]
    parts = []
    if cells:
        parts.append(f'{len(views) - len(named)} sampled in the cells, of {smp.get("sampled_views", 0) - len(named)} '
                     'before thinning')
    if cameras:
        parts.append(f'{len(named)} from {len(cameras)} camera' + ('s' if len(cameras) != 1 else '')
                     + (f' x {len(smp.get("layer_sets", []))} layer sets' if len(named) > len(cameras) else ''))
    out.append(f'Views: {len(views)} ({"; ".join(parts)}); limits {_n(th["view_triangles"])} triangles, '
               f'{_n(th["draw_cpu_cycles"])} draw CPU, {_n(th["gpu_cycles"])} GPU cycles')
    sampled = sorted((r for r in views if 'name' not in r),
                     key=lambda r: (-max(r['stats']['triangles'] / th['view_triangles'],
                                         r['stats']['draw_cpu_cycles'] / th['draw_cpu_cycles'],
                                         r['stats']['gpu_cycles'] / th['gpu_cycles']), r['index']))
    shown = named + sampled[:rows]
    if shown:
        out.append(f'  {"view":28} {"tris":>6} {"draw CPU":>9} {"GPU":>9} {"stand-ins":>9}  heaviest placements (faces, level)')
    eyes = set()
    for r in shown:
        s, cam = r['stats'], r['camera']
        label = r.get('name') or f'#{r["index"]} {r["kind"]}'
        if r['layer_set'] != 'none':
            label += f' [{r["layer_set"]}]'
        flags = [k for k, v, lim in (('tris', s['triangles'], th['view_triangles']),
                                     ('cpu', s['draw_cpu_cycles'], th['draw_cpu_cycles']),
                                     ('gpu', s['gpu_cycles'], th['gpu_cycles'])) if lim is not None and v > lim]
        heavy = ', '.join(f'{h.get("id", h["tag"])} {h["faces"]}' + (f' L{h["level"]}' if h['levels'] > 1 else '')
                          for h in r.get('heaviest', [])[:3])
        out.append(f'  {label[:28]:28} {s["triangles"]:>6,} {s["draw_cpu_cycles"]:>9,} {s["gpu_cycles"]:>9,} '
                   f'{s["standins_drawn"]:>9}  {heavy}' + ('  OVER ' + ','.join(flags) if flags else ''))
        o = r['ordering']
        if 'skipped' not in o and (o['wrong_near_pixels'] or o['wrong_far_pixels'] or o['coverage_errors']):
            out.append(f'  {"":28} ordering: {o["wrong_near_pixels"]} wrong near, {o["wrong_far_pixels"]} wrong far, '
                       f'{o["coverage_errors"]} coverage pixels')
        if 'name' in r and r['name'] not in eyes:
            eyes.add(r['name'])
            out.append(f'  {"":28} eye {cam["eye"]} yaw {cam["yaw_degrees"]} pitch {cam["pitch_degrees"]}')
    if len(sampled) > rows:
        out.append(f'  ... {len(sampled) - rows} more sampled views (--rows N, or --json for every row)')
    hard, over = report['hard_failures'], report['threshold_failures']
    out.append(f'{"ok" if report["ok"] else "FAILED"}: {len(hard)} hard failures, {len(over)} over thresholds')
    listed = [f for f in over + hard if f.get('check') != 'collision']     # collision: under Static
    if len(listed) < len(over + hard):
        out.append(f'  {len(over + hard) - len(listed)} collision findings (listed under Static)')
    for f in listed[:12]:
        if 'view' in f:
            v = views[f['view']] if f['view'] < len(views) else {}
            where = f'view {v.get("name") or "#" + str(f["view"])}' + (
                f' [{f["layer_set"]}]' if f.get('layer_set', 'none') != 'none' else '')
        else:
            where = f'cell {f.get("cell")}' + (f' {f["at"]}' if 'at' in f else '')
        what = (f'{f["floor"]} | {f["beyond"]}' if 'floor' in f else
                f'{f["value"]:,}' if isinstance(f.get('value'), int) else str(f.get('value', '')))
        out.append(f'  {f.get("check")}/{f.get("code")} at {where}: {what}'
                   + (f' (limit {f["limit"]:,})' if isinstance(f.get('limit'), int) else ''))
    if len(listed) > 12:
        out.append(f'  ... {len(listed) - 12} more (--json)')
    return '\n'.join(out)


# ---- floors


def floors(world, area, step=1.0, layers=None, below=None):
    """The pack's floor under each point of a grid over area (x0, z0, x1, z1), as the reader's
    wp_floor() finds it from far above (or from `below`: the highest floor at or below that
    height, as a body there finds it): the highest floor, its height and what it belongs to.
    Points without a floor whose four neighbours all have one (within the probe's step of each
    other) are holes; the World Checker's crack findings in the area are listed too."""
    from . import verify_static as ST
    from .verify import DEFAULTS, merge_settings
    pack = world.decoded
    x0, z0, x1, z1 = area
    if x1 < x0 or z1 < z0:
        raise WorldError('/arguments/area', 'The area is X0,Z0,X1,Z1 with X0 <= X1 and Z0 <= Z1.')
    if step <= 0:
        raise WorldError('/arguments/step', 'The step is more than 0.')
    nx, nz = int(math.floor((x1 - x0) / step + 1e-9)) + 1, int(math.floor((z1 - z0) / step + 1e-9)) + 1
    if nx * nz > 250000:
        raise WorldError('/arguments/step', f'{nx} x {nz} points is too many: a larger step, or a smaller area.')
    names = [n for n, _ in world.meta['layers']]
    if layers is None:
        on = frozenset(k for k, (_, start) in enumerate(world.meta['layers']) if start)
    else:
        unknown = [l for l in layers if l not in names]
        if unknown:
            raise WorldError('/arguments/layers', f'No layer {unknown[0]!r}. Layers: {", ".join(names) or "none"}.')
        on = frozenset(names.index(l) for l in layers)
    xs = [round(x0 + k * step, 6) for k in range(nx)]
    zs = [round(z0 + k * step, 6) for k in range(nz)]
    top = (1 << 40) if below is None else round(below * ONE)
    heights, sources = [], []
    for z in zs:
        hrow, srow = [], []
        for x in xs:
            rx, rz = round(x * ONE), round(z * ONE)
            got = ST.reader_floor(pack, rx, top, rz, on)
            if got is None:
                hrow.append(None)
                srow.append(None)
                continue
            ij = pack.cell_of(rx, rz)[0]
            hrow.append(round(got[0] / ONE, 4))
            srow.append((ij, got[1], got[2]))
        heights.append(hrow)
        sources.append(srow)
    probe = merge_settings({'probe': {**DEFAULTS['probe'], **{k: v for k, v in world.meta['settings']['probe'].items()
                                                                if k in DEFAULTS['probe']}}})['probe']
    holes = []
    for b in range(nz):
        for a in range(nx):
            if heights[b][a] is not None:
                continue
            around = [heights[b + db][a + da] for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1))
                      if 0 <= a + da < nx and 0 <= b + db < nz]
            if len(around) == 4 and all(h is not None for h in around) and max(around) - min(around) <= probe['step']:
                holes.append([xs[a], zs[b]])
    # what each floor belongs to, named once per (cell, tag)
    named, legend = {}, {}
    grid = []
    for b, z in enumerate(zs):
        row = []
        for a, x in enumerate(xs):
            s = sources[b][a]
            if s is None:
                row.append(None)
                continue
            key = (s[0], s[1])
            if key not in named:
                named[key] = tag_name(world, s[0], s[1], (x, z))
            n = named[key]
            label = n['id'] if n['id'] in ('terrain', 'sweep', 'scatter') else f'{n.get("cell", "?")}/{n["id"]}'
            legend.setdefault(label, {'what': label, **({'asset': n['asset']} if 'asset' in n else {}),
                                      'points': 0, 'min_y': heights[b][a], 'max_y': heights[b][a],
                                      'surfaces': set()})
            g = legend[label]
            g['points'] += 1
            g['min_y'], g['max_y'] = min(g['min_y'], heights[b][a]), max(g['max_y'], heights[b][a])
            g['surfaces'].add(s[2])
            row.append(label)
        grid.append(row)
    # the World Checker's crack findings in the area
    tris = ST.world_triangles(pack)
    near = ST.near_boxes(tris, [(x0 - 1, z0 - 1, x1 + 1, z1 + 1)])
    cfg = merge_settings({})
    found, _, _, _ = ST.crack_check(pack, near, on, probe, cfg['collision'], 10 ** 9)
    cracks = [f for f in found if x0 <= f['at'][0] <= x1 and z0 <= f['at'][2] <= z1]
    for f in cracks:
        where = (f['at'][0], f['at'][2])
        f['floor'] = tag_name(world, f['cell'], f['floor_tag'], where)['id']
        f['beyond'] = tag_name(world, f['cell'], f['beyond_tag'], where)['id']
    return {'ok': True, 'world': world.meta['name'], 'area': [x0, z0, x1, z1], 'step': step,
            'layers': sorted(names[k] for k in on), 'below': below, 'x': xs, 'z': zs, 'heights': heights, 'from': grid,
            'sources': [dict(g, surfaces=sorted(g['surfaces'])) for g in sorted(legend.values(), key=lambda g: -g['points'])],
            'holes': holes, 'cracks': cracks, 'probe_step': probe['step'], 'compiled': world.how()}


LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'


def grid_text(xs, zs, heights, marks, legend_lines, title):
    """Two maps, north (+Z) up: the heights, then a letter per point for what is there."""
    width = max([5] + [len(f'{h:.2f}') for row in heights for h in row if h is not None])
    out = [title, 'heights (north up; "-": no floor)']
    out.append(' ' * 9 + ' '.join(f'{x:>{width}g}' for x in xs))
    for z, row in zip(reversed(zs), reversed(heights)):
        out.append(f'{z:>8g} ' + ' '.join(f'{h:>{width}.2f}' if h is not None else f'{"-":>{width}}' for h in row))
    out.append('')
    out.append(' ' * 9 + ''.join(f'{x:g}'[-1] if k % 5 == 0 else ' ' for k, x in enumerate(xs)))
    for z, row in zip(reversed(zs), reversed(marks)):
        out.append(f'{z:>8g} ' + ''.join(row))
    return '\n'.join(out + legend_lines)


def floors_text(r):
    letters = {}
    for k, g in enumerate(r['sources']):
        letters[g['what']] = LETTERS[k] if k < len(LETTERS) else '*'
    holes = {(h[0], h[1]) for h in r['holes']}
    marks = []
    for z, row in zip(r['z'], r['from']):
        marks.append(['!' if (x, z) in holes else '.' if w is None else letters[w] for x, w in zip(r['x'], row)])
    legend = ['', 'what (letter: points, heights, surface bytes; "!" a hole, "." no floor)']
    for g in r['sources']:
        legend.append(f'  {letters[g["what"]]} {g["what"]}' + (f' ({g["asset"]})' if 'asset' in g else '')
                      + f': {g["points"]} points, y {g["min_y"]:g}..{g["max_y"]:g}, surface {",".join(map(str, g["surfaces"]))}')
    legend.append(f'holes: {len(r["holes"])}' + (' at ' + ', '.join(f'({x:g}, {z:g})' for x, z in r['holes'][:12])
                                                if r['holes'] else ''))
    legend.append(f'cracks (World Checker): {len(r["cracks"])}')
    for f in r['cracks'][:12]:
        legend.append(f'  {f["code"]} at {f["at"]}: {f["floor"]} | {f["beyond"]}' + (f' gap {f["gap"]}' if 'gap' in f else ''))
    how = r['compiled']
    title = (f'{r["world"]}: the pack\'s floors over x {r["area"][0]:g}..{r["area"][2]:g}, z {r["area"][1]:g}..'
             f'{r["area"][3]:g}, step {r["step"]:g}' + (f', at or below y {r["below"]:g}' if r['below'] is not None else '')
             + f' (layers on: {", ".join(r["layers"]) or "none"}; compiled world '
             f'{how["compiled"]}, {how["seconds"]} s)')
    return grid_text(r['x'], r['z'], r['heights'], marks, legend, title)


# ---- cracks


def load_routes(path):
    """--routes: a JSON object of named polylines, {"NAME": [[x, z], ...]} (world units, seen
    from above)."""
    from kitcore import jsonio
    data = jsonio.load(str(path), WorldError)
    ok = isinstance(data, dict) and all(
        isinstance(pts, list) and len(pts) >= 2 and all(isinstance(p, list) and len(p) == 2 and
                                                        all(isinstance(v, (int, float)) for v in p) for p in pts)
        for pts in data.values())
    if not ok:
        raise WorldError('/arguments/routes', f'{path}: routes are {{"NAME": [[x, z], [x, z], ...]}}, two points or more each.')
    return data


def _route_distance(x, z, pts):
    best = math.inf
    for (ax, az), (bx, bz) in zip(pts, pts[1:]):
        dx, dz = bx - ax, bz - az
        ln = dx * dx + dz * dz
        t = 0.0 if ln == 0 else min(1.0, max(0.0, ((x - ax) * dx + (z - az) * dz) / ln))
        best = min(best, math.hypot(x - ax - t * dx, z - az - t * dz))
    return best


def cracks(world, routes=None, near=3.0, baseline=None):
    """The World Checker's crack and mismatched-edge findings over the whole world, every one
    (the full check lists at most collision.findings), with every layer off and each layer on
    alone, as the full check runs them, and with the game's floor query's bridging (the probe's
    bridge): what remains. Each is named (both floors), gets its route (the nearest of `routes`,
    {name: [[x, z], ...]}, within `near` units) and is sorted: on a route first, then the
    widest first. With `baseline` (NAME.cracks.json's entries) each is new or known, and the
    entries nothing matches are fixed."""
    from . import verify_static as ST
    from .verify import DEFAULTS, merge_settings
    pack = world.decoded
    probe = merge_settings({'probe': {**DEFAULTS['probe'], **{k: v for k, v in world.meta['settings']['probe'].items()
                                                                if k in DEFAULTS['probe']}}})['probe']
    cfg = merge_settings({})
    tris = ST.world_triangles(pack)
    sets = [frozenset()] + [frozenset([k]) for k in range(len(pack.layers))]
    found = []
    for on in sets:
        got, _, _, _ = ST.crack_check(pack, tris, on, probe, cfg['collision'], 10 ** 9)
        for f in got:
            f['layers'] = sorted(pack.layers[k][0] for k in on)
            key = (f['code'], tuple(f['cell']), f['floor_tag'], f['beyond_tag'])
            if all((g['code'], tuple(g['cell']), g['floor_tag'], g['beyond_tag']) != key for g in found):
                found.append(f)
    for f in found:
        where = (f['at'][0], f['at'][2])
        f['floor'] = tag_name(world, f['cell'], f['floor_tag'], where)['id']
        f['beyond'] = tag_name(world, f['cell'], f['beyond_tag'], where)['id']
        if routes:
            d, name = min((_route_distance(where[0], where[1], pts), name) for name, pts in routes.items())
            if d <= near:
                f['route'] = name
                f['route_distance'] = round(d, 2)
    found.sort(key=lambda f: ('route' not in f, -f.get('width', 0.0), f['code'], f['cell'], f['at']))
    out = {'ok': True, 'world': world.meta['name'],
           'probe': {k: probe[k] for k in ('radius', 'step', 'bridge')},
           'bridge_steps': ST.across_steps(probe['bridge']),
           'count': len(found), 'on_routes': sum('route' in f for f in found), 'cracks': found,
           'compiled': world.how()}
    if baseline is not None:
        new, known, fixed = ST.against_baseline(found, baseline)
        for f in found:
            f['new'] = any(f is g for g in new)
        out['baseline'] = {'new': len(new), 'known': len(known), 'fixed': len(fixed), 'fixed_entries': fixed}
        out['ok'] = not new
    return out


def baseline_file(world, found):
    """NAME.cracks.json's content for these findings, sorted by cell and point so that a change
    reads as one."""
    from .verify_static import BASELINE_FORMAT, baseline_entry
    entries = sorted((baseline_entry(f) for f in found), key=lambda e: (e['cell'], e['code'], e['at']))
    return {'format': BASELINE_FORMAT, 'version': 1, 'world': world.meta['name'],
            'note': 'The cracks the World Checker found when this was written (mei_world.py cracks RECIPE '
                    '--write-baseline); the checker lists them as known, not as failures. WORLDCHECKER.md, '
                    '"Crack baseline".',
            'cracks': entries}


def cracks_text(r):
    p = r['probe']
    out = [f'{r["world"]}: {r["count"]} cracks and mismatched floor edges the floor query does not bridge '
           f'(probe radius {p["radius"]:g}, step {p["step"]:g}, bridge {p["bridge"]:g}: {r["bridge_steps"]} steps of 1/16)'
           + (f', {r["on_routes"]} on a route' if r['on_routes'] else '')]
    if 'baseline' in r:
        b = r['baseline']
        out.append(f'against the baseline: {b["new"]} new, {b["known"]} known, {b["fixed"]} fixed')
    for f in r['cracks']:
        mark = ('NEW ' if f.get('new') else '    ') if 'baseline' in r else ''
        width = f'{f["width"]:.3f}' if 'width' in f else '  -  '
        layers = f' [layers {",".join(f["layers"])}]' if f.get('layers') else ''
        route = f' on {f["route"]} ({f["route_distance"]:g})' if 'route' in f else ''
        x, y, z = f['at']
        out.append(f'{mark}{f["code"]:13s} {width} at ({x:g}, {y:g}, {z:g}) cell {f["cell"]}: '
                   f'{f["floor"]} | {f["beyond"]}{layers}{route}')
    for e in (r.get('baseline') or {}).get('fixed_entries', []):
        x, y, z = e['at']
        out.append(f'FIXED {e["code"]} at ({x:g}, {y:g}, {z:g}) cell {e["cell"]}: {e.get("floor", "?")} | {e.get("beyond", "?")}')
    how = r['compiled']
    out.append(f'(compiled world {how["compiled"]}, {how["seconds"]} s)')
    return '\n'.join(out)


# ---- textures


def textures(world, region=None, cells=(), add=None, library=None):
    """Texture VRAM per region as the kit packs it (each distinct tile once, on the 8-texel
    grid, against the region's textures.budget): by asset (its own tiles, and tiles it shares
    with other assets of the region) and by image. cells: only the assets drawn in those cells,
    with their share of their region. add: {region: [asset names]} counted as if placed there
    (compiled from the world's asset directories, through `library`)."""
    from .textures import allocated
    regions = world.meta['regions']
    if region is not None and region not in regions:
        raise WorldError('/arguments/region', f'No region {region!r}. Regions: {", ".join(regions)}.')
    out = {'ok': True, 'world': world.meta['name'], 'regions': {}, 'compiled': world.how()}
    chosen = None
    if cells:
        chosen = {}
        for ij in cells:
            c = world.cell(ij)
            chosen.setdefault(c['region'], set()).update(c['drawn'])
        out['cells'] = [world.cell(ij)['id'] for ij in cells]
    for r in regions:
        if region is not None and r != region:
            continue
        if chosen is not None and r not in chosen:
            continue
        spec = world.meta['textures'].get(r, {'budget': None, 'slots': [], 'tiles': {}})
        tiles = {k: dict(v, users=[list(u) for u in v['users']]) for k, v in spec['tiles'].items()}
        added = []
        for name in (add or {}).get(r, []):
            asset = library.get(name, '/arguments/add')
            added.append(name)
            if not asset.textured:
                continue
            for material, tex in asset.mesh.textures['textures'].items():
                t = tex.tile
                row = tiles.setdefault(t.key, {'bits': t.bits, 'size': [t.width, t.height], 'window': t.window,
                                               'stored': t.vram_bytes(), 'allocated': allocated(t), 'users': [],
                                               'source': None})
                if [name, material] not in row['users']:
                    row['users'].append([name, material])
                if 'image' in tex.source and 'image' not in row:
                    row['image'] = os.path.relpath((Path(asset.file).parent/tex.source['image']).resolve(),
                                                   Path(world.meta['recipe']).parent)
        by_asset = {}
        for key, t in tiles.items():
            for a, _ in t['users']:
                by_asset.setdefault(a, set()).add(key)
        total = sum(t['allocated'] for t in tiles.values())
        assets = []
        for a, keys in by_asset.items():
            own = [k for k in keys if {u[0] for u in tiles[k]['users']} == {a}]
            assets.append({'asset': a, 'tiles': len(keys), 'allocated': sum(tiles[k]['allocated'] for k in keys),
                           'stored': sum(tiles[k]['stored'] for k in keys),
                           'own': sum(tiles[k]['allocated'] for k in own),
                           'shared': sum(tiles[k]['allocated'] for k in keys if k not in own),
                           'shared_with': sorted({u[0] for k in keys if k not in own for u in tiles[k]['users']} - {a}),
                           **({'added': True} if a in added else {})})
        assets.sort(key=lambda a: (-a['allocated'], a['asset']))
        images = {}
        for key, t in tiles.items():
            if t.get('image'):
                g = images.setdefault(t['image'], {'image': t['image'], 'tiles': 0, 'allocated': 0, 'assets': set()})
                g['tiles'] += 1
                g['allocated'] += t['allocated']
                g['assets'].update(u[0] for u in t['users'])
        rr = {'budget': spec['budget'], 'slots': spec['slots'], 'allocated': total,
              'stored': sum(t['stored'] for t in tiles.values()), 'tiles': len(tiles),
              'over': spec['budget'] is not None and total > spec['budget'],
              'assets': assets,
              'images': [dict(g, assets=sorted(g['assets'])) for g in sorted(images.values(), key=lambda g: -g['allocated'])],
              'shared_tiles': [{'tile': k, 'allocated': t['allocated'], 'source': t.get('source'),
                                **({'image': t['image']} if t.get('image') else {}),
                                'users': [f'{a}.{m}' for a, m in t['users']]}
                               for k, t in sorted(tiles.items(), key=lambda kv: -kv[1]['allocated'])
                               if len({u[0] for u in t['users']}) > 1]}
        if added:
            rr['added'] = added
        if chosen is not None:
            mine = chosen[r] | set(added)
            keys = {k for k, t in tiles.items() if any(u[0] in mine for u in t['users'])}
            rr['selected'] = {'assets': sorted(a for a in mine if a in by_asset),
                              'untextured': sorted(a for a in mine if a not in by_asset),
                              'tiles': len(keys), 'allocated': sum(tiles[k]['allocated'] for k in keys),
                              'only_here': sum(tiles[k]['allocated'] for k in keys
                                               if all(u[0] in mine for u in tiles[k]['users']))}
            rr['assets'] = [a for a in assets if a['asset'] in mine]
        out['regions'][r] = rr
    out['ok'] = not any(r['over'] for r in out['regions'].values())
    return out


def textures_text(r):
    how = r['compiled']
    out = [f'{r["world"]}: texture VRAM by region (tiles on the 8-texel grid, each distinct tile once; '
           f'compiled world {how["compiled"]}, {how["seconds"]} s)'
           + (f'; the assets drawn in {", ".join(r["cells"])}' if 'cells' in r else '')]
    for name, g in r['regions'].items():
        budget = f'{g["budget"]:,}' if g['budget'] is not None else '-'
        out.append(f'{name}: {g["allocated"]:,} of {budget} bytes{" OVER" if g["over"] else ""} '
                   f'({g["tiles"]} tiles, {g["stored"]:,} bytes of texels; slots {",".join(map(str, g["slots"]))})'
                   + (f'; with {", ".join(g["added"])} added' if g.get('added') else ''))
        if 'selected' in g:
            s = g['selected']
            out.append(f'  these cells\' assets: {s["allocated"]:,} bytes in {s["tiles"]} tiles, {s["only_here"]:,} of them '
                       f'used by no other asset of the region; untextured: {len(s["untextured"])}')
        if g['assets']:
            out.append(f'  {"asset":32} {"bytes":>8} {"tiles":>5} {"own":>8} {"shared":>8}  shared with')
        for a in g['assets']:
            out.append(f'  {a["asset"][:32]:32} {a["allocated"]:>8,} {a["tiles"]:>5} {a["own"]:>8,} {a["shared"]:>8,}  '
                       + ', '.join(a['shared_with'][:4]) + (' ...' if len(a['shared_with']) > 4 else '')
                       + (' (added)' if a.get('added') else ''))
        if g['images']:
            out.append('  by image:')
            for im in g['images'][:20]:
                out.append(f'    {im["image"]}: {im["allocated"]:,} bytes, {im["tiles"]} tile{"s" if im["tiles"] != 1 else ""}, used by '
                           + ', '.join(im['assets'][:6]) + (' ...' if len(im['assets']) > 6 else ''))
        if g['shared_tiles']:
            out.append(f'  tiles shared between assets: {len(g["shared_tiles"])}')
            for t in g['shared_tiles'][:10]:
                out.append(f'    {t["allocated"]:,} bytes, {t.get("image") or t.get("source")}: ' + ', '.join(t['users'][:6]))
    return '\n'.join(out)


def write_text(text):
    sys.stdout.write(text + '\n')
