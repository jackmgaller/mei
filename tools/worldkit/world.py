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
import hashlib
import math
from pathlib import Path
import struct

from kitcore import jsonio
from kitcore.errors import pointer
from kitcore.vector import yaw as turn
from . import farground, ids, merge, quads
from . import pack as P
from .assets import Library, collision_triangles, relative
from .palettes import RegionPalette
from .textures import RegionTextures, relocated_palette
from . import backdrop as BD
from .terrain import TAG_FIELD, TAG_SWEEP, TAG_SCATTER, compile_terrain, q16
from .scatter import scatter_items
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
    game_text: bytes = b''   # the game schema file as written (comments and layout kept)


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
    game_text = game_path.read_bytes()
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
    return Source(world, world_path, base, game, game_path, cells, game_text)


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
    terrain_files: list = field(default_factory=list)   # heights files the terrain read
    terrain: object = None                              # terrain.Result, or None
    water: bytes = b''                                  # NAME.water.bin (wp_water()), or empty


@dataclass
class TerrainAsset:
    """What RegionPalette needs of the terrain to give its materials region entries: a name
    (owners read "terrain.MATERIAL"), a manifest's entries and, to relocate, a mesh."""
    name: str
    manifest: dict
    binary: bytes = b''


class TerrainTextures:
    """What RegionTextures needs of the terrain's textured materials: an asset's name, materials
    and textures (WORLDKIT.md, "Textured terrain"). A material with faces drawn through a texture
    window also brings its tile as loaded, as 'MATERIAL window'."""
    textured = True

    def __init__(self, name, materials, textures, windowed):
        self.name, self.materials = name, dict(materials)
        textures = dict(textures)
        for m in sorted(windowed & set(textures)):
            self.materials[f'{m} window'] = materials[m]
            textures[f'{m} window'] = type('W', (), {'tile': textures[m].window_tile})()
        self.mesh = type('M', (), {'textures': {'textures': textures}})()


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

    library = Library(assets_dir or (source.base / w['assets']).resolve(), source.base,
                      [(source.base / d).resolve() for d in w.get('asset_dirs', [])])
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

    auto_standins = w.get('standins')
    if auto_standins and len(regions) > 1:
        raise WorldError('/standins', 'Stand-ins made by the kit keep their placements\' textures, and a stand-in '
                         'is drawn whichever region is loaded: they need a world with one region. Give each cell '
                         'its own stand-in instead.')
    for cid in (auto_standins or {}).get('cells', {}):
        if cid not in seen_cells:
            raise WorldError(pointer('/standins/cells', cid), f'No cell {cid!r}.')
    if len(source.cells) > 1 and not auto_standins:
        for cs in source.cells:
            if 'standin' not in cs.recipe:
                warnings.append({'code': 'no_standin', 'cell': cs.recipe['id'],
                                 'message': 'The cell has no stand-in; it disappears beyond the near ring.'})

    # ---- terrain: heightfields and sweeps, made in world coordinates and cut per cell
    terrain = compile_terrain(w, source.base, size, seen_at, surface_of, warnings, overhang, probe["floor_max_degrees"])
    scattered, scatter_report = scatter_items(w, terrain, size, seen_at, warnings)

    def on_ground(spec, path, cs):
        """A placement's or entity's position: as given, or on the ground ([x, z], or drop) and
        lifted (WORLDKIT.md, "On the ground")."""
        pos = spec['position']
        drop = spec.get('drop', False)
        if len(pos) == 3 and not drop:
            if 'lift' in spec:
                raise err(path + '/lift', 'lift raises what is put on the ground: give the position as [x, z], or drop.', cs)
            return tuple(pos)
        if not terrain:
            raise err(path + '/position', 'Putting things on the ground ([x, z] or drop) needs terrain: a field or a sweep.', cs)
        if drop and len(pos) == 2:
            raise err(path + '/drop', 'drop lowers [x, y, z] to the floor below y; [x, z] is on the ground already.', cs)
        hit = terrain.floors().at(pos[0], pos[-1], pos[1] if drop else None)
        if hit is None:
            raise err(path + '/position', f'No terrain or sweep floor under ({pos[0]:g}, {pos[-1]:g})'
                      + (f' at or below {pos[1]:g}.' if drop else '.'), cs)
        return (pos[0], q16(hit[0] + spec.get('lift', 0.0)), pos[-1])

    # ---- assets, collision and placements per cell
    region_palettes = {r: RegionPalette(r, w['regions'][r], pointer('/regions', r)) for r in regions}
    region_textures = {r: RegionTextures(r, w['regions'][r], pointer('/regions', r), w.get('textures'))
                       for r in regions}
    used_layers = set()
    def plan_cell(cs):
        c, p = cs.recipe, cs.path
        i, j = c['at']
        lo_x, lo_z = i * size, j * size
        rp = region_palettes[c['region']]
        rt = region_textures[c['region']]
        plan = {'source': cs, 'placements': [], 'merged': {}, 'collision': [], 'entities': [], 'layers': [],
                'stripped': 0, 'standin': None, 'scatter': []}

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
            rt.add_asset(asset)
            pos = on_ground(pl, pp, cs)
            inside(pos, pp + '/position', 'Placement')
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
                corners = [tuple(x + o for x, o in zip(turn(v, yaw), pos)) for v in (a, b, cc)]
                plan['collision'].append(P.Tri(*corners, surface=surface, layer=pl.get('layer'), tag=k))
            plan['placements'].append({'k': k, 'spec': pl, 'asset': asset, 'yaw': yaw, 'pos': pos})
        for it in scattered.get((i, j), []):
            asset = library.get(it.asset, it.path + '/asset', None, 'scatter')
            rp.add_asset(asset)
            rt.add_asset(asset)
            if it.layer: use_layer(it.layer, it.path)
            if it.collision != 'none':
                casset = asset if it.collision == 'self' else library.get(it.collision, it.path + '/collision', None, 'collision')
                for a, b, cc, surface in collision_triangles(casset, surface_of):
                    corners = [tuple(x + o for x, o in zip(turn(v, it.yaw), it.position)) for v in (a, b, cc)]
                    plan['collision'].append(P.Tri(*corners, surface=surface, layer=it.layer, tag=TAG_SCATTER))
            plan['scatter'].append((it, asset))
        if 'standin' in c:
            plan['standin'] = library.get(c['standin'], p + '/standin', cs.file, 'standin')
            if plan['standin'].textured:
                raise err(p + '/standin', f'Stand-in {c["standin"]!r} has textured materials. A stand-in is drawn '
                          'whichever region is loaded, so it cannot use a region\'s textures: give it palette-backed '
                          'or plain materials.', cs)
            rp.add_asset(plan['standin'])
        for k, e in enumerate(c.get('entities', [])):
            ep = f'{p}/entities/{k}'
            if e['type'] not in game['types']:
                raise err(ep + '/type', f'No entity type {e["type"]!r} in the game schema. Types: {", ".join(types)}.', cs)
            epos = on_ground(e, ep, cs)
            inside(epos, ep + '/position', 'Entity')
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
            if asset:
                rp.add_asset(asset)
                rt.add_asset(asset)
            ecoll = []
            if 'collision' in e:
                casset = library.get(e['collision'], ep + '/collision', cs.file, 'collision')
                ecoll = [P.Tri(a, b, cc, surface=s, tag=k) for a, b, cc, s in collision_triangles(casset, surface_of)]
            plan['entities'].append({'k': k, 'spec': e, 'asset': asset, 'collision': ecoll, 'values': values, 'pos': epos})
        if len(plan['layers']) > P.MAX_CELL_LAYERS:
            raise err(p, f'Cell {c["id"]!r} uses {len(plan["layers"])} layers ({", ".join(plan["layers"])}); '
                      f'a cell holds at most {P.MAX_CELL_LAYERS}.', cs)
        if terrain and (i, j) in terrain.pieces:
            if len(c.get('placements', [])) > TAG_SCATTER:
                raise err(p + '/placements', f'At most {TAG_SCATTER:,} placements in a cell with terrain: '
                          'the tags above are the terrain\'s.', cs)
            plan['collision'].extend(terrain.collision.get((i, j), []))
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

    # terrain materials join each region's palette as one asset named "terrain" would
    terrain_assets = {}
    if terrain:
        region_of = {tuple(cs.recipe['at']): cs.recipe['region'] for cs in source.cells}
        used = {}
        for key, pieces in terrain.pieces.items():
            for piece in pieces:
                used.setdefault(region_of[key], set()).update(piece.materials)
        for r in regions:
            if r not in used:
                continue
            entries = []
            for e in (terrain.palette['entries'] if terrain.palette else []):
                mats = [m for m in e['materials'] if m in used[r]]
                if mats:
                    entries.append(dict(e, materials=mats))
            terrain_assets[r] = TerrainAsset('terrain', {'entries': entries})
            region_palettes[r].add_asset(terrain_assets[r])
            # textured terrain materials join the region's texture set as one more asset's
            drawn = {m: t for m, t in terrain.textures.items() if m in used[r]}
            if drawn:
                region_textures[r].add_asset(TerrainTextures('terrain', w['terrain']['materials'], drawn,
                                                                   terrain.windowed))

    # ---- levels of detail: the switch distances per asset (the recipe's, then the world's)
    lod_cfg = w.get('lod', {})
    lod_report = {}
    for aname in lod_cfg.get('assets', {}):
        if aname not in library.assets or 'lod' not in library.assets[aname].recipe:
            warnings.append({'code': 'lod_unused', 'asset': aname, 'message': 'lod.assets names an asset that '
                             'no placement draws, or whose recipe has no lod.'})

    def lod_entry(asset):
        """The asset's levels as the pack holds them: {'distances', 'cull', 'band', 'off', ...}, or
        None for an asset without lod. A recipe whose lod has only a cull distance gets a cull mark."""
        if not asset.levels and 'lod' not in asset.recipe:
            return None
        if asset.name not in lod_report:
            spec = dict(asset.recipe['lod'])
            over = lod_cfg.get('assets', {}).get(asset.name, {})
            ap = pointer('/lod/assets', asset.name)
            distances = [lv['distance'] for lv in spec.get('levels', [])]
            if 'distances' in over:
                if len(over['distances']) != len(distances):
                    raise WorldError(ap + '/distances', f'Asset {asset.name!r} has {len(distances)} levels after '
                                     f'level 0; give one distance for each.')
                distances = list(over['distances'])
            cull = over['cull'] if 'cull' in over else spec.get('cull')
            band = over.get('band', spec.get('band', 1.0))
            scale = lod_cfg.get('scale', 1.0)
            distances = [d * scale for d in distances]
            cull = cull * scale if cull is not None else None
            marks = distances + ([cull] if cull is not None else [])
            entry = {'distances': distances, 'cull': cull, 'band': band, 'off': bool(over.get('off')),
                     'triangles': [r['triangles'] for r in asset.report.get('lod', {}).get('levels', [])]}
            prev = 0
            for d in ([] if over.get('off') else marks):
                if d - band <= prev + band or d + band > P.MAX_LOD_DISTANCE:
                    raise WorldError(ap if over else '/lod/scale', f'Asset {asset.name!r}: switch distances '
                                     f'{marks} must increase by more than twice the band ({band}) and stay '
                                     f'within {P.MAX_LOD_DISTANCE} units.')
                prev = d
            lod_report[asset.name] = entry
        return lod_report[asset.name]

    def level_meshes(asset, rp, slot, row):
        """The asset's levels 1.. as relocated mesh bytes for region rp."""
        if asset.textured:
            rt = region_textures[rp.name]
            return [rt.binary(asset, relocated_palette(asset, rp, slot, row), k) for k in range(1, len(asset.levels) + 1)]
        return rp.relocated_levels(asset, slot, row)

    ground_lod = lod_cfg.get('ground', [])
    far_ground = {'triangles': [0] * len(ground_lod), 'tiles': [0] * len(ground_lod)}

    def sweep_cull(name):
        """The distance a sweep's pieces are culled from (lod.sweeps), or None."""
        sw = lod_cfg.get('sweeps', {})
        own = sw.get('paths', {}).get(name, {})
        cull = own['cull'] if 'cull' in own else sw.get('cull')
        return cull * lod_cfg.get('scale', 1.0) if cull is not None else None

    def lod_of(asset, rp, slot, row):
        entry = lod_entry(asset)
        if entry is None or entry['off'] or (not entry['distances'] and entry['cull'] is None):
            return None
        meshes = level_meshes(asset, rp, slot, row) if asset.levels else []
        levels = list(zip(entry['distances'], meshes))
        if entry['cull'] is not None:
            levels.append((entry['cull'], None))
        return P.Lod(levels, entry['band'])

    def chunk_levels(sname, sc, batch, rp, centre):
        """A scatter chunk's levels with "lod": "assets" (WORLDKIT.md, "Scatter"): a level wherever
        one of its assets switches level or is culled, at that asset's own distance (the world's
        lod overrides and scale applied), each level the merge of every prop at the level its
        asset draws there, without the props culled by then; a cull mark once every prop is culled,
        or at the scatter's cull. With thin, from its distance only a seeded share (keep) of the
        props is drawn, each grown by its scale. Distances closer than twice the band to the one before are moved
        out to keep the reader's rule, so a change can come a few units late, never early."""
        marks = {}
        for _, asset, _ in batch:
            if asset.name not in marks:
                e = lod_entry(asset)
                m = []
                if e is not None and not e['off']:
                    m = [(d, k + 1) for k, d in enumerate(e['distances'])]
                    if e['cull'] is not None:
                        m.append((e['cull'], None))
                marks[asset.name] = m
        cap = sc.get('cull')
        thin = sc.get('thin')
        wanted = {d for m in marks.values() for d, _ in m if cap is None or d < cap}
        if thin and (cap is None or thin['distance'] < cap):
            wanted.add(thin['distance'] * lod_cfg.get('scale', 1.0))
        wanted = sorted(wanted)
        def kept(it):
            return hashlib.sha256(f'thin:{it.id}'.encode()).digest()[0] / 256 < thin['keep']
        def level_at(asset, d, it=None):
            lv = 0
            for at, k in marks[asset.name]:
                if d >= at: lv = k
            if thin and it is not None and lv is not None and d >= thin['distance'] * lod_cfg.get('scale', 1.0) \
                    and not kept(it):
                return None
            return lv
        meshes = {}
        def level_mesh(asset, k):
            if k == 0:
                return mesh_of(asset)
            if asset.name not in meshes:
                meshes[asset.name] = level_meshes(asset, rp, slot, row)
            return meshes[asset.name][k - 1]
        band, levels, prev, last = 2.0, [], 0.0, None
        for d in wanted:
            state = [level_at(asset, d, it) for it, asset, _ in batch]
            if state == last:
                continue
            at = max(d, prev + 2 * band + 0.25)
            grow = thin.get('scale', 1.0) if thin and d >= thin['distance'] * lod_cfg.get('scale', 1.0) else 1.0
            parts = [(level_mesh(asset, k), it.position, it.yaw, grow) for (it, asset, _), k in zip(batch, state)
                     if k is not None]
            if not parts:
                levels.append((at, None))
                break
            levels.append((at, merge.merge(parts, centre)[0]))
            note_props(levels[-1][1], parts, [it for (it, _, _), k in zip(batch, state) if k is not None])
            prev, last = at, state
        else:
            if cap is not None:
                levels.append((max(cap, prev + 2 * band + 0.25), None))
        if len(levels) > P.MAX_LOD_LEVELS:
            raise WorldError(pointer('/scatter', sname) + '/lod', f'A chunk would have {len(levels)} levels after '
                             f'level 0; the pack holds at most {P.MAX_LOD_LEVELS}. Scatter assets that share '
                             'switch distances, or fewer kinds of asset.')
        return levels

    chunk_props = {}        # a scatter chunk's level mesh -> [((mesh, position, yaw[, scale]), item)]

    def note_props(mesh, parts, items):
        """Remembers the props a chunk's level was merged from, so that a stand-in with a cap can
        take some of them when the whole chunk does not fit."""
        if mesh is not None and auto_standins and any(
                'triangles' in o for o in [auto_standins, *auto_standins.get('cells', {}).values()]):
            chunk_props[mesh] = list(zip(parts, items))

    def standin_of(cell, centre, cid, far_grids, field_src):
        """A stand-in made from the cell itself (standins): each placement not in a layer (sweeps only
        with standins.sweeps) at the level it draws at standins.distance, merged into one mesh around
        the cell's centre; None when nothing is drawn from that far. A far ground level is made
        again without the skirts between the cell's own tiles, which meet exactly. With ground, the
        field's tiles are resampled on that grid instead. With triangles, the ground (field tiles and
        ground placements) goes in first, then the rest largest first (standin_size), each whole or
        not at all, a scatter chunk's props one by one in a seeded order."""
        dist = auto_standins['distance'] * lod_cfg.get('scale', 1.0)
        limits = dict(auto_standins, **auto_standins.get('cells', {}).get(cid, {}))
        cap, grid = limits.get('triangles'), limits.get('ground')
        half = size / 2
        def border(a, b):
            return any(abs(a[q]) >= half - 1e-3 and abs(b[q]) >= half - 1e-3 and a[q] * b[q] > 0 for q in (0, 2))
        ground, items, tiles, windows = [], [], [], False
        for k, pl in enumerate(cell.placements):
            if pl.layer is not None or (pl.tag == TAG_SWEEP and not auto_standins.get('sweeps')):
                continue
            if grid and k in field_src:
                tiles.append(field_src[k])
                continue
            mesh = pl.mesh
            for d, m in (pl.lod.levels if pl.lod else []):
                if dist >= d:
                    mesh = m
            src, fars = far_grids.get(k, (None, []))
            grids = [g for d, g in fars if dist >= d]
            if grids and mesh is not None:
                mesh = farground.far_levels(src, [g for _, g in fars], skirted=border)[len(grids) - 1]
            if mesh is None:
                continue
            windows = windows or bool(struct.unpack_from('<I', mesh, 12)[0])
            if cap is not None and (pl.tag == TAG_FIELD or pl.ground):
                ground.append((mesh, pl.position, pl.yaw))
            elif cap is not None and mesh in chunk_props:
                for part, it in chunk_props[mesh]:
                    items.append((part, hashlib.sha256(f'standin:{it.id}'.encode()).digest()))
            else:
                items.append(((mesh, pl.position, pl.yaw), struct.pack('>I', k)))
        if tiles:
            # the field's tiles resampled together on one grid over the cell, or one by one where
            # that cannot be (ground not under every grid point, or more than one mesh would hold it)
            windows = windows or any(struct.unpack_from('<I', m, 12)[0] for m in tiles)
            whole = merge.merge([(m, centre, 0.0) for m in tiles], centre)
            got = farground.far_levels(whole[0], [grid], skirted=border)[0] if len(whole) == 1 else None
            parts = [(m, centre, 0.0) for m in
                     ([got] if got else [farground.far_levels(m, [grid], skirted=border)[0] or m for m in tiles])]
            if cap is not None:
                ground[:0] = parts
            else:
                items[:0] = [(part, b'') for part in parts]
        left_out = 0
        if cap is not None:
            used = sum(standin_triangles(m) for m, *_ in ground)
            if used > cap:
                warnings.append({'code': 'standin_over_cap', 'cell': cid, 'triangles': used, 'cap': cap,
                                 'message': 'The ground alone is more triangles than the stand-in\'s cap, so the '
                                            'stand-in is the ground alone. Give it a coarser ground or a higher cap.'})
            keep = set()
            for q in sorted(range(len(items)), key=lambda q: (standin_size(*items[q][0]), items[q][1])):
                t = standin_triangles(items[q][0][0])
                if used + t <= cap:
                    keep.add(q)
                    used += t
            left_out = len(items) - len(keep)
            items = [(part, b'') for part in ground] + [it for q, it in enumerate(items) if q in keep]
        if not items:
            return None
        meshes = merge.merge([part for part, _ in items], centre)
        if len(meshes) > 1:
            nf = sum(struct.unpack_from('<H', m, 2)[0] for m in meshes)
            raise WorldError('/standins/distance', f'Cell {cid!r} drawn from {dist:g} units is {nf} faces, more than '
                             f'one mesh holds (2,048 vertices, 4,000 faces). Raise the distance, or give what it '
                             'holds coarser levels or cull distances.')
        if windows:
            warnings.append({'code': 'standin_windows', 'cell': cid,
                             'message': 'The stand-in merges faces with repeating textures; a merged mesh has no '
                                        'texture window table, so they are drawn without their windows.'})
        auto_report[cid] = {'placements': len(items), 'left_out': left_out, 'triangles': standin_triangles(meshes[0])}
        if cap is not None:
            auto_report[cid]['cap'] = cap
        if grid:
            auto_report[cid]['ground'] = grid
        return meshes[0]

    auto_report = {}

    # ---- paths: named polylines in world coordinates, stored once per world (WORLDPACK.md, "Paths")
    paths, path_report = [], {}
    for pname, spec in w.get('paths', {}).items():
        pp = pointer('/paths', pname)
        if 'drape' in spec:
            pts = list(terrain.paths[pname]) if terrain else []
            if not terrain:
                raise WorldError(pp + '/drape', 'A draped path lies on terrain: declare a field in terrain.fields.')
        else:
            short = [k for k, q in enumerate(spec['points']) if len(q) != 3]
            if short:
                raise WorldError(f'{pp}/points/{short[0]}', 'A point is [x, y, z]; [x, z] only on a draped path (drape).')
            pts = [tuple(q) for q in spec['points']]
        closed = bool(spec.get('closed'))
        for k in range(1, len(pts)):
            if pts[k] == pts[k - 1]:
                raise WorldError(f'{pp}/points/{k}', 'The point repeats the one before it; a segment needs a length.')
        if closed and len(pts) < 3:
            raise WorldError(f'{pp}/points', 'A closed path has at least 3 points.')
        if closed and pts[-1] == pts[0]:
            raise WorldError(f'{pp}/points/{len(pts) - 1}', 'A closed path joins its last point to its first by '
                             'itself: do not repeat the first point.')
        path = P.Path(pname, pts, bool(spec.get('raised')), closed, surface_of(spec.get('tag')))
        try:
            recs, _, _ = P.path_points(path)
        except P.PackError as error:
            raise WorldError(pp, f'The pack cannot hold this path: {error}.') from error
        outside = [k for k, q in enumerate(pts) if (math.floor(q[0] / size), math.floor(q[2] / size)) not in seen_at]
        if outside:
            warnings.append({'code': 'path_outside_cells', 'path': pname, 'points': outside,
                             'message': 'These points lie over no cell of the world. The path is kept; '
                                        'nothing is drawn or collided with there.'})
        paths.append(path)
        path_report[pname] = {'number': len(path_report), 'points': len(pts), 'segments': len(recs) - 1,
                              'length': round(recs[-1][2] / P.ONE, 4), 'raised': path.raised, 'closed': closed,
                              'surface': path.surface}

    # ---- palettes: each region's entries, then the assets' faces moved to them
    palette = w.get('palette', {})
    slot, row = palette.get('swatch_slot', 14), palette.get('swatch_row', 0)
    nxt = palette.get('first', 0)
    next8 = palette.get('first8', 14)
    any_palette = any(rp.by_key for rp in region_palettes.values())
    backdrops = {}
    for r in regions:
        rspec = w['regions'][r]
        if 'backdrop' in rspec:
            bp = pointer(pointer('/regions', r), 'backdrop')
            backdrops[r] = BD.build(rspec['backdrop'], bp, source.base)
            vnames = list(rspec.get('variants') or {'default': {}})
            for vn in backdrops[r].sky:
                if vn not in vnames:
                    raise WorldError(pointer(bp + '/sky', vn), f'Region {r!r} has no palette variant {vn!r}; its '
                                     f'variants: {", ".join(vnames)}.')
    for r in regions:
        rp, rt = region_palettes[r], region_textures[r]
        if rt.assets or r in backdrops:
            # textures, then the backdrop's palette, after the entries' palettes in the region's range
            first = rp.spec.get('palettes', {}).get('first', nxt)
            extra = 0
            if rt.assets:
                rt.pack(warnings, first + rp.entry_palettes(), next8, (slot, row) if any_palette else None)
                rp.tex4, rp.tex8, rp.texels = rt.palettes4(), rt.palettes8(), rt.texel_owners()
                extra = len(rp.tex4)
                if rp.tex8:
                    next8 = min(rp.tex8) - 1
            if r in backdrops:
                rp.sky = backdrops[r]
                if rp.sky.height:
                    rp.backdrop = (first + rp.entry_palettes() + extra, rp.sky.colours)
                    extra += 1
            nxt = rp.assign(nxt, extra)
        else:
            nxt = region_palettes[r].assign(nxt) if region_palettes[r].by_key or 'palettes' in w['regions'][r] else nxt
        if not region_palettes[r].by_key and not region_palettes[r].extra and 'variants' in w['regions'][r]:
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
    low8 = [p for rp in region_palettes.values() for p in rp.tex8]
    if low8 and taken and max(taken) >= 16 * min(low8):
        raise WorldError('/palette', f'8-bit palette {min(low8)} (colours {256 * min(low8)}-{256 * min(low8) + 255}) '
                         f'overlaps 4-bit palette {max(taken)}, which region {taken[max(taken)]!r} uses. Use fewer '
                         '8-bit textures, palette.first8, or lower 4-bit palettes.')

    # ---- the pack's description
    variants_shown = {}
    pregions = []
    for r in regions:
        rp = region_palettes[r]
        if rp.entries or rp.extra:
            rows, shown = rp.variants(warnings)
            variants_shown[r] = shown
            reg = P.Region(r, first_colour=rp.first_colour, variants=rows)
            rt = region_textures[r]
            if rt.packing:
                reg.textures = rt.slot_textures(SWATCH if any_palette else b'')
                reg.runs = [P.PaletteRun(pal * 256, rp.run_rows[q]) for q, pal in enumerate(sorted(rp.tex8))]
                reg.animations = [a for _, a in rt.animations()]
            if rp.sky:
                bd = rp.sky
                reg.sky = P.Sky(bd.elevations, rp.sky_rows, bd.mode(rp.backdrop[0]) if bd.height else 0,
                                BD.ATLAS if bd.height else 0, BD.MAP if bd.height else 0, bd.rate if bd.height else 0.0,
                                bd.horizon, bd.top, bd.height)
                if bd.height:
                    reg.backdrop = [P.VramCopy(BD.ATLAS, bd.atlas), P.VramCopy(BD.MAP, bd.map)]
            pregions.append(reg)
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
        rt = region_textures[c['region']]

        def mesh_of(asset):
            if getattr(asset, 'textured', False):
                return rt.binary(asset, relocated_palette(asset, rp, slot, row))
            return rp.relocated(asset, slot, row)
        i, j = c['at']
        centre = (i * size + half, 0, j * size + half)
        cell = P.Cell(i, j, region=regions.index(c['region']), layers=list(plan['layers']))
        to_merge = {}
        for pl in plan['placements']:
            binary = mesh_of(pl['asset'])
            ground = bool(pl['spec'].get('ground'))
            if pl['spec'].get('merge'):
                if struct.unpack_from('<I', binary, 12)[0]:
                    raise err(f'{cs.path}/placements/{pl["k"]}/merge', f'Asset {pl["asset"].name!r} has repeating '
                              'textures (a texture window table), which a merged mesh cannot keep. Do not merge it.', cs)
                if pl['asset'].levels:
                    warnings.append({'code': 'lod_merged', 'cell': c['id'], 'placement': pl['spec']['id'],
                                     'message': 'A merged placement draws its level 0 only: merged meshes have '
                                                'no levels of detail.'})
                to_merge.setdefault((pl['spec'].get('layer'), ground), []).append((binary, pl))
                continue
            cell.placements.append(P.Placement(binary, tuple(pl['pos']), pl['yaw'],
                                               pl['spec'].get('layer'), pl['k'], ground,
                                               lod_of(pl['asset'], rp, slot, row)))
        # merged props: one mesh per layer, ground and the rest apart (a merged ground mesh is a
        # ground placement, the way a terrain piece is)
        for (lname, ground), items in sorted(to_merge.items(),
                                             key=lambda kv: (kv[0][0] is not None, kv[0][0] or '', kv[0][1])):
            meshes = merge.merge([(b, pl['pos'], pl['yaw']) for b, pl in items], centre)
            for m in meshes:
                cell.placements.append(P.Placement(m, centre, 0.0, lname, 0xFFFF, ground))
            entry = {'layer': lname, 'placements': [pl['spec']['id'] for _, pl in items], 'meshes': len(meshes)}
            if ground: entry['ground'] = True
            merged_report.setdefault(c['id'], []).append(entry)
        # scatter: each chunk's props merged into one mesh (or more, split between props), with a
        # coarser level of its assets' level 1 and a cull distance when the scatter asks
        chunks = {}
        for it, asset in plan['scatter']:
            chunks.setdefault(it.chunk, []).append((it, asset))
        for (sname, lname, ci, cj), items in sorted(chunks.items(), key=lambda kv: (kv[0][0], kv[0][1] or '', kv[0][2], kv[0][3])):
            sc = w['scatter'][sname]
            batches, cur, nv, nf = [], [], 0, 0
            for it, asset in items:
                binary = mesh_of(asset)
                if struct.unpack_from('<I', binary, 12)[0]:
                    raise WorldError(it.path + '/asset', f'Asset {asset.name!r} has repeating textures (a texture window '
                                     'table), which a merged chunk cannot keep. Scatter assets without them.')
                v, f = struct.unpack_from('<HH', binary)
                if cur and (nv + v > merge.MAX_VERTICES or nf + f > merge.MAX_FACES):
                    batches.append(cur)
                    cur, nv, nf = [], 0, 0
                cur.append((it, asset, binary))
                nv, nf = nv + v, nf + f
            if cur: batches.append(cur)
            for batch in batches:
                mesh = merge.merge([(b, it.position, it.yaw) for it, _, b in batch], centre)[0]
                note_props(mesh, [(b, it.position, it.yaw) for it, _, b in batch], [it for it, _, _ in batch])
                levels = []
                if sc.get('lod') == 'assets':
                    levels = chunk_levels(sname, sc, batch, rp, centre)
                elif 'coarse' in sc:
                    coarse = []
                    for it, asset, b in batch:
                        lv = (rt.binary(asset, relocated_palette(asset, rp, slot, row), 1) if asset.textured
                              else rp.relocated_levels(asset, slot, row)[0]) if asset.levels else b
                        coarse.append((lv, it.position, it.yaw))
                    levels.append((sc['coarse'], merge.merge(coarse, centre)[0]))
                    note_props(levels[-1][1], coarse, [it for it, _, _ in batch])
                if 'cull' in sc and sc.get('lod') != 'assets':
                    levels.append((sc['cull'], None))
                lod = P.Lod(levels, 2.0) if levels else None
                if lod:
                    try:
                        P.lod_rows(lod)
                    except P.PackError as error:
                        raise WorldError(pointer('/scatter', sname), f'coarse and cull: {error}.') from error
                cell.placements.append(P.Placement(mesh, centre, 0.0, lname, TAG_SCATTER, False, lod))
                srep = scatter_report[sname]
                srep['chunks'] = srep.get('chunks', 0) + 1
                srep['triangles'] = srep.get('triangles', 0) + struct.unpack_from('<H', mesh, 2)[0]
        far_grids = {}          # placement number -> (mesh resampled, [(distance, grid)]) of its far ground
        field_src = {}          # placement number -> the mesh a field tile's far levels are resampled from
        for piece in (terrain.pieces.get((i, j), []) if terrain else []):
            ta = terrain_assets[c['region']]

            def terrain_mesh(m):
                if isinstance(m, bytes):
                    return rp.relocated(TerrainAsset(ta.name, ta.manifest, m), slot, row)
                # textured: written for the region's palette entries and texture packing
                return m.native(rp.mapping(ta), slot, row, rt.packing)
            lod = None
            base = terrain_mesh(piece.mesh)
            levels = [(d, terrain_mesh(m)) for d, m in piece.levels]
            where = pointer('/terrain/fields', piece.name) + '/lod'
            if piece.kind == 'field':
                field_src[len(cell.placements)] = levels[-1][1] if levels and levels[-1][1] else base
            if piece.kind == 'field' and ground_lod:
                # far ground (WORLDKIT.md, "Levels of detail"): grids resampled from level 0, each
                # kept only where it has fewer faces than the level before it
                # resampled from the coarsest level there is: with textured ground that level is
                # drawn in the textures' far colours, which suit the distance
                src = levels[-1][1] if levels else base
                fewest = struct.unpack_from('<H', src, 2)[0]
                for k, (spec, m) in enumerate(zip(ground_lod, farground.far_levels(src, [g['grid'] for g in ground_lod]))):
                    if m is None:
                        continue
                    nf = struct.unpack_from('<H', m, 2)[0]
                    if nf < fewest:
                        levels.append((spec['distance'] * lod_cfg.get('scale', 1.0), m))
                        far_grids.setdefault(len(cell.placements), (src, []))[1].append((levels[-1][0], spec['grid']))
                        fewest = nf
                        far_ground['triangles'][k] += nf
                        far_ground['tiles'][k] += 1
                where = '/lod/ground'
            elif piece.kind == 'sweep' and sweep_cull(piece.name) is not None and not levels:
                levels = [(sweep_cull(piece.name), None)]
                where = pointer('/lod/sweeps/paths', piece.name) if piece.name in lod_cfg.get('sweeps', {}).get('paths', {}) \
                    else '/lod/sweeps/cull'
            if levels:
                lod = P.Lod(levels, piece.band)
                try:
                    P.lod_rows(lod)
                except P.PackError as error:
                    raise WorldError(where, f'{error}.') from error
            cell.placements.append(P.Placement(base, centre, 0.0, None, piece.tag, piece.ground, lod))
        if plan['standin']:
            cell.standin = rp.relocated(plan['standin'], slot, row)
        elif auto_standins:
            cell.standin = standin_of(cell, centre, c['id'], far_grids, field_src)
        cell.collision = plan['collision']
        for e in plan['entities']:
            spec = e['spec']
            cell.entities.append(P.Entity(types.index(spec['type']), tuple(e['pos']), spec.get('yaw', 0),
                                          spec.get('layer'), mesh=mesh_of(e['asset']) if e['asset'] else None,
                                          collision=e['collision']))
        cells.append(cell)

    if w.get('meshes', {}).get('quads'):
        # pairs of triangles drawn as quads (WORLDKIT.md, "Quads"): the same pictures, fewer faces;
        # at level 0 double-sided faces (cutout cards) stay triangles, sorted nearest first one by
        # one, which keeps the overdraw of a crown of cards filling the screen down
        paired = {}

        def quads_of(m, skip=0):
            if m is None:
                return None
            if (m, skip) not in paired:
                paired[m, skip] = quads.pair(m, skip=skip)
            return paired[m, skip]
        for cell in cells:
            for pl in cell.placements:
                pl.mesh = quads_of(pl.mesh, quads.DOUBLE)
                if pl.lod:
                    pl.lod.levels = [(d, quads_of(m)) for d, m in pl.lod.levels]
            cell.standin = quads_of(cell.standin)
            for e in cell.entities:
                e.mesh = quads_of(e.mesh, quads.DOUBLE)
    world = P.World(cells=cells, cell_shift=shift, layers=players, regions=pregions, coll_pad=pad,
                    near_far=w.get('runtime', {}).get('near_far'),
                    overhang=overhang, floor_max_degrees=probe['floor_max_degrees'],
                    ceiling_max_degrees=probe.get('ceiling_max_degrees', DEFAULT_CEILING_DEGREES), paths=paths)

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
    report['paths'] = path_report
    for r in regions:
        entry = report['regions'][r]
        if region_textures[r].packing:
            entry['textures'] = region_textures[r].report()
        if r in backdrops:
            entry['backdrop'] = backdrops[r].report()
    report['lod'] = {n: s for n, s in lod_report.items()}
    if auto_standins:
        report['standins'] = {'distance': auto_standins['distance'], 'cells': auto_report}
    if ground_lod:
        report['far_ground'] = {'levels': [dict(g) for g in ground_lod], 'tiles': far_ground['tiles'],
                                'triangles': far_ground['triangles']}
    if terrain:
        report['terrain'] = terrain.report
        for entry, plan in zip(report['cells'], plans):
            pieces = terrain.pieces.get(tuple(entry['at']), [])
            if not pieces:
                continue
            tags = entry['collision']['placement_tags']
            for piece in pieces:
                tags[str(piece.tag)] = 'terrain' if piece.tag == TAG_FIELD else 'sweeps'
            if any(it for it in scattered.get(tuple(entry['at']), [])):
                tags[str(TAG_SCATTER)] = 'scatter'
            entry['terrain'] = {'pieces': len(pieces), 'triangles': sum(p.faces for p in pieces),
                                'coarse_triangles': sum(p.level_faces[-1] for p in pieces),
                                'collision_triangles': len(terrain.collision.get(tuple(entry['at']), []))}
    compiled = Compiled(data, report, '', '', SWATCH if any_palette else b'', new_lock, changes, library, world, encoded)
    compiled.terrain_files = terrain.files if terrain else []
    if scatter_report:
        report['scatter'] = scatter_report
    compiled.water = water_blob(terrain.water) if terrain and terrain.water else b''
    compiled.terrain = terrain
    from .akr import world_source, game_source
    compiled.akr = world_source(source, compiled, region_palettes, slot, row, number_of, groups)
    compiled.game_akr = game_source(game)
    return compiled


