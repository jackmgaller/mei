#!/usr/bin/env python3
"""The world-file edits the water and the backdrops need, as code: APPLY.md in water/ and
backdrop/ says the same in words, for the generators (`notes/gen_town.py`, `gen_core.py`,
`make_mountain.py`, `make_world.py`), which this does not replace. `preview_scratch.py` applies
them to a copy of `shrinetown.world.json` to build and photograph the result.

    from apply_patch import patch_water, patch_backdrop
"""
import copy
import math

# the world's own colours, kept as the materials' far colours (the stand-ins' flat colour is the
# texture's mean, the kit works it out)
WATER = {
    'water': {'image': 'art/water/water.png', 'scale': [4.8, 4.8], 'span': 23},
    # the brook between the falls pool and the pond: the same image as `water` at a larger scale (one
    # tile in VRAM), so that a 4 m cross-section interval is within the texture's reach and the sweep
    # is not cut into twice the triangles (wp_water() tests every water triangle: 12 cycles each)
    'stream_water': {'image': 'art/water/water.png', 'scale': [7.2, 7.2], 'span': 23},
    'pond_water': {'image': 'art/water/pond_water.png', 'scale': [4.8, 4.8], 'span': 23},
    'falls': {'image': 'art/water/falls.png', 'scale': [3.0, 6.4], 'span': 23},
}
# water operations (indices in terrain.fields.ground.operations, in the current world file) that
# become `pond_water`: the two ponds and the falls pool; the streams' sweeps (paths stream and
# stream_upper) stay `water`
POND_OPS = [52, 53, 73]


def patch_water(w, ops=POND_OPS):
    w = copy.deepcopy(w)
    mats = w['terrain']['materials']
    mats['water'] = dict(mats['water'], texture=WATER['water'])
    mats['falls'] = dict(mats['falls'], texture=WATER['falls'])
    mats['stream_water'] = {'color': '#3f7393', 'water': True, 'tag': 'water', 'texture': WATER['stream_water']}
    assert w['paths']['stream']['sweep']['material'] == 'water'
    w['paths']['stream']['sweep']['material'] = 'stream_water'
    mats['pond_water'] = {'color': '#2f4c46', 'water': True, 'tag': 'water', 'texture': WATER['pond_water']}
    fops = w['terrain']['fields']['ground']['operations']
    for i in ops:
        assert fops[i]['op'] == 'water', (i, fops[i])
        fops[i]['material'] = 'pond_water'
    # the north pond's circle (234, 140, r 16.8) reaches z 123.2: the quads south of the region
    # boundary (z 128) are the town's, and the town cannot pay for a second water texture. A later
    # water operation wins a quad, so the cap is `water` again.
    cx, cz, r = fops[52]['area']['circle']
    pts = [[round(cx + r * math.cos(a), 3), round(cz + r * math.sin(a), 3)]
           for a in (math.radians(d) for d in range(0, 360, 10))]
    half = math.sqrt(r * r - (128.0 - cz) ** 2)
    poly = [[round(cx - half, 3), 128.0], [round(cx + half, 3), 128.0]]
    poly += [[x, z] for x, z in sorted(((x, z) for x, z in pts if z < 128.0),
                                      key=lambda p: -math.atan2(p[1] - cz, p[0] - cx))]
    fops.append({'op': 'water', 'area': {'polygon': poly}, 'level': fops[52]['level'], 'material': 'water'})
    # a textured material has no palette entry to recolour: the night multiply tints its texture
    for r in w['regions'].values():
        for v in r.get('variants', {}).values():
            if 'water' in v.get('colors', {}):
                del v['colors']['water']
                if not v['colors']:
                    del v['colors']
    return w


def patch_backdrop(w, town='art/backdrop/town_backdrop.png', shrine='art/backdrop/shrine_backdrop.png'):
    import json
    from pathlib import Path
    spec = json.loads((Path(__file__).resolve().parent / 'backdrop' / 'backdrop.json').read_text())
    w = copy.deepcopy(w)
    for region, image in (('town', town), ('shrine', shrine)):
        r = w['regions'][region]
        s = spec[region]
        r['backdrop'] = {'elevations': s['elevations'], 'sky': s['sky'],
                         'silhouette': {'image': image, 'horizon': s.get('horizon', 0), 'repeat': 1}}
        for vname, extra in s.get('variants', {}).items():
            r['variants'][vname]['backdrop'] = extra
    return w
