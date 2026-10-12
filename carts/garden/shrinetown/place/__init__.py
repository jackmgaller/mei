"""The placement zones' hook: the generators hand each zone module what they are about to write.

PLACE_SPLIT's five zones (station, street, east, canal, shrine) put the real assets in place of
the grey boxes, each in its own module here, `place/ZONE.py`. A generator calls

    apply(STAGE, globals())

just before it writes, with STAGE its name (`town` from notes/gen_town.py, `core`, `mountain`,
`world` from make_world.py) and its own namespace: the cells, the world part, the helpers. Each
zone module that defines a function named STAGE is called with that namespace, in the order of
ZONES, and changes what it finds there (removes grey boxes, adds placements, entities, paths,
terrain operations, asset directories). A missing module or function is skipped.
"""
import importlib
import importlib.util

ZONES = ('station', 'street', 'east', 'canal', 'shrine', 'art', 'occluders')
# art: not a zone, the textures over them (place/art.py); occluders: the world's occlusion zones
# over all of them (place/occluders.py, DESIGN.md 12.9)


def apply(stage, ns):
    for zone in ZONES:
        if importlib.util.find_spec(f'{__name__}.{zone}') is None:
            continue
        fn = getattr(importlib.import_module(f'{__name__}.{zone}'), stage, None)
        if fn is not None:
            fn(ns)


def add_dir(dirs, d):
    """Add the asset directory D to the world's DIRS, unless it is there or a `PARENT/*` glob there
    holds it (make_world.py lists `assets/*`, a folder per asset)."""
    if d not in dirs and (d.rpartition('/')[0] + '/*') not in dirs:
        dirs.append(d)


def unused(recipes, *where):
    """The names in RECIPES that nothing in WHERE (the cells, the part: placements, collisions,
    scatters) names: the grey boxes the zones swapped out. A generator drops them before it writes
    its recipes."""
    import json
    text = json.dumps(where)
    return [name for name in recipes if f'"{name}"' not in text]
