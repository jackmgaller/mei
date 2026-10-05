#!/usr/bin/env python3
"""The shrine town's texture VRAM by region and zone, against the allowances in TEXTURES.md.

    python3 carts/garden/shrinetown/tools/textures.py                 # what the cells place now
    python3 carts/garden/shrinetown/tools/textures.py --try street:town:dagashi_shop,crane_game
    python3 carts/garden/shrinetown/tools/textures.py --report $B/worlds/carts/garden/shrinetown/report.json

Every textured asset placed in a cell counts in its cell's region (cells say which: layout.py's
region_of()) and in the zone holding the placement's origin (PLACE_SPLIT: station, street, east,
canal, shrine). Bytes are the World Kit's: each distinct tile once (the same image in two assets
is one tile), on the packer's 8-texel grid (worldkit/textures.py, allocated()), as the region's
`textures.budget` counts them. A tile of a shared prop (SHARED), or one that two zones' assets
use, is the region's shared set's; a zone's own bytes are its other tiles.

--try ZONE:REGION:ASSET,... adds assets to a zone as if placed there (repeatable), to check an
allowance before placing. --report reads a built world's report.json for the terrain's textures
(none until the ground is textured). Exits 1 when a region is over its budget or a part over
its allowance. Asset names resolve in the world's asset directories, then
carts/garden/shrinetown/assets/NAME/, then ../shrine/assets/ (`shrine:NAME` names that one).
Game entities' meshes are not counted (the coins are untextured).
"""
import argparse, json, sys
from pathlib import Path

ST = Path(__file__).resolve().parent.parent
ROOT = ST.parent.parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ST))
import layout as L                                           # noqa: E402
from kitcore import jsonio                                    # noqa: E402
from assetkit.compiler import compile_recipe                  # noqa: E402
from assetkit.geometry import AssetError                      # noqa: E402
from worldkit.textures import allocated                       # noqa: E402

KB = 1024
# The plan (TEXTURES.md): each region's budget (make_world.py's TEXTURE_BUDGETS) split into the
# terrain's textures, the shared set and each zone's own tiles.
ALLOWANCE = {
    'town': {'budget': 380 * KB, 'terrain': 40 * KB, 'shared': 48 * KB,
             'station': 96 * KB, 'street': 144 * KB, 'east': 26 * KB, 'canal': 26 * KB, 'shrine': 0},
    'shrine': {'budget': 300 * KB, 'terrain': 120 * KB, 'shared': 48 * KB,
               'shrine': 88 * KB, 'canal': 36 * KB, 'station': 8 * KB, 'street': 0, 'east': 0},
}
# Props any zone of the region may place: their tiles are the region's shared set's.
SHARED = {
    'town': ['town_street_lamp', 'street_lamp', 'vending_machine', 'postbox', 'town_road_signs', 'delivery_van',
             'traffic_mirror', 'mamachari', 'town_potted_plants', 'town_laundry_pole', 'town_aircon_pipes',
             'town_utility_pole_transformer', 'street_utility_pole', 'street_barrier', 'street_guardrail',
             'street_vending_machine', 'town_bench', 'firepost', 'jizo', 'hokora', 'tanuki', 'town_crates_bins'],
    'shrine': ['plant_bamboo', 'plant_fern', 'plant_sasa', 'plant_shrub', 'plant_susuki', 'litter_gold', 'litter_red',
               'tree_cedar', 'tree_cedar_giant', 'tree_maple', 'tree_maple_small', 'tree_ginkgo', 'tree_zelkova',
               'tree_bamboo_tall', 'forest_stone_lantern', 'shishi_odoshi', 'jizo', 'hokora', 'tanuki',
               'street_lamp', 'town_street_lamp', 'town_bench'],
}


def zone_of(x, z):
    """PLACE_SPLIT's zones: a placement belongs to the zone holding its origin. (The viaduct is the
    station zone's wherever it runs: pass it with --try, or it counts where it stands.)"""
    if x < 64:
        return 'canal'
    if z >= 128:
        return 'shrine'
    if z < 40:
        return 'station'
    return 'street' if x < 210 else 'east'


def asset_dirs(world):
    dirs = [ST / world['assets']] + [ST / d for d in world.get('asset_dirs', [])]
    return dirs


