#!/usr/bin/env python3
"""Checks that no After Hours world takes the front end's texture rows or palettes (agent E).

    python3 carts/afterhours/tests/front/check_worlds.py [CART_WORLDS_DIR]

The front end's fonts (art/front_title.fnt, art/front_head.fnt, made by art/make_front_art.py)
are loaded once, at boot, into a texture slot and two 4-bit palettes; a world region that copies
a texture into that slot, or loads colours into those palettes, turns the menus' text to noise
(stage 2's dressed rooms did, on the kit's default slots and palettes). This reads the slot and
palettes from the fonts' own headers and every world's build report (CART_WORLDS_DIR, default
build/cart-worlds/afterhours: its worlds.json names each world's output folder), and fails,
naming the world, the region and what it takes, when a region's texture set uses that slot, or
its palettes (its 4-bit palettes, its colour run, its textures' 4-bit and 8-bit palettes) reach
those palettes. tests/front/check.sh runs it before the scenarios. Standard library only.
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CART = os.path.dirname(os.path.dirname(HERE))
ROOT = os.path.dirname(os.path.dirname(CART))


def font_header(path):
    with open(path, 'rb') as fh:
        h, line, first, count, slot, palette, row, rows = struct.unpack('<8B', fh.read(8))
    return slot, palette, row, rows


def main():
    worlds_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build', 'cart-worlds', 'afterhours')
    slots, palettes = set(), set()
    for name in ('front_title.fnt', 'front_head.fnt'):
        slot, palette, _, _ = font_header(os.path.join(CART, 'art', name))
        slots.add(slot)
        palettes.add(palette)
    with open(os.path.join(worlds_dir, 'worlds.json')) as fh:
        worlds = json.load(fh)['worlds']
    bad = []
    for w in worlds:
        out = w['output']
        if not os.path.isabs(out):
            out = os.path.join(ROOT, out)
        with open(os.path.join(out, 'report.json')) as fh:
            report = json.load(fh)
        for rname, reg in (report.get('regions') or {}).items():
            tex = reg.get('textures') or {}
            for t in tex.get('slots') or []:
                if t.get('slot') in slots:
                    bad.append('%s, region %s: a texture in slot %d' % (w['name'], rname, t['slot']))
            for p in tex.get('palettes_4bit') or []:
                if p in palettes:
                    bad.append('%s, region %s: a texture\'s 4-bit palette %d' % (w['name'], rname, p))
            for p8 in tex.get('palettes_8bit') or []:     # 8-bit palette p: colours 256p .. 256p + 255
                for p in palettes:
                    if 16 * p8 <= p < 16 * p8 + 16:
                        bad.append('%s, region %s: a texture\'s 8-bit palette %d (4-bit palettes %d-%d)'
                                   % (w['name'], rname, p8, 16 * p8, 16 * p8 + 15))
            pal = reg.get('palette') or {}
            for p in pal.get('palettes') or []:
                if p in palettes:
                    bad.append('%s, region %s: 4-bit palette %d' % (w['name'], rname, p))
            first, n = pal.get('first_colour'), pal.get('colours')
            if first is not None and n:
                for p in palettes:
                    if first < (p + 1) * 16 and p * 16 < first + n:
                        bad.append('%s, region %s: colours %d-%d over palette %d' % (w['name'], rname, first, first + n - 1, p))
        st = ((report.get('standins') or {}).get('textures') or {})
        for t in st.get('slots') or []:
            s = t.get('slot') if isinstance(t, dict) else t
            if s in slots:
                bad.append('%s: the stand-ins\' textures in slot %d' % (w['name'], s))
    if bad:
        print('FAIL the worlds take the front end\'s texture slot %s or palettes %s:' % (
            sorted(slots), sorted(palettes)))
        for b in sorted(set(bad)):
            print('  ' + b)
        print('  (reserve them in the world recipes: "textures": {"slots": ...} without the slot, '
              '"palette": {"reserved": [...]})')
        return 1
    print('OK %d worlds leave the front end\'s texture slot %s and palettes %s alone' % (
        len(worlds), sorted(slots), sorted(palettes)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
