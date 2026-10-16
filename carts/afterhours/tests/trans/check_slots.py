#!/usr/bin/env python3
"""Whether every two rooms a way out joins keep their textures in different slots (agent H,
NOTES_H.md "Textures"), so the transition between them draws both rooms textured. The owner chose
this (option 1): each world recipe gives its regions slot sets (`regions.NAME.textures.slots`),
two or more, so that no door joins two rooms of one set.

    python3 carts/afterhours/tests/trans/check_slots.py [BUILD]       (default build)

Reads every world in carts/afterhours/worlds.txt: the recipe for its rooms, their ways out (a
door's `to`, or a room's `exit` to its `next`) and the slots each region is given, and
BUILD/worlds/<its folder>/report.json for the slots each region's textures took. Prints each
pair that shares a slot and exits 1 if any does; a world not built yet is skipped with a line.
Python's standard library only.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CART = ROOT/'carts'/'afterhours'


def entities(recipe):
    """Every entity of the recipe: (id, type, position, params, cell id)."""
    world = json.loads(recipe.read_text())
    out = []
    for cell in world.get('cells', []):
        if cell.get('file'):
            cell = {**json.loads((recipe.parent/cell['file']).read_text()), **cell}
        for e in cell.get('entities', []):
            out.append((e['id'], e.get('type'), e.get('position', [0, 0, 0]), e.get('params', {}), cell.get('id')))
    return world, out


def parse(spec):
    """A slot list ('13-8,6-0,16-31') as a set."""
    out = set()
    for part in str(spec).split(','):
        a, _, b = part.strip().partition('-')
        a, b = int(a), int(b or a)
        out |= set(range(min(a, b), max(a, b) + 1))
    return out


def check(recipe, build):
    world, ents = entities(recipe)
    report = build/'worlds'/recipe.parent.relative_to(ROOT)/'report.json'
    if not report.exists():
        print(f'{recipe.relative_to(ROOT)}: not built in {build}, skipped')
        return 0
    rep = json.loads(report.read_text())
    cell_region = {c['id']: c.get('region') for c in rep['cells']}
    # the slots each region may use (the recipe's set, else the world's) and those its textures
    # took (a room with no textures, a greybox, takes none): both must be apart
    default = world.get('textures', {}).get('slots', '13-0,16-31')
    given = {name: parse((r.get('textures') or {}).get('slots', default)) for name, r in world['regions'].items()}
    slots = {name: given.get(name, set()) | {s['slot'] for s in r.get('textures', {}).get('slots', [])}
             for name, r in rep['regions'].items()}
    rooms = {i: (p, prm, cell) for i, t, p, prm, cell in ents if t == 'room'}
    if len(rooms) < 2:
        return 0

    def room_of(p):
        for rid, (rp, prm, _) in rooms.items():
            sx, _, sz = prm['size']
            if abs(p[0] - rp[0]) <= sx / 2 + 0.5 and abs(p[2] - rp[2]) <= sz / 2 + 0.5:
                return rid
        return None
    pos = {i: p for i, t, p, prm, cell in ents}
    pairs = set()
    for i, t, p, prm, cell in ents:
        if t == 'door' and prm.get('to') and not prm.get('end'):
            a, b = room_of(p), room_of(pos[prm['to']])
            if a and b and a != b: pairs.add(tuple(sorted((a, b))))
    for rid, (rp, prm, cell) in rooms.items():
        if prm.get('exit') and prm.get('next'):
            pairs.add(tuple(sorted((rid, prm['next']))))
    bad = 0
    for a, b in sorted(pairs):
        ra, rb = cell_region[rooms[a][2]], cell_region[rooms[b][2]]
        shared = sorted(slots.get(ra, set()) & slots.get(rb, set()))
        if ra == rb or shared:
            print(f'{recipe.relative_to(ROOT)}: {a} ({ra}) and {b} ({rb}) share texture slots {shared or "(one region)"}')
            bad += 1
    if not bad:
        print(f'{recipe.relative_to(ROOT)}: {len(pairs)} joined pairs, none share a slot')
    return bad


def main():
    build = (ROOT/(sys.argv[1] if len(sys.argv) > 1 else 'build')).resolve()
    bad = 0
    for line in (CART/'worlds.txt').read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            bad += check(ROOT/line, build)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
