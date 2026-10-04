"""Writes the shrine world's far-cell stand-ins, assets/standin_cI_J.asset.json: for each 64 m
cell, a coarse sheet sampled every 8 m from the world's own floors (`mei_world.py floor`: the
terrain, sweeps and roofs), raised into a canopy where the forest stands and coloured as the
autumn forest, the gravel, the roofs and the water read from far away. Run it after changing
the terrain or the layout: python3 carts/garden/shrine/standins.py (the world must validate
first). Standard library only. The recipes it writes are its output: do not edit them."""
import hashlib, json, math, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
WORLD = os.path.join(HERE, 'shrine.world.json')
S, STEP, NX, NZ = 64, 8, 3, 5
N = S // STEP

# Where there is no forest canopy (x0, z0, x1, z1 rectangles and x, z, r circles), and water.
OPEN_RECTS = [(36, 0, 156, 158), (0, 0, 192, 34), (52, 256, 92, 294)]
OPEN_CIRCLES = [(48, 230, 14), (98, 208, 11), (150, 250, 11), (18, 112, 8)]
WATER = [(148, 32, 188, 106)]
CANOPY = 9.0            # how far the canopy stands above the ground
COLOURS = {'maple': '#82402a', 'scarlet': '#985434', 'ginkgo': '#9c8a3c', 'cedar': '#30442e',
           'cedar2': '#40503a', 'gravel': '#d4ccb8', 'roof': '#3e4248', 'water': '#3f7393', 'road': '#4a4a50',
           'rock': '#6a665e'}

def is_open(x, z):
    return (any(a <= x <= c and b <= z <= d for a, b, c, d in OPEN_RECTS) or
            any(math.hypot(x - cx, z - cz) < r for cx, cz, r in OPEN_CIRCLES))

def is_water(x, z):
    return any(a <= x <= c and b <= z <= d for a, b, c, d in WATER)

def _hash(i, j):
    return hashlib.sha256(f'{i},{j}'.encode()).digest()[0] / 255

def noise(x, z, size=28.0):
    """Smooth value noise in 0..1: patches of colour about `size` metres across."""
    fx, fz = x / size, z / size
    i, j = math.floor(fx), math.floor(fz)
    u, v = fx - i, fz - j
    u, v = u * u * (3 - 2 * u), v * v * (3 - 2 * v)
    a, b = _hash(i, j), _hash(i + 1, j)
    c, d = _hash(i, j + 1), _hash(i + 1, j + 1)
    return (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v

def pick(x, z):
    h = noise(x, z) * 0.8 + _hash(int(x), int(z)) * 0.2
    if z > 214:
        return 'cedar' if h < 0.4 else 'cedar2' if h < 0.6 else 'maple' if h < 0.78 else 'ginkgo'
    return 'cedar' if h < 0.25 else 'cedar2' if h < 0.38 else 'maple' if h < 0.62 else 'scarlet' if h < 0.78 else 'ginkgo'

def main():
    pts = [(i * S + gx * STEP, j * S + gz * STEP) for j in range(NZ) for i in range(NX)
           for gz in range(N + 1) for gx in range(N + 1)]
    pts = sorted(set((min(x, 191.9), min(z, 319.9)) for x, z in pts))
    args = [a for p in pts for a in (f'{p[0]:g}', f'{p[1]:g}')]
    out = subprocess.run([sys.executable, os.path.join(ROOT, 'tools/mei_world.py'), 'floor', WORLD] + args,
                         capture_output=True, text=True, check=True)
    fl = {tuple(f['at']): (f['y'] if f['y'] is not None else 0.0) for f in json.loads(out.stdout)['floors']}
    def height(x, z):
        x, z = min(x, 191.9), min(z, 319.9)
        y = fl[(x, z)]
        if not is_open(x, z) and not is_water(x, z):
            y += CANOPY
        return y
    for j in range(NZ):
        for i in range(NX):
            cx, cz = i * S + S / 2, j * S + S / 2
            verts, faces, mats = [], [], []
            for gz in range(N + 1):
                for gx in range(N + 1):
                    x, z = i * S + gx * STEP, j * S + gz * STEP
                    verts.append([round(x - cx, 3), round(height(x, z), 3), round(z - cz, 3)])
            for gz in range(N):
                for gx in range(N):
                    a = gz * (N + 1) + gx
                    b, c, d = a + 1, a + N + 2, a + N + 1
                    x, z = i * S + (gx + 0.5) * STEP, j * S + (gz + 0.5) * STEP
                    if is_water(x, z):
                        m = 'water'
                    elif z < 30:
                        m = 'road'
                    elif is_open(x, z):
                        m = 'roof' if fl.get((min(x - 4, 191.9), min(z - 4, 319.9)), 0) > 3 + (5 if z > 80 else 0) else 'gravel'
                    else:
                        m = pick(x, z)
                    # each quad as two triangles, wound to face up
                    faces += [[a, d, c], [a, c, b]]
                    mats += [m, m]
            used = sorted(set(mats))
            rec = {'format': 'mei-asset', 'version': 1, 'name': f'standin_c{i}_{j}',
                   'materials': {m: {'color': COLOURS[m], 'palette': True} for m in used},
                   'lighting': {'mode': 'vertical', 'ambient': 0.5},
                   'nodes': [{'id': 'sheet', 'op': 'mesh', 'vertices': verts, 'faces': faces, 'face_materials': mats}]}
            with open(os.path.join(HERE, 'assets', f'standin_c{i}_{j}.asset.json'), 'w') as f:
                json.dump(rec, f, indent=None, separators=(',', ':'))
                f.write('\n')
    print('wrote', NX * NZ, 'stand-ins')

if __name__ == '__main__':
    main()
