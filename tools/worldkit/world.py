"""Reads a world recipe (the world file, its cell files and the game schema), checks it, builds
the assets it references and assembles the pack.

    source = load('garden.world.json')
    compiled = compile_world(source)     # WorldError with a JSON Pointer at the first problem
    compiled.pack, compiled.report, compiled.akr, compiled.lock

Nothing here interprets game data: entity types and parameters are checked against the game's
schema and packed into records; layers, regions and variants are names.
"""
from dataclasses import dataclass, field
from fractions import Fraction
import math
from pathlib import Path
import struct

from kitcore import jsonio
from kitcore.errors import pointer
from kitcore.vector import yaw as turn
from . import ids, merge
from . import pack as P
from .assets import Library, collision_triangles, relative
from .palettes import RegionPalette
from .schema import (WorldError, validate_world, validate_cell_file, validate_game, param_schema, obj,
                     AKARI_KEYWORDS)

DEFAULT_OVERHANG = 8.0
DEFAULT_CEILING_DEGREES = 45.0
REST_EPSILON = Fraction(1, 256)      # a downward face this close above a floor rests on it


@dataclass
class CellSource:
    recipe: dict
    file: str            # None for a cell inline in the world file
    path: str            # JSON Pointer prefix of the cell within `file`


@dataclass
class Source:
    world: dict
    world_path: Path     # None for stdin
    base: Path           # relative paths resolve against this
    game: dict
    game_path: Path
    cells: list          # CellSource


def err(path, message, cell=None):
    return WorldError(path, message, cell.file if cell else None)


def load(path):
    """The world recipe at path ('-' for stdin), its cell files and its game schema, validated
    against their schemas (not yet cross-checked)."""
    world = jsonio.load(path, WorldError)
    validate_world(world)
    world_path = None if path == '-' else Path(path).resolve()
    base = world_path.parent if world_path else Path.cwd()
    if ('cells' in world) == ('cell_dir' in world):
        raise WorldError('/cells', 'Give the cells inline (cells) or as one file each (cell_dir), not both or neither.')
    if not world['regions']:
        raise WorldError('/regions', 'A world has at least one region.')
    game_path = (base / world['game']).resolve()
    if not game_path.is_file():
        raise WorldError('/game', f'No game schema at {game_path}.')
    game = load_game(str(game_path))
    cells = []
    if 'cells' in world:
        cells = [CellSource(c, None, f'/cells/{k}') for k, c in enumerate(world['cells'])]
    else:
        directory = (base / world['cell_dir']).resolve()
        if not directory.is_dir():
            raise WorldError('/cell_dir', f'No directory {directory}.')
        files = sorted(directory.glob('*.cell.json'))
        if not files:
            raise WorldError('/cell_dir', f'No *.cell.json files in {directory}.')
        for f in files:
            recipe = jsonio.load(str(f), WorldError)
            try:
                validate_cell_file(recipe)
            except WorldError as error:
                error.file = str(f)
                raise
            if f.name != recipe['id'] + '.cell.json':
                raise WorldError('/id', f'A cell file is named after its cell: {recipe["id"]}.cell.json.', str(f))
            cells.append(CellSource(recipe, str(f), ''))
    return Source(world, world_path, base, game, game_path, cells)


def load_game(path):
    """A game schema, Mochi (a .mochi file) or JSON ('-' reads JSON from stdin), validated and
    cross-checked. Errors name the file and, in Mochi, the line and column."""
    at = None
    try:
        if not path.endswith('.mochi'):
            game = jsonio.load(path, WorldError)
        else:
            from . import mochi
            with open(path, encoding='utf-8') as stream: text = stream.read(jsonio.MAX_INPUT + 1)
            if len(text) > jsonio.MAX_INPUT: raise WorldError('/input', 'Input exceeds 8 MiB.')
            game, at = mochi.parse(text)
        validate_game(game)
        check_game(game, path)
    except WorldError as error:
        if path != '-': error.file = path
        if at is not None: mochi.locate(error, at)
        raise
    return game


