#!/usr/bin/env python3
"""The aquarium, room 3: the ocean gallery's play file for this stage. Writes ocean.play.json
beside itself.

    python3 carts/afterhours/levels/aquarium/ocean/make_ocean_play.py

The room is the sketched aquarium (rooms/aquarium/, its builder's; its floor plan
rooms/aquarium/PLAN.md). Its play is the tower's (levels/level1/aquarium/aquarium.play.json, the
level lead's), unchanged but for how it joins: in this stage it is a room of doors, entered from
the jellyfish gallery by the way in at its front left and left by the staff door at its back
right, into quarantine. The ids take this stage's prefix, ao_.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CART = HERE.parents[2]
sys.path.insert(0, str(CART / 'levels'))
from greybox import write_json  # noqa: E402

SOURCE = CART / 'levels/level1/aquarium/aquarium.play.json'


def play():
    src = json.loads(SOURCE.read_text())
    ents = json.loads(json.dumps(src['entities']).replace('"r5_', '"ao_'))
    by = {e['id']: e for e in ents}
    spawn, exit_ = by.pop('ao_spawn'), by.pop('ao_exit')
    room = by['ao_room']
    room['params'].pop('exit', None)
    room['params'] = dict({'name': 'the_ocean_gallery'}, **room['params'])
    room['params']['entry'] = 'ao_spawn_jelly'
    out = [room]
    # the way in at the front left: a door in the front wall's gap, facing into the room
    out.append({'id': 'ao_spawn_jelly', 'type': 'spawn', 'position': spawn['position'], 'params': spawn['params']})
    out.append({'id': 'ao_door_jelly', 'type': 'door', 'position': [-4.3, 0, -3.025], 'yaw': 0,
                'params': {'size': [1.2, 2.2, 0.4], 'spawn': 'ao_spawn_jelly', 'to': 'aj_door_ocean'}})
    # the staff door at the back right (the tower's exit box), into quarantine
    ex = exit_['position']
    out.append({'id': 'ao_spawn_quar', 'type': 'spawn', 'position': [ex[0], 0, round(ex[2] - 0.75, 4)],
                'params': {'yaw': 180}})
    out.append({'id': 'ao_door_quar', 'type': 'door', 'position': ex, 'yaw': 0,
                'params': {'size': [exit_['params']['size'][0], 2.2, exit_['params']['size'][2]],
                           'spawn': 'ao_spawn_quar', 'to': 'qt_door_ocean'}})
    out += [e for e in ents if e['id'] in by and e['id'] != 'ao_room']
    return {'format': 'after-hours-play', 'version': 1, 'room': 'aquarium', 'entities': out, 'paths': {}}


SKETCH = {
    3: [(-4.3, -2.45), (-2.0, -2.4, 'wait'), (-0.2, -2.45, 'wait'), (1.4, -1.65), (5.35, -1.65), (5.35, 2.45)],
}


if __name__ == '__main__':
    write_json(HERE / 'ocean.play.json', play())