def find(name, dirs):
    if name.startswith('shrine:'):
        return ST.parent / 'shrine' / 'assets' / f'{name[7:]}.asset.json'
    for d in dirs:
        if (d / f'{name}.asset.json').is_file():
            return d / f'{name}.asset.json'
    for f in [*sorted((ST / 'assets').glob(f'*/{name}.asset.json')), ST.parent / 'shrine' / 'assets' / f'{name}.asset.json']:
        if f.is_file() and f.parent.name != 'greybox':
            return f
    raise SystemExit(f'No asset recipe {name!r} (looked in the world\'s asset directories, assets/{name}/, '
                     '../shrine/assets/).')


_tiles = {}


def tiles_of(name, dirs):
    """{tile key: allocated bytes} of an asset's textures (empty for a flat-colour asset)."""
    if name not in _tiles:
        f = find(name, dirs)
        try:
            recipe = jsonio.load(str(f), AssetError)
            mesh, _, _ = compile_recipe(recipe, f.parent)
        except (AssetError, OSError, ValueError) as error:
            raise SystemExit(f'{f}: {error}')
        _tiles[name] = {t.tile.key: allocated(t.tile) for t in (mesh.textures or {}).get('textures', {}).values()}
    return _tiles[name]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--try', dest='extra', action='append', default=[], metavar='ZONE:REGION:ASSET,...')
    ap.add_argument('--report', help="a built world's report.json, for the terrain's textures")
    args = ap.parse_args()
    world = json.loads((ST / 'shrinetown.world.json').read_text())
    dirs = asset_dirs(world)
    placed = {}                          # (region, zone) -> {asset names}
    for f in sorted((ST / world['cell_dir']).glob('*.cell.json')):
        cell = json.loads(f.read_text())
        for pl in cell.get('placements', []):
            pos = pl['position']
            placed.setdefault((cell['region'], zone_of(pos[0], pos[-1])), set()).add(pl['asset'])
    for spec in args.extra:
        zone, region, names = spec.split(':', 2)
        if region not in ALLOWANCE or zone not in ALLOWANCE[region]:
            raise SystemExit(f'--try {spec}: ZONE is station, street, east, canal or shrine; REGION town or shrine.')
        placed.setdefault((region, zone), set()).update(n for n in names.split(',') if n)
    terrain = {}
    if args.report:
        rep = json.loads(Path(args.report).read_text())
        for r, g in rep['regions'].items():
            terrain[r] = g.get('textures', {}).get('by_asset', {}).get('terrain', {}).get('vram_bytes', 0)
    over = False
    for region, allow in ALLOWANCE.items():
        zones = {z: set(n) for (r, z), n in placed.items() if r == region}
        ztiles = {z: {} for z in zones}
        for z, names in zones.items():
            for n in names:
                ztiles[z].update(tiles_of(n, dirs))
        shared = {}
        for z, names in zones.items():
            for n in names:
                if n.split(':')[-1] in SHARED[region]:
                    shared.update(tiles_of(n, dirs))
        seen = {}
        for z, t in ztiles.items():
            for k, b in t.items():
                if k in seen and seen[k] != z:
                    shared[k] = b
                seen.setdefault(k, z)
        every = {k: b for t in ztiles.values() for k, b in t.items()}
        total = sum(every.values()) + terrain.get(region, 0)
        rows = [('terrain', terrain.get(region, 0), allow['terrain']), ('shared', sum(shared.values()), allow['shared'])]
        for z in ('station', 'street', 'east', 'canal', 'shrine'):
            own = sum(b for k, b in ztiles.get(z, {}).items() if k not in shared)
            if own or allow[z]:
                rows.append((z, own, allow[z]))
        flag = total > allow['budget']
        over |= flag
        print(f'{region}: {total:,} of {allow["budget"]:,} bytes{" OVER" if flag else ""} '
              f'({len(every)} tiles; slots 13-0 hold {14 * 32 * KB:,})')
        for name, used, cap in rows:
            flag = used > cap
            over |= flag
            print(f'  {name:8s} {used:9,d} of {cap:9,d}{"  OVER" if flag else ""}')
    sys.exit(1 if over else 0)


if __name__ == '__main__':
    main()