def check_game(game, file):
    """Cross-checks of the game schema the JSON Schema cannot express."""
    worlds = game.get('worlds', [])
    if len(set(worlds)) != len(worlds):
        raise WorldError('/worlds', 'World names must be distinct.', file)
    if len(game['types']) > 0xFFFF:
        raise WorldError('/types', 'At most 65,535 entity types.', file)
    for tname, t in game['types'].items():
        for pname, p in t.get('params', {}).items():
            path = f'/types/{tname}/params/{pname}'
            if pname in AKARI_KEYWORDS:
                raise WorldError(path, f'{pname!r} is an Akari keyword and cannot name a struct field.', file)
            if p['type'] == 'enum':
                if 'values' not in p:
                    raise WorldError(path + '/values', 'An enum lists its values.', file)
                if len(set(p['values'])) != len(p['values']):
                    raise WorldError(path + '/values', 'Enum values must be distinct.', file)
            elif 'values' in p:
                raise WorldError(path + '/values', 'Only enum parameters have values.', file)
            if 'required' in p and p['type'] != 'entity_ref':
                raise WorldError(path + '/required', 'Only entity_ref parameters take required; give others a default or not.', file)
            if p['type'] == 'world_ref' and not worlds:
                raise WorldError(path, 'A world_ref needs the game schema\'s worlds list.', file)
            if p['type'] == 'entity_ref' and 'default' in p:
                raise WorldError(path + '/default', 'An entity_ref has no default; omit it for none.', file)
            if 'default' in p:
                validate_game(p['default'], param_schema(p, worlds), path + '/default')


@dataclass
class Compiled:
    pack: bytes
    report: dict
    akr: str
    game_akr: str
    swatch: bytes
    lock: dict
    lock_changes: dict
    library: Library
    world: object = None
    encoded: dict = field(default_factory=dict)


def cell_shift(size):
    return {16: 4, 32: 5, 64: 6, 128: 7}[size]


