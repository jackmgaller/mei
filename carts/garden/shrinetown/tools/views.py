#!/usr/bin/env python3
"""The World Checker at the shrine town's worst views (spec 8.3, V1-V6, and the regions' own), with
every row of the level present, as a table.

    make B=$B $B/carts/garden.mei
    B=$B python3 carts/garden/shrinetown/tools/views.py [PACK]

PACK defaults to $B/worlds/carts/garden/shrinetown/shrinetown.world.bin. The checker's report goes
to $B/shrinetown_views/; the table is printed (Markdown) and written there as table.md.
Budgets: 4,000 triangles, 600,000 draw CPU cycles, 1,600,000 GPU cycles a view.
"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '../../../..'))
B = os.environ.get('B', 'build')
pack = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, B, 'worlds', 'carts', 'garden', 'shrinetown',
                                                           'shrinetown.world.bin')
# name, camera (x, y, z), yaw (degrees: 0 north, 90 east), pitch (degrees, negative down)
VIEWS = [
    ('V1 arcade roof, north end, looking south', (160, 10.0, 94), 180, -8),
    ('V2 pagoda top (47) looking south', (178, 47.0, 262), 180, -12),
    ('V2 pagoda top, looking south-west', (178, 47.0, 262), 225, -12),
    ('V2 pagoda top, looking south-east', (178, 47.0, 262), 135, -12),
    ("V2 at the spec's 52, looking south", (178, 52.0, 262), 180, -12),
    ('V3 stage looking south', (154, 62.0, 345), 180, -10),
    ('V3 stage looking south-west', (154, 62.0, 345), 225, -10),
    ('V3 stage looking south-east', (154, 62.0, 345), 135, -10),
    ('V4 danchi roof looking north-east', (78, 20.3, 30), 45, -10),
    ('V5 spawn looking north', (160, 1.6, 26), 0, 0),
    ('V5 spawn looking north, up 5', (160, 1.6, 26), 0, 5),
    ('V6 cemetery top looking west', (286, 18.0, 244), 270, -10),
    ('Shotengai floor (160, 50) looking north', (160, 1.5, 50), 0, 0),
    ('Platform looking north', (160, 10.5, 8), 0, -5),
    ('Fire tower top looking east', (102, 16.7, 74), 90, -15),
    ('Building roof looking west', (193, 19.8, 90), 270, -15),
    ('Courtyard toward the gate', (160, 2.1, 130), 0, 0),
    ('Temple ridge looking south', (160, 29.5, 221), 180, -10),
    ('Deck 3 looking east', (80, 16.6, 206), 90, -5),
    ('Torii steps looking north', (100, 33.0, 325), 0, 0),
    ('Shoulder top looking south-west (the whole level)', (300, 65.0, 372), 225, -12),
]
settings = {
    'runtime': {'depth': True, 'perspective': True},
    'sampling': {'floor_spacing': None, 'follow': None, 'rooftops_per_cell': 0, 'air': None, 'seams': None,
                 'entities': None, 'layer_combinations': False},
    'vantage_points': [{'position': list(p), 'yaw': yaw, 'pitch': pitch} for _, p, yaw, pitch in VIEWS],
    'images': 0,
}
out = os.path.join(ROOT, B, 'shrinetown_views')
os.makedirs(out, exist_ok=True)
sp = os.path.join(out, 'settings.json')
json.dump(settings, open(sp, 'w'))
r = subprocess.run([sys.executable, 'tools/worldkit/verify.py', pack, '-o', out, '--settings', sp,
                    '--compiler', os.path.join(ROOT, B, 'meic'), '--probe', os.path.join(ROOT, B, 'mei-scene-probe')],
                   cwd=ROOT, capture_output=True, text=True)
views = json.load(open(os.path.join(out, 'world-check.json')))['views']
lines = ['| View | Triangles | Draw CPU | GPU | Placements | Stand-ins |', '|---|---|---|---|---|---|']
for v, (name, *_r) in zip(views, VIEWS):
    st = v['stats']
    lines.append(f"| {name} | {st['triangles']:,} | {st['draw_cpu_cycles']:,} | {st['gpu_cycles']:,} | "
                 f"{st['placements_drawn']} | {st['standins_drawn']} |")
text = '\n'.join(lines)
open(os.path.join(out, 'table.md'), 'w').write(text + '\n')
print(text)
