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

ZONES = ('station', 'street', 'east', 'canal', 'shrine')


def apply(stage, ns):
    for zone in ZONES:
        if importlib.util.find_spec(f'{__name__}.{zone}') is None:
            continue
        fn = getattr(importlib.import_module(f'{__name__}.{zone}'), stage, None)
        if fn is not None:
            fn(ns)