def compile_world(source, lock=None, assets_dir=None):
    """Checks everything, builds the referenced assets (without running their verification) and
    encodes the pack. lock is the current ID lock (None: an empty one)."""
    w, game = source.world, source.game
    name = w['name']
    size = w['grid']['cell_size']
    shift = cell_shift(size)
    half = size / 2
    overhang = w.get('overhang', DEFAULT_OVERHANG)
    if overhang > half:
        raise WorldError('/overhang', f'Overhang is at most half a cell ({half}).')
    probe = game['probe']
    pad = w.get('collision', {}).get('pad', probe['radius'])
    if pad < probe['radius']:
        raise WorldError('/collision/pad', f'The pad must be at least the probe radius ({probe["radius"]}), or walls '
                         'near a cell edge are missed by pushes.')
    if pad > half:
        raise WorldError('/collision/pad', f'The pad is at most half a cell ({half}).')
    surfaces = w.get('collision', {}).get('surfaces', {})
    surface_tags = surfaces.get('tags', {})
    unmapped = set()

    def surface_of(tag):
        if tag is None: return surfaces.get('default', 0)
        if tag not in surface_tags:
            unmapped.add(tag)
            return surfaces.get('default', 0)
        return surface_tags[tag]

    library = Library(assets_dir or (source.base / w['assets']).resolve(), source.base)
    warnings = []
    regions = list(w['regions'])
    layer_names = list(w.get('layers', {}))
    groups = []
    for lname, spec in w.get('layers', {}).items():
        if 'group' in spec and spec['group'] not in groups: groups.append(spec['group'])
    if len(groups) > 254:
        raise WorldError('/layers', 'At most 254 exclusive groups.')
    for g in groups:
        on = [l for l, s in w.get('layers', {}).items() if s.get('group') == g and s.get('on')]
        if len(on) > 1:
            raise WorldError('/layers', f'Layers {on} of exclusive group {g!r} are all on at the start; at most one may be.')
    types = list(game['types'])
    worlds = game.get('worlds', [])
    if worlds and name not in worlds:
        warnings.append({'code': 'world_not_listed', 'message': f'World {name!r} is not in the game schema\'s worlds list.'})

    # ---- cells: structure and references
    seen_cells, seen_at, entity_where = {}, {}, {}
    for cs in source.cells:
        c, p = cs.recipe, cs.path
        if c['id'] in seen_cells:
            raise err(p + '/id', f'Two cells are called {c["id"]!r}.', cs)
        seen_cells[c['id']] = cs
        at = tuple(c['at'])
        if at in seen_at:
            raise err(p + '/at', f'Cells {seen_at[at]!r} and {c["id"]!r} are both at {list(at)}.', cs)
        seen_at[at] = c['id']
        if not (-32767 <= at[0] * size and (at[0] + 1) * size <= 32767 and -32767 <= at[1] * size and (at[1] + 1) * size <= 32767):
            raise err(p + '/at', f'Cell {list(at)} lies beyond +-32767 units at cell size {size}.', cs)
        if c['region'] not in w['regions']:
            raise err(p + '/region', f'No region {c["region"]!r}. Regions: {", ".join(regions)}.', cs)
        for k, e in enumerate(c.get('entities', [])):
            if e['id'] in entity_where:
                other = entity_where[e['id']]
                raise err(f'{p}/entities/{k}/id', f'Entity ID {e["id"]!r} is also used in cell {other[0]!r}; entity IDs are world-wide.', cs)
            entity_where[e['id']] = (c['id'], k)

    if len(source.cells) > 1:
        for cs in source.cells:
            if 'standin' not in cs.recipe:
                warnings.append({'code': 'no_standin', 'cell': cs.recipe['id'],
                                 'message': 'The cell has no stand-in; it disappears beyond the near ring.'})

    # ---- assets, collision and placements per cell
    region_palettes = {r: RegionPalette(r, w['regions'][r], pointer('/regions', r)) for r in regions}
    used_layers = set()
    def plan_cell(cs):
        c, p = cs.recipe, cs.path
        i, j = c['at']
        lo_x, lo_z = i * size, j * size
        rp = region_palettes[c['region']]
        plan = {'source': cs, 'placements': [], 'merged': {}, 'collision': [], 'entities': [], 'layers': [],
                'stripped': 0, 'standin': None}

        def use_layer(lname, path):
            if lname not in w.get('layers', {}):
                raise err(path, f'No layer {lname!r}. Declare it in the world\'s layers.', cs)
            used_layers.add(lname)
            if lname not in plan['layers']: plan['layers'].append(lname)

        def inside(pos, path, what):
            if not (lo_x <= pos[0] < lo_x + size and lo_z <= pos[2] < lo_z + size):
                raise err(path, f'{what} at {pos} is outside cell {c["id"]!r} (x {lo_x}..{lo_x + size}, '
                          f'z {lo_z}..{lo_z + size}, high sides excluded).', cs)

        seen = set()
        for k, pl in enumerate(c.get('placements', [])):
            pp = f'{p}/placements/{k}'
            if pl['id'] in seen:
                raise err(pp + '/id', f'Two placements in cell {c["id"]!r} are called {pl["id"]!r}.', cs)
            seen.add(pl['id'])
            if len(c['placements']) > 0xFFFE:
                raise err(p + '/placements', 'At most 65,534 placements a cell.', cs)
            asset = library.get(pl['asset'], pp + '/asset', cs.file)
            rp.add_asset(asset)
            inside(pl['position'], pp + '/position', 'Placement')
            if 'layer' in pl: use_layer(pl['layer'], pp + '/layer')
            yaw = pl.get('yaw', 0)
            if yaw % 360 and not asset.vertical:
                warnings.append({'code': 'yaw_shading', 'cell': c['id'], 'placement': pl['id'],
                                 'message': f'Asset {asset.name!r} bakes directional light in its own frame and is placed at '
                                            f'yaw {yaw}, so it is lit from a different side than its neighbours. '
                                            'Use lighting.mode "vertical" in its recipe.'})
            coll = pl['collision']
            if coll == 'none':
                tris = []
            else:
                casset = asset if coll == 'self' else library.get(coll, pp + '/collision', cs.file, 'collision')
                tris = collision_triangles(casset, surface_of)
            for a, b, cc, surface in tris:
                corners = [tuple(x + o for x, o in zip(turn(v, yaw), pl['position'])) for v in (a, b, cc)]
                plan['collision'].append(P.Tri(*corners, surface=surface, layer=pl.get('layer'), tag=k))
            plan['placements'].append({'k': k, 'spec': pl, 'asset': asset, 'yaw': yaw})
        if 'standin' in c:
            plan['standin'] = library.get(c['standin'], p + '/standin', cs.file, 'standin')
            rp.add_asset(plan['standin'])
        for k, e in enumerate(c.get('entities', [])):
            ep = f'{p}/entities/{k}'
            if e['type'] not in game['types']:
                raise err(ep + '/type', f'No entity type {e["type"]!r} in the game schema. Types: {", ".join(types)}.', cs)
            inside(e['position'], ep + '/position', 'Entity')
            if 'layer' in e: use_layer(e['layer'], ep + '/layer')
            spec = game['types'][e['type']]
            params = spec.get('params', {})
            values = e.get('params', {})
            schema = obj({n: param_schema(q, worlds) for n, q in params.items()},
                         [n for n, q in params.items() if ('default' not in q and q['type'] != 'entity_ref') or q.get('required')])
            validate_world(values, schema, ep + '/params')
            for pname, q in params.items():
                if q['type'] == 'entity_ref' and pname in values and values[pname] not in entity_where:
                    raise err(f'{ep}/params/{pname}', f'No entity {values[pname]!r} in this world.', cs)
            asset = library.get(e['asset'], ep + '/asset', cs.file, 'entity') if 'asset' in e else None
            if asset: rp.add_asset(asset)
            ecoll = []
            if 'collision' in e:
                casset = library.get(e['collision'], ep + '/collision', cs.file, 'collision')
                ecoll = [P.Tri(a, b, cc, surface=s, tag=k) for a, b, cc, s in collision_triangles(casset, surface_of)]
            plan['entities'].append({'k': k, 'spec': e, 'asset': asset, 'collision': ecoll, 'values': values})
        if len(plan['layers']) > P.MAX_CELL_LAYERS:
            raise err(p, f'Cell {c["id"]!r} uses {len(plan["layers"])} layers ({", ".join(plan["layers"])}); '
                      f'a cell holds at most {P.MAX_CELL_LAYERS}.', cs)
        plan['collision'], plan['stripped'] = strip_resting(plan['collision'], probe)
        return plan

    plans = []          # per cell: dict of what goes into the pack
    for cs in source.cells:
        try:
            plans.append(plan_cell(cs))
        except WorldError as error:
            if error.file is None: error.file = cs.file
            raise

    for lname in layer_names:
        if lname not in used_layers:
            warnings.append({'code': 'unused_layer', 'layer': lname, 'message': 'No placement or entity uses this layer.'})

    # ---- palettes: each region's entries, then the assets' faces moved to them
    palette = w.get('palette', {})
    slot, row = palette.get('swatch_slot', 14), palette.get('swatch_row', 0)
    nxt = palette.get('first', 0)
    for r in regions:
        nxt = region_palettes[r].assign(nxt) if region_palettes[r].by_key or 'palettes' in w['regions'][r] else nxt
        if not region_palettes[r].by_key and 'variants' in w['regions'][r]:
            warnings.append({'code': 'variants_without_entries', 'region': r,
                             'message': 'The region has palette variants but no palette-backed material is drawn in it.'})
    taken = {}
    for r in regions:
        rp = region_palettes[r]
        for pal in range(rp.first or 0, (rp.first or 0) + rp.count):
            if pal in taken:
                raise WorldError(pointer('/regions', r) + '/palettes', f'Regions {taken[pal]!r} and {r!r} both use '
                                 f'4-bit palette {pal}; regions never share palettes.')
            taken[pal] = r
    any_palette = any(rp.entries for rp in region_palettes.values())

    # ---- the pack's description
    variants_shown = {}
    pregions = []
    for r in regions:
        rp = region_palettes[r]
        if rp.entries:
            rows, shown = rp.variants(warnings)
            variants_shown[r] = shown
            pregions.append(P.Region(r, first_colour=rp.first_colour, variants=rows))
        else:
            pregions.append(P.Region(r))
    group_of = {g: n for n, g in enumerate(groups)}
    players = [P.Layer(l, group_of.get(s.get('group'), P.NO_GROUP), bool(s.get('on')))
               for l, s in w.get('layers', {}).items()]
    cells = []
    merged_report = {}
    for plan in plans:
        cs = plan['source']
        c = cs.recipe
        rp = region_palettes[c['region']]
        i, j = c['at']
        centre = (i * size + half, 0, j * size + half)
        cell = P.Cell(i, j, region=regions.index(c['region']), layers=list(plan['layers']))
        to_merge = {}
        for pl in plan['placements']:
            binary = rp.relocated(pl['asset'], slot, row)
            if pl['spec'].get('merge'):
                to_merge.setdefault(pl['spec'].get('layer'), []).append((binary, pl))
                continue
            cell.placements.append(P.Placement(binary, tuple(pl['spec']['position']), pl['yaw'],
                                               pl['spec'].get('layer'), pl['k']))
        for lname, items in sorted(to_merge.items(), key=lambda kv: (kv[0] is not None, kv[0] or '')):
            meshes = merge.merge([(b, pl['spec']['position'], pl['yaw']) for b, pl in items], centre)
            for m in meshes:
                cell.placements.append(P.Placement(m, centre, 0.0, lname, 0xFFFF))
            merged_report.setdefault(c['id'], []).append(
                {'layer': lname, 'placements': [pl['spec']['id'] for _, pl in items], 'meshes': len(meshes)})
        if plan['standin']:
            cell.standin = rp.relocated(plan['standin'], slot, row)
        cell.collision = plan['collision']
        for e in plan['entities']:
            spec = e['spec']
            cell.entities.append(P.Entity(types.index(spec['type']), tuple(spec['position']), spec.get('yaw', 0),
                                          spec.get('layer'), mesh=rp.relocated(e['asset'], slot, row) if e['asset'] else None,
                                          collision=e['collision']))
        cells.append(cell)

    world = P.World(cells=cells, cell_shift=shift, layers=players, regions=pregions, coll_pad=pad,
                    overhang=overhang, floor_max_degrees=probe['floor_max_degrees'],
                    ceiling_max_degrees=probe.get('ceiling_max_degrees', DEFAULT_CEILING_DEGREES))

    # ---- entity numbers, saved bits, parameter records
    numbers = P.entity_numbers(world)
    number_of = {}
    for cell, plan in zip(cells, plans):
        for k, e in enumerate(plan['entities']):
            number_of[e['spec']['id']] = numbers[(cell.i, cell.j, k)]
    saved = [e['spec']['id'] for plan in plans for e in plan['entities'] if game['types'][e['spec']['type']].get('saved')]
    renames = {}
    for plan in plans:
        for e in plan['entities']:
            if 'was' in e['spec']:
                renames[e['spec']['id']] = (e['spec']['was'], f'{plan["source"].path}/entities/{e["k"]}/was')
    lock = lock or ids.empty(name)
    new_lock, changes = ids.update(lock, saved, renames)
    for cell, plan in zip(cells, plans):
        for pe, e in zip(cell.entities, plan['entities']):
            spec = e['spec']
            pe.saved_bit = new_lock['bits'].get(spec['id'], -1) if game['types'][spec['type']].get('saved') else -1
            fields, names = [], []
            for pname, q in game['types'][spec['type']].get('params', {}).items():
                v = e['values'].get(pname, q.get('default'))
                kind = q['type']
                if kind == 'enum': v = q['values'].index(v)
                elif kind == 'entity_ref': v = number_of[v] if v is not None else 0xFFFFFFFF
                elif kind == 'world_ref': v = worlds.index(v)
                elif kind == 'name':
                    names.append((record_offset(fields, kind), v))
                    v = 0
                fields.append((kind, v))
            pe.params = P.pack_params(fields) if fields else b''
            pe.names = names

    encoded = {}
    try:
        data = P.encode(world, encoded)
    except P.PackError as error:
        raise WorldError('/cells', f'The pack cannot hold this world: {error}.') from error
    if unmapped:
        warnings.append({'code': 'unmapped_tags', 'tags': sorted(unmapped),
                         'message': 'Collision faces with these material tags get the default surface byte. '
                                    'Map them in collision.surfaces.tags if the game should tell them apart.'})

    report = make_report(source, world, data, plans, library, region_palettes, variants_shown, encoded, warnings,
                         new_lock, changes, merged_report, number_of, pad)
    compiled = Compiled(data, report, '', '', SWATCH if any_palette else b'', new_lock, changes, library, world, encoded)
    from .akr import world_source, game_source
    compiled.akr = world_source(source, compiled, region_palettes, slot, row, number_of, groups)
    compiled.game_akr = game_source(game)
    return compiled


