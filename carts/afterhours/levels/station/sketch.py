#!/usr/bin/env python3
"""The station's layout sheet (the owner's gate before a stage is built): its section and a plan of
each room, with the watchers and the solution's path. Writes sketch.png beside itself.

    python3 carts/afterhours/levels/station/sketch.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CART = HERE.parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import layout_sheet as sketch  # noqa: E402
import solutions as SOL  # noqa: E402

PLANS = {c: plan for c, _, plan, _ in SOL.ROOMS}
ROOMS = [
    dict(label='1  The last train', play=CART / 'rooms/arrival/arrival.play.json', plan=PLANS['ARRIVAL'], status='dressed',
         floor=-16, storey=-3, width=13.5, note='teaches: a cone, and timing it. One posted guard turning his head.',
         **{'in': 'off the last train'}),
    dict(label='2  The ticket gates', play=CART / 'rooms/gates/gates.play.json', plan=PLANS['GATES'], status='dressed',
         floor=-11, storey=-2, width=13.5, note='teaches: hiding (A in the lockers). One patrol guard.'),
    dict(label='3  The passage', play=CART / 'rooms/passage/passage.play.json', plan=PLANS['PASSAGE'], status='dressed',
         floor=-6, storey=-1, width=22.5, note='teaches: pillars cast shadows. One camera sweeping the length. Out: the station\'s own street stair (changed).',
         **{'out': 'the station\'s stair up to the street (was: the tower\'s lobby)'}),
]

if __name__ == '__main__':
    sketch.sheet('Stage 1, the station', ROOMS, HERE / 'sketch.png', footer=[
        'Changed from the old stage 1 (level 1): the station is its first three rooms, unchanged in play and dressed; the stage ends',
        'at the passage\'s east doorway, now the station\'s own stair up to the street (only what is seen beyond it is redressed).',
        'The lobby and the aquarium leave: the lobby opens the tower (stage 2); the aquarium is a stage of its own (agent J\'s).',
        'Played perfectly: 47 s (2,835 ticks in the cart). No tools; the dash is never needed.'])
