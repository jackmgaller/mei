#!/usr/bin/env python3
"""Writes the road-works hoarding that closes the front road's two ends (README.md, "The frame";
the grey box's hoarding_w and hoarding_e, 14 m long, 5.5 m tall, 0.4 m thick): art/panel.png,
art/sign.png and edge_hoarding.asset.json.

A Japanese road-works hoarding (kakoi): white ribbed steel panels on a green kick plate under a
blue top rail, and the bowing-worker sign ("sorry for the trouble") on its front. The panel is
one 32 x 64 tile repeating every 2 m along the hoarding and once up its height (a 6.25 x 8.6 cm
texel); the sign a 32 x 32 decal drawn once, 1.6 m square. 18 triangles; 1,024 + 800 bytes of
VRAM, one 4-bit palette for the two.

Origin and facing: the middle of the hoarding's foot; its front (the sign's side) faces -Z.
Each replaces the grey box's hoarding at the middle of its footprint (0.2, 111) and (319.8, 111),
with the yaw that turns the front to the road (GROUND.md, "Edges"). Collision: "self".

Run: python3 carts/garden/shrinetown/assets/edge_hoarding/make_edge_hoarding.py   (Pillow)
"""
import json
import random
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
LENGTH, HEIGHT, THICK = 14.0, 5.5, 0.4

WHITE, RIB, GRIME, BLUE, BLUE2 = '#eceae4', '#d0cec6', '#b8b6ae', '#3a6ab0', '#2a4a80'
GREEN, GREEN2, YELLOW, BLACK, SKIN = '#40a060', '#2e7a48', '#f0c030', '#2c2a28', '#e8b890'
ORANGE = '#e8782a'


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def save(px, name):
    h, w = len(px), len(px[0])
    assert len({c for row in px for c in row}) <= 15
    img = Image.new('RGB', (w, h))
    img.putdata([rgb(c) for row in px for c in row])
    (HERE / 'art').mkdir(exist_ok=True)
    img.save(HERE / 'art' / f'{name}.png')


def panel():
    """32 wide (2 m), 64 tall (5.5 m): ribs every 4 texels, a blue top rail, a green kick plate,
    road grime splashed up the bottom metre, a joint between two panels at u 0."""
    r = random.Random(401)
    px = [[WHITE] * 32 for _ in range(64)]
    for y in range(64):
        for x in range(32):
            if x % 4 == 3:
                px[y][x] = RIB
        px[y][0] = GRIME
    for y in range(0, 4):
        for x in range(32):
            px[y][x] = BLUE if y < 3 else BLUE2
    for y in range(57, 64):
        for x in range(32):
            px[y][x] = GREEN if y > 57 else GREEN2
    for _ in range(70):
        x, y = r.randrange(32), r.randrange(44, 57)
        if r.random() < (y - 44) / 13:
            px[y][x] = GRIME
    save(px, 'panel')


def sign():
    """The bowing worker: a yellow board, black border, a worker in a white helmet bowing low,
    an orange band at the foot."""
    px = [[YELLOW] * 32 for _ in range(32)]
    for k in range(32):
        for t in (0, 1):
            px[t][k] = px[31 - t][k] = px[k][t] = px[k][31 - t] = BLACK
    for y in range(24, 30):
        for x in range(2, 30):
            px[y][x] = ORANGE
    def rect(x0, y0, x1, y1, c):
        for y in range(y0, y1):
            for x in range(x0, x1):
                px[y][x] = c
    rect(22, 13, 24, 24, BLACK)          # legs, a little apart
    rect(25, 13, 27, 24, BLACK)
    rect(21, 23, 25, 24, BLACK)          # feet
    rect(25, 23, 29, 24, BLACK)
    rect(20, 9, 28, 14, BLACK)           # hips
    rect(12, 10, 22, 14, BLACK)          # the back, bent forward and down
    rect(10, 11, 13, 15, BLACK)           # shoulders
    rect(11, 15, 14, 21, BLACK)           # an arm hanging straight
    rect(5, 14, 11, 19, SKIN)             # the head, bowed below the shoulders
    rect(4, 12, 11, 15, WHITE)            # the helmet's crown and brim
    rect(4, 15, 5, 18, WHITE)
    for x in range(5, 10):
        px[11][x] = BLACK
    px[12][4] = px[12][10] = YELLOW               # round the helmet's corners
    save(px, 'sign')


def recipe():
    return {
        'format': 'mei-asset', 'version': 1, 'name': 'edge_hoarding',
        'budget': {'triangles': 24},
        'lighting': {'mode': 'vertical', 'ambient': 0.5},
        'verification': {'required': True, 'depth': True, 'perspective': True},
        'materials': {
            'panel': {'color': WHITE, 'tag': 'wall',
                      'texture': {'image': 'art/panel.png', 'projection': 'box', 'scale': [2.0, HEIGHT],
                                  'offset': [round((LENGTH / 2 / 2.0) % 1, 4), 0.5]}},
            'top': {'color': BLUE, 'palette': True},
            'sign': {'color': YELLOW, 'texture': {'image': 'art/sign.png', 'projection': 'fit'}},
        },
        'nodes': [
            {'id': 'wall', 'op': 'box', 'size': [LENGTH, HEIGHT, THICK], 'material': 'panel',
             'open': ['bottom'], 'faces': {'top': 'top', 'left': 'top', 'right': 'top'},
             'transform': {'translate': [0, HEIGHT / 2, 0]},
             'decals': [{'id': 'sign', 'face': 'back', 'material': 'sign', 'size': [1.6, 1.6], 'at': [-2.0, -0.35]}]},
        ],
    }


if __name__ == '__main__':
    panel()
    sign()
    (HERE / 'edge_hoarding.asset.json').write_text(json.dumps(recipe(), indent=1) + '\n')
    print('edge_hoarding: 14 x 5.5 x 0.4 m')