SWATCH = bytes(2 * j | (2 * j + 1) << 4 for j in range(8))


def record_offset(fields, kind):
    """Where a 4-byte field appended to fields lands in pack_params' layout."""
    return len(P.pack_params(fields + [(kind, 0)])) - 4


def strip_resting(tris, probe):
    """Drops downward faces that rest on a floor: the bottom of a box standing on the ground would
    otherwise be a ceiling at ground level that catches a body walking over it. A face is dropped
    when a floor lies under its centroid within 1/256 unit."""
    fc = math.cos(math.radians(probe['floor_max_degrees']))
    cc = math.cos(math.radians(probe.get('ceiling_max_degrees', DEFAULT_CEILING_DEGREES)))
    exact = [tuple(tuple(Fraction(x) for x in v) for v in (t.a, t.b, t.c)) for t in tris]
    kinds = []
    for v in exact:
        n = P.front_normal(*v)
        kinds.append(P.classify(n, fc, cc) if P.dot3(n, n) else None)
    floors = [(v, t) for v, t, k in zip(exact, tris, kinds) if k == P.KIND_FLOOR]
    keep, stripped = [], 0
    for v, t, k in zip(exact, tris, kinds):
        if k == P.KIND_CEILING:
            g = tuple(sum(p[q] for p in v) / 3 for q in range(3))
            if any(t.layer == ft.layer or ft.layer is None for fv, ft in floors if resting(fv, g)):
                stripped += 1
                continue
        keep.append(t)
    return keep, stripped


