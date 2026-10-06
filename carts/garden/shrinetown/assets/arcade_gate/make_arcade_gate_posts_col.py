#!/usr/bin/env python3
"""Writes arcade_gate_posts_col.asset.json beside this script from arcade_gate_col.asset.json: the
arcade gate's collision without the lower part of its name board: the two pillars, the board's
top 0.3 m and the crest.

    python3 carts/garden/shrinetown/assets/arcade_gate/make_arcade_gate_posts_col.py

The shotengai's north gate uses it. Glide G8, the race line from the stage into the arcade (spec
4.4, scenario 417), comes in under the north gate with its feet at about 4.3 and its top at
about 5.9; the board's underside is at 5.11, so with the full collision the glider struck the
board and fell short of the arcade (the spec's gate had a beam at 7.0). With the pillars alone,
a walk north off the arcade roof's end fell through the board and crest to the road (alpha
review r08 #7): the board's top (6.51-6.81) and the crest (6.75-8.15) are solid again, all above
the glider.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOP = 0.3                      # the board's top kept, metres
col = json.loads((HERE / 'arcade_gate_col.asset.json').read_text())
col['name'] = 'arcade_gate_posts_col'
nodes = {n['id']: n for n in col['nodes']}
board = nodes['board']
sx, sy, sz = board['size']
cy = board['transform']['translate'][1]
top = dict(board, id='board_top', size=[sx, TOP, sz])
top['transform'] = dict(board['transform'], translate=[0, round(cy + sy / 2 - TOP / 2, 4), 0])
col['nodes'] = [nodes['pillars'], top, nodes['crest']]
(HERE / 'arcade_gate_posts_col.asset.json').write_text(json.dumps(col, indent=1) + '\n')
print('wrote arcade_gate_posts_col')