def water_blob(tris):
    """NAME.water.bin for stdlib/wpwater.akr: u32 count, then per upward water triangle 14
    s32 (16.16 unless said): its bounds x0, z0, x1, z1; corner a (x, y, z); edges b - a and c - a
    (x, z); the plane's slopes dy/dx and dy/dz; the surface byte (an integer)."""
    out = [struct.pack('<I', len(tris))]
    for a, b, c, surface in tris:
        n = ((b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]),
             (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]),
             (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
        xs, zs = [p[0] for p in (a, b, c)], [p[2] for p in (a, b, c)]
        words = [min(xs), min(zs), max(xs), max(zs), a[0], a[1], a[2], b[0] - a[0], b[2] - a[2],
                 c[0] - a[0], c[2] - a[2], -n[0] / n[1], -n[2] / n[1]]
        out.append(struct.pack('<14i', *(P.fx(v) for v in words), surface))
    return b''.join(out)


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
            'ground_placements': sum(1 for p in pcell.placements if p.ground),
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
        'pack': {'bytes': len(data), 'version': f'{decoded.major}.{decoded.minor}', 'cells': len(world.cells),
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


def standin_triangles(binary):
    """A mesh's triangles as drawn: a quad is two."""
    nf, fo = struct.unpack_from('<H', binary, 2)[0], struct.unpack_from('<I', binary, 8)[0]
    return sum(2 if binary[fo + 36 * k] & 4 else 1 for k in range(nf))


def standin_size(binary, position=None, yaw=0.0, scale=1.0):
    """The sort key of a piece of a capped stand-in, largest first (WORLDKIT.md, "Stand-ins made by
    the kit"): its bounding box's height times its larger horizontal side, then its footprint."""
    nv, _, vo = struct.unpack_from('<HHI', binary)
    if not nv:
        return (0.0, 0.0)
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    for k in range(nv):
        for q, c in enumerate(struct.unpack_from('<3i', binary, vo + 16 * k)):
            lo[q], hi[q] = min(lo[q], c), max(hi[q], c)
    dx, dy, dz = ((hi[q] - lo[q]) / 65536 * scale for q in range(3))
    return (-dy * max(dx, dz), -dx * dz)