def resting(v, g):
    """Whether point g lies over floor triangle v (seen from above) within REST_EPSILON of it."""
    sides = []
    for e in range(3):
        p, q = v[e], v[(e + 1) % 3]
        sides.append((q[0] - p[0]) * (g[2] - p[2]) - (q[2] - p[2]) * (g[0] - p[0]))
    if not (all(s >= 0 for s in sides) or all(s <= 0 for s in sides)):
        return False
    n = P.front_normal(*v)
    h = v[0][1] - (n[0] * (g[0] - v[0][0]) + n[2] * (g[2] - v[0][2])) / n[1]
    return abs(h - g[1]) <= REST_EPSILON


def make_report(source, world, data, plans, library, region_palettes, variants_shown, encoded, warnings,
                lock, changes, merged, number_of, pad):
    decoded = P.decode(data)
    cells, regions = [], {}
    for plan, pcell in zip(plans, world.cells):
        c = plan['source'].recipe
        d = decoded.cells[(pcell.i, pcell.j)]
        always = sum(mesh_faces(p.mesh) for p in pcell.placements if p.layer is None)
        by_layer = {}
        for p in pcell.placements:
            if p.layer is not None: by_layer[p.layer] = by_layer.get(p.layer, 0) + mesh_faces(p.mesh)
        coll = d.coll
        coll_counts = {'floors': len(coll.floors), 'walls': len(coll.walls), 'ceilings': len(coll.ceilings)} if coll else \
            {'floors': 0, 'walls': 0, 'ceilings': 0}
        coll_bytes = 0
        if coll:
            g = 1 << coll.grid_shift
            coll_bytes = P.COLL_SIZE + P.FLAT_SIZE * (len(coll.floors) + len(coll.ceilings)) + P.WALL_SIZE * len(coll.walls) + \
                P.BUCKET_SIZE * g * g + 2 * sum(len(f) + len(wl) + len(cl) for f, wl, cl in coll.lists)
        meshes = {p.mesh for p in pcell.placements} | ({pcell.standin} if pcell.standin else set()) | \
            {e.mesh for e in pcell.entities if e.mesh}
        entry = {
            'id': c['id'], 'at': c['at'], 'region': c['region'],
            'file': relative(plan['source'].file, source.base) if plan['source'].file else None,
            'placements': len(c.get('placements', [])), 'drawn_placements': len(pcell.placements),
            'triangles': {'always': always, 'by_layer': by_layer,
                          'most': always + sum(by_layer.values())},
            'standin_triangles': mesh_faces(pcell.standin) if pcell.standin else None,
            'entities': len(pcell.entities), 'layers': list(pcell.layers),
            'collision': dict(coll_counts, grid=(1 << coll.grid_shift) if coll else 0,
                              stripped_resting=plan['stripped'],
                              placement_tags={str(pl['k']): pl['spec']['id'] for pl in plan['placements']}),
            'bytes': {'records': P.CELL_SIZE + P.PLACEMENT_SIZE * len(pcell.placements) + P.ENTITY_SIZE * len(pcell.entities)
                      + sum(len(e.params) for e in pcell.entities),
                      'collision': coll_bytes, 'meshes': sum(len(m) for m in meshes)},
        }
        if c['id'] in merged: entry['merged'] = merged[c['id']]
        cells.append(entry)
        r = regions.setdefault(c['region'], {'cells': [], 'triangles': 0, 'placements': 0, 'collision_triangles': 0})
        r['cells'].append(c['id'])
        r['triangles'] += entry['triangles']['most']
        r['placements'] += entry['drawn_placements']
        r['collision_triangles'] += sum(coll_counts.values())
    for name, rp in region_palettes.items():
        r = regions.setdefault(name, {'cells': [], 'triangles': 0, 'placements': 0, 'collision_triangles': 0})
        if rp.entries:
            r['palette'] = rp.describe()
            r['variants'] = variants_shown.get(name, {})
        else:
            r['palette'] = None
    mesh_pool = sum(len(data[o:o + 16 + 16 * struct.unpack_from('<H', data, o)[0] + 36 * struct.unpack_from('<H', data, o + 2)[0]])
                    for o in decoded.meshes)
    return {
        'ok': True, 'format': 'mei-world-report', 'version': 1, 'name': source.world['name'],
        'recipe_sha256': jsonio.sha256({'world': source.world, 'cells': [cs.recipe for cs in source.cells]}),
        'game_sha256': jsonio.sha256(source.game),
        'pack': {'bytes': len(data), 'version': f'{P.VERSION_MAJOR}.{P.VERSION_MINOR}', 'cells': len(world.cells),
                 'cell_size': 1 << world.cell_shift, 'meshes': len(decoded.meshes), 'mesh_pool_bytes': mesh_pool,
                 'entities': len(decoded.entities), 'layers': [l.name for l in world.layers],
                 'coll_pad': pad, 'overhang': world.overhang,
                 'floor_max_degrees': world.floor_max_degrees, 'ceiling_max_degrees': world.ceiling_max_degrees},
        'cells': cells, 'regions': regions,
        'entities': {k: {'number': v} for k, v in sorted(number_of.items(), key=lambda kv: kv[1])},
        'ids': {'saved_bits': lock['next_bit'], 'live': len(lock['bits']), 'retired': len(lock['retired']),
                'changes': changes},
        'assets': {n: a.summary() for n, a in sorted(library.assets.items())},
        'warnings': warnings,
    }


def mesh_faces(binary):
    return struct.unpack_from('<H', binary, 2)[0]
