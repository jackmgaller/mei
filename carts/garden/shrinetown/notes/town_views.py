#!/usr/bin/env python3
"""The World Checker at the town's vantage points only (parts/town.json), as a table.

  B=$B python3 carts/garden/shrinetown/notes/town_views.py [PACK [TAG]]
PACK defaults to $B/worlds/town_gb/town_gb.world.bin; the report goes to $B/town_views_TAG/.
"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '../../../..'))
B = os.environ.get('B', 'build')
pack = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, B, 'worlds', 'town_gb', 'town_gb.world.bin')
tag = sys.argv[2] if len(sys.argv) > 2 else 'weighted'
vps = json.load(open(os.path.join(HERE, '..', 'parts', 'town.json')))['vantage_points']
settings = {
    'runtime': {'depth': True, 'perspective': True},
    'sampling': {'floor_spacing': None, 'follow': None, 'rooftops_per_cell': 0, 'air': None, 'seams': None,
                 'entities': None, 'layer_combinations': False},
    'vantage_points': [{k: v for k, v in vp.items() if k != 'name'} for vp in vps],
    'images': 0,
}
out = os.path.join(ROOT, B, f'town_views_{tag}')
os.makedirs(out, exist_ok=True)
sp = os.path.join(out, 'settings.json')
json.dump(settings, open(sp, 'w'))
subprocess.run(['python3', 'tools/worldkit/verify.py', pack, '-o', out, '--settings', sp,
                '--compiler', os.path.join(ROOT, B, 'meic'), '--probe', os.path.join(ROOT, B, 'mei-scene-probe')],
               cwd=ROOT, capture_output=True, text=True)
views = json.load(open(os.path.join(out, 'world-check.json')))['views']
table = []
for v, vp in zip(views, vps):
    st = v['stats']
    table.append(dict(name=vp['name'], triangles=st['triangles'], draw_cpu=st['draw_cpu_cycles'], gpu=st['gpu_cycles'],
                      placements=st['placements_drawn'], standins=st['standins_drawn'], entities=st['entities_drawn'],
                      coarse=st['coarse_drawn'], heaviest=v.get('heaviest', [])[:3]))
    print(f"{vp['name']:<44} tris {st['triangles']:5d}  cpu {st['draw_cpu_cycles']:8d}  gpu {st['gpu_cycles']:8d}  "
          f"placements {st['placements_drawn']:3d}  stand-ins {st['standins_drawn']:2d}")
json.dump(table, open(os.path.join(out, 'table.json'), 'w'), indent=1)
